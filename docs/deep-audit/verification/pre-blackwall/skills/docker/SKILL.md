1: ---
2: name: docker
3: description: Docker and docker-compose work. Use when writing or editing Dockerfiles, compose files, debugging containers, networks, volumes, or deploying containerized services. Encodes the milestone-core compose conventions.
4: ---
5: 
6: # Docker / Compose conventions
7: 
8: ## Project layout (milestone-core pattern)
9: - `docker-compose.yml` = production base. `docker-compose.dev.yml` = dev
10:   overlay, selected via `COMPOSE_FILE` in `.env` (dev) or base-only (prod).
11: - Root `.env` is the single source of truth for compose interpolation AND
12: [CREDENTIAL-RELATED LINE OMITTED]
13: [CREDENTIAL-RELATED LINE OMITTED]
14: [CREDENTIAL-RELATED LINE OMITTED]
15:   infra-side DB bootstrap vars, which must match the app envs.
16: 
17: ## Service patterns
18: - One-shot containers for migrations/setup: `*-migrate` (talks to postgres
19:   directly, bypassing the pooler), `minio-setup` (bucket bootstrap). Gate
20:   dependents with `depends_on` health/complete conditions.
21: - Fixed `container_name: milestone-*` + `COMPOSE_PROJECT_NAME` prefixes all
22:   volumes/networks. Parallel streams must use isolated containers or their own
23:   `COMPOSE_PROJECT_NAME` — never stop shared compose services.
24: - Logs: json-file rotation (`10m x3`) plus host bind for app logs.
25: 
26: ## Networking
27: - Internal bridge nets per tier (`data-net`, `db-net`, …); only the edge
28:   (nginx/web) publishes ports. Prod publishes 80/443 only (+ monitoring on a
29:   tailnet IP). Dev publishes everything on `127.0.0.1`.
30: - Nginx: one vhost/conf per site, shared `-locations.conf` snippets, fail
31:   closed (missing `ssl_certificate` must not kill nginx — install vhosts
32:   conditionally). Certs via `tools/issue-*-cert.sh` (certbot webroot) + reload.
33: 
34: ## When debugging
35: 1. `docker compose ps` + `docker compose logs --tail=50 <svc>` first.
36: 2. `docker compose config` to verify interpolation before `up`.
37: 3. Never `down -v` on shared/data volumes without explicit confirmation.
