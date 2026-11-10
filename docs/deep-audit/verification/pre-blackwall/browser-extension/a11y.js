1: // Instant accessibility snapshot for opencode (MCP-blind pages included).
2: // Runs at document_start on all pages; collects on demand via messages.
3: function collect() {
4:   const out = [];
5:   const els = document.querySelectorAll(
6:     "a,button,input,select,textarea,[role],[tabindex],h1,h2,h3,img,video,iframe"
7:   );
8:   for (const el of els) {
9:     if (out.length >= 1500) break;
10:     const r = el.getBoundingClientRect?.();
11:     if (!r || (r.width === 0 && r.height === 0)) continue;
12:     const name = (
13:       el.getAttribute("aria-label") ||
14:       el.innerText ||
15:       el.value ||
16:       el.alt ||
17:       el.title ||
18:       el.placeholder ||
19:       ""
20:     ).trim().replace(/\s+/g, " ").slice(0, 120);
21:     out.push({
22:       tag: el.tagName.toLowerCase(),
23:       role: el.getAttribute("role") || "",
24:       name,
25:       x: Math.round(r.x),
26:       y: Math.round(r.y),
27:     });
28:   }
29:   return { url: location.href, title: document.title, nodes: out };
30: }
31: 
32: chrome.runtime.onMessage.addListener((msg, _sender, send) => {
33:   if (msg?.type === "opencode-a11y") send(collect());
34:   return true;
35: });
