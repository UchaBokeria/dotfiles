// Registers this browser; opens the accept page for new requests;
// uploads full tab snapshots (incl. chrome:// pages the MCP can't see);
// groups opencode session tabs like Claude does.
importScripts("config.js", "perm.js", "cdp.js", "hub.js");

async function myName() {
  const l = await chrome.storage.local.get({ name: "" });
  if (l.name) return l.name;
  const s = await chrome.storage.sync.get({ name: "archlinux-1" });
  if (s.name && s.name !== "archlinux-1") {
    await chrome.storage.local.set({ name: s.name });
    return s.name;
  }
  return s.name;
}

async function register() {
  try {
    await fetch(`${API}/register`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: await myName() }),
    });
  } catch {}
}

async function snapshot() {
  try {
    const tabs = await chrome.tabs.query({});
    await fetch(`${API}/tabsnapshot`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        browser: await myName(),
        tabs: tabs.map((t) => ({ id: t.id, windowId: t.windowId, title: t.title, url: t.url, openerTabId: t.openerTabId ?? null })),
      }),
    });
  } catch {}
}

async function processGroups() {
  try {
    const name = await myName();
    const reqs = await (await fetch(`${API}/group-requests/${encodeURIComponent(name)}`)).json();
    const seen = (await chrome.storage.local.get({ grouped: [] })).grouped;
    for (const r of reqs) {
      if (seen.includes(r.requestId)) continue;
      const tabs = await chrome.tabs.query({});
      const ids = tabs.filter((t) => r.urls.includes(t.url)).map((t) => t.id).filter(Boolean);
      if (ids.length) {
        const gid = await chrome.tabs.group({ tabIds: ids });
        await chrome.tabGroups.update(gid, { title: r.title, color: r.color });
      }
      seen.push(r.requestId);
    }
    await chrome.storage.local.set({ grouped: seen.slice(-50) });
  } catch {}
}

async function checkPending() {
  try {
    const r = await (await fetch(`${API}/pending-latest`)).json();
    const has = r.status === "pending";
    await chrome.action.setBadgeText({ text: has ? "?" : "" });
    if (!has) return;
    const opts = await chrome.storage.local.get({ paired: false, autoAccept: false });
    if (opts.paired || opts.autoAccept) {
      try {
        await fetch(`${API}/accept`, { method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ session: r.session, browser: await myName() }) });
        chrome.notifications?.create(`opencode-auto-${r.session}`, {
          type: "basic",
          iconUrl: chrome.runtime.getURL("icon.png"),
          title: "opencode auto-connected",
          message: `Session ${r.session} accepted automatically.`,
        });
      } catch {}
      await chrome.action.setBadgeText({ text: "" });
      return;
    }
    await chrome.action.setBadgeBackgroundColor({ color: "#4285f4" });
    const opened = (await chrome.storage.local.get({ opened: [] })).opened;
    if (opened.includes(r.session)) return;
    opened.push(r.session);
    await chrome.storage.local.set({ opened: opened.slice(-20) });
    await chrome.tabs.create({ url: chrome.runtime.getURL(`accept.html?session=${encodeURIComponent(r.session)}`) });
    chrome.notifications?.create(`opencode-${r.session}`, {
      type: "basic",
      iconUrl: chrome.runtime.getURL("icon.png"),
      title: "opencode wants to connect",
      message: `Session ${r.session} — accept tab opened.`,
    });
  } catch {}
}

async function processMarks() {
  try {
    const name = await myName();
    const reqs = await (await fetch(`${API}/marks/${encodeURIComponent(name)}`)).json();
    const seen = (await chrome.storage.local.get({ marked: [] })).marked;
    for (const r of reqs) {
      if (seen.includes(r.requestId)) continue;
      const tabs = await chrome.tabs.query({});
      for (const t of tabs) {
        if (!r.urls.length || r.urls.includes(t.url)) {
          try {
            await chrome.scripting.executeScript({
              target: { tabId: t.id },
              func: (session) => {
                if (document.getElementById("opencode-mark")) return;
                const d = document.createElement("div");
                d.id = "opencode-mark";
                d.textContent = `opencode: ${session}`;
                d.style.cssText =
                  "position:fixed;top:8px;right:8px;z-index:2147483647;background:#1a73e8;color:#fff;font:12px sans-serif;padding:4px 10px;border-radius:10px;pointer-events:none";
                (document.body || document.documentElement).appendChild(d);
              },
              args: [r.session || "working"],
            });
          } catch {}
        }
      }
      seen.push(r.requestId);
    }
    await chrome.storage.local.set({ marked: seen.slice(-50) });
  } catch {}
}

