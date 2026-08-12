export function offlinePage(lastSeenIso) {
  const lastSeenJson = JSON.stringify(lastSeenIso || null);

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eidetic — offline</title>
<style>
  :root {
    color-scheme: dark;
    --ground: #0a0b0d;
    --panel: #121417;
    --border: #23262b;
    --text: #e6e8eb;
    --text-dim: #8b9099;
    --accent: #e0a640;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    padding: 0;
    height: 100%;
    background: var(--ground);
    color: var(--text);
  }
  body {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo, Consolas, monospace;
    padding: 24px;
  }
  .card {
    max-width: 560px;
    width: 100%;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 32px;
  }
  .badge {
    display: inline-block;
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
    border: 1px solid var(--accent);
    border-radius: 3px;
    padding: 2px 8px;
    margin-bottom: 20px;
  }
  h1 {
    font-size: 20px;
    line-height: 1.5;
    font-weight: 500;
    margin: 0 0 8px;
    color: var(--text);
  }
  p {
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-dim);
    margin: 0 0 4px;
  }
  .meta {
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
    font-size: 13px;
    color: var(--text-dim);
  }
  .meta strong { color: var(--text); font-weight: 500; }
  .footer {
    margin-top: 20px;
    font-size: 13px;
  }
  a {
    color: var(--accent);
    text-decoration: none;
  }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
  <div class="card">
    <span class="badge">offline</span>
    <h1>Demo runs on a home server, sorry for the downtime.</h1>
    <p>The box behind this demo is off, asleep, or off the network right now. This page will
    reload automatically once it is back.</p>
    <div class="meta">
      <div>Last seen: <strong id="last-seen">unknown</strong></div>
    </div>
    <div class="footer">
      <a href="https://github.com/ymr-gif/eidetic">View the project on GitHub</a>
    </div>
  </div>
  <script>
    (function () {
      var lastSeenIso = ${lastSeenJson};
      var el = document.getElementById("last-seen");

      function relativeFrom(iso) {
        var deltaMs = Date.now() - new Date(iso).getTime();
        var sec = Math.round(deltaMs / 1000);
        if (sec < 60) return "just now";
        var min = Math.round(sec / 60);
        if (min < 60) return min + " minute" + (min === 1 ? "" : "s") + " ago";
        var hr = Math.round(min / 60);
        if (hr < 24) return "about " + hr + " hour" + (hr === 1 ? "" : "s") + " ago";
        var day = Math.round(hr / 24);
        return "about " + day + " day" + (day === 1 ? "" : "s") + " ago";
      }

      if (lastSeenIso) {
        var abs = new Date(lastSeenIso).toUTCString();
        el.textContent = abs + " (" + relativeFrom(lastSeenIso) + ")";
      } else {
        el.textContent = "unknown";
      }

      function poll() {
        fetch("/__status", { cache: "no-store" })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data && data.up) location.reload();
          })
          .catch(function () {});
      }
      setInterval(poll, 30000);
    })();
  </script>
</body>
</html>
`;
}
