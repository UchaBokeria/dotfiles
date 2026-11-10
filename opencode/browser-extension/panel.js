const $ = (id) => document.getElementById(id);
const DEFAULTS = { name: "archlinux-1", srv: "http://127.0.0.1:4096", usr: "ucha", pwd: "", agent: "build", model: "", effort: "auto", session: "" };
const store = {
  async get() {
    const local = await chrome.storage.local.get(DEFAULTS);
    const old = await chrome.storage.sync.get({ name: "", srv: "", usr: "", pwd: "" });
    if (old.name || old.srv || old.usr || old.pwd) {
      const merged = { ...local, name: old.name || local.name, srv: old.srv || local.srv,
        usr: old.usr || local.usr, pwd: old.pwd || local.pwd };
      await chrome.storage.local.set(merged);
      await chrome.storage.sync.remove(["name", "srv", "usr", "pwd"]);
      return merged;
    }
    return local;
  },
  set(o) { return chrome.storage.local.set(o); },
};
const auth = (c) => (c.pwd ? { Authorization: "Basic " + btoa(`${c.usr}:${c.pwd}`) } : {});
async function api(path, opts = {}) {
  const c = await store.get();
  const r = await fetch(c.srv.replace(/\/$/, "") + path, {
    ...opts,
    headers: { ...(opts.headers || {}), ...auth(c) },
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`server ${r.status} on ${path}: ${text.slice(0, 160) || r.statusText} (check ⋯ → Server login)`);
  return text ? JSON.parse(text) : null;
}
const esc = (s) => String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
// hover copy button for any rendered message (user + assistant).
// Button lives UNDER the bubble inside a .msgwrap that reserves its slot,
// so showing it never moves layout (absolute, out of flow).
// classic overlapping-rectangles copy icon with the brand gradient stroke
const COPY_SVG = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><defs><linearGradient id="cpg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1a73e8"/><stop offset="1" stop-color="#7b5cff"/></linearGradient></defs><rect x="9" y="9" width="12" height="12" rx="2" stroke="url(#cpg)"/><path d="M5 15V5a2 2 0 0 1 2-2h10" stroke="url(#cpg)"/></svg>`;
const PENCIL_SVG = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>`;
const TRASH_SVG = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>`;
function addCopy(div, text) {
  if (!text || !text.trim()) return;
  const w = document.createElement("div");
  w.className = "msgwrap " + (div.classList.contains("user") ? "u" : "a");
  div.before(w);
  w.appendChild(div);
  const b = document.createElement("button");
  b.className = "copybelow";
  b.innerHTML = COPY_SVG;
  b.onclick = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      b.innerHTML = `<span style="font-size:16px;line-height:1">✓</span>`;
    } catch { b.textContent = "!"; }
    setTimeout(() => { b.innerHTML = COPY_SVG; }, 1000);
  };
  w.appendChild(b);
}
// ---------- custom tooltips (dark card; [data-tip] only, never send/copy) ----------
function initTips() {
  let tip = $("tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "tip";
    document.body.appendChild(tip);
  }
  let t = null;
  const hide = () => { tip.classList.remove("on"); if (t) { clearTimeout(t); t = null; } };
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest("[data-tip]");
    if (!el) return;
    hide();
    t = setTimeout(() => {
      tip.textContent = el.dataset.tip;
      const r = el.getBoundingClientRect();
      tip.style.visibility = "hidden";
      tip.classList.add("on");
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      let x = Math.min(Math.max(6, r.left), innerWidth - tw - 6);
      let y = r.bottom + 6;
      if (y + th > innerHeight - 6) y = Math.max(6, r.top - th - 6);
      tip.style.left = `${x}px`;
      tip.style.top = `${y}px`;
      tip.style.visibility = "";
    }, 120);
  });
  document.addEventListener("mouseout", (e) => {
    if (e.target.closest && e.target.closest("[data-tip]")) hide();
  });
  document.addEventListener("click", hide, true);
}
const fmtT = (n) => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n ?? 0);
// exact cost, no rounding: full value, tiny amounts in exponent form instead of $0.00
const exactCost = (c) => {
  const v = c ?? 0;
  if (v !== 0 && Math.abs(v) < 0.01) return v.toExponential(1);
  return String(Math.round(v * 1e6) / 1e6);
};
const fmtTime = (ts) => ts ? new Date(ts).toTimeString().slice(0, 5) : "";

// ---------- busy dot ----------
function setBusy(b) {
  $("dot").classList.toggle("busy", !!b);
}

// ---------- custom dropdowns ----------
// labelFor maps "provider/model" -> "model · nick" using the provider's
// display name (e.g. meta-lucky/muse-spark-1.3 -> "muse-spark-1.3 · lucky"),
// so all four accounts stay distinguishable. Pass null for the plain agent list.
let labelFor = (o) => o;
function dropdown(id, options, value, onPick, tipFor) {
  const root = $(id);
  const btn = root.querySelector("button");
  const list = root.querySelector(".list");
  const render = (opts, val) => {
    btn.textContent = labelFor(val || opts[0] || "–");
    list.innerHTML = "";
    for (const o of opts) {
      const b = document.createElement("button");
      b.textContent = labelFor(o);
      b.dataset.raw = o;
      if (tipFor) {
        const t = tipFor(o);
        if (t) b.dataset.tip = t;
      }
      if (o === val) b.classList.add("on");
      b.onclick = (e) => {
        e.stopPropagation();
        root.classList.remove("open");
        onPick(o);
        render(opts, o);
      };
      list.appendChild(b);
    }
  };
  btn.onclick = (e) => {
    e.stopPropagation();
    document.querySelectorAll(".dd.open").forEach((d) => d !== root && d.classList.remove("open"));
    try { if (typeof modelClose === "function") modelClose(); } catch {}
    root.classList.toggle("open");
    if (root.classList.contains("open")) {
      const l = root.querySelector(".list");
      if (l) { l.scrollLeft = 0; l.scrollTop = 0; }
    }
  };
  document.addEventListener("click", () => root.classList.remove("open"));
  render(options, value);
  return { render };
}
let ddAgent;
let modelOpts = ["…"]; // loading placeholder until serve answers
// custom model popup: fixed-position sheet pinned to composer width.
// Fixed (not absolute) escapes the ancestor clipping that cut long labels.
function modelRender(models, value) {
  const btn = document.querySelector("#dd-model > button");
  const list = document.querySelector("#dd-model .list");
  if (!btn || !list) return;
  btn.textContent = labelFor(value || models[0] || "–");
  list.innerHTML = "";
  const si = document.createElement("input");
  si.className = "msearch";
  si.placeholder = "Search models…";
  si.value = modelSearchQ;
  si.addEventListener("input", () => { modelSearchQ = si.value; applyModelFilter(); });
  list.appendChild(si);
  const mkItem = (o) => {
    const b = document.createElement("button");
    const si = String(o).indexOf("/");
    const spid = si > 0 ? String(o).slice(0, si) : "", smid = si > 0 ? String(o).slice(si + 1) : String(o);
    const snick = (provNames[spid] || spid).split(/[\s-]+/).pop();
    const t1 = document.createElement("div");
    t1.className = "mname";
    t1.textContent = smid;
    const t2 = document.createElement("div");
    t2.className = "mnick";
    t2.textContent = snick;
    b.append(t1, t2);
    const t = costTip(o);
    if (t) b.dataset.tip = t;
    if (o === value) b.classList.add("on");
    b.onclick = async (e) => {
      e.stopPropagation();
      await store.set({ model: o });
      modelClose();
      modelRender(models, o);
      refreshEffort();
    };
    return b;
  };
  let lastPid = "";
  for (const o of models) {
    const si = String(o).indexOf("/");
    const pid = si > 0 ? String(o).slice(0, si) : "";
    if (pid && pid !== lastPid) {
      lastPid = pid;
      const h = document.createElement("div");
      h.className = "mgroup";
      h.textContent = pid;
      list.appendChild(h);
    }
    list.appendChild(mkItem(o));
  }
  if (value && !models.includes(value)) {
    list.appendChild(mkItem(value));
  }
  applyModelFilter();
}
let modelSearchQ = "";
function applyModelFilter() {
  const list = document.querySelector("#dd-model .list");
  if (!list) return;
  const q = (modelSearchQ || "").toLowerCase().trim();
  for (const b of list.querySelectorAll(":scope > button")) {
    b.style.display = (!q || (b.textContent || "").toLowerCase().includes(q)) ? "" : "none";
  }
  let curH = null, curVisible = 0;
  const flush = () => { if (curH) curH.style.display = curVisible ? "" : "none"; };
  for (const el of [...list.children]) {
    if (el.classList.contains("msearch")) continue;
    if (el.classList.contains("mgroup")) { flush(); curH = el; curVisible = 0; }
    else if (el.tagName === "BUTTON" && el.style.display !== "none") curVisible++;
  }
  flush();
}
function modelOpen() {
  const list = document.querySelector("#dd-model .list");
  document.querySelectorAll(".dd.open").forEach((d) => d.classList.remove("open"));
  const box = document.querySelector("#composer .box").getBoundingClientRect();
  list.style.left = `${Math.max(6, box.left + 8)}px`;
  list.style.right = `${Math.max(6, window.innerWidth - box.right + 8)}px`;
  list.style.bottom = `${Math.max(6, window.innerHeight - box.top + 8)}px`;
  list.style.top = "auto";
  try { if (!list.matches(":popover-open")) list.showPopover(); } catch {}
  list.scrollLeft = 0; list.scrollTop = 0;
}
function modelClose() {
  const list = document.querySelector("#dd-model .list");
  try { if (list && list.matches(":popover-open")) list.hidePopover(); } catch {}
}
document.querySelector("#dd-model > button").onclick = (e) => {
  e.stopPropagation();
  const list = document.querySelector("#dd-model .list");
  if (list.matches(":popover-open")) { modelClose(); return; }
  document.querySelectorAll(".dd.open").forEach((d) => d.classList.remove("open"));
  maybeRefreshModels();
  if (modelOpts.length <= 1 && (!modelOpts[0] || modelOpts[0] === "…")) {
    reloadModels().then(() => modelOpen());
  } else {
    modelOpen();
  }
};
// light-dismiss closes the popover on outside click automatically;
// no manual document closer needed (and it would fight the popover).
// re-fetch when stale so opencode.json adds/removes/updates appear once the serve restarts
let refreshing = false;
async function maybeRefreshModels() {
  if (refreshing || Date.now() - lastCfgFetch < 10000) return;
  refreshing = true;
  try { await reloadModels(); } catch {}
  refreshing = false;
}
document.addEventListener("visibilitychange", () => { if (!document.hidden) maybeRefreshModels(); });
let modelCosts = {}; // "provider/id" -> "$X in · $Y out /1M"
async function loadCosts() {
  try {
    const pr = await api("/provider");
    const list = pr.all || pr.providers || [];
    for (const p of list) for (const [mid, m] of Object.entries(p.models || {})) {
      const c = m && m.cost;
      if (!c || c.input == null) continue;
      const s = `$${c.input} in · $${c.output} out /1M`;
      modelCosts[mid] = s;
      modelCosts[String(mid).split("/").pop()] = s;
    }
  } catch {}
}
const costTip = (o) => modelCosts[o] || "";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// provider display names for nickname labels, e.g. "Meta Model API - lucky" -> "lucky"
let provNames = {};
let modelVariants = {}; // "provider/id" -> ["minimal","low",...] (reasoning variants the model offers)
let modelModalities = {}; // "provider/id" -> ["text","image",...] (input modalities)
let modelLimits = {}; // "provider/id" -> context token limit
let lastCfgFetch = 0;
async function fetchModels() {
  const cfg = await api("/config");
  lastCfgFetch = Date.now();
  const set = new Set();
  if (cfg.model) set.add(cfg.model);
  for (const [pid, p] of Object.entries(cfg.provider || {})) {
    if (p.name) provNames[pid] = p.name;
    for (const [mid, md] of Object.entries(p.models || {})) {
      const key = `${pid}/${mid}`;
      set.add(key);
      modelVariants[key] = Object.keys(md?.variants || {});
      modelModalities[key] = (md?.modalities?.input || []).slice();
      if (md?.limit?.context) modelLimits[key] = md.limit.context;
    }
  }
  // label "provider/model" as "model · nick" (nick = last word of provider name)
  labelFor = (o) => {
    const s = String(o || "");
    const i = s.indexOf("/");
    if (i <= 0) return s || "–";
    const pid = s.slice(0, i), mid = s.slice(i + 1);
    const nick = (provNames[pid] || pid).split(/[\s-]+/).pop();
    return `${mid} · ${nick}`;
  };
  return { cfg, models: set.size ? [...set].slice(0, 60) : [""] };
}
async function reloadModels() {
  for (let i = 0; i < 4; i++) {
    try {
      const { cfg, models } = await fetchModels();
      if (models.length > 1 || models[0]) {
        modelOpts = models;
        const cur = await store.get();
        if (!cur.model && cfg.model) await store.set({ model: cfg.model });
        const c = await store.get();
        if (c.model && !models.includes(c.model)) {
          toast(`Model ${labelFor(c.model)} no longer offered — using serve default.`);
          await store.set({ model: "" });
        }
        modelRender(models, (await store.get()).model);
        refreshEffort();
        return true;
      }
    } catch {}
    await sleep(1500);
  }
  return false;
}
async function initDropdowns() {
  const c = await store.get();
  ddAgent = dropdown("dd-agent", ["build", "ask", "plan"], c.agent, (v) => store.set({ agent: v }));
  modelRender(modelOpts, c.model);
  initEffort();
  await reloadModels();
  loadCosts().then(async () => {
    if (Object.keys(modelCosts).length)
      modelRender(modelOpts, (await store.get()).model);
  });

}


// ---------- effort (variant) ----------
let ddEffort;
// effort options follow the SELECTED model — variants differ per model
// (gpt offers "none", muse offers "minimal", only some offer "max", some offer none)
const effortFor = (model) => ["auto", ...(modelVariants[model] || [])];
function refreshEffort() {
  store.get().then((c) => {
    const opts = effortFor(c.model);
    let eff = c.effort || "auto";
    if (!opts.includes(eff)) {
      eff = "auto";
      store.set({ effort: eff });
    }
    if (ddEffort) ddEffort.render(opts, eff);
  });
}
function initEffort() {
  ddEffort = dropdown("dd-effort", ["auto"], "auto", (v) => store.set({ effort: v }));
  refreshEffort();
}

// ---------- context meter ----------
let ctxLimit = 1048576;
async function initLimit() {
  try {
    const cfg = await api("/config");
    let mx = 0;
    for (const p of Object.values(cfg.provider || {}))
      for (const m of Object.values(p.models || {}))
        if (m?.limit?.context) mx = Math.max(mx, m.limit.context);
    if (mx) ctxLimit = mx;
  } catch {}
}
async function refreshMeter() {
  try {
    const c = await store.get();
    if (!c.session) {
      $("ctx-tokens").textContent = "no chat";
      $("ctx-pct").textContent = "–";
      $("ctx-cost").textContent = "$0.00";
      $("ctxfill").style.width = "0%";
      return;
    }
    const ss = await api("/session");
    const s = ss.find((x) => x.id === c.session);
    if (!s) return;
    // use the session's (or selected) model limit — not an arbitrary last-seen one
    const sm = s.model || {};
    const skey = sm.id ? `${sm.providerID}/${sm.id}` : "";
    if (skey && modelLimits[skey]) ctxLimit = modelLimits[skey];
    else if (c.model && modelLimits[c.model]) ctxLimit = modelLimits[c.model];
    const t = s.tokens || {};
    const total = (t.input || 0) + (t.output || 0);
    const left = Math.max(0, ctxLimit - total);
    const pct = Math.min(100, (total / ctxLimit) * 100);
    $("ctx-tokens").innerHTML = `<b>ctx</b>${fmtT(total)} / ${fmtT(ctxLimit)}`;
    $("ctx-pct").innerHTML = `<b>left</b>${fmtT(left)} (${(100 - pct).toFixed(1)}%)`;
    $("ctx-cost").innerHTML = `<b>$</b>${exactCost(s.cost)}`;
    const fill = $("ctxfill");
    fill.style.width = `${pct}%`;
    $("ctx-pct").classList.toggle("hot", pct > 80);
  } catch {}
}

// ---------- chat ----------
let booted = false; // true once first full init finished; errors before that show "connecting…"
let histCache = [];
const relTime = (ts) => {
  if (!ts) return "";
  const d = new Date(ts), now = new Date();
  if (d.toDateString() === now.toDateString())
    return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const y = new Date(now - 864e5);
  if (d.toDateString() === y.toDateString()) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};
const dayLabel = (ts) => {
  if (!ts) return "Older";
  const d = new Date(ts), now = new Date();
  if (d.toDateString() === now.toDateString()) return "Today";
  const y = new Date(now - 864e5);
  if (d.toDateString() === y.toDateString()) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};
async function renderHist() {
  const q = ($("hist-search")?.value || "").toLowerCase();
  const box = $("hist");
  const curSess = (await store.get()).session;
  box.innerHTML = "";
  const groups = [];
  const byKey = new Map();
  for (const s of histCache) {
    if (q && !(s.title || s.slug || "").toLowerCase().includes(q)) continue;
    const ts = s.time?.updated || 0;
    const d = new Date(ts);
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
    let g = byKey.get(key);
    if (!g) {
      g = { label: dayLabel(ts), items: [] };
      byKey.set(key, g);
      groups.push(g);
    }
    g.items.push(s);
  }
  if (!groups.length) {
    const e = document.createElement("div");
    e.className = "small";
    e.textContent = "No chats found.";
    e.style.padding = "12px 4px";
    box.appendChild(e);
    return;
  }
  for (const g of groups) {
    const gd = document.createElement("div");
    gd.className = "daygroup";
    const hd = document.createElement("div");
    hd.className = "dayhead";
    const dl = document.createElement("span");
    dl.className = "dl";
    dl.textContent = g.label;
    const dc = document.createElement("span");
    dc.className = "dc";
    dc.textContent = `· ${g.items.length}`;
    const nav = document.createElement("span");
    nav.className = "dnav";
    const pv = document.createElement("button");
    pv.textContent = "‹";
    pv.dataset.tip = "Previous";
    const nx = document.createElement("button");
    nx.textContent = "›";
    nx.dataset.tip = "Next";
    nav.append(pv, nx);
    hd.append(dl, dc, nav);
    const track = document.createElement("div");
    track.className = "sess-list";
    for (const s of g.items) {
      const b = document.createElement("button");
      const t = s.tokens || {};
      const total = (t.input || 0) + (t.output || 0);
      b.innerHTML = `<span class="h-top"><span class="h-agent">${esc(s.agent || "build")}</span><span class="h-when">${esc(relTime(s.time?.updated))}</span></span><span class="rt">${esc(s.title || s.slug || "Untitled")}</span><span class="t">${total ? fmtT(total) + " tok" : "–"}</span>`;
      if (s.id === curSess) b.classList.add("on");
      b.onclick = async () => {
        await store.set({ session: s.id });
        toggleOverlay("hist-menu", false);
        loadMsgs();
        loadHist();
        refreshMeter();
      };
      const acts = document.createElement("span");
      acts.className = "sess-acts";
      const rn = document.createElement("button");
      rn.innerHTML = PENCIL_SVG;
      rn.title = "Rename";
      rn.dataset.tip = "Rename chat";
      rn.onclick = (e) => {
        e.stopPropagation();
        const rt = b.querySelector(".rt");
        if (!rt || b.querySelector(".sess-rename")) return;
        const inp = document.createElement("input");
        inp.className = "sess-rename";
        inp.value = s.title || s.slug || "";
        let done = false;
        const commit = async (save) => {
          if (done) return;
          done = true;
          const v = inp.value.trim();
          if (save && v && v !== (s.title || "")) {
            try {
              await api(`/session/${s.id}`, { method: "PATCH",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({ title: v }) });
              s.title = v;
            } catch (err) { toast(`Rename failed: ${err.message}`); }
          }
          loadHist();
        };
        inp.onkeydown = (ev) => {
          ev.stopPropagation();
          if (ev.key === "Enter") commit(true);
          if (ev.key === "Escape") commit(false);
        };
        inp.onblur = () => commit(true);
        rt.replaceWith(inp);
        inp.focus();
        inp.select();
      };
      const del = document.createElement("button");
      del.innerHTML = TRASH_SVG;
      del.title = "Delete";
      del.dataset.tip = "Delete chat";
      del.classList.add("danger");
      let armed = null;
      del.onclick = async (e) => {
        e.stopPropagation();
        if (!del.classList.contains("armed")) {
          del.classList.add("armed");
          del.textContent = "?";
          clearTimeout(armed);
          armed = setTimeout(() => { del.classList.remove("armed"); del.innerHTML = TRASH_SVG; }, 3000);
          return;
        }
        clearTimeout(armed);
        try {
          await api(`/session/${s.id}`, { method: "DELETE" });
          const cur = await store.get();
          if (cur.session === s.id) {
            await store.set({ session: "" });
            $("msgs").innerHTML = "";
          }
          toast(`Deleted “${s.title || s.slug || s.id}”.`);
          loadHist();
          refreshMeter();
        } catch (err) { toast(`Delete failed: ${err.message}`); }
      };
      acts.append(rn, del);
      b.appendChild(acts);
      track.appendChild(b);
    }
    pv.onclick = () => track.scrollBy({ left: -(track.clientWidth * 0.85), behavior: "smooth" });
    nx.onclick = () => track.scrollBy({ left: track.clientWidth * 0.85, behavior: "smooth" });
    gd.append(hd, track);
    box.appendChild(gd);
  }
}
async function loadHist() {
  try {
    const ss = await api("/session");
    ss.sort((a, b) => (b.time?.updated || 0) - (a.time?.updated || 0));
    histCache = ss.slice(0, 60);
    renderHist();
  } catch (e) {
    if (!booted) {
      // serve may still be starting — show connecting state and retry, not a scary error
      $("hist").innerHTML = `<div class="small">connecting…</div>`;
      setTimeout(() => { if (!booted) loadHist(); }, 2000);
    } else {
      $("hist").innerHTML = `<div class="small">${esc(e.message)}</div>`;
    }
  }
}
async function loadMsgs() {
  const c = await store.get();
  $("msgs").innerHTML = "";
  if (!c.session) return;
  try {
    const ms = await api(`/session/${c.session}/message`);
    const pendQ = await api(`/session/${c.session}/question`).then((r) => r.data || r).catch(() => []);
    for (const m of ms.slice(-40)) {
      const role = m.info?.role || "?";
      if (role !== "user" && role !== "assistant") continue;
      const div = document.createElement("div");
      div.className = `msg ${role === "user" ? "user" : "asst"}`;
      const t = m.info?.tokens;
      const when = fmtTime(m.info?.time?.created);
      const files = (m.parts || []).filter((p) => p.type === "file" && p.url);
      const text = (m.parts || []).map((p) => p.text || "").filter((s) => s.trim()).join("\n");
      const running = (m.parts || []).filter((p) => p.type === "tool" && p.state?.status === "running");
      if (!text && !files.length && !running.length) continue;
      if (text) {
        const td = document.createElement("div");
        td.innerHTML = esc(text.replace(/\s+$/, "").slice(0, 4000));
        div.appendChild(td);
      }
      if (!text && running.length) {
        const td = document.createElement("div");
        td.className = "small";
        td.textContent = `⏳ working… ${running.map((p) => p.tool || "tool").join(", ")}`;
        div.appendChild(td);
      }
      for (const f of files) {
        // NOTE: message-list API returns file parts with url stripped
        // or as blob refs; render whatever we can (thumb or name chip).
        if ((f.mime || "").startsWith("image/") && f.url?.startsWith("data:")) {
          const im = document.createElement("img");
          im.className = "thumb";
          im.src = f.url;
          div.appendChild(im);
        } else {
          const s = document.createElement("span");
          s.className = "filechip";
          s.textContent = `📄 ${f.filename || f.mime || "file"}`;
          div.appendChild(s);
        }
      }
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `${when}${when ? " · " : ""}${t ? `${fmtT((t.input || 0) + (t.output || 0))} tok` : ""}`;
      div.appendChild(meta);
      $("msgs").appendChild(div);
      addCopy(div, text);
    }
    // pending question-tool prompts: render with answer buttons (else the run
    // waits forever and the panel looks dead)
    for (const q of pendQ) {
      const qd = document.createElement("div");
      qd.className = "msg asst";
      for (const qq of q.questions || []) {
        const qt = document.createElement("div");
        qt.innerHTML = `<b>${esc(qq.header || "Question")}</b><br>${esc(qq.question || "")}`;
        qd.appendChild(qt);
        for (const o of qq.options || []) {
          const b = document.createElement("button");
          b.textContent = o.label;
          if (o.description) b.dataset.tip = o.description;
          b.style.cssText = "display:block;width:100%;text-align:left;margin-top:6px";
          b.onclick = async () => {
            b.disabled = true;
            try {
              await api(`/question/${q.id}/reply`, { method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({ answers: [[o.label]] }) });
              pollReply(c.session);
            } catch (e) {
              toast(`Answer failed: ${e.message}`);
              b.disabled = false;
            }
          };
          qd.appendChild(b);
        }
      }
      $("msgs").appendChild(qd);
    }
    $("msgs").scrollTop = 1e6;
  } catch {}
}
// ---- attachments (images, PDF, other files -> serve file parts) ----
const MAX_FILE = 20 * 1024 * 1024; // serve decodes max ~20MiB per item
let pending = []; // {name, mime, size, dataUrl}
function fmtSize(n) {
  if (n < 1024) return `${n}B`;
  if (n < 1048576) return `${(n / 1024).toFixed(0)}K`;
  return `${(n / 1048576).toFixed(1)}M`;
}
function readAsDataURL(f) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = () => rej(new Error(`cannot read ${f.name}`));
    r.readAsDataURL(f);
  });
}
function addFiles(files) {
  for (const f of files || []) {
    if (f.size > MAX_FILE) {
      const div = document.createElement("div");
      div.className = "msg asst";
      div.textContent = `Skipped ${f.name}: ${fmtSize(f.size)} exceeds the 20MB attachment limit.`;
      $("msgs").appendChild(div);
      continue;
    }
    readAsDataURL(f).then((dataUrl) => {
      pending.push({ name: f.name, mime: f.type || "application/octet-stream", size: f.size, dataUrl });
      renderTray();
    }).catch((e) => toast(e.message));
  }
}
function renderTray() {
  const t = $("tray");
  t.innerHTML = "";
  t.classList.toggle("on", pending.length > 0);
  pending.forEach((a, i) => {
    const c = document.createElement("div");
    c.className = "chip";
    const thumb = a.mime.startsWith("image/") ? `<img src="${a.dataUrl}" alt="">` : "📄";
    c.innerHTML = `${thumb}<span class="nm">${esc(a.name)}</span><span class="sz">${fmtSize(a.size)}</span>`;
    const x = document.createElement("button");
    x.className = "x";
    x.textContent = "×";
    x.dataset.tip = "Remove file";
    x.onclick = () => { pending.splice(i, 1); renderTray(); };
    c.appendChild(x);
    t.appendChild(c);
  });
}
function toast(msg) {
  const div = document.createElement("div");
  div.className = "msg asst";
  div.textContent = msg;
  $("msgs").appendChild(div);
  $("msgs").scrollTop = 1e6;
}
async function send() {
  const text = $("chat-in").value.trim();
  const files = pending;
  if (!text && !files.length) return;
  pending = [];
  renderTray();
  $("chat-in").value = "";
  $("chat-in").style.height = "auto";
  const d = document.createElement("div");
  d.className = "msg user";
  d.textContent = text || "";
  for (const a of files) {
    if (a.mime.startsWith("image/")) {
      const im = document.createElement("img");
      im.className = "thumb";
      im.src = a.dataUrl;
      d.appendChild(im);
    } else {
      const s = document.createElement("span");
      s.className = "filechip";
      s.textContent = `📄 ${a.name} (${fmtSize(a.size)})`;
      d.appendChild(s);
    }
  }
  if (!text && !files.length) { d.textContent = "(empty)"; }
  $("msgs").appendChild(d);
  addCopy(d, text);
  $("msgs").scrollTop = 1e6;
  $("sendbtn").disabled = true;
  setBusy(true);
  try {
    let c = await store.get();
    if (!c.session) {
      const body = {};
      if (c.agent && c.agent !== "build") body.agent = c.agent;
      // serve takes model as {id, providerID}, never a "provider/id" string (else 400)
      const toModelObj = (m) => {
        const s = String(m || "");
        const i = s.indexOf("/");
        return i > 0 ? { id: s.slice(i + 1), providerID: s.slice(0, i) } : null;
      };
      // drop a stored model the serve no longer offers (else 400 BadRequest)
      if (c.model && modelOpts.some(Boolean) && !modelOpts.includes(c.model)) {
        toast(`Model ${labelFor(c.model)} not offered by this serve — using serve default.`);
        c.model = "";
      }
      if (toModelObj(c.model)) {
        body.model = toModelObj(c.model);
        const eff = await store.get().then((x) => x.effort).catch(() => "auto");
        if (eff && eff !== "auto" && (modelVariants[c.model] || []).includes(eff)) body.model.variant = eff;
      }
      let s;
      try {
        s = await api("/session", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      } catch (e) {
        if (!/server 400/.test(e.message)) throw e;
        // stale model/agent convicted by serve: forget it, retry once with serve defaults
        await store.set({ model: "" });
        c = await store.get();
        toast(`Serve rejected session options (${e.message}) — cleared saved model, retrying with defaults.`);
        s = await api("/session", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
      }
      await store.set({ session: s.id });
      c = await store.get();
      loadHist();
    }
    const parts = [];
    for (const a of files) parts.push({ type: "file", mime: a.mime, filename: a.name, url: a.dataUrl });
    if (text) parts.push({ type: "text", text });
    const msgBody = { parts };
    // mid-session effort change: serve accepts top-level variant on message post
    const effNow = (await store.get().then((x) => x.effort).catch(() => "auto"));
    if (effNow && effNow !== "auto" && (!c.model || (modelVariants[c.model] || []).includes(effNow))) msgBody.variant = effNow;
    await api(`/session/${c.session}/message`, { method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(msgBody) });
    await pollReply(c.session); // re-read until the assistant text lands
    loadHist();
    refreshMeter();
  } catch (e) {
    const div = document.createElement("div");
    div.className = "msg asst";
    div.textContent = `Error: ${e.message}`;
    $("msgs").appendChild(div);
  }
  $("sendbtn").disabled = false;
  setBusy(false);
}
// live-tail the assistant reply: re-read messages every 2s until text stops
// growing (max ~5 min), so the answer streams into view instead of arriving
// only on the next manual refresh.
async function pollReply(sessionID, round = 0, prevLen = -1, still = 0) {
  const c = await store.get();
  if (c.session !== sessionID || round > 150) return;
  let ms;
  try {
    ms = await api(`/session/${sessionID}/message`);
  } catch { setTimeout(() => pollReply(sessionID, round + 1, prevLen, still), 4000); return; }
  const last = ms.filter((m) => (m.info?.role || "") === "assistant").pop();
  const done = !!(last?.info?.time?.completed);
  const busy = (last?.parts || []).some((p) => p.type === "tool" && p.state?.status === "running");
  const txt = (last?.parts || []).map((p) => p.text || "").join("").trim();
  await loadMsgs();
  if (done) return;
  // keep polling while tools run (even if text is stable) — but stop after
  // ~5 min regardless; the finished text arrives on next open/refresh
  const grew = (txt.length > prevLen || busy) ? 0 : still + 1;
  if (grew >= 3 && txt) return;
  setTimeout(() => pollReply(sessionID, round + 1, txt.length, grew), 2000);
}
$("sendbtn").onclick = send;
$("chat-in").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
$("chat-in").addEventListener("input", (e) => {
  e.target.style.height = "auto";
  e.target.style.height = Math.min(130, e.target.scrollHeight) + "px";
});
// ---- attachment inputs: picker button + clipboard paste + drag-drop ----
$("attachbtn").onclick = () => $("filepick").click();
$("filepick").addEventListener("change", (e) => {
  addFiles(e.target.files);
  e.target.value = ""; // allow re-picking the same file
});
$("chat-in").addEventListener("paste", (e) => {
  // clipboardData.files misses web-copied images — read items and use getAsFile
  const files = [];
  for (const it of [...(e.clipboardData?.items || [])]) {
    if (it.kind === "file") {
      const f = it.getAsFile();
      if (f) files.push(f);
    }
  }
  if (!files.length) files.push(...(e.clipboardData?.files || []));
  if (!files.length) return;
  e.preventDefault();
  addFiles(files);
  // warn if the selected model doesn't take this kind (image/pdf/...)
  store.get().then((c) => {
    const mods = modelModalities[c.model];
    if (!mods || !mods.length) return; // unknown model — don't nag
    for (const f of files) {
      const kind = (f.type || "").startsWith("image/") ? "image" : (f.type === "application/pdf" ? "pdf" : null);
      if (kind && !mods.includes(kind)) {
        toast(`${labelFor(c.model)} doesn't list ${kind} input (supports: ${mods.join(", ") || "text"}) — attached anyway, switch model if the serve rejects it.`);
        break;
      }
    }
  }).catch(() => {});
});
$("composer").addEventListener("dragover", (e) => e.preventDefault());
$("composer").addEventListener("drop", (e) => {
  e.preventDefault();
  const files = [...(e.dataTransfer?.files || [])];
  if (files.length) addFiles(files);
});
$("newchat").onclick = async () => {
  await store.set({ session: "" });
  $("msgs").innerHTML = "";
  loadHist();
  refreshMeter();
};

