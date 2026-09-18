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

async function cdpDetachIdle() {
  const now = Date.now();
  for (const [tabId, st] of attached) {
    if (now - st.lastUsed > 25000) {
      try {
        await chrome.debugger.detach({ tabId });
      } catch {}
      attached.delete(tabId);
    }
  }
}
setInterval(cdpDetachIdle, 10000);

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
    chrome.debugger.sendCommand({ tabId: src.tabId }, "Page.handleJavaScriptDialog", { accept: true }).catch(() => {});
  }
});
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
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: (pt) => {
        let c = document.getElementById("opencode-cursor");
        if (!c) {
          c = document.createElement("div");
          c.id = "opencode-cursor";
          c.style.cssText =
            "position:fixed;z-index:2147483647;width:18px;height:18px;border-radius:50%;background:radial-gradient(circle,#1a73e8 30%,rgba(26,115,232,.25) 70%);pointer-events:none;transition:left .18s ease-out,top .18s ease-out;box-shadow:0 0 0 2px #fff,0 2px 8px rgba(0,0,0,.4)";
          document.documentElement.appendChild(c);
        }
        c.style.left = pt.x - 9 + window.scrollX + "px";
        c.style.top = pt.y - 9 + window.scrollY + "px";
        clearTimeout(c._t);
        c._t = setTimeout(() => c.remove(), 2500);
      },
      args: [{ x, y }],
    });
  } catch {}
}

async function cdpExec(method, p) {
  const session = p.session || "default";
  switch (method) {
    case "ping":
      return { ok: true, tabs: attached.size };
    case "tabs": {
      const tabs = await chrome.tabs.query(p.windowId ? { windowId: p.windowId } : {});
      return tabs.map((t) => ({ id: t.id, windowId: t.windowId, title: t.title, url: t.url, active: t.active }));
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
        await chrome.debugger.sendCommand({ tabId: p.tabId }, "Input.dispatchMouseEvent", {});
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
      await chrome.tabs.remove(p.tabId);
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
        title: `opencode: ${session}`,
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
