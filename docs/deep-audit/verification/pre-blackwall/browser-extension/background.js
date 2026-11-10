1: // Registers this browser; opens the accept page for new requests;
2: // uploads full tab snapshots (incl. chrome:// pages the MCP can't see);
3: // groups opencode session tabs like Claude does.
4: const API = "http://127.0.0.1:9225";
5: importScripts("perm.js", "cdp.js", "hub.js");
6: 
7: async function myName() {
8:   const s = await chrome.storage.sync.get({ name: "archlinux-1" });
9:   return s.name;
10: }
11: 
12: async function register() {
13:   try {
14:     await fetch(`${API}/register`, {
15:       method: "POST",
16:       headers: { "content-type": "application/json" },
17:       body: JSON.stringify({ name: await myName() }),
18:     });
19:   } catch {}
20: }
21: 
22: async function snapshot() {
23:   try {
24:     const tabs = await chrome.tabs.query({});
25:     await fetch(`${API}/tabsnapshot`, {
26:       method: "POST",
27:       headers: { "content-type": "application/json" },
28:       body: JSON.stringify({
29:         browser: await myName(),
30:         tabs: tabs.map((t) => ({ id: t.id, windowId: t.windowId, title: t.title, url: t.url })),
31:       }),
32:     });
33:   } catch {}
34: }
35: 
36: async function processGroups() {
37:   try {
38:     const name = await myName();
39:     const reqs = await (await fetch(`${API}/group-requests/${encodeURIComponent(name)}`)).json();
40:     const seen = (await chrome.storage.local.get({ grouped: [] })).grouped;
41:     for (const r of reqs) {
42:       if (seen.includes(r.requestId)) continue;
43:       const tabs = await chrome.tabs.query({});
44:       const ids = tabs.filter((t) => r.urls.includes(t.url)).map((t) => t.id).filter(Boolean);
45:       if (ids.length) {
46:         const gid = await chrome.tabs.group({ tabIds: ids });
47:         await chrome.tabGroups.update(gid, { title: r.title, color: r.color });
48:       }
49:       seen.push(r.requestId);
50:     }
51:     await chrome.storage.local.set({ grouped: seen.slice(-50) });
52:   } catch {}
53: }
54: 
55: async function checkPending() {
56:   try {
57:     const r = await (await fetch(`${API}/pending-latest`)).json();
58:     const has = r.status === "pending";
59:     await chrome.action.setBadgeText({ text: has ? "?" : "" });
60:     if (!has) return;
61:     await chrome.action.setBadgeBackgroundColor({ color: "#4285f4" });
62:     const opened = (await chrome.storage.local.get({ opened: [] })).opened;
63:     if (opened.includes(r.session)) return;
64:     opened.push(r.session);
65:     await chrome.storage.local.set({ opened: opened.slice(-20) });
66:     await chrome.tabs.create({ url: chrome.runtime.getURL(`accept.html?session=${encodeURIComponent(r.session)}`) });
67:     chrome.notifications?.create(`opencode-${r.session}`, {
68:       type: "basic",
69:       iconUrl: "icon.png",
70:       title: "opencode wants to connect",
71:       message: `Session ${r.session} — accept tab opened.`,
72:     });
73:   } catch {}
74: }
75: 
76: async function processMarks() {
77:   try {
78:     const name = await myName();
79:     const reqs = await (await fetch(`${API}/marks/${encodeURIComponent(name)}`)).json();
80:     const seen = (await chrome.storage.local.get({ marked: [] })).marked;
81:     for (const r of reqs) {
82:       if (seen.includes(r.requestId)) continue;
83:       const tabs = await chrome.tabs.query({});
84:       for (const t of tabs) {
85:         if (!r.urls.length || r.urls.includes(t.url)) {
86:           try {
87:             await chrome.scripting.executeScript({
88:               target: { tabId: t.id },
89:               func: (session) => {
90:                 if (document.getElementById("opencode-mark")) return;
91:                 const d = document.createElement("div");
92:                 d.id = "opencode-mark";
93:                 d.textContent = `opencode: ${session}`;
94:                 d.style.cssText =
95:                   "position:fixed;top:8px;right:8px;z-index:2147483647;background:#1a73e8;color:#fff;font:12px sans-serif;padding:4px 10px;border-radius:10px;pointer-events:none";
96:                 document.documentElement.appendChild(d);
97:               },
98:               args: [r.session || "working"],
99:             });
100:           } catch {}
101:         }
102:       }
103:       seen.push(r.requestId);
104:     }
105:     await chrome.storage.local.set({ marked: seen.slice(-50) });
106:   } catch {}
107: }
108: 
109: const STEALTH_HEADERS = {
110:   "User-Agent":
111:     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
112:   "Accept-Language": "en-US,en;q=0.9",
113:   "Sec-CH-UA": '"Chromium";v="150", "Google Chrome";v="150", "Not-A.Brand";v="99"',
114:   "Sec-CH-UA-Mobile": "?0",
115:   "Sec-CH-UA-Platform": '"Linux"',
116: };
117: 
118: async function applyNetRules() {
119:   try {
120:     const name = await myName();
121:     const rules = await (await fetch(`${API}/netrules/${encodeURIComponent(name)}`)).json();
122:     const dyn = [];
123:     let i = 1;
124:     for (const kind of rules.block || []) {
125:       const rt =
126:         kind === "images" ? ["image"] : kind === "media" ? ["media", "object"] : kind === "fonts" ? ["font"] : ["image", "media", "font"];
127:       dyn.push({ id: i++, priority: 1, action: { type: "block" }, condition: { resourceTypes: rt } });
128:     }
129:     if (rules.stealth) {
130:       const requestHeaders = Object.entries(STEALTH_HEADERS).map(([header, value]) => ({
131:         header,
132:         operation: "set",
133:         value,
134:       }));
135:       dyn.push({
136:         id: 100,
137:         priority: 1,
138:         action: { type: "modifyHeaders", requestHeaders },
139:         condition: { urlFilter: "*", resourceTypes: ["main_frame", "sub_frame", "xmlhttprequest"] },
140:       });
141:     }
142:     const old = await chrome.declarativeNetRequest.getSessionRules();
143:     await chrome.declarativeNetRequest.updateSessionRules({
144:       removeRuleIds: old.map((r) => r.id),
145:       addRules: dyn,
146:     });
147:   } catch {}
148: }
149: 
150: async function uploadA11y() {
151:   try {
152:     const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
153:     if (!tab?.id || !/^https?:/.test(tab.url || "")) return;
154:     const tree = await chrome.tabs.sendMessage(tab.id, { type: "opencode-a11y" }).catch(() => null);
155:     if (!tree) return;
156:     await fetch(`${API}/a11y`, {
157:       method: "POST",
158:       headers: { "content-type": "application/json" },
159:       body: JSON.stringify({ browser: await myName(), url: tree.url, tree: tree.nodes }),
160:     });
161:   } catch {}
162: }
163: 
164: async function tick() {
165:   await checkPending();
166:   await snapshot();
167:   await processGroups();
168:   await processMarks();
169:   await applyNetRules();
170:   await uploadA11y();
171: }
172: 
173: async function ensureOffscreen() {
174:   try {
175:     if (await chrome.offscreen.hasDocument?.()) return;
176:     await chrome.offscreen.createDocument({
177:       url: "offscreen.html",
178:       reasons: ["DOM_SCRAPING"],
179:       justification: "Keepalive pings for opencode bridge sessions",
180:     });
181:   } catch {}
182: }
183: 
184: chrome.runtime.onMessage.addListener((msg, sender, send) => {
185:   if (msg?.type === "accept-done" && sender.tab?.id) {
186:     setTimeout(() => chrome.tabs.remove(sender.tab.id).catch(() => {}), 1500);
187:   }
188:   if (msg?._panel) {
189:     (async () => {
190:       const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
191:       if (!tab?.id) return send({ error: "no active tab" });
192:       const name = await myName();
193:       if (msg.type === "panel-nav") {
194:         await chrome.tabs.update(tab.id, { url: msg.url });
195:         return send({ ok: true });
196:       }
197:       if (msg.type === "panel-snap") {
198:         const r = await chrome.tabs.sendMessage(tab.id, { type: "opencode-a11y" }).catch(() => null);
199:         return send({ text: r ? r.nodes.slice(0, 60).map((n) => `${n.tag} ${n.name}`.trim()).join("\n") : "n/a" });
200:       }
201:       if (msg.type === "panel-shot") {
202:         await cdpAttach(tab.id, "panel");
203:         const r = await chrome.debugger.sendCommand({ tabId: tab.id }, "Page.captureScreenshot", { format: "png" });
204:         return send({ data: r.data });
205:       }
206:       send({ error: "unknown" });
207:     })();
208:     return true;
209:   }
210:   if (msg?.type === "keepalive") return true;
211:   return false;
212: });
213: 
214: chrome.runtime.onInstalled.addListener(() => { register(); snapshot(); ensureOffscreen(); });
215: chrome.runtime.onStartup.addListener(() => { register(); snapshot(); ensureOffscreen(); });
216: try {
217:   chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
218: } catch {}
219: chrome.alarms.onAlarm.addListener(tick);
220: chrome.alarms.create("tick", { periodInMinutes: 0.5 });
221: chrome.notifications?.onClicked.addListener(() => {});
222: register();
223: tick();
224: hubConnect();
