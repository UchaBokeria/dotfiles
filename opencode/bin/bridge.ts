// @ts-nocheck
// opencode browser bridge — lets Chrome extensions accept opencode sessions.
// Bun server on 127.0.0.1:9225. Endpoints:
//   POST /register {name, endpoint, windows} -> {ok}
//   GET  /browsers -> [{name, endpoint, windows, lastSeen}]
//   POST /pending  {session} -> {session, status}
//   GET  /pending/:session -> {status: pending|accepted, browser?}
//   POST /accept   {session, browser} -> {ok} (called by the extension)
import os from "node:os";
const browsers = new Map<string, any>();
const pending = new Map<string, any>();
const sessionTabs = new Map<string, any>();
const tabSnapshots = new Map<string, any>();
const groupReqs: any[] = [];
const extSockets = new Map<string, any>(); // sockId ("name#n") -> WS; name on ws.browser
let sockSeq = 0;
const onlineNames = () => [...new Set([...extSockets.values()].map((s) => (s as any).browser))];
const mcpWaiters = new Map<number, any>();
let msgId = 0;
const netRules = new Map<string, any>();
const a11yStore = new Map<string, any>();
const markReqs: any[] = [];
const recStore = new Map<string, any[]>();
const recFlag = new Set<string>();
const sseClients = new Set<ReadableStreamDefaultController>();
function emit(type: string, data: any) {
  const msg = `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const c of sseClients) {
    try {
      c.enqueue(new TextEncoder().encode(msg));
    } catch {}
  }
}

const json = (d: any, s = 200) =>
  new Response(JSON.stringify(d), { status: s, headers: { "content-type": "application/json" } });

Bun.serve({
  port: 9225,
  hostname: process.env.BIND || "127.0.0.1",
  websocket: {
    open(ws) {},
    close(ws) {
      for (const [id, s] of extSockets) if (s === ws) extSockets.delete(id);
    },
    message(ws, raw) {
      let m: any;
      try {
        m = JSON.parse(String(raw));
      } catch {
        return;
      }
      if (m.hello?.role === "extension" && m.hello.browser) {
        // multiple sockets may share one browser name (two profiles, same default).
        // Key each socket by unique id; name stays the display label.
        const sockId = `${m.hello.browser}#${++sockSeq}`;
        (ws as any).browser = m.hello.browser;
        (ws as any).sockId = sockId;
        extSockets.set(sockId, ws);
        ws.send(JSON.stringify({ hello: "ok" }));
        return;
      }
      if (m.to && m.id !== undefined) {
        // newest socket wins when several share a name; fallback to any live one
        const cands = [...extSockets.values()].filter((s) => (s as any).browser === m.to);
        const ext = cands[cands.length - 1];
        if (!ext) {
          ws.send(JSON.stringify({ id: m.id, error: `browser offline: ${m.to}` }));
          return;
        }
        mcpWaiters.set(m.id, ws);
        ext.send(JSON.stringify(m));
        return;
      }
      if (m.id !== undefined && m.from) {
        const waiter = mcpWaiters.get(m.id);
        if (waiter) {
          mcpWaiters.delete(m.id);
          waiter.send(JSON.stringify({ id: m.id, result: m.result, error: m.error }));
        }
        return;
      }
    },
  },
  async fetch(req, server) {
    const u = new URL(req.url);
    if (u.pathname === "/hub" && server.upgrade(req)) return;
    if (u.pathname === "/hub-browsers") {
      return json({ online: onlineNames(), registered: [...browsers.values()].map((b) => b.name) });
    }
    if (req.method === "POST" && u.pathname === "/register") {
      const b = await req.json();
      if (!b.name) return json({ error: "name required" }, 400);
      browsers.set(b.name, { ...b, lastSeen: Date.now() });
      return json({ ok: true });
    }
    if (req.method === "GET" && u.pathname === "/hub-browsers") {
      return json({ online: onlineNames(), registered: [...browsers.values()].map((b) => b.name), hint: "online = WS-connected browser names" });
    }
    if (req.method === "GET" && u.pathname === "/browsers") {
      return json([...browsers.values()]);
    }
    if (req.method === "GET" && u.pathname === "/events") {
      let ctrl: ReadableStreamDefaultController;
      const stream = new ReadableStream({
        start(c) {
          ctrl = c;
          sseClients.add(c);
        },
        cancel(c) {
          sseClients.delete(c);
        },
      });
      return new Response(stream, {
        headers: {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
          connection: "keep-alive",
        },
      });
    }
    if (req.method === "POST" && u.pathname === "/pending") {
      const { session } = await req.json();
      if (!session) return json({ error: "session required" }, 400);
      pending.set(session, { status: "pending", created: Date.now() });
      emit("pending", { session });
      return json({ session, status: "pending" });
    }
    if (req.method === "GET" && u.pathname.startsWith("/pending/")) {
      const session = decodeURIComponent(u.pathname.slice(9));
      const p = pending.get(session);
      if (!p) return json({ status: "unknown" }, 404);
      if (Date.now() - p.created > 5 * 60 * 1000) {
        pending.delete(session);
        return json({ status: "expired" });
      }
      return json(p.status === "accepted" ? { status: "accepted", browser: p.browser } : { status: "pending" });
    }
    if (req.method === "GET" && u.pathname === "/pending-latest") {
      const all = [...pending.entries()].filter(([, p]) => p.status === "pending" && Date.now() - p.created < 5 * 60 * 1000);
      if (!all.length) return json({ status: "none" });
      const [session] = all[all.length - 1];
      return json({ status: "pending", session });
    }
    if (req.method === "POST" && u.pathname === "/serve-restart") {
      try {
        const cfg = await Bun.file(`${os.homedir()}/.config/opencode/opencode.json`).text();
        JSON.parse(cfg); // refuse to restart on broken config
      } catch (e) {
        return json({ error: `opencode.json invalid, not restarting: ${e}` }, 400);
      }
      Bun.spawn(["systemctl", "--user", "restart", "opencode-mobile"], { stdout: "ignore", stderr: "ignore" });
      return json({ ok: true, restarting: true });
    }
    if (req.method === "POST" && u.pathname === "/accept") {
      const { session, browser } = await req.json();
      const p = pending.get(session);
      if (!p) return json({ error: "no such pending session" }, 404);
      pending.set(session, { ...p, status: "accepted", browser });
      emit("accepted", { session, browser });
      return json({ ok: true });
    }
    // periodic cleanup of transient stores (sessions/tabs/snapshots/marks/rules)
    if (!((globalThis as any).__sweepAt && Date.now() - (globalThis as any).__sweepAt < 60000)) {
      (globalThis as any).__sweepAt = Date.now();
      const TTL = 30 * 60 * 1000;
      for (const [k, v] of sessionTabs) if (Date.now() - (v.at || 0) > TTL) sessionTabs.delete(k);
      for (const [k, v] of tabSnapshots) if (Date.now() - (v.at || 0) > TTL) tabSnapshots.delete(k);
      for (const [k, v] of a11yStore) if (Date.now() - (v.at || 0) > TTL) a11yStore.delete(k);
      for (const [k, v] of netRules) if (Date.now() - (v.at || 0) > TTL) netRules.delete(k);
      while (groupReqs.length > 200) groupReqs.shift();
      while (markReqs.length > 200) markReqs.shift();
      for (const arr of recStore.values()) if (arr.length > 500) arr.splice(0, arr.length - 500);
      for (const [k, v] of pending) if (Date.now() - (v.created || 0) > 10 * 60 * 1000) pending.delete(k);
    }
    if (req.method === "POST" && u.pathname === "/session-tabs") {
      const { session, browser, tabs } = await req.json();
      if (!session) return json({ error: "session required" }, 400);
      sessionTabs.set(session, { browser, tabs, at: Date.now() });
      return json({ ok: true });
    }
    if (req.method === "GET" && u.pathname.startsWith("/session-tabs/")) {
      const s = sessionTabs.get(decodeURIComponent(u.pathname.slice("/session-tabs/".length)));
      return s ? json(s) : json({ error: "unknown session" }, 404);
    }
    if (req.method === "POST" && u.pathname === "/tabsnapshot") {
      const { browser, tabs } = await req.json();
      if (!browser) return json({ error: "browser required" }, 400);
      tabSnapshots.set(browser, { tabs, at: Date.now() });
      return json({ ok: true });
    }
    if (req.method === "GET" && u.pathname.startsWith("/tabsnapshot/")) {
      const s = tabSnapshots.get(decodeURIComponent(u.pathname.slice("/tabsnapshot/".length)));
      return s ? json(s) : json({ error: "no snapshot" }, 404);
    }
    if (req.method === "POST" && u.pathname === "/group") {
      const { browser, session, requestId, urls, title, color } = await req.json();
      if (!browser || !requestId) return json({ error: "browser+requestId required" }, 400);
      groupReqs.push({ browser, session, requestId, urls: urls || [], title: title || session, color: color || "blue", created: Date.now() });
      return json({ ok: true });
    }
    if (req.method === "GET" && u.pathname.startsWith("/group-requests/")) {
      const browser = decodeURIComponent(u.pathname.slice("/group-requests/".length));
      const now = Date.now();
      return json(groupReqs.filter((g) => g.browser === browser && now - g.created < 10 * 60 * 1000));
    }
    if (req.method === "GET" && u.pathname === "/profiles") {
      try {
        const ls = await Bun.file(`${os.homedir()}/.config/google-chrome/Local State`).json();
        const cache = ls.profile?.info_cache || {};
        return json(Object.entries(cache).map(([dir, v]: any) => ({ dir, name: v.name || dir })));
      } catch (e) {
        return json({ error: "cannot read Local State" }, 500);
      }
    }
    if ((req.method === "POST" || req.method === "PUT") && u.pathname === "/netrules") {
      const b = await req.json();
      if (!b.browser) return json({ error: "browser required" }, 400);
      netRules.set(b.browser, { block: b.block || [], stealth: !!b.stealth, at: Date.now() });
      emit("netrules", { browser: b.browser });
      return json({ ok: true });
    }
    if (req.method === "GET" && u.pathname.startsWith("/netrules/")) {
      const r = netRules.get(decodeURIComponent(u.pathname.slice("/netrules/".length)));
      return json(r || { block: [], stealth: false });
    }
    if (req.method === "POST" && u.pathname === "/a11y") {
      const { browser, url, tree } = await req.json();
      if (!browser) return json({ error: "browser required" }, 400);
      a11yStore.set(browser, { url, tree, at: Date.now() });
      return json({ ok: true });
    }
    if (req.method === "GET" && u.pathname.startsWith("/a11y/")) {
      const s = a11yStore.get(decodeURIComponent(u.pathname.slice("/a11y/".length)));
      return s ? json(s) : json({ error: "no snapshot" }, 404);
    }
    if ((req.method === "POST" || req.method === "DELETE") && u.pathname === "/record") {
      if (req.method === "DELETE") {
        const b = await req.json().catch(() => ({}));
        if (b.browser) recStore.delete(b.browser);
        else recStore.clear();
        return json({ ok: true });
      }
      const body = await req.json().catch(() => ({}));
      const { browser, action } = body;
      if (!browser || !action) return json({ error: "browser+action required" }, 400);
      if (!recStore.has(browser)) recStore.set(browser, []);
      const arr = recStore.get(browser)!;
      arr.push(body);
      if (arr.length > 500) arr.splice(0, arr.length - 500);
      return json({ ok: true, steps: arr.length });
    }
    if (req.method === "GET" && u.pathname.startsWith("/record/")) {
      const parts = decodeURIComponent(u.pathname.slice("/record/".length)).split("/");
      const arr = recStore.get(parts[0]) || [];
      if (parts[1] === "count") return json({ steps: arr.length, recording: recFlag.has(parts[0]) });
      return json(arr);
    }
    if (req.method === "POST" && u.pathname === "/record-flag") {
      const { browser, recording } = await req.json();
      if (!browser) return json({ error: "browser required" }, 400);
      if (recording) recFlag.add(browser);
      else recFlag.delete(browser);
      return json({ ok: true, recording: recFlag.has(browser) });
    }
    if (req.method === "POST" && u.pathname === "/mark") {
      const { browser, session, requestId, urls } = await req.json();
      if (!browser || !requestId) return json({ error: "browser+requestId required" }, 400);
      markReqs.push({ browser, session, requestId, urls: urls || [], created: Date.now() });
      emit("mark", { browser, session });
      return json({ ok: true });
    }
    if (req.method === "GET" && u.pathname.startsWith("/marks/")) {
      const browser = decodeURIComponent(u.pathname.slice("/marks/".length));
      const now = Date.now();
      return json(markReqs.filter((g) => g.browser === browser && now - g.created < 10 * 60 * 1000));
    }
    return json({ error: "not found" }, 404);
  },
});
console.log("browser bridge on 127.0.0.1:9225");
