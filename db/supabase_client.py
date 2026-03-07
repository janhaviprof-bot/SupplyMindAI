"""
Database client for SupplyMind Supabase (Postgres).
Uses psycopg2 with POSTGRES_CONNECTION_STRING from .env.
"""
import os
from contextlib import contextmanager
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None


def _load_env():
    """Load .env from project root if present."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_connection_string() -> str:
    """Get Postgres connection string from env."""
    _load_env()
    url = os.environ.get("POSTGRES_CONNECTION_STRING") or os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError(
            "Set POSTGRES_CONNECTION_STRING or DATABASE_URL in .env. "
            "Get it from Supabase Dashboard → Project Settings → Database."
        )
    if "postgresql://" not in url and "postgres://" not in url:
        url = f"postgresql://{url}"
    return url


@contextmanager
def get_connection():
    """Context manager for a database connection. Yields a connection with RealDictCursor."""
    if psycopg2 is None:
        raise ImportError("Install psycopg2-binary: pip install psycopg2-binary")
    conn = psycopg2.connect(get_connection_string())
    try:
        yield conn
    finally:
        conn.close()


def execute_query(query: str, params=None, fetch=True):
    """
    Execute a query and optionally fetch results.
    Returns list of dicts when fetch=True, else None.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            conn.commit()
            return None


def execute_many(query: str, params_list: list):
    """Execute a query for each params tuple. No fetch."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for params in params_list:
                cur.execute(query, params)
            conn.commit()
