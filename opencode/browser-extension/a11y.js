// Instant accessibility snapshot for opencode (MCP-blind pages included).
// Runs at document_start on all pages; collects on demand via messages.
function collect() {
  const out = [];
  const els = document.querySelectorAll(
    "a,button,input,select,textarea,[role],[tabindex],h1,h2,h3,img,video,iframe"
  );
  for (const el of els) {
    if (out.length >= 1500) break;
    const r = el.getBoundingClientRect?.();
    if (!r || (r.width === 0 && r.height === 0)) continue;
    const name = (
      el.getAttribute("aria-label") ||
      el.innerText ||
      el.value ||
      el.alt ||
      el.title ||
      el.placeholder ||
      ""
    ).trim().replace(/\s+/g, " ").slice(0, 120);
    out.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute("role") || "",
      name,
      x: Math.round(r.x),
      y: Math.round(r.y),
    });
  }
  return { url: location.href, title: document.title, nodes: out };
}

chrome.runtime.onMessage.addListener((msg, _sender, send) => {
  if (msg?.type === "opencode-a11y") send(collect());
  return true;
});
