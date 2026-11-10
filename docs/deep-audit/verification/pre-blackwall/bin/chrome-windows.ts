1: // @ts-nocheck
2: // List Chrome windows + their tabs via CDP. Usage: bun chrome-windows.ts <httpEndpoint>
3: // e.g. bun chrome-windows.ts http://127.0.0.1:9223
4: // Prints JSON: [{windowId, bounds, tabs:[{id,title,url,selected?}]}]
5: const endpoint = (process.argv[2] || "http://127.0.0.1:9223").replace(/\/$/, "");
6: 
7: const ver = await (await fetch(`${endpoint}/json/version`)).json();
8: const targets: any[] = await (await fetch(`${endpoint}/json/list`)).json();
9: const pages = targets.filter((t) => t.type === "page");
10: 
11: const ws = new WebSocket(ver.webSocketDebuggerUrl);
12: await new Promise<void>((res, rej) => {
13:   ws.addEventListener("open", () => res());
14:   ws.addEventListener("error", (e) => rej(e));
15: });
16: let id = 0;
17: const pending = new Map<number, (v: any) => void>();
18: ws.addEventListener("message", (ev) => {
19:   const m = JSON.parse(String(ev.data));
20:   if (m.id !== undefined && pending.has(m.id)) {
21:     pending.get(m.id)!(m);
22:     pending.delete(m.id);
23:   }
24: });
25: const call = (method: string, params: any = {}) =>
26:   new Promise<any>((res) => {
27:     const cur = ++id;
28:     pending.set(cur, res);
29:     ws.send(JSON.stringify({ id: cur, method, params }));
30:   });
31: 
32: const windows = new Map<string, any>();
33: for (const p of pages) {
34:   try {
35:     const r = await call("Browser.getWindowForTarget", { targetId: p.id });
36:     const wid = String(r.result.windowId);
37:     if (!windows.has(wid)) {
38:       const b = await call("Browser.getWindowBounds", { windowId: r.result.windowId });
39:       windows.set(wid, { windowId: wid, state: b.result.bounds.windowState, tabs: [] });
40:     }
41:     windows.get(wid).tabs.push({ id: p.id, title: p.title, url: p.url });
42:   } catch {}
43: }
44: ws.close();
45: console.log(JSON.stringify([...windows.values()], null, 1));
