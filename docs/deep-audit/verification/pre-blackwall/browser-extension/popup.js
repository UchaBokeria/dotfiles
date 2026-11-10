1: const API = "http://127.0.0.1:9225";
2: const $ = (id) => document.getElementById(id);
3: 
4: (async function init() {
5:   try {
6:     const { name } = await chrome.storage.sync.get({ name: "archlinux-1" });
7:     $("bname").textContent = `opencode · ${name}`;
8:   } catch {}
9:   refresh();
10: })();
11: 
12: async function refresh() {
13:   try {
14:     const r = await (await fetch(`${API}/pending-latest`)).json();
15:     const has = r.status === "pending";
16:     $("pcount").textContent = has ? "1" : "0";
17:     $("status").textContent = has ? `Pending: ${r.session}` : "";
18:   } catch {
19:     $("status").textContent = "Bridge unreachable.";
20:   }
21: }
22: 
23: async function openPanel(action) {
24:   if (action) await chrome.storage.local.set({ panelAction: action });
25:   const w = await chrome.windows.getCurrent();
26:   await chrome.sidePanel.open({ windowId: w.id });
27:   window.close();
28: }
29: $("open-panel").onclick = () => openPanel();
30: $("q-snap").onclick = () => openPanel("snap");
31: $("q-shot").onclick = () => openPanel("shot");
32: $("q-accept").onclick = async () => {
33:   try {
34:     const r = await (await fetch(`${API}/pending-latest`)).json();
35:     if (r.status !== "pending") {
36:       $("status").textContent = "Nothing pending.";
37:       return;
38:     }
39:     const { name } = await chrome.storage.sync.get({ name: "archlinux-1" });
40:     await fetch(`${API}/accept`, { method: "POST",
41:       headers: { "content-type": "application/json" },
42:       body: JSON.stringify({ session: r.session, browser: name }) });
43:     $("status").textContent = `Connected ${r.session}.`;
44:     refresh();
45:   } catch {
46:     $("status").textContent = "Bridge unreachable.";
47:   }
48: };
49: 
50: try {
51:   const es = new EventSource(`${API}/events`);
52:   es.addEventListener("pending", refresh);
53:   es.addEventListener("accepted", refresh);
54: } catch {}