// ---------- overlays ----------
function toggleOverlay(id, force) {
  const el = $(id);
  const show = force !== undefined ? force : !el.classList.contains("open");
  document.querySelectorAll(".overlay.open").forEach((o) => o.classList.remove("open"));
  if (show) el.classList.add("open");
}
$("menu-btn").onclick = (e) => { e.stopPropagation(); toggleOverlay("menu"); };
$("hist-btn").onclick = (e) => { e.stopPropagation(); toggleOverlay("hist-menu"); loadHist(); };
$("hist-x").onclick = (e) => { e.stopPropagation(); toggleOverlay("hist-menu", false); };
$("hist-new").onclick = (e) => { e.stopPropagation(); toggleOverlay("hist-menu", false); $("newchat").onclick(); };
document.addEventListener("click", (e) => {
  if (!e.target.closest(".overlay") && !e.target.closest("#menu-btn") && !e.target.closest("#hist-btn"))
    document.querySelectorAll(".overlay.open").forEach((o) => o.classList.remove("open"));
});

// ---------- direct drive ----------
function sw(msg) {
  return new Promise((res) => chrome.runtime.sendMessage({ ...msg, _panel: true }, (r) => res(r)));
}
$("nav-go").onclick = async () => {
  const url = $("nav-url").value.trim();
  if (url) { setBusy(true); await sw({ type: "panel-nav", url }); setBusy(false); }
};
$("do-snap").onclick = async () => {
  setBusy(true);
  const r = await sw({ type: "panel-snap" });
  $("snap").textContent = r?.text?.slice(0, 3000) || "n/a";
  setBusy(false);
};
$("do-shot").onclick = async () => {
  setBusy(true);
  const r = await sw({ type: "panel-shot" });
  if (r?.data) {
    $("shot").src = "data:image/png;base64," + r.data;
    $("shot").style.display = "block";
  }
  setBusy(false);
};

