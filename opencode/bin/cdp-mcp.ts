// @ts-nocheck
// cdp-mcp: MCP stdio adapter -> opencode browser bridge hub (WS) -> extension CDP driver.
// Env: CDP_HUB (default ws://127.0.0.1:9225/hub), CDP_BROWSER (default target browser name).
const HUB = process.env.CDP_HUB || "ws://127.0.0.1:9225/hub";
const DEFAULT_BROWSER = process.env.CDP_BROWSER || "archlinux-1";

let ws: any = null;
let seq = 0;
const waiters = new Map<number, (m: any) => void>();
let ready: Promise<void> | null = null;

function connect(): Promise<void> {
  if (ws && (ws as any).readyState === 1) return Promise.resolve();
  if (ready) return ready;
  ready = new Promise((res, rej) => {
    const s: any = new WebSocket(HUB);
    s.onopen = () => {
      ws = s;
      ready = null;
      res();
    };
    s.onmessage = (ev: any) => {
      let m: any;
      try {
        m = JSON.parse(String(ev.data));
      } catch {
        return;
      }
      if (m.id !== undefined && waiters.has(m.id)) {
        waiters.get(m.id)!(m);
        waiters.delete(m.id);
      }
    };
    s.onclose = () => {
      if (ws === s) ws = null;
      ready = null;
    };
    s.onerror = () => rej(new Error("hub unreachable"));
    setTimeout(() => rej(new Error("hub connect timeout")), 15000);
  });
  return ready;
}

async function hubCall(browser: string, method: string, params: any) {
  await connect();
  return new Promise((res, rej) => {
    const id = ++seq;
    waiters.set(id, (m: any) => (m.error ? rej(new Error(m.error)) : res(m.result)));
    (ws as any).send(JSON.stringify({ id, to: browser, method, params }));
    setTimeout(() => {
      if (waiters.has(id)) {
        waiters.delete(id);
        rej(new Error("hub call timeout"));
      }
    }, 1000 * 60 * 18);
  });
}

const TOOLS = [
  { name: "cdp_tabs", description: "List tabs in the browser", inputSchema: { type: "object", properties: { browser: { type: "string" } } } },
  { name: "cdp_navigate", description: "Open URL in new or existing tab (auto session-groups it)", inputSchema: { type: "object", required: ["url"], properties: { browser: { type: "string" }, url: { type: "string" }, tabId: { type: "number" }, session: { type: "string" }, group: { type: "boolean" } } } },
  { name: "cdp_snapshot", description: "Accessibility snapshot of a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" } } } },
  { name: "cdp_screenshot", description: "Screenshot a tab (returns PNG image)", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" } } } },
  { name: "cdp_evaluate", description: "Run JavaScript in a tab, return value", inputSchema: { type: "object", required: ["tabId", "fn"], properties: { browser: { type: "string" }, tabId: { type: "number" }, fn: { type: "string" }, session: { type: "string" } } } },
  { name: "cdp_click", description: "Click a CSS selector in a tab", inputSchema: { type: "object", required: ["tabId", "selector"], properties: { browser: { type: "string" }, tabId: { type: "number" }, selector: { type: "string" }, session: { type: "string" } } } },
  { name: "cdp_fill", description: "Fill input (clears first) + type", inputSchema: { type: "object", required: ["tabId", "selector", "text"], properties: { browser: { type: "string" }, tabId: { type: "number" }, selector: { type: "string" }, text: { type: "string" }, session: { type: "string" } } } },
  { name: "cdp_type", description: "Focus selector and type text", inputSchema: { type: "object", required: ["tabId", "selector", "text"], properties: { browser: { type: "string" }, tabId: { type: "number" }, selector: { type: "string" }, text: { type: "string" }, session: { type: "string" } } } },
  { name: "cdp_press", description: "Press a key in a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" }, key: { type: "string" }, session: { type: "string" } } } },
  { name: "cdp_console", description: "Recent console messages of a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" }, limit: { type: "number" } } } },
  { name: "cdp_network", description: "Recent network responses of a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" }, limit: { type: "number" } } } },
  { name: "cdp_close_tab", description: "Close a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" } } } },
  { name: "cdp_select_tab", description: "Activate a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" } } } },
  { name: "cdp_upload", description: "Set files on a file input (full user-like upload, no picker dialog)", inputSchema: { type: "object", required: ["tabId", "selector", "files"], properties: { browser: { type: "string" }, tabId: { type: "number" }, selector: { type: "string" }, files: { type: "array", items: { type: "string" } }, session: { type: "string" } } } },
];

const METHOD_OF: Record<string, string> = {
  cdp_tabs: "tabs", cdp_navigate: "navigate", cdp_snapshot: "snapshot",
  cdp_screenshot: "screenshot", cdp_evaluate: "evaluate", cdp_click: "click",
  cdp_fill: "fill", cdp_type: "type", cdp_press: "press",
  cdp_console: "console", cdp_network: "network",
  cdp_close_tab: "close_tab", cdp_select_tab: "select_tab", cdp_upload: "upload",
};

let buf = "";
process.stdin.on("data", async (d) => {
  buf += d.toString();
  let idx: number;
  while ((idx = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, idx).trim();
    buf = buf.slice(idx + 1);
    if (!line) continue;
    let m: any;
    try {
      m = JSON.parse(line);
    } catch {
      continue;
    }
    const out = async () => {
      if (m.method === "initialize")
        return { protocolVersion: "2025-06-18", capabilities: {}, serverInfo: { name: "cdp", version: "1.0.0" } };
      if (m.method === "tools/list") return { tools: TOOLS };
      if (m.method === "tools/call") {
        const { name, arguments: a = {} } = m.params;
        const method = METHOD_OF[name];
        if (!method) throw new Error(`unknown tool ${name}`);
        const browser = a.browser || DEFAULT_BROWSER;
        const r: any = await hubCall(browser, method, a);
        if (name === "cdp_screenshot")
          return { content: [{ type: "image", data: r.data, mimeType: "image/png" }] };
        return { content: [{ type: "text", text: typeof r === "string" ? r : JSON.stringify(r).slice(0, 8000) }] };
      }
      if (m.method?.startsWith("notifications/")) return null;
      throw new Error(`unknown method ${m.method}`);
    };
    try {
      const result = await out();
      if (m.id !== undefined)
        process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: m.id, result }) + "\n");
    } catch (e: any) {
      if (m.id !== undefined)
        process.stdout.write(
          JSON.stringify({ jsonrpc: "2.0", id: m.id, error: { code: -32000, message: String(e?.message || e) } }) + "\n"
        );
    }
  }
});
