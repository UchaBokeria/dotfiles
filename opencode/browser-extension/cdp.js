// CDP driver core: the extension is the SOLE debugger on tabs it owns.
// Lazy attach per tab (Claude-style), detach after 25s idle.
const attached = new Map(); // tabId -> {session, lastUsed, buffers:{console:[],network:[]}}
const groups = new Map(); // session -> groupId

async function cdpAttach(tabId, session) {
  const cur = attached.get(tabId);
  if (cur?.attached) {
    cur.lastUsed = Date.now();
    cur.session = session || cur.session;
    return;
  }
  await chrome.debugger.attach({ tabId }, "1.3");
  const st = { attached: true, session, lastUsed: Date.now(), buffers: { console: [], network: [] } };
  attached.set(tabId, st);
  try {
    await chrome.debugger.sendCommand({ tabId }, "Page.enable");
    await chrome.debugger.sendCommand({ tabId }, "Runtime.enable");
    await chrome.debugger.sendCommand({ tabId }, "Network.enable", { maxPostDataSize: 65536 });
  } catch {}
}

// Working indicator (Claude-style edge fade + status pill). Shown for the whole
// driven run: every MCP action refreshes it, so it stays as long as work flows.
const fadeTimers = new Map(); // tabId -> timeout
const FADE_IDLE_MS = 30000;
const FADE_ACTIVE = new Set(["navigate", "click", "fill", "type", "press", "evaluate", "screenshot", "upload", "scroll", "hover", "select", "dialog", "wait"]);
async function showWorkFade(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        let f = document.getElementById("opencode-workfade");
        if (!f) {
          f = document.createElement("div");
          f.id = "opencode-workfade";
          f.style.cssText =
            "position:fixed;inset:0;z-index:2147483646;pointer-events:none;box-shadow:inset 0 0 220px rgba(26,115,232,.75), inset 0 0 60px rgba(26,115,232,.45)";
          const pill = document.createElement("div");
          pill.textContent = "opencode working";
          pill.style.cssText =
            "position:fixed;top:14px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,rgba(26,115,232,.28),rgba(123,92,255,.28));backdrop-filter:blur(14px) saturate(1.4);-webkit-backdrop-filter:blur(14px) saturate(1.4);color:rgba(255,255,255,.92);font:500 13px system-ui,sans-serif;padding:8px 20px;border-radius:999px;border:1px solid rgba(255,255,255,.22);box-shadow:0 8px 32px rgba(26,115,232,.25),inset 0 1px 0 rgba(255,255,255,.25);pointer-events:none;letter-spacing:.4px";
          f.appendChild(pill);
          (document.body || document.documentElement).appendChild(f);
        }
        f.style.display = "block";
      },
    });
  } catch {}
}
async function hideWorkFade(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        document.getElementById("opencode-workfade")?.remove();
        document.getElementById("opencode-cursor")?.remove();
      },
    });
  } catch {}
}
const lastCursor = new Map(); // tabId -> {x, y}
function touchFade(tabId) {
  showWorkFade(tabId);
  const pt = lastCursor.get(tabId);
  if (pt) showCursor(tabId, pt.x, pt.y);
  clearTimeout(fadeTimers.get(tabId));
  fadeTimers.set(tabId, setTimeout(() => hideWorkFade(tabId), FADE_IDLE_MS));
}

async function cdpDetachIdle() {
  const now = Date.now();
  for (const [tabId, st] of attached) {
    if (now - st.lastUsed > 25000) {
      try {
        await chrome.debugger.detach({ tabId });
      } catch {}
      attached.delete(tabId);
      clearTimeout(fadeTimers.get(tabId));
      fadeTimers.delete(tabId);
      hideWorkFade(tabId);
    }
  }
  sweepDialogs();
}
setInterval(cdpDetachIdle, 10000);

