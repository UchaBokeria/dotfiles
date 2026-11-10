1: // @ts-nocheck
2: // cdp-mcp: MCP stdio adapter -> opencode browser bridge hub (WS) -> extension CDP driver.
3: // Env: CDP_HUB (default ws://127.0.0.1:9225/hub), CDP_BROWSER (default target browser name).
4: const HUB = process.env.CDP_HUB || "ws://127.0.0.1:9225/hub";
5: const DEFAULT_BROWSER = process.env.CDP_BROWSER || "archlinux-1";
6: 
7: let ws: any = null;
8: let seq = 0;
9: const waiters = new Map<number, (m: any) => void>();
10: let ready: Promise<void> | null = null;
11: 
12: function connect(): Promise<void> {
13:   if (ws && (ws as any).readyState === 1) return Promise.resolve();
14:   if (ready) return ready;
15:   ready = new Promise((res, rej) => {
16:     const s: any = new WebSocket(HUB);
17:     s.onopen = () => {
18:       ws = s;
19:       ready = null;
20:       res();
21:     };
22:     s.onmessage = (ev: any) => {
23:       let m: any;
24:       try {
25:         m = JSON.parse(String(ev.data));
26:       } catch {
27:         return;
28:       }
29:       if (m.id !== undefined && waiters.has(m.id)) {
30:         waiters.get(m.id)!(m);
31:         waiters.delete(m.id);
32:       }
33:     };
34:     s.onclose = () => {
35:       if (ws === s) ws = null;
36:       ready = null;
37:     };
38:     s.onerror = () => rej(new Error("hub unreachable"));
39:     setTimeout(() => rej(new Error("hub connect timeout")), 15000);
40:   });
41:   return ready;
42: }
43: 
44: async function hubCall(browser: string, method: string, params: any) {
45:   await connect();
46:   return new Promise((res, rej) => {
47:     const id = ++seq;
48:     waiters.set(id, (m: any) => (m.error ? rej(new Error(m.error)) : res(m.result)));
49:     (ws as any).send(JSON.stringify({ id, to: browser, method, params }));
50:     setTimeout(() => {
51:       if (waiters.has(id)) {
52:         waiters.delete(id);
53:         rej(new Error("hub call timeout"));
54:       }
55:     }, 1000 * 60 * 18);
56:   });
57: }
58: 
59: const TOOLS = [
60:   { name: "cdp_tabs", description: "List tabs in the browser", inputSchema: { type: "object", properties: { browser: { type: "string" } } } },
61:   { name: "cdp_navigate", description: "Open URL in new or existing tab (auto session-groups it)", inputSchema: { type: "object", required: ["url"], properties: { browser: { type: "string" }, url: { type: "string" }, tabId: { type: "number" }, session: { type: "string" }, group: { type: "boolean" } } } },
62:   { name: "cdp_snapshot", description: "Accessibility snapshot of a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" } } } },
63:   { name: "cdp_screenshot", description: "Screenshot a tab (returns PNG image)", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" } } } },
64:   { name: "cdp_evaluate", description: "Run JavaScript in a tab, return value", inputSchema: { type: "object", required: ["tabId", "fn"], properties: { browser: { type: "string" }, tabId: { type: "number" }, fn: { type: "string" }, session: { type: "string" } } } },
65:   { name: "cdp_click", description: "Click a CSS selector in a tab", inputSchema: { type: "object", required: ["tabId", "selector"], properties: { browser: { type: "string" }, tabId: { type: "number" }, selector: { type: "string" }, session: { type: "string" } } } },
66:   { name: "cdp_fill", description: "Fill input (clears first) + type", inputSchema: { type: "object", required: ["tabId", "selector", "text"], properties: { browser: { type: "string" }, tabId: { type: "number" }, selector: { type: "string" }, text: { type: "string" }, session: { type: "string" } } } },
67:   { name: "cdp_type", description: "Focus selector and type text", inputSchema: { type: "object", required: ["tabId", "selector", "text"], properties: { browser: { type: "string" }, tabId: { type: "number" }, selector: { type: "string" }, text: { type: "string" }, session: { type: "string" } } } },
68:   { name: "cdp_press", description: "Press a key in a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" }, key: { type: "string" }, session: { type: "string" } } } },
69:   { name: "cdp_console", description: "Recent console messages of a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" }, limit: { type: "number" } } } },
70:   { name: "cdp_network", description: "Recent network responses of a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" }, limit: { type: "number" } } } },
71:   { name: "cdp_close_tab", description: "Close a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" } } } },
72:   { name: "cdp_select_tab", description: "Activate a tab", inputSchema: { type: "object", required: ["tabId"], properties: { browser: { type: "string" }, tabId: { type: "number" } } } },
73:   { name: "cdp_upload", description: "Set files on a file input (full user-like upload, no picker dialog)", inputSchema: { type: "object", required: ["tabId", "selector", "files"], properties: { browser: { type: "string" }, tabId: { type: "number" }, selector: { type: "string" }, files: { type: "array", items: { type: "string" } }, session: { type: "string" } } } },
74: ];
75: 
76: const METHOD_OF: Record<string, string> = {
77:   cdp_tabs: "tabs", cdp_navigate: "navigate", cdp_snapshot: "snapshot",
78:   cdp_screenshot: "screenshot", cdp_evaluate: "evaluate", cdp_click: "click",
79:   cdp_fill: "fill", cdp_type: "type", cdp_press: "press",
80:   cdp_console: "console", cdp_network: "network",
81:   cdp_close_tab: "close_tab", cdp_select_tab: "select_tab", cdp_upload: "upload",
82: };
83: 
84: let buf = "";
85: process.stdin.on("data", async (d) => {
86:   buf += d.toString();
87:   let idx: number;
88:   while ((idx = buf.indexOf("\n")) >= 0) {
89:     const line = buf.slice(0, idx).trim();
90:     buf = buf.slice(idx + 1);
91:     if (!line) continue;
92:     let m: any;
93:     try {
94:       m = JSON.parse(line);
95:     } catch {
96:       continue;
97:     }
98:     const out = async () => {
99:       if (m.method === "initialize")
100:         return { protocolVersion: "2025-06-18", capabilities: {}, serverInfo: { name: "cdp", version: "1.0.0" } };
101:       if (m.method === "tools/list") return { tools: TOOLS };
102:       if (m.method === "tools/call") {
103:         const { name, arguments: a = {} } = m.params;
104:         const method = METHOD_OF[name];
105:         if (!method) throw new Error(`unknown tool ${name}`);
106:         const browser = a.browser || DEFAULT_BROWSER;
107:         const r: any = await hubCall(browser, method, a);
108:         if (name === "cdp_screenshot")
109:           return { content: [{ type: "image", data: r.data, mimeType: "image/png" }] };
110:         return { content: [{ type: "text", text: typeof r === "string" ? r : JSON.stringify(r).slice(0, 8000) }] };
111:       }
112:       if (m.method?.startsWith("notifications/")) return null;
113:       throw new Error(`unknown method ${m.method}`);
114:     };
115:     try {
116:       const result = await out();
117:       if (m.id !== undefined)
118:         process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: m.id, result }) + "\n");
119:     } catch (e: any) {
120:       if (m.id !== undefined)
121:         process.stdout.write(
122:           JSON.stringify({ jsonrpc: "2.0", id: m.id, error: { code: -32000, message: String(e?.message || e) } }) + "\n"
123:         );
124:     }
125:   }
126: });
