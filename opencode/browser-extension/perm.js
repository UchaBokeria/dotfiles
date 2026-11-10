// Turn-scoped permission store (cocodem-inspired, simplified).
// Global default allow; per-domain denies win. Optional deny-all mode with allowlist.
// Shape: { mode: "allow"|"deny", deny: [], allow: [], sessions: { id: { allow:[], deny:[], seen:[] } } }
async function permGet() {
  return (await chrome.storage.local.get({ perm: { mode: "allow", deny: [], allow: [], sessions: {} } })).perm;
}
async function permSet(p) {
  await chrome.storage.local.set({ perm: p });
}
function permMatch(list, domain) {
  return (list || []).some((x) => x && (domain === x || domain.endsWith(`.${x}`)));
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
  if (d && !(p.seenAll || []).includes(d)) {
    p.seenAll = [...(p.seenAll || []), d].slice(-200);
    const q = (await chrome.storage.local.get({ permNotices: [] })).permNotices;
    if (!q.some((x) => x.domain === d)) {
      q.push({ domain: d, at: Date.now() });
      await chrome.storage.local.set({ permNotices: q.slice(-20) });
    }
    await permSet(p);
  }
  if (!d) return true;
  if (s.deny && permMatch(s.deny, d)) return false; // session deny wins
  if (p.mode === "deny") return permMatch(p.allow, d); // deny-all: only allowlisted
  return !permMatch(p.deny, d); // allow-all (default): only denylisted blocked
}
async function permDeny(session, domain) {
  const p = await permGet();
  const s = p.sessions[session] || (p.sessions[session] = { allow: [], deny: [], seen: [] });
  if (!s.deny.includes(domain)) s.deny.push(domain);
  await permSet(p);
}
