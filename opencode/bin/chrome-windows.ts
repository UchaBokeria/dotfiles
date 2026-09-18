// @ts-nocheck
// List Chrome windows + their tabs via CDP. Usage: bun chrome-windows.ts <httpEndpoint>
// e.g. bun chrome-windows.ts http://127.0.0.1:9223
// Prints JSON: [{windowId, bounds, tabs:[{id,title,url,selected?}]}]
const endpoint = (process.argv[2] || "http://127.0.0.1:9223").replace(/\/$/, "");

const ver = await (await fetch(`${endpoint}/json/version`)).json();
const targets: any[] = await (await fetch(`${endpoint}/json/list`)).json();
const pages = targets.filter((t) => t.type === "page");

const ws = new WebSocket(ver.webSocketDebuggerUrl);
await new Promise<void>((res, rej) => {
  ws.addEventListener("open", () => res());
  ws.addEventListener("error", (e) => rej(e));
});
let id = 0;
const pending = new Map<number, (v: any) => void>();
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(String(ev.data));
  if (m.id !== undefined && pending.has(m.id)) {
    pending.get(m.id)!(m);
    pending.delete(m.id);
  }
});
const call = (method: string, params: any = {}) =>
  new Promise<any>((res) => {
    const cur = ++id;
    pending.set(cur, res);
    ws.send(JSON.stringify({ id: cur, method, params }));
  });

const windows = new Map<string, any>();
for (const p of pages) {
  try {
    const r = await call("Browser.getWindowForTarget", { targetId: p.id });
    const wid = String(r.result.windowId);
    if (!windows.has(wid)) {
      const b = await call("Browser.getWindowBounds", { windowId: r.result.windowId });
      windows.set(wid, { windowId: wid, state: b.result.bounds.windowState, tabs: [] });
    }
    windows.get(wid).tabs.push({ id: p.id, title: p.title, url: p.url });
  } catch {}
}
ws.close();
console.log(JSON.stringify([...windows.values()], null, 1));
