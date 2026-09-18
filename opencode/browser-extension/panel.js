const API = "http://127.0.0.1:9225";
const $ = (id) => document.getElementById(id);
const store = {
  async get() {
    return chrome.storage.sync.get({
      name: "archlinux-1", srv: "http://127.0.0.1:4096",
      usr: "ucha", pwd: "6b6fse5vx5ba", agent: "build", model: "", session: "",
    });
  },
  set(o) { return chrome.storage.sync.set(o); },
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
function dropdown(id, options, value, onPick, tipFor) {
  const root = $(id);
  const btn = root.querySelector("button");
  const list = root.querySelector(".list");
  const render = (opts, val) => {
    const short = (val || opts[0] || "–").split("/").pop();
    btn.textContent = short;
    list.innerHTML = "";
    for (const o of opts) {
      const b = document.createElement("button");
      b.textContent = o.split("/").pop();
      if (tipFor) {
        const t = tipFor(o);
        if (t) b.dataset.tip = t;
      }
      if (o === val || o.split("/").pop() === String(val || "").split("/").pop()) b.classList.add("on");
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
    root.classList.toggle("open");
  };
  document.addEventListener("click", () => root.classList.remove("open"));
  render(options, value);
  return { render };
}
let ddAgent, ddModel;
let modelOpts = ["…"]; // loading placeholder until serve answers
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
const costTip = (o) => modelCosts[o] || modelCosts[String(o).split("/").pop()] || "";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function fetchModels() {
  const cfg = await api("/config");
  const set = new Set();
  if (cfg.model) set.add(cfg.model);
  for (const [pid, p] of Object.entries(cfg.provider || {}))
    for (const m of Object.keys(p.models || {})) set.add(`${pid}/${m}`);
  return { cfg, models: set.size ? [...set].slice(0, 40) : [""] };
}
async function reloadModels() {
  if (!ddModel) return false;
  for (let i = 0; i < 4; i++) {
    try {
      const { cfg, models } = await fetchModels();
      if (models.length > 1 || models[0]) {
        modelOpts = models;
        const cur = await store.get();
        if (!cur.model && cfg.model) await store.set({ model: cfg.model });
        const c = await store.get();
        ddModel.render(models, c.model);
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
  ddModel = dropdown("dd-model", modelOpts, c.model, (v) => store.set({ model: v }), costTip);
  await reloadModels();
  loadCosts().then(async () => {
    if (ddModel && Object.keys(modelCosts).length)
      ddModel.render(modelOpts, (await store.get()).model);
  });
  try {
    const ss = await api("/session");
    const seen = new Set(modelOpts.filter(Boolean));
    for (const s of ss) {
      const mid = s.model || s.modelID;
      if (mid && !seen.has(mid)) {
        seen.add(mid);
        if (seen.size > 40) break;
      }
    }
    if (seen.size > modelOpts.filter(Boolean).length) {
      modelOpts = [...seen];
      ddModel.render(modelOpts, (await store.get()).model);
    }
  } catch {}
}
// retry model load when opening an empty/still-loading list (serve may have been starting)
$("dd-model").querySelector("button").addEventListener("click", () => {
  if (modelOpts.length <= 1 && (!modelOpts[0] || modelOpts[0] === "…")) reloadModels();
}, true);

// ---------- context meter ----------
let ctxLimit = 1048576;
async function initLimit() {
  try {
    const cfg = await api("/config");
    for (const p of Object.values(cfg.provider || {}))
      for (const m of Object.values(p.models || {}))
        if (m?.limit?.context) ctxLimit = m.limit.context;
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
const dayOf = (ts) => {
  const d = new Date(ts || 0);
  const t = new Date();
  const day = (x) => x.toDateString();
  if (day(d) === day(t)) return "Today";
  const y = new Date(t - 864e5);
  if (day(d) === day(y)) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};
const fmtDT = (ts) => ts ? new Date(ts).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
function renderHist() {
  const q = ($("hist-search")?.value || "").toLowerCase();
  const box = $("hist");
  box.innerHTML = "";
  let lastDay = "";
  for (const s of histCache) {
    if (q && !(s.title || s.slug || "").toLowerCase().includes(q)) continue;
    const day = dayOf(s.time?.updated);
    if (day !== lastDay) {
      lastDay = day;
      const h = document.createElement("div");
      h.className = "small";
      h.style.cssText = "margin:8px 0 2px;font-weight:700";
      h.textContent = day;
      box.appendChild(h);
    }
    const b = document.createElement("button");
    const t = s.tokens || {};
    b.innerHTML = `${esc(s.title || s.slug)}<span class="t">${fmtDT(s.time?.updated)} · ${esc(s.agent || "")} · ${fmtT((t.input || 0) + (t.output || 0))} tok</span>`;
    (async () => {
      const c = await store.get();
      if (s.id === c.session) b.classList.add("on");
    })();
    b.onclick = async () => {
      await store.set({ session: s.id });
      toggleOverlay("hist-menu", false);
      loadMsgs();
      loadHist();
      refreshMeter();
    };
    box.appendChild(b);
  }
  if (!box.children.length) box.innerHTML = `<div class="small">No chats found.</div>`;
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
    for (const m of ms.slice(-40)) {
      const role = m.info?.role || "?";
      if (role !== "user" && role !== "assistant") continue;
      const div = document.createElement("div");
      div.className = `msg ${role === "user" ? "user" : "asst"}`;
      const t = m.info?.tokens;
      const when = fmtTime(m.info?.time?.created);
      const files = (m.parts || []).filter((p) => p.type === "file" && p.url);
      const text = (m.parts || []).map((p) => p.text || "").filter((s) => s.trim()).join("\n");
      if (!text && !files.length) continue;
      if (text) {
        const td = document.createElement("div");
        td.innerHTML = esc(text.replace(/\s+$/, "")).slice(0, 4000);
        div.appendChild(td);
      }
      for (const f of files) {
        // NOTE: message-list API returns file parts with url stripped
        // or as blob refs; render whatever we can (thumb or name chip).
        if ((f.mime || "").startsWith("image/") && f.url.startsWith("data:")) {
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
        toast(`Model ${c.model} not offered by this serve — using serve default.`);
        c.model = "";
      }
      if (toModelObj(c.model)) body.model = toModelObj(c.model);
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
    await api(`/session/${c.session}/message`, { method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ parts }) });
    loadMsgs();
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
  const files = [...(e.clipboardData?.files || [])];
  if (files.length) { e.preventDefault(); addFiles(files); }
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

// ---------- connect (elements optional — menu may not include them) ----------
async function refreshConnect() {
  const pend = $("pend"), browsers = $("browsers");
  if (!pend && !browsers) return;
  try {
    const p = await (await fetch(`${API}/pending-latest`)).json();
    const c = await store.get();
    if (pend) pend.innerHTML = p.status === "pending"
      ? `<button data-s="${esc(p.session)}" class="primary" style="width:100%">Accept ${esc(p.session)}</button>` : `<div class="small">No pending requests.</div>`;
    if (pend) pend.querySelectorAll("button").forEach((b) => (b.onclick = async () => {
      await fetch(`${API}/accept`, { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ session: b.dataset.s, browser: c.name }) });
      refreshConnect();
    }));
  } catch {}
  try {
    if (!browsers) return;
    const bs = await (await fetch(`${API}/browsers`)).json();
    browsers.textContent = "Registered: " + (bs.map((b) => b.name).join(", ") || "none");
  } catch {}
}

// ---------- rules + server ----------
async function refreshRules() {
  if (!$("stealth")) return;
  const n = (await store.get()).name;
  try {
    const rules = await (await fetch(`${API}/netrules/${encodeURIComponent(n)}`)).json();
    $("stealth").checked = !!rules.stealth;
    $("nimg").checked = (rules.block || []).includes("images");
  } catch {}
}
if ($("apply")) $("apply").onclick = async () => {
  const n = (await store.get()).name;
  await fetch(`${API}/netrules`, { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ browser: n, block: $("nimg").checked ? ["images", "media", "fonts"] : [], stealth: $("stealth").checked }) });
  $("netstat").textContent = "Applied.";
};
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

(async function init() {
  await loadSrv();
  initTips();
  const hs = $("hist-search");
  if (hs) hs.addEventListener("input", renderHist);
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
  refreshConnect(); refreshRules();
  booted = true;
  try {
    const es = new EventSource(`${API}/events`);
    es.addEventListener("pending", refreshConnect);
    es.addEventListener("accepted", refreshConnect);
  } catch {}
})();
