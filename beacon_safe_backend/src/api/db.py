import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import psycopg

logger = logging.getLogger("beacon_safe_backend.db")


@dataclass(frozen=True)
class DbConfig:
    """
    Database configuration normalized at the boundary.

    Contract:
    - Input source: environment variables only
    - Required:
        - DATABASE_URL: Postgres connection string (e.g. postgresql://user:pass@host:5432/db)
    - Output: validated DbConfig
    - Errors: ValueError if required configuration missing
    """

    database_url: str


# PUBLIC_INTERFACE
def load_db_config() -> Optional[DbConfig]:
    """Load DB config from environment.

    Contract:
    - Output:
        - DbConfig if DATABASE_URL set and non-empty
        - None if DATABASE_URL missing (DB treated as optional for this MVP)
    - Side effects: none
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return None
    return DbConfig(database_url=database_url)


# PUBLIC_INTERFACE
def try_connect_once(cfg: DbConfig) -> Tuple[bool, str]:
    """Attempt a single DB connection and return a (ok, message) tuple.

    Contract:
    - Inputs: DbConfig with database_url
    - Output:
        - (True, "ok") on successful connection + SELECT 1
        - (False, "<error summary>") on failure
    - Side effects:
        - Opens and closes a single DB connection
    """
    try:
        # Keep this minimal: connect + simple ping.
        with psycopg.connect(cfg.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                _ = cur.fetchone()
        return True, "ok"
    except Exception as e:  # noqa: BLE001 - boundary returns diagnostic string
        logger.warning("DB connectivity check failed: %s", e)
        return False, f"{type(e).__name__}: {e}"
