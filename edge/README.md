# Eidetic edge Worker

Cloudflare Worker that sits in front of the Tailscale Funnel and is the advertised public URL:
**`https://eidetic.work`** (custom domain, added 2026-08-11 — Cloudflare Registrar, $10.20/yr,
auto-renew on). The Worker also still answers at its original `https://eidetic.cabucosyamierzane.workers.dev`
address; both route to the same script. It proxies every request to `ORIGIN`
(`https://eidetic.taile6aad6.ts.net`) untouched when the box is reachable, and serves a themed
offline page when it is not.

Full contract, the two implementation gotchas (abort-timer scope, KV write throttling), and the
verification checklist live in `plans/cloudflare-worker/README.md` — read that first. This file is
the operational runbook: deploy, rollback, repoint.

Owned by the `docker/` worker as infra. Not part of the Docker Compose stack — nothing here builds
into a container or touches the box. `ts.net` stays the direct/origin URL for CI, OAuth redirects,
and debugging; this Worker is only the public-facing front door.

## Layout

```
edge/
├── wrangler.toml   name, main, compatibility_date, [vars] (ORIGIN, CONNECT_TIMEOUT_MS), KV binding, custom domain route
├── package.json    pins wrangler as a devDependency
├── README.md       this file
└── src/
    ├── worker.js   proxy + failure detection + /__status
    └── offline.js  offlinePage(lastSeenIso) -> HTML string
```

## Deploy

Account is already authenticated (`npx wrangler whoami`). One-time setup, then deploy:

```bash
cd edge
npx wrangler kv namespace create EIDETIC_STATE   # copy the returned id into wrangler.toml's [[kv_namespaces]] id
npx wrangler deploy
```

The first deploy may prompt for a `workers.dev` subdomain if the account has never set one —
that prompt is interactive and answered by whoever runs the deploy.

## Custom domain (`eidetic.work`)

Bound via `wrangler.toml`:

```toml
[[routes]]
pattern = "eidetic.work"
custom_domain = true
```

No dashboard clicking needed — `eidetic.work` was bought through Cloudflare Registrar, so it's
already a zone in the same account, and `custom_domain = true` in a route block is enough for
`wrangler deploy` to provision the DNS record and TLS cert itself.

**Timing, measured on the actual first setup:** for a domain that already has an active zone, this
is roughly a minute (same as the `workers.dev` subdomain cert). For a **freshly purchased** domain
like this one, budget 15-20+ minutes total: the registry has to delegate the zone to Cloudflare's
nameservers first (public DNS returned NXDOMAIN for a while — check with
`curl -s "https://1.1.1.1/dns-query?name=<domain>&type=NS" -H "accept: application/dns-json"`,
`"Status":3` means not yet delegated), and only after that resolves does the dedicated TLS cert
start issuing (`curl -v https://<domain>/` showing `TLS alert, handshake failure` means DNS is
fine but the cert isn't ready yet). Both steps are Cloudflare/registry-side; nothing to do but wait
and re-check.

To add another custom domain later (e.g. a `www.` alias or a different TLD), add another
`[[routes]]` block with its own `pattern` and redeploy.

## Redeploy after a code change

```bash
cd edge
npx wrangler deploy
```

No build step; `worker.js` and `offline.js` ship as-is.

## Verify

```bash
BASE=https://eidetic.work   # or https://eidetic.cabucosyamierzane.workers.dev — same Worker

curl -s -o /dev/null -w '%{http_code}\n' "$BASE/"          # 200
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/docs"  # 200
curl -s "$BASE/__status"                                    # {"up":true,"last_seen":"..."}
```

Offline path — simulate the box being unreachable, verify for real:

```bash
tailscale funnel off
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/"           # 503
curl -sI "$BASE/" | grep -i retry-after                     # Retry-After: 300
curl -s "$BASE/api/health"                                  # JSON {"detail": "..."}, not HTML
tailscale funnel --bg 3000                                  # restore
```

Then load `$BASE/` in a browser: the last-seen timestamp should populate and the page should
auto-reload once `/__status` reports `up: true` again (polls every 30s).

Also confirm a real chat stream (SSE, runs past 8 seconds) completes through the Worker — this is
the proof the abort timer only bounds headers, not the body. Skipping this check is how you ship a
Worker that silently kills every chat reply at the 8-second mark.

## Rollback

Zero-risk — `ts.net` never stops working underneath.

```bash
cd edge
npx wrangler delete
```

This also releases the `eidetic.work` route binding (the domain registration itself is untouched —
it stays owned in Cloudflare Registrar, just no longer pointed at a Worker). Then hand out the
`ts.net` URL again until redeployed.

## Repoint at a different origin later

Everything upstream-facing is in `wrangler.toml` `[vars]`. To move off the Tailscale Funnel (e.g.
onto the home-server box or an Oracle VM once that plan un-parks):

1. Edit `ORIGIN` in `edge/wrangler.toml`.
2. `npx wrangler deploy`.

No code change. `CONNECT_TIMEOUT_MS` may need tuning if the new origin's cold-start / TLS handshake
time differs meaningfully from the funnel's.

## Known limits

- Free plan: 100k requests/day, 10ms CPU/request — proxying is I/O, not CPU-bound, so this is not a
  real constraint at demo traffic.
- Adds one network hop (~20-60ms) versus hitting the funnel directly.
- New origin means a fresh `localStorage` per browser — sessions from the old `ts.net` URL do not
  carry over.
- `last_seen` writes are throttled to once per 5 minutes (KV free tier: 1000 writes/day) via an
  in-isolate timestamp guard in `worker.js`. `/__status` does its own live probe of `ORIGIN` on every
  call, so the offline page's auto-reload is not gated by that throttle.
- CI (`VERIFY_BASE_URL`) intentionally stays pointed at `ts.net`, never at this Worker.
