// Turn-scoped permission store (cocodem-inspired, simplified).
// Default allow; explicit denies win. Grants auto-record per session+domain.
async function permGet() {
  return (await chrome.storage.local.get({ perm: { sessions: {} } })).perm;
}
async function permSet(p) {
  await chrome.storage.local.set({ perm: p });
}
function permDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}
async function permCheck(session, url, _write) {
  const p = await permGet();
  const s = p.sessions[session] || (p.sessions[session] = { allow: [], deny: [], seen: [] });
  const d = permDomain(url);
  if (d && !s.seen.includes(d)) {
    s.seen.push(d);
    await permSet(p);
  }
  if (!d) return true;
  if (s.deny.some((x) => d === x || d.endsWith(`.${x}`))) return false;
  return true; // default allow; denies managed in side panel
}
async function permDeny(session, domain) {
  const p = await permGet();
  const s = p.sessions[session] || (p.sessions[session] = { allow: [], deny: [], seen: [] });
  if (!s.deny.includes(domain)) s.deny.push(domain);
  await permSet(p);
}
