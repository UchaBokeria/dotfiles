# Remote ADB — blackwall drives the PC emulator (P4+ verification)

Source of truth: grand-plan.md (topology). Status: PLUMBING READY, needs 1 user step (§4).

## Why

Blackwall has no KVM (verified: no /dev/kvm, no vmx/svm flags, itself a KVM guest) → no emulator
there, ever. Instead the emulator stays on the PC and blackwall controls it over ADB-through-Tunnel
with the SAME recipes used in P0–P3 (uiautomator dump, input tap/text, screencap).

## Architecture

- PC: `adb -a nodaemon server start` (listens *:5037) + api26 emulator + systemd
  `adb-emu-tunnel.service` → named tunnel `adb-emu`
  (`70161d17-d394-42a9-b5a4-129c7432df39`, creds `~/.cloudflared/adb-emu*.json`)
  ingress `tcp://localhost:5037`.
- Blackwall: `cloudflared access tcp --hostname <HOST> --url 127.0.0.1:5037`
  (+ `--service-token-id/--service-token-secret` once Access exists — see §4),
  then `~/Android/platform-tools/adb connect 127.0.0.1:5037`.
- Then ALL P0–P3 device recipes work verbatim with `-s 127.0.0.1:5037`:
  `shell uiautomator dump`, `input tap`, `input text`, `exec-out screencap -p`,
  `install -r`, `logcat -d | grep OC-`.
- Keep-alive contract: PC keeps emulator + adb + tunnel service up. If screenshots stop,
  check (PC): `systemctl --user is-active adb-emu-tunnel`, `adb devices`, emulator process.

## Security (non-negotiable)

- ADB has NO auth — full shell on the emulator. The tunnel MUST sit behind Cloudflare Access
  (email-OTP/app policy for humans + service token for this agent). NEVER run the tunnel
  without an Access policy except for a minutes-long user-supervised test.
- Service token lives ONLY in `~/.config/blackwall-secrets/adb-service-token` (git-untracked,
  chmod 600) on blackwall — never in repo, docs, logs, or chat.

## User step (once, ~2 min, dashboard)

1. Cloudflare Zero Trust → Networks → (tunnel adb-emu already exists) → Public Hostnames →
   add `adb-emu.uchabokeria.space` → service `tcp://localhost:5037`.
   (If the dashboard route is preferred over the auto `<uuid>.cfargotunnel.com` name.)
2. Zero Trust → Access → Applications → Add self-hosted: domain as above → policy Allow,
   include your email (OTP) → create Service Token for the agent → save id+secret into
   `~/.config/blackwall-secrets/adb-service-token` on blackwall (format: `id:secret`).
3. Tell the agent — it wires `--service-token-*` into a persistent `adb-emu-access.service`
   on blackwall and verifies end-to-end (connect → dump → tap → screencap).

## Blackwall agent usage (after §4)

```bash
export PATH=$PATH:~/Android/platform-tools
TOK=$(cat ~/.config/blackwall-secrets/adb-service-token)
cloudflared access tcp --hostname adb-emu.uchabokeria.space \
  --service-token-id "${TOK%%:*}" --service-token-secret "${TOK#*:}" \
  --url 127.0.0.1:5037
# another shell:
adb connect 127.0.0.1:5037 && adb -s 127.0.0.1:5037 shell getprop sys.boot_completed
```

## BLOCKER (2026-10-07, verified end-to-end, no workaround found)

`cloudflared access tcp` + `adb connect` reaches the PC adb server through the tunnel
(listener binds, Access 302→token accepted), but the ADB handshake itself never completes:
`adb devices` stays `offline`, all shell commands hang. Tried, each with clean reconnects
and waits up to 8 min: fresh keys both sides, pre-seeded `adb_keys` in the emulator,
adbd restart, clean-boot emulator, USB-transport-only mode, removing/re-adding the device,
`adb reconnect`. Root cause: the ADB wire protocol does not survive Cloudflare's TCP proxy
for `access tcp` (frame timing / multiplexing mismatch) — the TLS/WebSocket hop breaks the
persistent ADB session even though the initial TCP connect succeeds.

Fallback options (pick one with the user):
1. **Tailscale** (rejected by brief) — would work instantly (real L3, adb connects natively).
2. **WireGuard/other L3 tunnel** — same effect, self-hosted, no Cloudflare TCP proxy in path.
3. **Reverse direction**: keep emulator verification on the PC (status quo ante) — blackwall
   does code + unit tests + assemble; PC does device screenshots. No infra needed.
4. **Physical device via USB on blackwall** — needs hardware attached to the box (not present).
