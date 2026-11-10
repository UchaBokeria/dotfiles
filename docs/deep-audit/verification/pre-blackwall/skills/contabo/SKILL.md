1: ---
2: name: contabo
3: description: Contabo VPS work. Use for the blackwall box (13.140.155.113), volumes, snapshots, or rescue mode.
4: ---
5: 
6: # Contabo (blackwall: 13.140.155.113)
7: 
8: - Panel: `https://my.contabo.com` (VPS control, snapshots, rescue, reverse DNS).
9: - SSH: `ssh -i ~/.ssh/idiot-doll scriptkid@13.140.155.113` (BatchMode for
10:   scripts; never interactive without reason).
11: - On-box layout: prod stack in `~/opt/cloud` (compose project `cloud`),
12:   edge = Traefik + Cloudflare wildcard; ufw 22/80/443 + tailscale.
13: - Discipline: snapshots before risky changes, `git pull` + compose
14:   rebuilds only (no snowflake edits on prod), restic backups exist — verify
15:   before destructive ops. Check load first (`uptime`) — it runs hot.
