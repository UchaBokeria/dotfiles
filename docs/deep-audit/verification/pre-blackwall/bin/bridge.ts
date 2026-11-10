1: // @ts-nocheck
2: // opencode browser bridge — lets Chrome extensions accept opencode sessions.
3: // Bun server on 127.0.0.1:9225. Endpoints:
4: //   POST /register {name, endpoint, windows} -> {ok}
5: //   GET  /browsers -> [{name, endpoint, windows, lastSeen}]
6: //   POST /pending  {session} -> {session, status}
7: //   GET  /pending/:session -> {status: pending|accepted, browser?}
8: //   POST /accept   {session, browser} -> {ok} (called by the extension)
9: const browsers = new Map<string, any>();
10: const pending = new Map<string, any>();
11: const sessionTabs = new Map<string, any>();
12: const tabSnapshots = new Map<string, any>();
13: const groupReqs: any[] = [];
14: const extSockets = new Map<string, any>(); // browser name -> WS
15: const mcpWaiters = new Map<number, any>();
16: let msgId = 0;
17: const netRules = new Map<string, any>();
18: const a11yStore = new Map<string, any>();
19: const markReqs: any[] = [];
20: const sseClients = new Set<ReadableStreamDefaultController>();
21: function emit(type: string, data: any) {
22:   const msg = `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
23:   for (const c of sseClients) {
24:     try {
25:       c.enqueue(new TextEncoder().encode(msg));
26:     } catch {}
27:   }
28: }
29: 
30: const json = (d: any, s = 200) =>
31:   new Response(JSON.stringify(d), { status: s, headers: { "content-type": "application/json" } });
32: 
33: Bun.serve({
34:   port: 9225,
35:   hostname: process.env.BIND || "127.0.0.1",
36:   websocket: {
37:     open(ws) {},
38:     close(ws) {
39:       for (const [name, s] of extSockets) if (s === ws) extSockets.delete(name);
40:     },
41:     message(ws, raw) {
42:       let m: any;
43:       try {
44:         m = JSON.parse(String(raw));
45:       } catch {
46:         return;
47:       }
48:       if (m.hello?.role === "extension" && m.hello.browser) {
49:         extSockets.set(m.hello.browser, ws);
50:         (ws as any).browser = m.hello.browser;
51:         ws.send(JSON.stringify({ hello: "ok" }));
52:         return;
53:       }
54:       if (m.to && m.id !== undefined) {
55:         const ext = extSockets.get(m.to);
56:         if (!ext) {
57:           ws.send(JSON.stringify({ id: m.id, error: `browser offline: ${m.to}` }));
58:           return;
59:         }
60:         mcpWaiters.set(m.id, ws);
61:         ext.send(JSON.stringify(m));
62:         return;
63:       }
64:       if (m.id !== undefined && m.from) {
65:         const waiter = mcpWaiters.get(m.id);
66:         if (waiter) {
67:           mcpWaiters.delete(m.id);
68:           waiter.send(JSON.stringify({ id: m.id, result: m.result, error: m.error }));
69:         }
70:         return;
71:       }
72:     },
73:   },
74:   async fetch(req, server) {
75:     const u = new URL(req.url);
76:     if (u.pathname === "/hub" && server.upgrade(req)) return;
77:     if (u.pathname === "/hub-browsers") {
78:       return json({ online: [...extSockets.keys()], registered: [...browsers.values()].map((b) => b.name) });
79:     }
80:     if (req.method === "POST" && u.pathname === "/register") {
81:       const b = await req.json();
82:       if (!b.name) return json({ error: "name required" }, 400);
83:       browsers.set(b.name, { ...b, lastSeen: Date.now() });
84:       return json({ ok: true });
85:     }
86:     if (req.method === "GET" && u.pathname === "/browsers") {
87:       return json([...browsers.values()]);
88:     }
89:     if (req.method === "GET" && u.pathname === "/events") {
90:       let ctrl: ReadableStreamDefaultController;
91:       const stream = new ReadableStream({
92:         start(c) {
93:           ctrl = c;
94:           sseClients.add(c);
95:         },
96:         cancel(c) {
97:           sseClients.delete(c);
98:         },
99:       });
100:       return new Response(stream, {
101:         headers: {
102:           "content-type": "text/event-stream",
103:           "cache-control": "no-cache",
104:           connection: "keep-alive",
105:         },
106:       });
107:     }
108:     if (req.method === "POST" && u.pathname === "/pending") {
109:       const { session } = await req.json();
110:       if (!session) return json({ error: "session required" }, 400);
111:       pending.set(session, { status: "pending", created: Date.now() });
112:       emit("pending", { session });
113:       return json({ session, status: "pending" });
114:     }
115:     if (req.method === "GET" && u.pathname.startsWith("/pending/")) {
116:       const session = decodeURIComponent(u.pathname.slice(9));
117:       const p = pending.get(session);
118:       if (!p) return json({ status: "unknown" }, 404);
119:       if (Date.now() - p.created > 5 * 60 * 1000) {
120:         pending.delete(session);
121:         return json({ status: "expired" });
122:       }
123:       return json(p.status === "accepted" ? { status: "accepted", browser: p.browser } : { status: "pending" });
124:     }
125:     if (req.method === "GET" && u.pathname === "/pending-latest") {
126:       const all = [...pending.entries()].filter(([, p]) => p.status === "pending" && Date.now() - p.created < 5 * 60 * 1000);
127:       if (!all.length) return json({ status: "none" });
128:       const [session] = all[all.length - 1];
129:       return json({ status: "pending", session });
130:     }
131:     if (req.method === "POST" && u.pathname === "/accept") {
132:       const { session, browser } = await req.json();
133:       const p = pending.get(session);
134:       if (!p) return json({ error: "no such pending session" }, 404);
135:       pending.set(session, { ...p, status: "accepted", browser });
136:       emit("accepted", { session, browser });
137:       return json({ ok: true });
138:     }
139:     if (req.method === "POST" && u.pathname === "/session-tabs") {
140:       const { session, browser, tabs } = await req.json();
141:       if (!session) return json({ error: "session required" }, 400);
142:       sessionTabs.set(session, { browser, tabs, at: Date.now() });
143:       return json({ ok: true });
144:     }
145:     if (req.method === "GET" && u.pathname.startsWith("/session-tabs/")) {
146:       const s = sessionTabs.get(decodeURIComponent(u.pathname.slice("/session-tabs/".length)));
147:       return s ? json(s) : json({ error: "unknown session" }, 404);
148:     }
149:     if (req.method === "POST" && u.pathname === "/tabsnapshot") {
150:       const { browser, tabs } = await req.json();
151:       if (!browser) return json({ error: "browser required" }, 400);
152:       tabSnapshots.set(browser, { tabs, at: Date.now() });
153:       return json({ ok: true });
154:     }
155:     if (req.method === "GET" && u.pathname.startsWith("/tabsnapshot/")) {
156:       const s = tabSnapshots.get(decodeURIComponent(u.pathname.slice("/tabsnapshot/".length)));
157:       return s ? json(s) : json({ error: "no snapshot" }, 404);
158:     }
159:     if (req.method === "POST" && u.pathname === "/group") {
160:       const { browser, session, requestId, urls, title, color } = await req.json();
161:       if (!browser || !requestId) return json({ error: "browser+requestId required" }, 400);
162:       groupReqs.push({ browser, session, requestId, urls: urls || [], title: title || session, color: color || "blue", created: Date.now() });
163:       return json({ ok: true });
164:     }
165:     if (req.method === "GET" && u.pathname.startsWith("/group-requests/")) {
166:       const browser = decodeURIComponent(u.pathname.slice("/group-requests/".length));
167:       const now = Date.now();
168:       return json(groupReqs.filter((g) => g.browser === browser && now - g.created < 10 * 60 * 1000));
169:     }
170:     if (req.method === "GET" && u.pathname === "/profiles") {
171:       try {
172:         const ls = await Bun.file(`${process.env.HOME}/.config/google-chrome/Local State`).json();
173:         const cache = ls.profile?.info_cache || {};
174:         return json(Object.entries(cache).map(([dir, v]: any) => ({ dir, name: v.name || dir })));
175:       } catch (e) {
176:         return json({ error: "cannot read Local State" }, 500);
177:       }
178:     }
179:     if ((req.method === "POST" || req.method === "PUT") && u.pathname === "/netrules") {
180:       const b = await req.json();
181:       if (!b.browser) return json({ error: "browser required" }, 400);
182:       netRules.set(b.browser, { block: b.block || [], stealth: !!b.stealth, at: Date.now() });
183:       emit("netrules", { browser: b.browser });
184:       return json({ ok: true });
185:     }
186:     if (req.method === "GET" && u.pathname.startsWith("/netrules/")) {
187:       const r = netRules.get(decodeURIComponent(u.pathname.slice("/netrules/".length)));
188:       return json(r || { block: [], stealth: false });
189:     }
190:     if (req.method === "POST" && u.pathname === "/a11y") {
191:       const { browser, url, tree } = await req.json();
192:       if (!browser) return json({ error: "browser required" }, 400);
193:       a11yStore.set(browser, { url, tree, at: Date.now() });
194:       return json({ ok: true });
195:     }
196:     if (req.method === "GET" && u.pathname.startsWith("/a11y/")) {
197:       const s = a11yStore.get(decodeURIComponent(u.pathname.slice("/a11y/".length)));
198:       return s ? json(s) : json({ error: "no snapshot" }, 404);
199:     }
200:     if (req.method === "POST" && u.pathname === "/mark") {
201:       const { browser, session, requestId, urls } = await req.json();
202:       if (!browser || !requestId) return json({ error: "browser+requestId required" }, 400);
203:       markReqs.push({ browser, session, requestId, urls: urls || [], created: Date.now() });
204:       emit("mark", { browser, session });
205:       return json({ ok: true });
206:     }
207:     if (req.method === "GET" && u.pathname.startsWith("/marks/")) {
208:       const browser = decodeURIComponent(u.pathname.slice("/marks/".length));
209:       const now = Date.now();
210:       return json(markReqs.filter((g) => g.browser === browser && now - g.created < 10 * 60 * 1000));
211:     }
212:     return json({ error: "not found" }, 404);
213:   },
214: });
215: console.log("browser bridge on 127.0.0.1:9225");