const pendingDialogs = new Map(); // tabId -> {type, message, defaultPrompt, at}
chrome.debugger.onEvent.addListener((src, method, params) => {
  const st = src.tabId !== undefined ? attached.get(src.tabId) : null;
  if (!st) return;
  st.lastUsed = Date.now();
  if (method === "Runtime.consoleAPICalled" || method === "Runtime.exceptionThrown") {
    st.buffers.console.push({ at: Date.now(), method, params });
    if (st.buffers.console.length > 200) st.buffers.console.shift();
  }
  if (method.startsWith("Network.")) {
    st.buffers.network.push({ at: Date.now(), method, params });
    if (st.buffers.network.length > 300) st.buffers.network.shift();
  }
  if (method === "Page.javascriptDialogOpening") {
    // explicit handling via cdp_dialog; auto-dismiss after 15s so pages never hang
    pendingDialogs.set(src.tabId, { type: params.type, message: params.message, defaultPrompt: params.defaultPrompt, at: Date.now() });
    st.buffers.console.push({ at: Date.now(), method: "Page.dialogOpened", params });
    if (st.buffers.console.length > 200) st.buffers.console.shift();
  }
  if (method === "Page.javascriptDialogClosed") {
    pendingDialogs.delete(src.tabId);
  }
});
function sweepDialogs() {
  const now = Date.now();
  for (const [tabId, d] of pendingDialogs) {
    if (now - d.at > 15000) {
      pendingDialogs.delete(tabId);
      chrome.debugger.sendCommand({ tabId }, "Page.handleJavaScriptDialog", { accept: false }).catch(() => {});
      const st = attached.get(tabId);
      st?.buffers.console.push({ at: now, method: "Page.dialogAutoDismissed", params: d });
    }
  }
}
chrome.debugger.onDetach.addListener((src) => attached.delete(src.tabId));

function checkDomain(session, url, write) {
  // Turn-scoped permission store (cocodem-inspired). Default allow; explicit denies win.
  return permCheck(session, url, write).then((ok) => {
    if (!ok) throw new Error(`denied by session policy: ${url}`);
  });
}

async function waitLoad(tabId, ms = 25000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const tab = await chrome.tabs.get(tabId).catch(() => null);
    if (tab && tab.status === "complete") return;
    await new Promise((r) => setTimeout(r, 300));
  }
}

async function showCursor(tabId, x, y) {
  lastCursor.set(tabId, { x, y });
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: (pt) => {
        let c = document.getElementById("opencode-cursor");
        if (!c) {
          c = document.createElement("div");
          c.id = "opencode-cursor";
          c.style.cssText =
            "position:fixed;z-index:2147483647;width:44px;height:44px;pointer-events:none;transition:left .18s ease-out,top .18s ease-out;filter:drop-shadow(0 2px 5px rgba(0,0,0,.55))";
        c.innerHTML =
          '<svg viewBox="0 0 22 22" width="44" height="44"><path d="M5 3 L5 17 L9.5 13.5 L12 19 L14.5 17.8 L12 12.5 L16.5 12 Z" fill="#1a73e8" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
        (document.body || document.documentElement).appendChild(c);
        }
        c.style.left = pt.x + window.scrollX + "px";
        c.style.top = pt.y + window.scrollY + "px";
        c.style.display = "block";
      },
      args: [{ x, y }],
    });
  } catch {}
}

