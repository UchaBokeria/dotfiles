1: // 20s keepalive ping — keeps the service worker alive for bridge sessions
2: // (same trick as Claude's offscreen doc).
3: setInterval(() => chrome.runtime.sendMessage({ type: "keepalive", at: Date.now() }).catch(() => {}), 20000);
