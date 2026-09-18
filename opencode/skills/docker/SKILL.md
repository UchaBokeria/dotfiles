---
name: docker
description: Docker and docker-compose work. Use when writing or editing Dockerfiles, compose files, debugging containers, networks, volumes, or deploying containerized services. Encodes the milestone-core compose conventions.
---

# Docker / Compose conventions

## Project layout (milestone-core pattern)
- `docker-compose.yml` = production base. `docker-compose.dev.yml` = dev
  overlay, selected via `COMPOSE_FILE` in `.env` (dev) or base-only (prod).
- Root `.env` is the single source of truth for compose interpolation AND
  `env_file:` for app services. `.env.example` is tracked with blanked secrets
  and must stay in sync — compose aborts on `${VAR?msg}` required secrets.
- Per-app secrets live in `source/<app>/.env`, never in root. Root holds only
  infra-side DB bootstrap vars, which must match the app envs.

## Service patterns
- One-shot containers for migrations/setup: `*-migrate` (talks to postgres
  directly, bypassing the pooler), `minio-setup` (bucket bootstrap). Gate
  dependents with `depends_on` health/complete conditions.
- Fixed `container_name: milestone-*` + `COMPOSE_PROJECT_NAME` prefixes all
  volumes/networks. Parallel streams must use isolated containers or their own
  `COMPOSE_PROJECT_NAME` — never stop shared compose services.
- Logs: json-file rotation (`10m x3`) plus host bind for app logs.

## Networking
- Internal bridge nets per tier (`data-net`, `db-net`, …); only the edge
  (nginx/web) publishes ports. Prod publishes 80/443 only (+ monitoring on a
  tailnet IP). Dev publishes everything on `127.0.0.1`.
- Nginx: one vhost/conf per site, shared `-locations.conf` snippets, fail
  closed (missing `ssl_certificate` must not kill nginx — install vhosts
  conditionally). Certs via `tools/issue-*-cert.sh` (certbot webroot) + reload.

## When debugging
1. `docker compose ps` + `docker compose logs --tail=50 <svc>` first.
2. `docker compose config` to verify interpolation before `up`.
3. Never `down -v` on shared/data volumes without explicit confirmation.
