---
name: postgres
description: PostgreSQL work. Use for queries, schema inspection, migrations, dumps, or debugging app DBs (usually inside compose projects).
---

# Postgres

```bash
# via compose (preferred — matches project env, no local port needed)
docker compose exec -T postgres psql $DATABASE_URL -c '\dt'
docker compose exec -T postgres psql $DATABASE_URL -c 'SELECT ...' 
# direct (dev ports usually bound to 127.0.0.1 — see project .env)
psql "host=127.0.0.1 port=5432 dbname=app user=postgres"
```

## Rules
- Default to **read-only**: `SELECT`, `\d`, `EXPLAIN ANALYZE`. Any
  `INSERT/UPDATE/DELETE/DDL` needs explicit user confirmation, and a backup
  (`pg_dump`) first on non-dev databases.
- Connection strings live in the project's `.env` — never print secrets to
  chat beyond what's needed, never commit them.
- Migrations run through the project's own path (`migrate` one-shot
  containers, `prisma migrate`, `alembic`), not hand-applied DDL — unless the
  project has no migration story.
- Multi-DB setups (app + geo/postgis + per-platform DBs): confirm which
  database before every write.
