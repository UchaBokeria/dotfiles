1: ---
2: name: cloudflare
3: description: Cloudflare work. Use for DNS, tunnels, Workers, WAF, or debugging edge/CDN issues. Traefik gets certs via Cloudflare DNS-01 here.
4: ---
5: 
6: # Cloudflare
7: 
8: - Dashboard: `https://dash.cloudflare.com` (DNS, WAF, caching, tunnels).
9: - CLI: `cloudflared` (tunnels), `wrangler` (Workers/D1/R2).
10: - This setup: wildcard `*.uchabokeria.space` via DNS-01; registry host stays
11:   grey-clouded (100MB cap); `cloudflared tunnel --url` for quick public URLs.
12: - Debugging: `curl -sI` edge headers (`cf-cache-status`, `cf-ray`),
13:   WAF events in dashboard before blaming origin. Purge cache per-path after
14:   deploys, never "purge everything" on shared zones without asking.
