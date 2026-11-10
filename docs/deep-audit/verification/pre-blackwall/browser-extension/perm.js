1: // Turn-scoped permission store (cocodem-inspired, simplified).
2: // Default allow; explicit denies win. Grants auto-record per session+domain.
3: async function permGet() {
4:   return (await chrome.storage.local.get({ perm: { sessions: {} } })).perm;
5: }
6: async function permSet(p) {
7:   await chrome.storage.local.set({ perm: p });
8: }
9: function permDomain(url) {
10:   try {
11:     return new URL(url).hostname.replace(/^www\./, "");
12:   } catch {
13:     return "";
14:   }
15: }
16: async function permCheck(session, url, _write) {
17:   const p = await permGet();
18:   const s = p.sessions[session] || (p.sessions[session] = { allow: [], deny: [], seen: [] });
19:   const d = permDomain(url);
20:   if (d && !s.seen.includes(d)) {
21:     s.seen.push(d);
22:     await permSet(p);
23:   }
24:   if (!d) return true;
25:   if (s.deny.some((x) => d === x || d.endsWith(`.${x}`))) return false;
26:   return true; // default allow; denies managed in side panel
27: }
28: async function permDeny(session, domain) {
29:   const p = await permGet();
30:   const s = p.sessions[session] || (p.sessions[session] = { allow: [], deny: [], seen: [] });
31:   if (!s.deny.includes(domain)) s.deny.push(domain);
32:   await permSet(p);
33: }
