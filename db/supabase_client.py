"""
Database client for SupplyMind Supabase (Postgres).
Uses psycopg2. Connection string resolution (first set wins):

  POSTGRES_CONNECTION_STRING — repo default
  DIRECT_URL — Supabase Connect → ORM “Direct connection” (session pooler, port 5432)
  DATABASE_URL — Supabase ORM “Connection pooling” (transaction pooler, port 6543)

Supabase adds ?pgbouncer=true on the :6543 URI; libpq/psycopg2 reject that parameter — we strip it.
"""
import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

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


def normalize_postgres_uri(uri: str) -> str:
    """Drop query keys that psycopg2/libpq do not accept (e.g. pgbouncer from Supabase DATABASE_URL)."""
    if not uri or "pgbouncer" not in uri.lower():
        return uri
    u = uri.strip().strip('"').strip("'")
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]
    p = urlparse(u)
    qs = parse_qs(p.query, keep_blank_values=True)
    qs.pop("pgbouncer", None)
    new_q = urlencode(qs, doseq=True)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))


def get_connection_string() -> str:
    """Get Postgres connection string from env."""
    _load_env()
    url = (
        os.environ.get("POSTGRES_CONNECTION_STRING")
        or os.environ.get("DIRECT_URL")
        or os.environ.get("DATABASE_URL")
    )
    if not url:
        raise ValueError(
            "Set POSTGRES_CONNECTION_STRING, DIRECT_URL, or DATABASE_URL in .env. "
            "Supabase: Connect → ORM tab (DIRECT_URL = session pooler :5432; DATABASE_URL = pooler :6543)."
        )
    if "postgresql://" not in url and "postgres://" not in url:
        url = f"postgresql://{url}"
    return normalize_postgres_uri(url)


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