async function cdpExec(method, p) {
  const session = p.session || "default";
  if (p.tabId && FADE_ACTIVE.has(method)) touchFade(p.tabId);
  if (method === "close_tab" && p.tabId) {
    clearTimeout(fadeTimers.get(p.tabId));
    fadeTimers.delete(p.tabId);
    hideWorkFade(p.tabId);
  }
  switch (method) {
    case "ping":
      return { ok: true, tabs: attached.size };
    case "tabs": {
      const tabs = await chrome.tabs.query(p.windowId ? { windowId: p.windowId } : {});
      return tabs.map((t) => ({ id: t.id, windowId: t.windowId, title: t.title, url: t.url, active: t.active, openerTabId: t.openerTabId ?? null }));
    }
    case "navigate": {
      await checkDomain(session, p.url, false);
      let tabId = p.tabId;
      if (!tabId) {
        const tab = await chrome.tabs.create({ url: p.url, active: false });
        tabId = tab.id;
      } else {
        await chrome.tabs.update(tabId, { url: p.url });
      }
      await waitLoad(tabId);
      if (p.group !== false) await groupTab(session, tabId);
      return { tabId };
    }
    case "snapshot": {
      const r = await chrome.tabs.sendMessage(p.tabId, { type: "opencode-a11y" }).catch(() => null);
      if (!r) throw new Error("no a11y host on tab (chrome:// pages excluded)");
      return r;
    }
    case "evaluate": {
      await checkDomain(session, p.url || "", true);
      await cdpAttach(p.tabId, session);
      const r = await chrome.debugger.sendCommand({ tabId: p.tabId }, "Runtime.evaluate", {
        expression: p.fn,
        returnByValue: true,
        awaitPromise: true,
      });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.text || "evaluate failed");
      return r.result?.value ?? null;
    }
    case "screenshot": {
      await cdpAttach(p.tabId, session);
      const r = await chrome.debugger.sendCommand({ tabId: p.tabId }, "Page.captureScreenshot", {
        format: p.format || "png",
      });
      return { data: r.data };
    }
    case "click": {
      await cdpAttach(p.tabId, session);
      const pt = await cdpExec("evaluate", { tabId: p.tabId, session, fn: `(() => { const el = document.querySelector(${JSON.stringify(p.selector)}); if (!el) return null; const r = el.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; })()` });
      if (!pt) throw new Error(`no match: ${p.selector}`);
      await showCursor(p.tabId, pt.x, pt.y);
      for (const t of ["mousePressed", "mouseReleased"]) {
        await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.dispatchMouseEvent", {
          type: t,
          x: pt.x,
          y: pt.y,
          button: "left",
          clickCount: 1,
        });
      }
      return { ok: true, at: pt };
    }
    case "fill":
    case "type": {
      await cdpAttach(p.tabId, session);
      await cdpExec("click", { tabId: p.tabId, session, selector: p.selector });
      if (method === "fill") {
        await cdpExec("evaluate", {
          tabId: p.tabId,
          session,
          fn: `(() => { const el = document.querySelector(${JSON.stringify(p.selector)}); if (el) { el.focus(); el.select?.(); document.execCommand('selectAll', false, null); } return !!el; })()`,
        });
      }
      await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.insertText", { text: p.text });
      return { ok: true };
    }
    case "press": {
      await cdpAttach(p.tabId, session);
      const key = p.key || "Enter";
      const code = key.length === 1 ? `Key${key.toUpperCase()}` : key;
      for (const t of ["keyDown", "keyUp"]) {
        await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.dispatchKeyEvent", {
          type: t,
          key,
          windowsVirtualKeyCode: key.length === 1 ? key.toUpperCase().charCodeAt(0) : undefined,
          code,
        });
      }
      return { ok: true };
    }
    case "scroll": {
      await checkDomain(session, p.url || "", false);
      if (!p.selector && p.dy === undefined && p.dx === undefined && p.x === undefined && p.y === undefined)
        throw new Error("scroll needs selector, x/y, or dx/dy");
      const sr = await chrome.scripting.executeScript({
        target: { tabId: p.tabId },
        func: (a) => {
          if (a.selector) {
            const el = document.querySelector(a.selector);
            if (!el) return false;
            el.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
            return true;
          }
          if (a.dy !== undefined || a.dx !== undefined) {
            window.scrollBy({ left: a.dx || 0, top: a.dy || 0, behavior: "instant" });
            return true;
          }
          window.scrollTo({ left: a.x || 0, top: a.y || 0, behavior: "instant" });
          return true;
        },
        args: [{ selector: p.selector, x: p.x, y: p.y, dx: p.dx, dy: p.dy }],
      });
      if (sr?.[0]?.result === false) throw new Error(`no match: ${p.selector}`);
      return { ok: true };
    }
    case "hover": {
      await cdpAttach(p.tabId, session);
      let pt = null;
      if (p.selector) {
        pt = await cdpExec("evaluate", { tabId: p.tabId, session, fn: `(() => { const el = document.querySelector(${JSON.stringify(p.selector)}); if (!el) return null; const r = el.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; })()` });
        if (!pt) throw new Error(`no match: ${p.selector}`);
      } else if (p.x !== undefined && p.y !== undefined) {
        pt = { x: p.x, y: p.y };
      } else {
        throw new Error("hover needs selector or x/y");
      }
      await showCursor(p.tabId, pt.x, pt.y);
      await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.dispatchMouseEvent", {
        type: "mouseMoved", x: pt.x, y: pt.y,
      });
      return { ok: true, at: pt };
    }
    case "select": {
      await checkDomain(session, p.url || "", true);
      if (!p.selector || p.value === undefined) throw new Error("select needs selector and value");
      const okr = await chrome.scripting.executeScript({
        target: { tabId: p.tabId },
        func: (a) => {
          const el = document.querySelector(a.selector);
          if (!el || el.tagName !== "SELECT") return false;
          const opts = [...el.options];
          const opt = opts.find((o) => o.value === a.value) || opts.find((o) => (o.text || "").trim() === String(a.value).trim());
          if (!opt) return false;
          el.value = opt.value;
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          return true;
        },
        args: [{ selector: p.selector, value: p.value }],
      });
      if (!okr?.[0]?.result) throw new Error(`no matching option: ${p.value}`);
      return { ok: true };
    }
    case "dialog": {
      const d = pendingDialogs.get(p.tabId);
      if (!d) throw new Error("no dialog pending on tab");
      const accept = p.action !== "dismiss";
      await chrome.debugger.sendCommand({ tabId: p.tabId }, "Page.handleJavaScriptDialog", {
        accept,
        promptText: p.text,
      });
      pendingDialogs.delete(p.tabId);
      return { ok: true, accepted: accept, type: d.type, message: d.message };
    }
    case "wait": {
      await checkDomain(session, p.url || "", false);
      if (!p.text && !p.selector) throw new Error("wait needs text or selector");
      const timeout = Math.min(p.timeout || 10000, 60000);
      const t0 = Date.now();
      for (;;) {
        const found = await chrome.scripting.executeScript({
          target: { tabId: p.tabId },
          func: (a) => {
            if (a.selector) return !!document.querySelector(a.selector);
            return (document.body?.innerText || "").includes(a.text);
          },
          args: [{ selector: p.selector, text: p.text }],
        }).then((r) => r?.[0]?.result).catch(() => false);
        if (found) return { ok: true, found: true, elapsed: Date.now() - t0 };
        if (Date.now() - t0 > timeout) return { ok: true, found: false, elapsed: Date.now() - t0 };
        await new Promise((r) => setTimeout(r, 500));
      }
    }
    case "console": {
      const st = attached.get(p.tabId);
      return (st?.buffers.console || []).slice(-(p.limit || 50));
    }
    case "network": {
      const st = attached.get(p.tabId);
      return (st?.buffers.network || [])
        .filter((e) => e.method === "Network.responseReceived")
        .slice(-(p.limit || 50))
        .map((e) => ({ url: e.params.response.url, status: e.params.response.status, mime: e.params.response.mimeType }));
    }
    case "close_tab":
      clearTimeout(fadeTimers.get(p.tabId));
      fadeTimers.delete(p.tabId);
      lastCursor.delete(p.tabId);
      hideWorkFade(p.tabId);
      await chrome.tabs.remove(p.tabId);
      return { ok: true };
    case "release_tab":
      // hand the tab back: hide indicators immediately, detach debugger
      clearTimeout(fadeTimers.get(p.tabId));
      fadeTimers.delete(p.tabId);
      lastCursor.delete(p.tabId);
      hideWorkFade(p.tabId);
      pendingDialogs.delete(p.tabId);
      try {
        await chrome.debugger.detach({ tabId: p.tabId });
      } catch {}
      attached.delete(p.tabId);
      return { ok: true };
    case "upload": {
      await cdpAttach(p.tabId, session);
      const node = await chrome.debugger.sendCommand({ tabId: p.tabId }, "DOM.getDocument", { depth: 0 });
      const found = await chrome.debugger.sendCommand({ tabId: p.tabId }, "DOM.querySelector", {
        nodeId: node.root.nodeId,
        selector: p.selector,
      }).catch(() => null);
      if (!found) throw new Error(`no match: ${p.selector}`);
      const desc = await chrome.debugger.sendCommand({ tabId: p.tabId }, "DOM.describeNode", {
        nodeId: found.nodeId,
      });
      await chrome.debugger.sendCommand({ tabId: p.tabId }, "DOM.setFileInputFiles", {
        files: p.files,
        backendNodeId: desc.node.backendNodeId,
      });
      return { ok: true, files: p.files.length };
    }
    case "select_tab":
      await chrome.tabs.update(p.tabId, { active: true });
      return { ok: true };
    default:
      throw new Error(`unknown method: ${method}`);
  }
}

