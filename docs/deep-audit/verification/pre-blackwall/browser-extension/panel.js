1: const API = "http://127.0.0.1:9225";
2: const $ = (id) => document.getElementById(id);
3: const store = {
4:   async get() {
5:     return chrome.storage.sync.get({
6:       name: "archlinux-1", srv: "http://127.0.0.1:4096",
7: [CREDENTIAL-RELATED LINE OMITTED]
8:     });
9:   },
10:   set(o) { return chrome.storage.sync.set(o); },
11: };
12: [CREDENTIAL-RELATED LINE OMITTED]
13: async function api(path, opts = {}) {
14:   const c = await store.get();
15:   const r = await fetch(c.srv.replace(/\/$/, "") + path, {
16:     ...opts,
17:     headers: { ...(opts.headers || {}), ...auth(c) },
18:   });
19:   const text = await r.text();
20:   if (!r.ok) throw new Error(`server ${r.status} on ${path}: ${text.slice(0, 160) || r.statusText} (check ⋯ → Server login)`);
21:   return text ? JSON.parse(text) : null;
22: }
23: const esc = (s) => String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
24: // hover copy button for any rendered message (user + assistant).
25: // Button lives UNDER the bubble inside a .msgwrap that reserves its slot,
26: // so showing it never moves layout (absolute, out of flow).
27: // classic overlapping-rectangles copy icon with the brand gradient stroke
28: const COPY_SVG = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><defs><linearGradient id="cpg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1a73e8"/><stop offset="1" stop-color="#7b5cff"/></linearGradient></defs><rect x="9" y="9" width="12" height="12" rx="2" stroke="url(#cpg)"/><path d="M5 15V5a2 2 0 0 1 2-2h10" stroke="url(#cpg)"/></svg>`;
29: function addCopy(div, text) {
30:   if (!text || !text.trim()) return;
31:   const w = document.createElement("div");
32:   w.className = "msgwrap " + (div.classList.contains("user") ? "u" : "a");
33:   div.before(w);
34:   w.appendChild(div);
35:   const b = document.createElement("button");
36:   b.className = "copybelow";
37:   b.innerHTML = COPY_SVG;
38:   b.onclick = async (e) => {
39:     e.stopPropagation();
40:     try {
41:       await navigator.clipboard.writeText(text);
42:       b.innerHTML = `<span style="font-size:18px;line-height:1">✓</span>`;
43:     } catch { b.textContent = "!"; }
44:     setTimeout(() => { b.innerHTML = COPY_SVG; }, 1000);
45:   };
46:   w.appendChild(b);
47: }
48: // ---------- custom tooltips (dark card; [data-tip] only, never send/copy) ----------
49: function initTips() {
50:   let tip = $("tip");
51:   if (!tip) {
52:     tip = document.createElement("div");
53:     tip.id = "tip";
54:     document.body.appendChild(tip);
55:   }
56:   let t = null;
57:   const hide = () => { tip.classList.remove("on"); if (t) { clearTimeout(t); t = null; } };
58:   document.addEventListener("mouseover", (e) => {
59:     const el = e.target.closest("[data-tip]");
60:     if (!el) return;
61:     hide();
62:     t = setTimeout(() => {
63:       tip.textContent = el.dataset.tip;
64:       const r = el.getBoundingClientRect();
65:       tip.style.visibility = "hidden";
66:       tip.classList.add("on");
67:       const tw = tip.offsetWidth, th = tip.offsetHeight;
68:       let x = Math.min(Math.max(6, r.left), innerWidth - tw - 6);
69:       let y = r.bottom + 6;
70:       if (y + th > innerHeight - 6) y = Math.max(6, r.top - th - 6);
71:       tip.style.left = `${x}px`;
72:       tip.style.top = `${y}px`;
73:       tip.style.visibility = "";
74:     }, 120);
75:   });
76:   document.addEventListener("mouseout", (e) => {
77:     if (e.target.closest && e.target.closest("[data-tip]")) hide();
78:   });
79:   document.addEventListener("click", hide, true);
80: }
81: const fmtT = (n) => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n ?? 0);
82: // exact cost, no rounding: full value, tiny amounts in exponent form instead of $0.00
83: const exactCost = (c) => {
84:   const v = c ?? 0;
85:   if (v !== 0 && Math.abs(v) < 0.01) return v.toExponential(1);
86:   return String(Math.round(v * 1e6) / 1e6);
87: };
88: const fmtTime = (ts) => ts ? new Date(ts).toTimeString().slice(0, 5) : "";
89: 
90: // ---------- busy dot ----------
91: function setBusy(b) {
92:   $("dot").classList.toggle("busy", !!b);
93: }
94: 
95: // ---------- custom dropdowns ----------
96: function dropdown(id, options, value, onPick) {
97:   const root = $(id);
98:   const btn = root.querySelector("button");
99:   const list = root.querySelector(".list");
100:   const render = (opts, val) => {
101:     const short = (val || opts[0] || "–").split("/").pop();
102:     btn.textContent = short;
103:     list.innerHTML = "";
104:     for (const o of opts) {
105:       const b = document.createElement("button");
106:       b.textContent = o.split("/").pop();
107:       if (o === val || o.split("/").pop() === String(val || "").split("/").pop()) b.classList.add("on");
108:       b.onclick = (e) => {
109:         e.stopPropagation();
110:         root.classList.remove("open");
111:         onPick(o);
112:         render(opts, o);
113:       };
114:       list.appendChild(b);
115:     }
116:   };
117:   btn.onclick = (e) => {
118:     e.stopPropagation();
119:     document.querySelectorAll(".dd.open").forEach((d) => d !== root && d.classList.remove("open"));
120:     root.classList.toggle("open");
121:   };
122:   document.addEventListener("click", () => root.classList.remove("open"));
123:   render(options, value);
124:   return { render };
125: }
126: let ddAgent, ddModel;
127: let modelOpts = ["…"]; // loading placeholder until serve answers
128: const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
129: async function fetchModels() {
130:   const cfg = await api("/config");
131:   const set = new Set();
132:   if (cfg.model) set.add(cfg.model);
133:   for (const [pid, p] of Object.entries(cfg.provider || {}))
134:     for (const m of Object.keys(p.models || {})) set.add(`${pid}/${m}`);
135:   return { cfg, models: set.size ? [...set].slice(0, 40) : [""] };
136: }
137: async function reloadModels() {
138:   if (!ddModel) return false;
139:   for (let i = 0; i < 4; i++) {
140:     try {
141:       const { cfg, models } = await fetchModels();
142:       if (models.length > 1 || models[0]) {
143:         modelOpts = models;
144:         const cur = await store.get();
145:         if (!cur.model && cfg.model) await store.set({ model: cfg.model });
146:         const c = await store.get();
147:         ddModel.render(models, c.model);
148:         return true;
149:       }
150:     } catch {}
151:     await sleep(1500);
152:   }
153:   return false;
154: }
155: async function initDropdowns() {
156:   const c = await store.get();
157:   ddAgent = dropdown("dd-agent", ["build", "ask", "plan"], c.agent, (v) => store.set({ agent: v }));
158:   ddModel = dropdown("dd-model", modelOpts, c.model, (v) => store.set({ model: v }));
159:   await reloadModels();
160:   try {
161:     const ss = await api("/session");
162:     const seen = new Set(modelOpts.filter(Boolean));
163:     for (const s of ss) {
164:       const mid = s.model || s.modelID;
165:       if (mid && !seen.has(mid)) {
166:         seen.add(mid);
167:         if (seen.size > 40) break;
168:       }
169:     }
170:     if (seen.size > modelOpts.filter(Boolean).length) {
171:       modelOpts = [...seen];
172:       ddModel.render(modelOpts, (await store.get()).model);
173:     }
174:   } catch {}
175: }
176: // retry model load when opening an empty/still-loading list (serve may have been starting)
177: $("dd-model").querySelector("button").addEventListener("click", () => {
178:   if (modelOpts.length <= 1 && (!modelOpts[0] || modelOpts[0] === "…")) reloadModels();
179: }, true);
180: 
181: // ---------- context meter ----------
182: let ctxLimit = 1048576;
183: async function initLimit() {
184:   try {
185:     const cfg = await api("/config");
186:     for (const p of Object.values(cfg.provider || {}))
187:       for (const m of Object.values(p.models || {}))
188:         if (m?.limit?.context) ctxLimit = m.limit.context;
189:   } catch {}
190: }
191: async function refreshMeter() {
192:   try {
193:     const c = await store.get();
194:     if (!c.session) {
195: [CREDENTIAL-RELATED LINE OMITTED]
196:       $("ctx-pct").textContent = "–";
197:       $("ctx-cost").textContent = "$0.00";
198:       $("ctxfill").style.width = "0%";
199:       return;
200:     }
201:     const ss = await api("/session");
202:     const s = ss.find((x) => x.id === c.session);
203:     if (!s) return;
204: [CREDENTIAL-RELATED LINE OMITTED]
205:     const total = (t.input || 0) + (t.output || 0);
206:     const left = Math.max(0, ctxLimit - total);
207:     const pct = Math.min(100, (total / ctxLimit) * 100);
208: [CREDENTIAL-RELATED LINE OMITTED]
209:     $("ctx-pct").innerHTML = `<b>left</b>${fmtT(left)} (${(100 - pct).toFixed(1)}%)`;
210:     $("ctx-cost").innerHTML = `<b>$</b>${exactCost(s.cost)}`;
211:     const fill = $("ctxfill");
212:     fill.style.width = `${pct}%`;
213:     $("ctx-pct").classList.toggle("hot", pct > 80);
214:   } catch {}
215: }
216: 
217: // ---------- chat ----------
218: let booted = false; // true once first full init finished; errors before that show "connecting…"
219: let histCache = [];
220: const dayOf = (ts) => {
221:   const d = new Date(ts || 0);
222:   const t = new Date();
223:   const day = (x) => x.toDateString();
224:   if (day(d) === day(t)) return "Today";
225:   const y = new Date(t - 864e5);
226:   if (day(d) === day(y)) return "Yesterday";
227:   return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
228: };
229: const fmtDT = (ts) => ts ? new Date(ts).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
230: function renderHist() {
231:   const q = ($("hist-search")?.value || "").toLowerCase();
232:   const box = $("hist");
233:   box.innerHTML = "";
234:   let lastDay = "";
235:   for (const s of histCache) {
236:     if (q && !(s.title || s.slug || "").toLowerCase().includes(q)) continue;
237:     const day = dayOf(s.time?.updated);
238:     if (day !== lastDay) {
239:       lastDay = day;
240:       const h = document.createElement("div");
241:       h.className = "small";
242:       h.style.cssText = "margin:8px 0 2px;font-weight:700";
243:       h.textContent = day;
244:       box.appendChild(h);
245:     }
246:     const b = document.createElement("button");
247: [CREDENTIAL-RELATED LINE OMITTED]
248:     b.innerHTML = `${esc(s.title || s.slug)}<span class="t">${fmtDT(s.time?.updated)} · ${esc(s.agent || "")} · ${fmtT((t.input || 0) + (t.output || 0))} tok</span>`;
249:     (async () => {
250:       const c = await store.get();
251:       if (s.id === c.session) b.classList.add("on");
252:     })();
253:     b.onclick = async () => {
254:       await store.set({ session: s.id });
255:       toggleOverlay("hist-menu", false);
256:       loadMsgs();
257:       loadHist();
258:       refreshMeter();
259:     };
260:     box.appendChild(b);
261:   }
262:   if (!box.children.length) box.innerHTML = `<div class="small">No chats found.</div>`;
263: }
264: async function loadHist() {
265:   try {
266:     const ss = await api("/session");
267:     ss.sort((a, b) => (b.time?.updated || 0) - (a.time?.updated || 0));
268:     histCache = ss.slice(0, 60);
269:     renderHist();
270:   } catch (e) {
271:     if (!booted) {
272:       // serve may still be starting — show connecting state and retry, not a scary error
273:       $("hist").innerHTML = `<div class="small">connecting…</div>`;
274:       setTimeout(() => { if (!booted) loadHist(); }, 2000);
275:     } else {
276:       $("hist").innerHTML = `<div class="small">${esc(e.message)}</div>`;
277:     }
278:   }
279: }
280: async function loadMsgs() {
281:   const c = await store.get();
282:   $("msgs").innerHTML = "";
283:   if (!c.session) return;
284:   try {
285:     const ms = await api(`/session/${c.session}/message`);
286:     for (const m of ms.slice(-40)) {
287:       const role = m.info?.role || "?";
288:       if (role !== "user" && role !== "assistant") continue;
289:       const div = document.createElement("div");
290:       div.className = `msg ${role === "user" ? "user" : "asst"}`;
291: [CREDENTIAL-RELATED LINE OMITTED]
292:       const when = fmtTime(m.info?.time?.created);
293:       const files = (m.parts || []).filter((p) => p.type === "file" && p.url);
294:       const text = (m.parts || []).map((p) => p.text || "").join("\n");
295:       if (!text.trim() && !files.length) continue;
296:       if (text.trim()) {
297:         const td = document.createElement("div");
298:         td.innerHTML = esc(text).slice(0, 4000);
299:         div.appendChild(td);
300:       }
301:       for (const f of files) {
302:         // NOTE: message-list API returns file parts with url stripped
303:         // or as blob refs; render whatever we can (thumb or name chip).
304:         if ((f.mime || "").startsWith("image/") && f.url.startsWith("data:")) {
305:           const im = document.createElement("img");
306:           im.className = "thumb";
307:           im.src = f.url;
308:           div.appendChild(im);
309:         } else {
310:           const s = document.createElement("span");
311:           s.className = "filechip";
312:           s.textContent = `📄 ${f.filename || f.mime || "file"}`;
313:           div.appendChild(s);
314:         }
315:       }
316:       const meta = document.createElement("div");
317:       meta.className = "meta";
318:       meta.textContent = `${when}${when ? " · " : ""}${t ? `${fmtT((t.input || 0) + (t.output || 0))} tok` : ""}`;
319:       div.appendChild(meta);
320:       $("msgs").appendChild(div);
321:       addCopy(div, text);
322:     }
323:     $("msgs").scrollTop = 1e6;
324:   } catch {}
325: }
326: // ---- attachments (images, PDF, other files -> serve file parts) ----
327: const MAX_FILE = 20 * 1024 * 1024; // serve decodes max ~20MiB per item
328: let pending = []; // {name, mime, size, dataUrl}
329: function fmtSize(n) {
330:   if (n < 1024) return `${n}B`;
331:   if (n < 1048576) return `${(n / 1024).toFixed(0)}K`;
332:   return `${(n / 1048576).toFixed(1)}M`;
333: }
334: function readAsDataURL(f) {
335:   return new Promise((res, rej) => {
336:     const r = new FileReader();
337:     r.onload = () => res(r.result);
338:     r.onerror = () => rej(new Error(`cannot read ${f.name}`));
339:     r.readAsDataURL(f);
340:   });
341: }
342: function addFiles(files) {
343:   for (const f of files || []) {
344:     if (f.size > MAX_FILE) {
345:       const div = document.createElement("div");
346:       div.className = "msg asst";
347:       div.textContent = `Skipped ${f.name}: ${fmtSize(f.size)} exceeds the 20MB attachment limit.`;
348:       $("msgs").appendChild(div);
349:       continue;
350:     }
351:     readAsDataURL(f).then((dataUrl) => {
352:       pending.push({ name: f.name, mime: f.type || "application/octet-stream", size: f.size, dataUrl });
353:       renderTray();
354:     }).catch((e) => toast(e.message));
355:   }
356: }
357: function renderTray() {
358:   const t = $("tray");
359:   t.innerHTML = "";
360:   t.classList.toggle("on", pending.length > 0);
361:   pending.forEach((a, i) => {
362:     const c = document.createElement("div");
363:     c.className = "chip";
364:     const thumb = a.mime.startsWith("image/") ? `<img src="${a.dataUrl}" alt="">` : "📄";
365:     c.innerHTML = `${thumb}<span class="nm">${esc(a.name)}</span><span class="sz">${fmtSize(a.size)}</span>`;
366:     const x = document.createElement("button");
367:     x.className = "x";
368:     x.textContent = "×";
369:     x.dataset.tip = "Remove file";
370:     x.onclick = () => { pending.splice(i, 1); renderTray(); };
371:     c.appendChild(x);
372:     t.appendChild(c);
373:   });
374: }
375: function toast(msg) {
376:   const div = document.createElement("div");
377:   div.className = "msg asst";
378:   div.textContent = msg;
379:   $("msgs").appendChild(div);
380:   $("msgs").scrollTop = 1e6;
381: }
382: async function send() {
383:   const text = $("chat-in").value.trim();
384:   const files = pending;
385:   if (!text && !files.length) return;
386:   pending = [];
387:   renderTray();
388:   $("chat-in").value = "";
389:   $("chat-in").style.height = "auto";
390:   const d = document.createElement("div");
391:   d.className = "msg user";
392:   d.textContent = text || "";
393:   for (const a of files) {
394:     if (a.mime.startsWith("image/")) {
395:       const im = document.createElement("img");
396:       im.className = "thumb";
397:       im.src = a.dataUrl;
398:       d.appendChild(im);
399:     } else {
400:       const s = document.createElement("span");
401:       s.className = "filechip";
402:       s.textContent = `📄 ${a.name} (${fmtSize(a.size)})`;
403:       d.appendChild(s);
404:     }
405:   }
406:   if (!text && !files.length) { d.textContent = "(empty)"; }
407:   $("msgs").appendChild(d);
408:   addCopy(d, text);
409:   $("msgs").scrollTop = 1e6;
410:   $("sendbtn").disabled = true;
411:   setBusy(true);
412:   try {
413:     let c = await store.get();
414:     if (!c.session) {
415:       const body = {};
416:       if (c.agent && c.agent !== "build") body.agent = c.agent;
417:       // serve takes model as {id, providerID}, never a "provider/id" string (else 400)
418:       const toModelObj = (m) => {
419:         const s = String(m || "");
420:         const i = s.indexOf("/");
421:         return i > 0 ? { id: s.slice(i + 1), providerID: s.slice(0, i) } : null;
422:       };
423:       // drop a stored model the serve no longer offers (else 400 BadRequest)
424:       if (c.model && modelOpts.some(Boolean) && !modelOpts.includes(c.model)) {
425:         toast(`Model ${c.model} not offered by this serve — using serve default.`);
426:         c.model = "";
427:       }
428:       if (toModelObj(c.model)) body.model = toModelObj(c.model);
429:       let s;
430:       try {
431:         s = await api("/session", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
432:       } catch (e) {
433:         if (!/server 400/.test(e.message)) throw e;
434:         // stale model/agent convicted by serve: forget it, retry once with serve defaults
435:         await store.set({ model: "" });
436:         c = await store.get();
437:         toast(`Serve rejected session options (${e.message}) — cleared saved model, retrying with defaults.`);
438:         s = await api("/session", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
439:       }
440:       await store.set({ session: s.id });
441:       c = await store.get();
442:       loadHist();
443:     }
444:     const parts = [];
445:     for (const a of files) parts.push({ type: "file", mime: a.mime, filename: a.name, url: a.dataUrl });
446:     if (text) parts.push({ type: "text", text });
447:     await api(`/session/${c.session}/message`, { method: "POST",
448:       headers: { "content-type": "application/json" },
449:       body: JSON.stringify({ parts }) });
450:     loadMsgs();
451:     loadHist();
452:     refreshMeter();
453:   } catch (e) {
454:     const div = document.createElement("div");
455:     div.className = "msg asst";
456:     div.textContent = `Error: ${e.message}`;
457:     $("msgs").appendChild(div);
458:   }
459:   $("sendbtn").disabled = false;
460:   setBusy(false);
461: }
462: $("sendbtn").onclick = send;
463: $("chat-in").addEventListener("keydown", (e) => {
464:   if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
465: });
466: $("chat-in").addEventListener("input", (e) => {
467:   e.target.style.height = "auto";
468:   e.target.style.height = Math.min(130, e.target.scrollHeight) + "px";
469: });
470: // ---- attachment inputs: picker button + clipboard paste + drag-drop ----
471: $("attachbtn").onclick = () => $("filepick").click();
472: $("filepick").addEventListener("change", (e) => {
473:   addFiles(e.target.files);
474:   e.target.value = ""; // allow re-picking the same file
475: });
476: $("chat-in").addEventListener("paste", (e) => {
477:   const files = [...(e.clipboardData?.files || [])];
478:   if (files.length) { e.preventDefault(); addFiles(files); }
479: });
480: $("composer").addEventListener("dragover", (e) => e.preventDefault());
481: $("composer").addEventListener("drop", (e) => {
482:   e.preventDefault();
483:   const files = [...(e.dataTransfer?.files || [])];
484:   if (files.length) addFiles(files);
485: });
486: $("newchat").onclick = async () => {
487:   await store.set({ session: "" });
488:   $("msgs").innerHTML = "";
489:   loadHist();
490:   refreshMeter();
491: };
492: 
493: // ---------- overlays ----------
494: function toggleOverlay(id, force) {
495:   const el = $(id);
496:   const show = force !== undefined ? force : !el.classList.contains("open");
497:   document.querySelectorAll(".overlay.open").forEach((o) => o.classList.remove("open"));
498:   if (show) el.classList.add("open");
499: }
500: $("menu-btn").onclick = (e) => { e.stopPropagation(); toggleOverlay("menu"); };
501: $("hist-btn").onclick = (e) => { e.stopPropagation(); toggleOverlay("hist-menu"); loadHist(); };
502: $("hist-x").onclick = (e) => { e.stopPropagation(); toggleOverlay("hist-menu", false); };
503: $("hist-new").onclick = (e) => { e.stopPropagation(); toggleOverlay("hist-menu", false); $("newchat").onclick(); };
504: document.addEventListener("click", (e) => {
505:   if (!e.target.closest(".overlay") && !e.target.closest("#menu-btn") && !e.target.closest("#hist-btn"))
506:     document.querySelectorAll(".overlay.open").forEach((o) => o.classList.remove("open"));
507: });
508: 
509: // ---------- direct drive ----------
510: function sw(msg) {
511:   return new Promise((res) => chrome.runtime.sendMessage({ ...msg, _panel: true }, (r) => res(r)));
512: }
513: $("nav-go").onclick = async () => {
514:   const url = $("nav-url").value.trim();
515:   if (url) { setBusy(true); await sw({ type: "panel-nav", url }); setBusy(false); }
516: };
517: $("do-snap").onclick = async () => {
518:   setBusy(true);
519:   const r = await sw({ type: "panel-snap" });
520:   $("snap").textContent = r?.text?.slice(0, 3000) || "n/a";
521:   setBusy(false);
522: };
523: $("do-shot").onclick = async () => {
524:   setBusy(true);
525:   const r = await sw({ type: "panel-shot" });
526:   if (r?.data) {
527:     $("shot").src = "data:image/png;base64," + r.data;
528:     $("shot").style.display = "block";
529:   }
530:   setBusy(false);
531: };
532: 
533: // ---------- connect (elements optional — menu may not include them) ----------
534: async function refreshConnect() {
535:   const pend = $("pend"), browsers = $("browsers");
536:   if (!pend && !browsers) return;
537:   try {
538:     const p = await (await fetch(`${API}/pending-latest`)).json();
539:     const c = await store.get();
540:     if (pend) pend.innerHTML = p.status === "pending"
541:       ? `<button data-s="${esc(p.session)}" class="primary" style="width:100%">Accept ${esc(p.session)}</button>` : `<div class="small">No pending requests.</div>`;
542:     if (pend) pend.querySelectorAll("button").forEach((b) => (b.onclick = async () => {
543:       await fetch(`${API}/accept`, { method: "POST", headers: { "content-type": "application/json" },
544:         body: JSON.stringify({ session: b.dataset.s, browser: c.name }) });
545:       refreshConnect();
546:     }));
547:   } catch {}
548:   try {
549:     if (!browsers) return;
550:     const bs = await (await fetch(`${API}/browsers`)).json();
551:     browsers.textContent = "Registered: " + (bs.map((b) => b.name).join(", ") || "none");
552:   } catch {}
553: }
554: 
555: // ---------- rules + server ----------
556: async function refreshRules() {
557:   if (!$("stealth")) return;
558:   const n = (await store.get()).name;
559:   try {
560:     const rules = await (await fetch(`${API}/netrules/${encodeURIComponent(n)}`)).json();
561:     $("stealth").checked = !!rules.stealth;
562:     $("nimg").checked = (rules.block || []).includes("images");
563:   } catch {}
564: }
565: if ($("apply")) $("apply").onclick = async () => {
566:   const n = (await store.get()).name;
567:   await fetch(`${API}/netrules`, { method: "POST", headers: { "content-type": "application/json" },
568:     body: JSON.stringify({ browser: n, block: $("nimg").checked ? ["images", "media", "fonts"] : [], stealth: $("stealth").checked }) });
569:   $("netstat").textContent = "Applied.";
570: };
571: async function loadSrv() {
572:   const c = await store.get();
573: [CREDENTIAL-RELATED LINE OMITTED]
574:   if ($("bname-in")) $("bname-in").value = c.name || "";
575: }
576: $("srv-save").onclick = async () => {
577: [CREDENTIAL-RELATED LINE OMITTED]
578:   if ($("bname-in") && $("bname-in").value.trim()) {
579:     upd.name = $("bname-in").value.trim();
580:     const b = $("bname");
581:     if (b) b.textContent = `opencode · ${upd.name}`;
582:   }
583:   await store.set(upd);
584:   $("srv-stat").textContent = "Saved.";
585:   loadHist(); loadMsgs(); refreshMeter(); initDropdowns();
586: };
587: 
588: (async function init() {
589:   await loadSrv();
590:   initTips();
591:   const hs = $("hist-search");
592:   if (hs) hs.addEventListener("input", renderHist);
593:   try {
594:     const { panelAction } = await chrome.storage.local.get({ panelAction: "" });
595:     if (panelAction) {
596:       await chrome.storage.local.set({ panelAction: "" });
597:       setTimeout(() => $(panelAction === "shot" ? "do-shot" : "do-snap").click(), 400);
598:     }
599:   } catch {}
600:   try {
601:     const c = await store.get();
602:     const b = $("bname");
603:     if (b) b.textContent = `opencode · ${c.name}`;
604:   } catch {}
605:   await initLimit();
606:   // load chat content first so the panel is usable fast; model list resolves in background
607:   loadHist(); loadMsgs(); refreshMeter();
608:   await initDropdowns();
609:   loadHist(); loadMsgs(); refreshMeter();
610:   refreshConnect(); refreshRules();
611:   booted = true;
612:   try {
613:     const es = new EventSource(`${API}/events`);
614:     es.addEventListener("pending", refreshConnect);
615:     es.addEventListener("accepted", refreshConnect);
616:   } catch {}
617: })();