function stealthHeaders() {
  const ua = navigator.userAgent;
  const major = ua.match(/Chrome\/(\d+)/)?.[1] || "150";
  return {
    "User-Agent": ua,
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-CH-UA": `"Chromium";v="${major}", "Google Chrome";v="${major}", "Not-A.Brand";v="99"`,
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": `"Linux"`,
  };
}

async function applyNetRules() {
  try {
    const name = await myName();
    const rules = await (await fetch(`${API}/netrules/${encodeURIComponent(name)}`)).json();
    const dyn = [];
    let i = 1;
    for (const kind of rules.block || []) {
      const rt =
        kind === "images" ? ["image"] : kind === "media" ? ["media", "object"] : kind === "fonts" ? ["font"] : ["image", "media", "font"];
      dyn.push({ id: i++, priority: 1, action: { type: "block" }, condition: { resourceTypes: rt } });
    }
    if (rules.stealth) {
      const requestHeaders = Object.entries(stealthHeaders()).map(([header, value]) => ({
        header,
        operation: "set",
        value,
      }));
      dyn.push({
        id: 100,
        priority: 1,
        action: { type: "modifyHeaders", requestHeaders },
        condition: { urlFilter: "*", resourceTypes: ["main_frame", "sub_frame", "xmlhttprequest"] },
      });
    }
    const old = await chrome.declarativeNetRequest.getSessionRules();
    await chrome.declarativeNetRequest.updateSessionRules({
      removeRuleIds: old.map((r) => r.id),
      addRules: dyn,
    });
  } catch {}
}

async function uploadA11y() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (!tab?.id || !/^https?:/.test(tab.url || "")) return;
    const tree = await chrome.tabs.sendMessage(tab.id, { type: "opencode-a11y" }).catch(() => null);
    if (!tree) return;
    await fetch(`${API}/a11y`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ browser: await myName(), url: tree.url, tree: tree.nodes }),
    });
  } catch {}
}

async function watchReply() {
  try {
    const o = await chrome.storage.local.get({ notifyReply: false, panelHeartbeat: 0, srv: "", usr: "", pwd: "", session: "", watchNotified: {} });
    if (!o.notifyReply || !o.srv || !o.session) return;
    if (Date.now() - (o.panelHeartbeat || 0) < 25000) return; // panel open, user sees it live
    const base = o.srv.replace(/\/$/, "");
    const headers = o.pwd ? { Authorization: "Basic " + btoa(`${o.usr}:${o.pwd}`) } : {};
    const r = await fetch(base + `/session/${o.session}/message`, { headers });
    if (!r.ok) return;
    const ms = await r.json();
    const last = ms.filter((m) => (m.info?.role || "") === "assistant").pop();
    if (!last?.info?.time?.completed) return;
    const txt = (last.parts || []).map((p) => p.text || "").join("").trim();
    const key = `${last.info.time.completed}:${txt.length}`;
    if (!o.watchNotified[o.session]) {
      o.watchNotified[o.session] = key;
      await chrome.storage.local.set({ watchNotified: o.watchNotified });
      return; // baseline, don't notify for history
    }
    if (o.watchNotified[o.session] === key) return;
    o.watchNotified[o.session] = key;
    await chrome.storage.local.set({ watchNotified: o.watchNotified });
    chrome.notifications?.create(`opencode-reply-${o.session}-${Date.now()}`, {
      type: "basic",
      iconUrl: chrome.runtime.getURL("icon.png"),
      title: "opencode reply ready",
      message: txt.slice(0, 150) || "Assistant finished.",
    });
  } catch {}
}

