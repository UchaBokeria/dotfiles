const $ = (id) => document.getElementById(id);

(async function init() {
  try {
    const l = await chrome.storage.local.get({ name: "" }).catch(() => ({}));
    const name = l.name || (await chrome.storage.sync.get({ name: "archlinux-1" })).name;
    $("bname").textContent = `opencode · ${name}`;
  } catch {}
  refresh();
})();

async function refresh() {
  try {
    const r = await (await fetch(`${API}/pending-latest`)).json();
    const has = r.status === "pending";
    $("pcount").textContent = has ? "1" : "0";
    $("status").textContent = has ? `Pending: ${r.session}` : "";
  } catch {
    $("status").textContent = "Bridge unreachable.";
  }
}

async function openPanel(action) {
  if (action) await chrome.storage.local.set({ panelAction: action });
  const w = await chrome.windows.getCurrent();
  await chrome.sidePanel.open({ windowId: w.id });
  window.close();
}
$("open-panel").onclick = () => openPanel();
$("q-snap").onclick = () => openPanel("snap");
$("q-shot").onclick = () => openPanel("shot");
$("q-accept").onclick = async () => {
  try {
    const r = await (await fetch(`${API}/pending-latest`)).json();
    if (r.status !== "pending") {
      $("status").textContent = "Nothing pending.";
      return;
    }
    const l = await chrome.storage.local.get({ name: "" }).catch(() => ({}));
    const name = l.name || (await chrome.storage.sync.get({ name: "archlinux-1" })).name;
    await fetch(`${API}/accept`, { method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ session: r.session, browser: name }) });
    $("status").textContent = `Connected ${r.session}.`;
    refresh();
  } catch {
    $("status").textContent = "Bridge unreachable.";
  }
};

try {
  const es = new EventSource(`${API}/events`);
  es.addEventListener("pending", refresh);
  es.addEventListener("accepted", refresh);
} catch {}
