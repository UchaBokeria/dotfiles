1: // WS link to the opencode bridge hub. Reconnects with backoff.
2: // Incoming: {id, to, method, params} -> handled by cdp.exec -> replies {id, from, result|error}.
3: const HUB_URL = "ws://127.0.0.1:9225/hub";
4: let hubWs = null;
5: let hubBackoff = 2000;
6: 
7: async function hubName() {
8:   const s = await chrome.storage.sync.get({ name: "archlinux-1" });
9:   return s.name;
10: }
11: 
12: function hubConnect() {
13:   hubName().then((name) => {
14:     try {
15:       hubWs?.close();
16:     } catch {}
17:     const ws = new WebSocket(HUB_URL);
18:     hubWs = ws;
19:     ws.onopen = () => {
20:       hubBackoff = 2000;
21:       ws.send(JSON.stringify({ hello: { role: "extension", browser: name } }));
22:     };
23:     ws.onmessage = async (ev) => {
24:       let m;
25:       try {
26:         m = JSON.parse(ev.data);
27:       } catch {
28:         return;
29:       }
30:       if (m.hello) return;
31:       if (m.method && m.id !== undefined) {
32:         try {
33:           const result = await cdpExec(m.method, m.params || {});
34:           ws.send(JSON.stringify({ id: m.id, from: name, result }));
35:         } catch (e) {
36:           ws.send(JSON.stringify({ id: m.id, from: name, error: String(e?.message || e) }));
37:         }
38:       }
39:     };
40:     ws.onclose = () => {
41:       setTimeout(hubConnect, Math.min(hubBackoff, 30000));
42:       hubBackoff *= 2;
43:     };
44:   });
45: }