async function permNotice() {
  try {
    const o = await chrome.storage.local.get({ permNotices: [], permNotified: {} });
    if (!o.permNotices.length) return;
    const item = o.permNotices.shift();
    await chrome.storage.local.set({ permNotices: o.permNotices });
    if (o.permNotified[item.domain]) return;
    o.permNotified[item.domain] = 1;
    await chrome.storage.local.set({ permNotified: o.permNotified });
    const p = await permGet();
    const denyAll = p.mode === "deny";
    const allowed = denyAll ? permMatch(p.allow, item.domain) : !permMatch(p.deny, item.domain);
    chrome.notifications?.create(`opencode-perm-${item.domain}`, {
      type: "basic",
      iconUrl: chrome.runtime.getURL("icon.png"),
      title: `opencode ${allowed ? "using" : "blocked on"} ${item.domain}`,
      message: denyAll
        ? (allowed ? "On your allowlist." : "Blocked by deny-all. Allow it?")
        : (allowed ? "First visit — allowed by default." : "On your deny list."),
      buttons: denyAll ? [{ title: "Always allow" }, { title: "Keep blocked" }] : [{ title: "Deny site" }, { title: "Keep allowing" }],
    });
  } catch {}
}

async function tick() {
  await checkPending();
  await snapshot();
  await processGroups();
  await processMarks();
  await applyNetRules();
  await uploadA11y();
  await watchReply();
  await permNotice();
}

async function ensureOffscreen() {
  try {
    if (await chrome.offscreen.hasDocument?.()) return;
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["DOM_SCRAPING"],
      justification: "Keepalive pings for opencode bridge sessions",
    });
  } catch {}
}

chrome.runtime.onMessage.addListener((msg, sender, send) => {
  if (msg?.type === "accept-done" && sender.tab?.id) {
    setTimeout(() => chrome.tabs.remove(sender.tab.id).catch(() => {}), 1500);
  }
  if (msg?._panel) {
    (async () => {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (!tab?.id) return send({ error: "no active tab" });
      const name = await myName();
      if (msg.type === "panel-nav") {
        await chrome.tabs.update(tab.id, { url: msg.url });
        return send({ ok: true });
      }
      if (msg.type === "panel-snap") {
        const r = await chrome.tabs.sendMessage(tab.id, { type: "opencode-a11y" }).catch(() => null);
        return send({ text: r ? r.nodes.slice(0, 60).map((n) => `${n.tag} ${n.name}`.trim()).join("\n") : "n/a" });
      }
      if (msg.type === "panel-shot") {
        await cdpAttach(tab.id, "panel");
        const r = await chrome.debugger.sendCommand({ tabId: tab.id }, "Page.captureScreenshot", { format: "png" });
        return send({ data: r.data });
      }
      send({ error: "unknown" });
    })();
    return true;
  }
  if (msg?.type === "keepalive") return true;
  return false;
});

chrome.runtime.onInstalled.addListener(() => { register(); snapshot(); ensureOffscreen(); });
chrome.runtime.onStartup.addListener(() => { register(); snapshot(); ensureOffscreen(); });
chrome.storage.onChanged.addListener((changes, area) => {
  if ((area === "sync" && changes.name) || (area === "local" && (changes.paired || changes.autoAccept))) {
    register();
    hubConnect();
  }
});
try {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
} catch {}
chrome.alarms.onAlarm.addListener(tick);
chrome.alarms.get("tick").then((a) => { if (!a) chrome.alarms.create("tick", { periodInMinutes: 0.5 }); });
chrome.notifications?.onClicked.addListener(async (nid) => {
  if (/^opencode-(reply|perm)-/.test(String(nid || ""))) {
    try {
      const w = await chrome.windows.getCurrent();
      if (w?.id !== undefined) await chrome.sidePanel.open({ windowId: w.id });
    } catch {}
  }
});
chrome.notifications?.onButtonClicked.addListener(async (nid, btn) => {
  try {
    if (!String(nid || "").startsWith("opencode-perm-")) return;
    const domain = String(nid).slice("opencode-perm-".length);
    const p = await permGet();
    if (p.mode === "deny") {
      if (btn === 0 && !p.allow.includes(domain)) p.allow.push(domain); // Always allow
    } else {
      if (btn === 0 && !p.deny.includes(domain)) p.deny.push(domain); // Deny site
    }
    await permSet(p);
  } catch {}
});
register();
tick();
hubConnect();
