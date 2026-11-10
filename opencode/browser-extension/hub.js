// WS link to the opencode bridge hub. Reconnects with backoff.
// Incoming: {id, to, method, params} -> handled by cdp.exec -> replies {id, from, result|error}.
let hubWs = null;
let hubBackoff = 2000;

async function hubName() {
  const l = await chrome.storage.local.get({ name: "" }).catch(() => ({}));
  if (l.name) return l.name;
  const s = await chrome.storage.sync.get({ name: "archlinux-1" });
  return s.name;
}

function hubConnect() {
  hubName().then((name) => {
    try {
      hubWs?.close();
    } catch {}
    const ws = new WebSocket(HUB_URL);
    hubWs = ws;
    ws.onopen = () => {
      hubBackoff = 2000;
      ws.send(JSON.stringify({ hello: { role: "extension", browser: name } }));
      fetch(`${API}/register`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name }),
      }).catch(() => {});
    };
    ws.onmessage = (ev) => {
      let m;
      try {
        m = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (m.hello) return;
      if (m.method && m.id !== undefined) {
        // never block the socket: concurrent dispatch, stale-call guard
        const started = Date.now();
        cdpExec(m.method, m.params || {}).then(
          (result) => {
            if (ws.readyState === 1 && Date.now() - started < 17 * 60 * 1000)
              ws.send(JSON.stringify({ id: m.id, from: name, result }));
          },
          (e) => {
            if (ws.readyState === 1)
              ws.send(JSON.stringify({ id: m.id, from: name, error: String(e?.message || e) }));
          }
        );
      }
      if (m.type === "ping") {
        try {
          if (ws.readyState === 1) ws.send(JSON.stringify({ type: "pong" }));
        } catch {}
      }
    };
    ws.onclose = () => {
      // fast first retry (bridge restarts are seconds), then back off
      const wait = hubBackoff <= 2000 ? 500 : Math.min(hubBackoff, 15000);
      setTimeout(hubConnect, wait);
      hubBackoff = Math.min(hubBackoff * 2, 15000);
    };
  });
}
