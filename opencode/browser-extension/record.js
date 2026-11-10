// Workflow recorder: captures user clicks/fills/selects as replayable steps
// (selectors opencode can feed straight back into cdp_click/cdp_fill).
// Only records while the `recording` flag is set in storage. Password fields
// are never captured. Toggle via panel Drive section or cdp_record MCP tool.
function recSel(el) {
  if (!(el instanceof Element)) return null;
  if (el.id) return `#${CSS.escape(el.id)}`;
  const t = el.getAttribute("data-testid");
  if (t) return `[data-testid="${CSS.escape(t)}"]`;
  const parts = [];
  let cur = el;
  while (cur && cur !== document.body && parts.length < 4) {
    let s = cur.tagName.toLowerCase();
    const sibs = [...(cur.parentElement?.children || [])].filter((c) => c.tagName === cur.tagName);
    if (sibs.length > 1) s += `:nth-of-type(${sibs.indexOf(cur) + 1})`;
    parts.unshift(s);
    cur = cur.parentElement;
  }
  return parts.join(" > ");
}

async function recEnabled() {
  try {
    const { name } = await chrome.storage.sync.get({ name: "archlinux-1" });
    const r = await fetch(`http://127.0.0.1:9225/record/${encodeURIComponent(name)}/count`).then((x) => x.json()).catch(() => null);
    return r && r.recording ? name : null;
  } catch {
    return null;
  }
}

async function recPush(step) {
  const browser = await recEnabled();
  if (!browser) return;
  try {
    await fetch("http://127.0.0.1:9225/record", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ browser, ...step, url: location.href, at: Date.now() }),
    }).catch(() => {});
  } catch {}
}

document.addEventListener(
  "click",
  (e) => {
    if (e.button !== 0) return;
    const el = e.target.closest?.("a,button,input,select,textarea,[role=button]");
    if (!el) return;
    const sel = recSel(el);
    if (!sel) return;
    recPush({ action: "click", selector: sel, text: (el.innerText || el.value || "").trim().slice(0, 80) });
  },
  true
);
document.addEventListener(
  "change",
  (e) => {
    const el = e.target;
    if (!(el instanceof Element)) return;
    if (el.tagName === "SELECT") {
      const sel = recSel(el);
      if (sel) recPush({ action: "select", selector: sel, value: el.value });
      return;
    }
    if ((el.tagName === "INPUT" || el.tagName === "TEXTAREA") && el.type !== "password" && el.type !== "file") {
      const sel = recSel(el);
      if (sel) recPush({ action: "fill", selector: sel, text: String(el.value || "").slice(0, 500) });
    }
  },
  true
);
