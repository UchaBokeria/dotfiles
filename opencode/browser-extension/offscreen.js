// 20s keepalive ping — keeps the service worker alive for bridge sessions
// (same trick as Claude's offscreen doc).
setInterval(() => chrome.runtime.sendMessage({ type: "keepalive", at: Date.now() }).catch(() => {}), 20000);
