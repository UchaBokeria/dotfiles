1: // CDP driver core: the extension is the SOLE debugger on tabs it owns.
2: // Lazy attach per tab (Claude-style), detach after 25s idle.
3: const attached = new Map(); // tabId -> {session, lastUsed, buffers:{console:[],network:[]}}
4: const groups = new Map(); // session -> groupId
5: 
6: async function cdpAttach(tabId, session) {
7:   const cur = attached.get(tabId);
8:   if (cur?.attached) {
9:     cur.lastUsed = Date.now();
10:     cur.session = session || cur.session;
11:     return;
12:   }
13:   await chrome.debugger.attach({ tabId }, "1.3");
14:   const st = { attached: true, session, lastUsed: Date.now(), buffers: { console: [], network: [] } };
15:   attached.set(tabId, st);
16:   try {
17:     await chrome.debugger.sendCommand({ tabId }, "Page.enable");
18:     await chrome.debugger.sendCommand({ tabId }, "Runtime.enable");
19:     await chrome.debugger.sendCommand({ tabId }, "Network.enable", { maxPostDataSize: 65536 });
20:   } catch {}
21: }
22: 
23: async function cdpDetachIdle() {
24:   const now = Date.now();
25:   for (const [tabId, st] of attached) {
26:     if (now - st.lastUsed > 25000) {
27:       try {
28:         await chrome.debugger.detach({ tabId });
29:       } catch {}
30:       attached.delete(tabId);
31:     }
32:   }
33: }
34: setInterval(cdpDetachIdle, 10000);
35: 
36: chrome.debugger.onEvent.addListener((src, method, params) => {
37:   const st = src.tabId !== undefined ? attached.get(src.tabId) : null;
38:   if (!st) return;
39:   st.lastUsed = Date.now();
40:   if (method === "Runtime.consoleAPICalled" || method === "Runtime.exceptionThrown") {
41:     st.buffers.console.push({ at: Date.now(), method, params });
42:     if (st.buffers.console.length > 200) st.buffers.console.shift();
43:   }
44:   if (method.startsWith("Network.")) {
45:     st.buffers.network.push({ at: Date.now(), method, params });
46:     if (st.buffers.network.length > 300) st.buffers.network.shift();
47:   }
48:   if (method === "Page.javascriptDialogOpening") {
49:     chrome.debugger.sendCommand({ tabId: src.tabId }, "Page.handleJavaScriptDialog", { accept: true }).catch(() => {});
50:   }
51: });
52: chrome.debugger.onDetach.addListener((src) => attached.delete(src.tabId));
53: 
54: function checkDomain(session, url, write) {
55:   // Turn-scoped permission store (cocodem-inspired). Default allow; explicit denies win.
56:   return permCheck(session, url, write).then((ok) => {
57:     if (!ok) throw new Error(`denied by session policy: ${url}`);
58:   });
59: }
60: 
61: async function waitLoad(tabId, ms = 25000) {
62:   const t0 = Date.now();
63:   while (Date.now() - t0 < ms) {
64:     const tab = await chrome.tabs.get(tabId).catch(() => null);
65:     if (tab && tab.status === "complete") return;
66:     await new Promise((r) => setTimeout(r, 300));
67:   }
68: }
69: 
70: async function showCursor(tabId, x, y) {
71:   try {
72:     await chrome.scripting.executeScript({
73:       target: { tabId },
74:       func: (pt) => {
75:         let c = document.getElementById("opencode-cursor");
76:         if (!c) {
77:           c = document.createElement("div");
78:           c.id = "opencode-cursor";
79:           c.style.cssText =
80:             "position:fixed;z-index:2147483647;width:18px;height:18px;border-radius:50%;background:radial-gradient(circle,#1a73e8 30%,rgba(26,115,232,.25) 70%);pointer-events:none;transition:left .18s ease-out,top .18s ease-out;box-shadow:0 0 0 2px #fff,0 2px 8px rgba(0,0,0,.4)";
81:           document.documentElement.appendChild(c);
82:         }
83:         c.style.left = pt.x - 9 + window.scrollX + "px";
84:         c.style.top = pt.y - 9 + window.scrollY + "px";
85:         clearTimeout(c._t);
86:         c._t = setTimeout(() => c.remove(), 2500);
87:       },
88:       args: [{ x, y }],
89:     });
90:   } catch {}
91: }
92: 
93: async function cdpExec(method, p) {
94:   const session = p.session || "default";
95:   switch (method) {
96:     case "ping":
97:       return { ok: true, tabs: attached.size };
98:     case "tabs": {
99:       const tabs = await chrome.tabs.query(p.windowId ? { windowId: p.windowId } : {});
100:       return tabs.map((t) => ({ id: t.id, windowId: t.windowId, title: t.title, url: t.url, active: t.active }));
101:     }
102:     case "navigate": {
103:       await checkDomain(session, p.url, false);
104:       let tabId = p.tabId;
105:       if (!tabId) {
106:         const tab = await chrome.tabs.create({ url: p.url, active: false });
107:         tabId = tab.id;
108:       } else {
109:         await chrome.tabs.update(tabId, { url: p.url });
110:       }
111:       await waitLoad(tabId);
112:       if (p.group !== false) await groupTab(session, tabId);
113:       return { tabId };
114:     }
115:     case "snapshot": {
116:       const r = await chrome.tabs.sendMessage(p.tabId, { type: "opencode-a11y" }).catch(() => null);
117:       if (!r) throw new Error("no a11y host on tab (chrome:// pages excluded)");
118:       return r;
119:     }
120:     case "evaluate": {
121:       await checkDomain(session, p.url || "", true);
122:       await cdpAttach(p.tabId, session);
123:       const r = await chrome.debugger.sendCommand({ tabId: p.tabId }, "Runtime.evaluate", {
124:         expression: p.fn,
125:         returnByValue: true,
126:         awaitPromise: true,
127:       });
128:       if (r.exceptionDetails) throw new Error(r.exceptionDetails.text || "evaluate failed");
129:       return r.result?.value ?? null;
130:     }
131:     case "screenshot": {
132:       await cdpAttach(p.tabId, session);
133:       const r = await chrome.debugger.sendCommand({ tabId: p.tabId }, "Page.captureScreenshot", {
134:         format: p.format || "png",
135:       });
136:       return { data: r.data };
137:     }
138:     case "click": {
139:       await cdpAttach(p.tabId, session);
140:       const pt = await cdpExec("evaluate", { tabId: p.tabId, session, fn: `(() => { const el = document.querySelector(${JSON.stringify(p.selector)}); if (!el) return null; const r = el.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; })()` });
141:       if (!pt) throw new Error(`no match: ${p.selector}`);
142:       await showCursor(p.tabId, pt.x, pt.y);
143:       for (const t of ["mousePressed", "mouseReleased"]) {
144:         await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.dispatchMouseEvent", {
145:           type: t,
146:           x: pt.x,
147:           y: pt.y,
148:           button: "left",
149:           clickCount: 1,
150:         });
151:       }
152:       return { ok: true, at: pt };
153:     }
154:     case "fill":
155:     case "type": {
156:       await cdpAttach(p.tabId, session);
157:       await cdpExec("click", { tabId: p.tabId, session, selector: p.selector });
158:       if (method === "fill") {
159:         await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.dispatchMouseEvent", {});
160:         await cdpExec("evaluate", {
161:           tabId: p.tabId,
162:           session,
163:           fn: `(() => { const el = document.querySelector(${JSON.stringify(p.selector)}); if (el) { el.focus(); el.select?.(); document.execCommand('selectAll', false, null); } return !!el; })()`,
164:         });
165:       }
166:       await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.insertText", { text: p.text });
167:       return { ok: true };
168:     }
169:     case "press": {
170:       await cdpAttach(p.tabId, session);
171:       const key = p.key || "Enter";
172:       const code = key.length === 1 ? `Key${key.toUpperCase()}` : key;
173:       for (const t of ["keyDown", "keyUp"]) {
174:         await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.dispatchKeyEvent", {
175:           type: t,
176:           key,
177:           windowsVirtualKeyCode: key.length === 1 ? key.toUpperCase().charCodeAt(0) : undefined,
178:           code,
179:         });
180:       }
181:       return { ok: true };
182:     }
183:     case "console": {
184:       const st = attached.get(p.tabId);
185:       return (st?.buffers.console || []).slice(-(p.limit || 50));
186:     }
187:     case "network": {
188:       const st = attached.get(p.tabId);
189:       return (st?.buffers.network || [])
190:         .filter((e) => e.method === "Network.responseReceived")
191:         .slice(-(p.limit || 50))
192:         .map((e) => ({ url: e.params.response.url, status: e.params.response.status, mime: e.params.response.mimeType }));
193:     }
194:     case "close_tab":
195:       await chrome.tabs.remove(p.tabId);
196:       return { ok: true };
197:     case "upload": {
198:       await cdpAttach(p.tabId, session);
199:       const node = await chrome.debugger.sendCommand({ tabId: p.tabId }, "DOM.getDocument", { depth: 0 });
200:       const found = await chrome.debugger.sendCommand({ tabId: p.tabId }, "DOM.querySelector", {
201:         nodeId: node.root.nodeId,
202:         selector: p.selector,
203:       }).catch(() => null);
204:       if (!found) throw new Error(`no match: ${p.selector}`);
205:       const desc = await chrome.debugger.sendCommand({ tabId: p.tabId }, "DOM.describeNode", {
206:         nodeId: found.nodeId,
207:       });
208:       await chrome.debugger.sendCommand({ tabId: p.tabId }, "DOM.setFileInputFiles", {
209:         files: p.files,
210:         backendNodeId: desc.node.backendNodeId,
211:       });
212:       return { ok: true, files: p.files.length };
213:     }
214:     case "select_tab":
215:       await chrome.tabs.update(p.tabId, { active: true });
216:       return { ok: true };
217:     default:
218:       throw new Error(`unknown method: ${method}`);
219:   }
220: }
221: 
222: async function groupTab(session, tabId) {
223:   try {
224:     const tab = await chrome.tabs.get(tabId);
225:     if (tab.groupId && tab.groupId !== -1) return tab.groupId;
226:     let gid = groups.get(session);
227:     if (gid === undefined) {
228:       gid = await chrome.tabs.group({ tabIds: [tabId] });
229:       groups.set(session, gid);
230:       const colors = ["blue", "green", "orange", "purple", "pink", "cyan"];
231:       await chrome.tabGroups.update(gid, {
232:         title: `opencode: ${session}`,
233:         color: colors[[...groups.keys()].length % colors.length],
234:       });
235:     } else {
236:       await chrome.tabs.group({ tabIds: [tabId], groupId: gid });
237:     }
238:     return gid;
239:   } catch {
240:     return -1;
241:   }
242: }
