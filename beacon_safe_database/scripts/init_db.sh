#!/usr/bin/env bash
set -euo pipefail

# Initializes the Beacon-Safe database schema and seed data.
#
# Contract:
# - Input: DATABASE_URL must be set (e.g., postgresql://user:pass@host:5432/dbname)
# - Output: applies schema and seed SQL files in order
# - Errors: exits non-zero on any psql failure
# - Side effects: creates tables and inserts seed user if not present

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set."
  echo "Example: export DATABASE_URL='postgresql://user:pass@localhost:5432/beacon_safe'"
  exit 1
fi

echo "Applying schema..."
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "./schema/001_init.sql"

echo "Applying seed..."
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "./seed/001_seed.sql"

echo "Done."
