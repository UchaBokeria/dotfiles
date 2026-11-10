1: const API = "http://127.0.0.1:9225";
2: const session = new URLSearchParams(location.search).get("session") || "";
3: document.getElementById("sess").textContent = session;
4: document.getElementById("accept").onclick = async () => {
5:   const { name } = await chrome.storage.sync.get({ name: "archlinux-1" });
6:   const r = await fetch(`${API}/accept`, {
7:     method: "POST",
8:     headers: { "content-type": "application/json" },
9:     body: JSON.stringify({ session, browser: name }),
10:   });
11:   if (r.ok) {
12:     document.getElementById("done").style.display = "block";
13:     document.getElementById("accept").style.display = "none";
14:     try {
15:       await chrome.runtime.sendMessage({ type: "accept-done", session });
16:     } catch {}
17:     setTimeout(() => window.close(), 1500);
18:   }
19: };
