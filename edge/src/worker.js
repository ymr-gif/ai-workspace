import { offlinePage } from "./offline.js";

const KV_WRITE_INTERVAL_MS = 5 * 60 * 1000;
let lastWriteMs = 0;

// 502/503/504: standard gateway failures. 520-527/530: Cloudflare's own codes for
// "could not reach the origin" (the Funnel is itself Cloudflare-fronted, so a dead
// box surfaces as e.g. 525 SSL handshake failed here, not a fetch() throw).
const UPSTREAM_DOWN_STATUSES = new Set([502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527, 530]);

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/__status") {
      return handleStatus(env, ctx);
    }

    const target = env.ORIGIN + url.pathname + url.search;
    const proxyRequest = new Request(target, request);
    const clientIp = request.headers.get("CF-Connecting-IP");
    if (clientIp) proxyRequest.headers.set("X-Forwarded-For", clientIp);

    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), Number(env.CONNECT_TIMEOUT_MS));

    try {
      const resp = await fetch(proxyRequest, {
        signal: ctl.signal,
        redirect: "manual",
        cache: "no-store", // never let the shared edge cache mask a dead origin (or leak between users)
      });
      clearTimeout(timer); // MUST be here — bounds headers only, body streams free after this

      if (UPSTREAM_DOWN_STATUSES.has(resp.status)) {
        return failureResponse(request, env, ctx);
      }

      recordLastSeen(env, ctx);
      return resp;
    } catch (e) {
      clearTimeout(timer);
      return failureResponse(request, env, ctx);
    }
  },
};

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
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), Number(env.CONNECT_TIMEOUT_MS));
    const resp = await fetch(env.ORIGIN + "/", {
      method: "HEAD",
      signal: ctl.signal,
      redirect: "manual",
      cache: "no-store", // must hit the real origin, never a cached prior success
    });
    clearTimeout(timer);
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