const groupTitles = new Map(); // session -> "title (id)" once resolved
async function sessionLabel(session) {
  if (groupTitles.has(session)) return groupTitles.get(session);
  let label = session;
  try {
    const cfg = await chrome.storage.local.get({ srv: "http://127.0.0.1:4096", usr: "ucha", pwd: "" });
    const headers = cfg.pwd ? { Authorization: "Basic " + btoa(`${cfg.usr}:${cfg.pwd}`) } : {};
    const r = await fetch(cfg.srv.replace(/\/$/, "") + "/session", { headers });
    if (r.ok) {
      const ss = await r.json();
      const s = ss.find((x) => x.id === session) || ss.find((x) => x.slug === session);
      if (s) label = `${s.title || s.slug || session} (${s.id})`;
    }
  } catch {}
  groupTitles.set(session, label);
  return label;
}
async function groupTab(session, tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (tab.groupId && tab.groupId !== -1) return tab.groupId;
    let gid = groups.get(session);
    if (gid === undefined) {
      gid = await chrome.tabs.group({ tabIds: [tabId] });
      groups.set(session, gid);
      const colors = ["blue", "green", "orange", "purple", "pink", "cyan"];
      await chrome.tabGroups.update(gid, {
        title: (await sessionLabel(session)).slice(0, 60),
        color: colors[[...groups.keys()].length % colors.length],
      });
    } else {
      await chrome.tabs.group({ tabIds: [tabId], groupId: gid });
    }
    return gid;
  } catch {
    return -1;
  }
}
