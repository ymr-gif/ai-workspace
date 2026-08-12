import { afterEach, describe, expect, it, vi } from "vitest";
import worker from "./worker.js";

function makeEnv(overrides = {}) {
  const store = new Map();
  return {
    ORIGIN: "https://origin.example",
    CONNECT_TIMEOUT_MS: "1000",
    STATE: {
      get: vi.fn(async (key) => (store.has(key) ? store.get(key) : null)),
      put: vi.fn(async (key, value) => {
        store.set(key, value);
      }),
    },
    ...overrides,
  };
}

function makeCtx() {
  const promises = [];
  return { waitUntil: (p) => promises.push(p) };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("bounded retry on upstream-down", () => {
  it("GET: retries once after a network throw and returns the real success, never the offline page", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("https://worker.example/", { method: "GET", headers: { Accept: "text/html" } });
    const resp = await worker.fetch(req, makeEnv(), makeCtx());

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(resp.status).toBe(200);
    const text = await resp.text();
    expect(text).toBe("ok");
    expect(text).not.toContain("Demo runs on a home server");
  });

  it("GET: two consecutive down-statuses exhaust the retry and show the offline page", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response("down", { status: 503 })));
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("https://worker.example/", { method: "GET", headers: { Accept: "text/html" } });
    const resp = await worker.fetch(req, makeEnv(), makeCtx());

    expect(fetchMock).toHaveBeenCalledTimes(2); // one attempt + exactly one retry, no more
    expect(resp.status).toBe(503);
    expect(resp.headers.get("Retry-After")).toBe("300");
    const text = await resp.text();
    expect(text).toContain("Demo runs on a home server");
  });

  it("POST: a down-status is never retried — exactly one upstream attempt, straight to the offline response", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response("down", { status: 503 })));
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("https://worker.example/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ message: "hi" }),
    });
    const resp = await worker.fetch(req, makeEnv(), makeCtx());

    expect(fetchMock).toHaveBeenCalledTimes(1); // guards the no-replay rule
    expect(resp.status).toBe(503);
    const body = await resp.json();
    expect(body.detail).toMatch(/unreachable/i);
  });

  it("GET /__status: a single transient blip does not get reported as down", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("https://worker.example/__status", { method: "GET" });
    const resp = await worker.fetch(req, makeEnv(), makeCtx());

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const body = await resp.json();
    expect(body.up).toBe(true);
  });

  it("a slow-body response completes untouched — the abort timer only ever bounds headers", async () => {
    const bodyDelayMs = 150;
    const connectTimeoutMs = 50; // comfortably shorter than bodyDelayMs

    const fetchMock = vi.fn((_input, init) => {
      const signal = init?.signal;
      let aborted = signal?.aborted ?? false;
      signal?.addEventListener("abort", () => {
        aborted = true;
      });

      const stream = new ReadableStream({
        async start(controller) {
          await new Promise((resolve) => setTimeout(resolve, bodyDelayMs));
          if (aborted) {
            controller.error(new DOMException("Aborted", "AbortError"));
            return;
          }
          controller.enqueue(new TextEncoder().encode("slow but healthy body"));
          controller.close();
        },
      });

      // fetch() itself resolves immediately (headers arrive fast); only the body is slow.
      return Promise.resolve(new Response(stream, { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("https://worker.example/", { method: "GET" });
    const resp = await worker.fetch(req, makeEnv({ CONNECT_TIMEOUT_MS: String(connectTimeoutMs) }), makeCtx());

    expect(resp.status).toBe(200);
    const text = await resp.text(); // would throw/AbortError here if the timer were still armed
    expect(text).toBe("slow but healthy body");
  });
});
