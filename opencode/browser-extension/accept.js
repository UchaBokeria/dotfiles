const API = "http://127.0.0.1:9225";
const session = new URLSearchParams(location.search).get("session") || "";
document.getElementById("sess").textContent = session;
document.getElementById("accept").onclick = async () => {
  const { name } = await chrome.storage.sync.get({ name: "archlinux-1" });
  const r = await fetch(`${API}/accept`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ session, browser: name }),
  });
  if (r.ok) {
    document.getElementById("done").style.display = "block";
    document.getElementById("accept").style.display = "none";
    try {
      await chrome.runtime.sendMessage({ type: "accept-done", session });
    } catch {}
    setTimeout(() => window.close(), 1500);
  }
};
