---
name: contabo
description: Contabo VPS work. Use for the blackwall box (13.140.155.113), volumes, snapshots, or rescue mode.
---

# Contabo (blackwall: 13.140.155.113)

- Panel: `https://my.contabo.com` (VPS control, snapshots, rescue, reverse DNS).
- SSH: `ssh -i ~/.ssh/idiot-doll scriptkid@13.140.155.113` (BatchMode for
  scripts; never interactive without reason).
- On-box layout: prod stack in `~/opt/cloud` (compose project `cloud`),
  edge = Traefik + Cloudflare wildcard; ufw 22/80/443 + tailscale.
- Discipline: snapshots before risky changes, `git pull` + compose
  rebuilds only (no snowflake edits on prod), restic backups exist — verify
  before destructive ops. Check load first (`uptime`) — it runs hot.
