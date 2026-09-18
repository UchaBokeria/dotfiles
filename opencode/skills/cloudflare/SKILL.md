---
name: cloudflare
description: Cloudflare work. Use for DNS, tunnels, Workers, WAF, or debugging edge/CDN issues. Traefik gets certs via Cloudflare DNS-01 here.
---

# Cloudflare

- Dashboard: `https://dash.cloudflare.com` (DNS, WAF, caching, tunnels).
- CLI: `cloudflared` (tunnels), `wrangler` (Workers/D1/R2).
- This setup: wildcard `*.uchabokeria.space` via DNS-01; registry host stays
  grey-clouded (100MB cap); `cloudflared tunnel --url` for quick public URLs.
- Debugging: `curl -sI` edge headers (`cf-cache-status`, `cf-ray`),
  WAF events in dashboard before blaming origin. Purge cache per-path after
  deploys, never "purge everything" on shared zones without asking.
