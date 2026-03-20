# beacon_safe_database (Postgres)

This container provides the Beacon-Safe Postgres database with a minimal schema and seed data.

## Contents
- `schema/001_init.sql` - Minimal schema (users, sessions, audit_log)
- `migrations/` - Placeholder for future migrations (kept for manifest compatibility)
- `seed/001_seed.sql` - Seed data (a demo user)
- `scripts/init_db.sh` - Optional helper to initialize a local Postgres using `psql`

## Notes
- The Beacon-Safe backend is designed to be tolerant of the DB not being critical for mock auth.
- This DB container is intended to be startable as a Postgres service via the platform manifest/runtime.
- If you are running this manually, ensure you have a Postgres instance and a valid connection string.
  Then run the SQL in `schema/` and `seed/` in order.

## Environment
Connection details are expected to be provided by the runtime environment.
Do not hardcode credentials in code or SQL.
