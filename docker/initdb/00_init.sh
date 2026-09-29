#!/bin/sh
# Runs once, automatically, the first time the postgres container starts
# against an EMPTY data directory (Postgres's own docker-entrypoint-initdb.d
# convention — it never re-runs against an already-initialized volume, so
# this can never destroy or duplicate-apply against existing data).
#
# Only enables pgvector here. It does NOT run db/*.sql automatically —
# verified by an actual failed run that db/003_sodir_knowledge_layer.sql
# (and everything after it) ALTERs/references core.wellbore,
# subsurface.formation, subsurface.formation_top, subsurface.log_curve,
# and subsurface.log_measurement, none of which are created by ANY file
# in this repository (confirmed: no db/*.sql, no Python script, creates
# `core.*` or the base `subsurface.formation*`/`log_*` tables — migration
# 003's own docstring says they "already exist" in the environment it was
# written against). That foundation was created manually, outside version
# control, at some point in this project's history, and running
# db/003 onward against a database that doesn't already have it fails with
# `ERROR: schema "subsurface" does not exist` / `relation ... does not
# exist` — exactly what happened when this script first tried it.
#
# See docs/docker.md "Database initialization" for the two real options:
# restoring a pg_dump of an already-complete instance (recommended, and
# what this project's own Docker verification used), or manually applying
# db/*.sql (still mounted at /docker-entrypoint-initdb.d/db-migrations,
# just not auto-run) against a database where the foundation already
# exists some other way.
set -e

echo "[initdb] enabling pgvector extension..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "[initdb] pgvector enabled. Schema/data are NOT created automatically —"
echo "[initdb] see docs/docker.md 'Database initialization' for the two"
echo "[initdb] real options (pg_dump restore, or manual db/*.sql apply onto"
echo "[initdb] a database that already has the core/subsurface foundation)."
