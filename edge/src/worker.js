import { offlinePage } from "./offline.js";

const KV_WRITE_INTERVAL_MS = 5 * 60 * 1000;
let lastWriteMs = 0;

// 502/503/504: standard gateway failures. 520-527/530: Cloudflare's own codes for
// "could not reach the origin" (the Funnel is itself Cloudflare-fronted, so a dead
// box surfaces as e.g. 525 SSL handshake failed here, not a fetch() throw).
const UPSTREAM_DOWN_STATUSES = new Set([502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527, 530]);

// Only bodyless, side-effect-free methods get a retry. A down-status on a
// POST/PUT/PATCH/DELETE can mean the request already reached the app (e.g. our own
// nginx 502ing after proxying through) — replaying it could double a chat turn or a
// calendar write, which is worse than showing the offline page once.
const IDEMPOTENT_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const RETRY_BACKOFF_MS = 300;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/__status") {
      return handleStatus(env, ctx);
    }

    const target = env.ORIGIN + url.pathname + url.search;
    const clientIp = request.headers.get("CF-Connecting-IP");
    const makeProxyRequest = () => {
      const req = new Request(target, request);
      if (clientIp) req.headers.set("X-Forwarded-For", clientIp);
      return req;
    };

    try {
      const resp = await fetchOrigin(makeProxyRequest, Number(env.CONNECT_TIMEOUT_MS), request.method);

      if (UPSTREAM_DOWN_STATUSES.has(resp.status)) {
        return failureResponse(request, env, ctx);
      }

      recordLastSeen(env, ctx);
      return resp;
    } catch (e) {
      return failureResponse(request, env, ctx);
    }
  },
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// One attempt: fresh AbortController/timer, cleared the instant fetch settles either
// way. MUST clear on resolve before the caller touches resp.body — fetch resolves on
// headers, so a still-armed timer would abort a perfectly healthy SSE stream mid-body.
async function attempt(makeRequest, timeoutMs) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const resp = await fetch(makeRequest(), {
      signal: ctl.signal,
      redirect: "manual",
      cache: "no-store", // never let the shared edge cache mask a dead origin (or leak between users)
    });
    clearTimeout(timer);
    return resp;
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}

// Bounded retry: on a down-status or a throw, idempotent methods get exactly one more
// attempt after a short backoff, then whatever that attempt produces (status or throw)
// is final. A genuinely dead box must still fail fast, so no escalating backoff and no
// second retry — worst case this adds one RETRY_BACKOFF_MS before the offline page.
async function fetchOrigin(makeRequest, timeoutMs, method) {
  const canRetry = IDEMPOTENT_METHODS.has(method.toUpperCase());

  try {
    const resp = await attempt(makeRequest, timeoutMs);
    if (canRetry && UPSTREAM_DOWN_STATUSES.has(resp.status)) {
      await sleep(RETRY_BACKOFF_MS);
      return attempt(makeRequest, timeoutMs);
    }
    return resp;
  } catch (e) {
    if (canRetry) {
      await sleep(RETRY_BACKOFF_MS);
      return attempt(makeRequest, timeoutMs);
    }
    throw e;
  }
}

function isNavigation(request) {
  if (request.headers.get("Sec-Fetch-Mode") === "navigate") return true;
  const accept = request.headers.get("Accept") || "";
  return accept.includes("text/html");
}

async function failureResponse(request, env, ctx) {
  const commonHeaders = {
    "Retry-After": "300",
    "Cache-Control": "no-store",
  };

  if (isNavigation(request)) {
    const lastSeen = await env.STATE.get("last_seen");
    return new Response(offlinePage(lastSeen), {
      status: 503,
      headers: { ...commonHeaders, "Content-Type": "text/html; charset=utf-8" },
    });
  }

  return new Response(
    JSON.stringify({
      detail: "Eidetic is temporarily unreachable — the demo runs on a home server that may be offline.",
    }),
    { status: 503, headers: { ...commonHeaders, "Content-Type": "application/json" } }
  );
}

function recordLastSeen(env, ctx) {
  const now = Date.now();
  if (now - lastWriteMs < KV_WRITE_INTERVAL_MS) return;
  lastWriteMs = now;
  ctx.waitUntil(env.STATE.put("last_seen", new Date(now).toISOString()));
}

async function handleStatus(env, ctx) {
  const lastSeen = await env.STATE.get("last_seen");
  let up = false;

  try {
    const resp = await fetchOrigin(
      () => new Request(env.ORIGIN + "/", { method: "HEAD" }),
      Number(env.CONNECT_TIMEOUT_MS),
      "HEAD"
    );
    up = resp.status < 500;
  } catch (e) {
    up = false;
  }

  if (up) recordLastSeen(env, ctx);

  return new Response(
    JSON.stringify({ up, last_seen: up ? new Date().toISOString() : lastSeen || null }),
    { headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } }
  );
}
