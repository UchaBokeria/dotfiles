// WS link to the opencode bridge hub. Reconnects with backoff.
// Incoming: {id, to, method, params} -> handled by cdp.exec -> replies {id, from, result|error}.
const HUB_URL = "ws://127.0.0.1:9225/hub";
let hubWs = null;
let hubBackoff = 2000;

async function hubName() {
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
    };
    ws.onmessage = async (ev) => {
      let m;
      try {
        m = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (m.hello) return;
      if (m.method && m.id !== undefined) {
        try {
          const result = await cdpExec(m.method, m.params || {});
          ws.send(JSON.stringify({ id: m.id, from: name, result }));
        } catch (e) {
          ws.send(JSON.stringify({ id: m.id, from: name, error: String(e?.message || e) }));
        }
      }
    };
    ws.onclose = () => {
      setTimeout(hubConnect, Math.min(hubBackoff, 30000));
      hubBackoff *= 2;
    };
  });
}