// ---------- workflow recording ----------
async function recStatus() {
  try {
    const n = (await store.get()).name;
    const r = await (await fetch(`${API}/record/${encodeURIComponent(n)}/count`)).json();
    $("rec-stat").textContent = r.recording ? `● Recording… ${r.steps} step(s)` : `${r.steps || 0} step(s) saved.`;
    $("rec-toggle").textContent = r.recording ? "■ Stop" : "● Record";
  } catch {
    $("rec-stat").textContent = "Bridge unreachable.";
  }
}
$("rec-toggle").onclick = async () => {
  const n = (await store.get()).name;
  const cur = await (await fetch(`${API}/record/${encodeURIComponent(n)}/count`)).json().catch(() => ({ recording: false }));
  if (cur.recording) {
    await fetch(`${API}/record-flag`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ browser: n, recording: false }) });
  } else {
    await fetch(`${API}/record`, { method: "DELETE", headers: { "content-type": "application/json" }, body: JSON.stringify({ browser: n }) });
    await fetch(`${API}/record-flag`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ browser: n, recording: true }) });
  }
  recStatus();
};
$("rec-dl").onclick = async () => {
  const n = (await store.get()).name;
  const steps = await (await fetch(`${API}/record/${encodeURIComponent(n)}`)).json();
  const blob = new Blob([JSON.stringify(steps, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `opencode-workflow-${n}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
};
$("rec-copy").onclick = async () => {
  const n = (await store.get()).name;
  const steps = await (await fetch(`${API}/record/${encodeURIComponent(n)}`)).json();
  try {
    await navigator.clipboard.writeText(JSON.stringify(steps, null, 2));
    $("rec-stat").textContent = "Copied.";
  } catch {
    $("rec-stat").textContent = "Copy failed.";
  }
};
$("rec-clear").onclick = async () => {
  const n = (await store.get()).name;
  await fetch(`${API}/record`, { method: "DELETE", headers: { "content-type": "application/json" }, body: JSON.stringify({ browser: n }) });
  recStatus();
};
setInterval(() => { try { recStatus(); } catch {} }, 8000);

// ---------- server ----------
async function loadSrv() {
  const c = await store.get();
  $("srv").value = c.srv; $("usr").value = c.usr; $("pwd").value = c.pwd;
  if ($("bname-in")) $("bname-in").value = c.name || "";
}
$("srv-save").onclick = async () => {
  const upd = { srv: $("srv").value.trim(), usr: $("usr").value.trim(), pwd: $("pwd").value };
  if ($("bname-in") && $("bname-in").value.trim()) {
    upd.name = $("bname-in").value.trim();
    const b = $("bname");
    if (b) b.textContent = `opencode · ${upd.name}`;
  }
  await store.set(upd);
  $("srv-stat").textContent = "Saved.";
  loadHist(); loadMsgs(); refreshMeter(); initDropdowns();
};
$("srv-restart").onclick = async () => {
  const st = $("srv-restat");
  st.textContent = "Restarting…";
  try {
    const r = await (await fetch(`${API}/serve-restart`, { method: "POST" })).json();
    if (r.error) throw new Error(r.error);
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      try {
        await api("/config");
        await reloadModels();
        loadCosts();
        refreshEffort();
        refreshMeter();
        st.textContent = "Models refreshed.";
        return;
      } catch {}
    }
    st.textContent = "Serve didn't come back in 20s — check systemctl.";
  } catch (e) {
    st.textContent = `Restart failed: ${e.message}`;
  }
};

// ---------- permissions (deny list + deny-all mode) ----------
function normDomain(raw) {
  let s = String(raw || "").trim().toLowerCase();
  if (!s) return "";
  try {
    if (!/^[a-z][a-z0-9+.-]*:\/\//.test(s)) s = "https://" + s;
    s = new URL(s).hostname;
  } catch { return ""; }
  return s.replace(/^www\./, "");
}
async function renderPerm() {
  const p = await permGet();
  document.querySelectorAll("#perm-mode button").forEach((b) =>
    b.classList.toggle("on", b.dataset.m === (p.mode === "deny" ? "deny" : "allow")));
  const list = p.mode === "deny" ? p.allow : p.deny;
  const box = $("perm-chips");
  box.innerHTML = "";
  for (const d of list || []) {
    const c = document.createElement("span");
    c.className = "pchip";
    c.textContent = d;
    const x = document.createElement("button");
    x.textContent = "×";
    x.dataset.tip = "Remove";
    x.onclick = async () => {
      const q = await permGet();
      const L = q.mode === "deny" ? q.allow : q.deny;
      const i = L.indexOf(d);
      if (i >= 0) L.splice(i, 1);
      await permSet(q);
      renderPerm();
    };
    c.appendChild(x);
    box.appendChild(c);
  }
}
document.querySelectorAll("#perm-mode button").forEach((b) => (b.onclick = async () => {
  const p = await permGet();
  p.mode = b.dataset.m === "deny" ? "deny" : "allow";
  await permSet(p);
  renderPerm();
}));
$("perm-add").onclick = async () => {
  const d = normDomain($("perm-in").value);
  if (!d) return;
  $("perm-in").value = "";
  const p = await permGet();
  const L = p.mode === "deny" ? p.allow : p.deny;
  if (!L.includes(d)) L.push(d);
  await permSet(p);
  renderPerm();
};
$("perm-in").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); $("perm-add").click(); }
});

// ---------- connect options (one-time pairing + reply notifications) ----------
// Pairing mirrors Codex/Claude setup: one explicit gesture per browser, then
// sessions connect silently. Per-site permissions above still apply.
async function refreshPair() {
  const b = $("pair-btn"), st = $("pair-stat");
  if (!b) return;
  const o = await chrome.storage.local.get({ paired: false }).catch(() => ({}));
  if (o.paired) {
    b.textContent = "Unpair";
    b.classList.remove("primary");
    if (st) st.textContent = "Paired ✓ — sessions connect automatically.";
  } else {
    b.textContent = "Pair this browser";
    b.classList.add("primary");
    if (st) st.textContent = "";
  }
  b.dataset.armed = "";
}
{
  const pb = $("pair-btn");
  if (pb) pb.onclick = async () => {
    const o = await chrome.storage.local.get({ paired: false }).catch(() => ({}));
    if (o.paired) {
      await chrome.storage.local.set({ paired: false });
      await refreshPair();
      return;
    }
    if (pb.dataset.armed) {
      await chrome.storage.local.set({ paired: true, autoAccept: false });
      await refreshPair();
      toast("Browser paired — future sessions connect automatically.");
      return;
    }
    pb.dataset.armed = "1";
    pb.textContent = "Confirm pairing?";
    setTimeout(() => { if (pb.dataset.armed) { pb.dataset.armed = ""; refreshPair(); } }, 4000);
  };
}
(async function initConnectOpts() {
  try {
    const o = await chrome.storage.local.get({ notifyReply: false });
    if ($("opt-notify")) $("opt-notify").checked = !!o.notifyReply;
  } catch {}
  refreshPair();
})();
{
  const nt = $("opt-notify");
  if (nt) nt.onchange = (e) => chrome.storage.local.set({ notifyReply: e.target.checked });
}
// heartbeat so background skips reply notifications while the panel is open
try { chrome.storage.local.set({ panelHeartbeat: Date.now() }); } catch {}
setInterval(() => { try { chrome.storage.local.set({ panelHeartbeat: Date.now() }); } catch {} }, 10000);
renderPerm();

(async function init() {
  await loadSrv();
  initTips();
  const ver = $("ext-ver");
  if (ver) ver.textContent = `ext ${chrome.runtime.getManifest().version}`;
  const hs = $("hist-search");
  let histDeb = null;
  if (hs) hs.addEventListener("input", () => {
    clearTimeout(histDeb);
    histDeb = setTimeout(renderHist, 150);
  });
  try {
    const { panelAction } = await chrome.storage.local.get({ panelAction: "" });
    if (panelAction) {
      await chrome.storage.local.set({ panelAction: "" });
      setTimeout(() => $(panelAction === "shot" ? "do-shot" : "do-snap").click(), 400);
    }
  } catch {}
  try {
    const c = await store.get();
    const b = $("bname");
    if (b) b.textContent = `opencode · ${c.name}`;
  } catch {}
  await initLimit();
  // load chat content first so the panel is usable fast; model list resolves in background
  loadHist(); loadMsgs(); refreshMeter();
  await initDropdowns();
  loadHist(); loadMsgs(); refreshMeter();
  booted = true;
})();
