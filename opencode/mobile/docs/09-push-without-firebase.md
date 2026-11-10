# 09 — Push without Firebase (ntfy + UnifiedPush + bridge)

Source of truth: grand-plan.md. No Firebase, no paid services — on-prem only.
Topology: `ntfy.uchabokeria.space` (doc: grand-plan §Topology).

## 1. Why a bridge is required

Android cannot hold a perpetual background SSE (doc 05): Doze, 6h `dataSync` cap,
OEM killers. When the app is dead, SOMETHING server-side must observe `serve` and wake the phone.
That something = tiny self-hosted bridge on blackwall: watches `serve /event` SSE,
publishes to self-hosted ntfy topics. Phone subscribes via UnifiedPush (ntfy distributor).

## 2. Components

- **ntfy server** (self-hosted, Go, single binary): topics over HTTPS;
  `GET /topic/json` (NDJSON + `since=` replay — use this), `/topic/sse`, `/topic/ws`;
  priorities, auth, attachments, keepalive events. https://docs.ntfy.sh · https://github.com/binwiederhier/ntfy
- **Bridge** (`serve → ntfy`, custom, runs on blackwall next to `serve`):
  opens `GET /event` SSE with Basic auth; on `message.part.updated` (reply done → `session.idle`),
  `permission.updated` (approval stall), `session.error` → POST to ntfy topic with priority +
  minimal payload (session id + title + snippet; never secrets).
  Supervised (systemd unit, auto-restart = "resurrection" on server side); backoff reconnect;
  dedupe by event id; `since=` gap backfill on its own reconnect.
- **App (UnifiedPush)**: embed `android-connector`; user picks distributor (ntfy app / Sunup / NextPush).
  https://unifiedpush.org · https://github.com/UnifiedPush/android-connector
- **Fallback (no distributor installed)**: foreground `dataSync` service holding ntfy SSE/WS
  directly + battery-exemption UX (Gotify android pattern); degraded, documented as such.

## 3. Topic + auth design (OPEN — spec phase with user)

- One topic per user-device or per server? Proposal: `opencode-<user>-<device>` unguessable names
  (random suffix), ntfy-native auth (Basic/token) stored in EncryptedSharedPreferences.
- Machine endpoints stay OFF Cloudflare Access (Access breaks machine clients);
  protected by ntfy auth + unguessable topics. Access only on human web UI, if ever.
- Payloads: session id, event type, short snippet. Full content pulled via `serve` API on tap
  (payload minimization = privacy + Doze-friendly small pushes).

## 4. Notification mapping (app side)

- Reply done → HIGH channel, actions: Open / Direct-reply / Mark-read. Presence-aware:
  suppress for session currently open on screen.
- Approval stall (`permission.updated`, `AskUserQuestion`) → separate HIGH channel,
  inline Approve / Deny actions on the notification itself.
- Bridge/error events → LOW channel (status), no sound.
- Quiet hours + per-session mute (settings) applied client-side before posting.

## 5. Cloudflare Tunnel notes

- `cloudflared` outbound-only; no inbound ports. WebSockets fully supported through tunnels.
- Prefer `/json` (NDJSON) or `/ws` endpoints with keepalives + client backoff over bare SSE
  through proxies (idle timeouts). Use ntfy keepalive events as connection-health signal.
- Cache + replay server-side (`since=<last-id>`) so Doze gaps backfill.

## 6. What we do NOT use

- FCM (Google dependency — banned by brief). Expo push (third-party cloud — banned).
- `remoteMessaging` FGS type for this (Play-policy risk, doc 05).

## Sources

- https://unifiedpush.org · https://unifiedpush.org/developers/spec/android/
- https://github.com/UnifiedPush/android-connector
- https://github.com/binwiederhier/ntfy · https://docs.ntfy.sh/subscribe/api/ · https://docs.ntfy.sh/install/
- https://github.com/gotify/server · https://github.com/gotify/android (FGS + exemption pattern)
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/
