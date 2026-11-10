1: ---
2: name: postgres
3: description: PostgreSQL work. Use for queries, schema inspection, migrations, dumps, or debugging app DBs (usually inside compose projects).
4: ---
5: 
6: # Postgres
7: 
8: ```bash
9: # via compose (preferred — matches project env, no local port needed)
10: docker compose exec -T postgres psql $DATABASE_URL -c '\dt'
11: docker compose exec -T postgres psql $DATABASE_URL -c 'SELECT ...' 
12: # direct (dev ports usually bound to 127.0.0.1 — see project .env)
13: psql "host=127.0.0.1 port=5432 dbname=app user=postgres"
14: ```
15: 
16: ## Rules
17: - Default to **read-only**: `SELECT`, `\d`, `EXPLAIN ANALYZE`. Any
18:   `INSERT/UPDATE/DELETE/DDL` needs explicit user confirmation, and a backup
19:   (`pg_dump`) first on non-dev databases.
20: [CREDENTIAL-RELATED LINE OMITTED]
21:   chat beyond what's needed, never commit them.
22: - Migrations run through the project's own path (`migrate` one-shot
23:   containers, `prisma migrate`, `alembic`), not hand-applied DDL — unless the
24:   project has no migration story.
25: - Multi-DB setups (app + geo/postgis + per-platform DBs): confirm which
26:   database before every write.
