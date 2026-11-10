# 10 — In-app browser (CDP relay + password handoff)

Source of truth: grand-plan.md. Covers B1–B4.

## 1. Decision: CDP relay (recommended), WebView for pages, no VNC

| Approach | Verdict |
|---|---|
| **CDP relay** | ✅ Observe + drive the EXISTING agent Chrome (box `--remote-debugging-port` via Tunnel; app WebSocket → `/json`, speaks CDP: `Page.startScreencast` observe, `Input.dispatch*` control, `Runtime.evaluate` queries). Mirrors existing CDP-bridge architecture (`bin/bridge.ts`, `bin/cdp-mcp.ts`). Transport: OkHttp WS + kotlinx.serialization; optional kklisura/chrome-devtools-java-client. |
| **WebView** (`androidx.webkit`, KevinnZou/compose-webview) | ✅ For rendering pages INSIDE the app (login pages, snapshots). Full DOM control. Cannot attach to external Chrome. |
| **VNC** (noVNC-in-WebView) | ❌ Full-desktop encode, no DOM semantics, painful input. Only if agent box were VNC-only — it isn't. |

## 2. B1 — Browser enable per chat

- Per-session toggle "browser enabled" (default per settings). When on, browser MCP tools stay
  in the message `tools` set; when off, excluded (same gating mechanism as H3 websearch).
- Which backend (B2): setting `browser.backend = playwright | chrome-extension`.
  Switch = MCP enable/disable via `POST /mcp` + per-message tools gating (verify against live `/doc` in spec phase).

## 3. B3 — In-app screencast observe/control

- Screen: screencast frames (throttled quality per settings) + status (URL, title) + control toggle.
- Observe mode default; control mode requires explicit tap (and shows "YOU control" banner).
- One-tap "return control to agent" + "kill CDP session" (revoke).
- `FLAG_SECURE` on the observation surface (no screenshots by other apps).

## 4. B4 — Password-entry handoff (concrete pattern)

1. Detect password field: CDP `DOM.describeNode` / focus on `input[type=password]`, or WebView URL heuristic.
2. Pause agent input; bottom-sheet: "Agent needs your login for *host*".
3. Credential ENTRY happens OUTSIDE the agent surface: open login URL in **Custom Tab**
   (`androidx.browser`) — user's own cookies, Android Autofill, passkeys — deep-link back
   (`app://auth-callback`), signal session resume. Fallback: native `CredentialManager`
   (passkey/password) sheet filling via CDP `DOM.setAttributeValue` without displaying the secret.
4. Never type passwords into screencast/WebView agent surfaces; never log keystrokes.
5. Post-login: explicit "control returned to agent" state + one-tap revoke.

## 5. Security rules

- CDP endpoint URL + headers stored encrypted; Tunnel URL pinned per server profile.
- Screencast frames never cached to disk; memory-only, cleared on screen exit.
- Audit-log browser-control sessions locally (when, which session, duration) — viewable in settings.

## Sources

- https://github.com/KevinnZou/compose-webview
- https://github.com/novnc/noVNC (reference only — not used)
- https://github.com/kklisura/chrome-devtools-java-client (optional)
- Repo: `bin/bridge.ts`, `bin/cdp-mcp.ts` (existing CDP-bridge architecture)
