"""
Apply schema + seed SQL to Supabase/Postgres using POSTGRES_CONNECTION_STRING,
DIRECT_URL, or DATABASE_URL from .env (same resolution as supplymind_db/supabase_client.py).

Usage (from repository root):
  py SupplyMindAI/supplymind_db/run_seeds.py
Or from the inner SupplyMindAI folder:
  py supplymind_db/run_seeds.py

Statements are split on semicolon + newline (safe for bundled seed files).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402

from supplymind_db.supabase_client import get_connection_string  # noqa: E402


def _strip_line_comments(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _split_statements(sql: str) -> list[str]:
    sql = _strip_line_comments(sql)
    parts = re.split(r";\s*\n", sql)
    out: list[str] = []
    for p in parts:
        s = p.strip()
        if s:
            out.append(s)
    return out


def _run_sql_file(conn, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    stmts = _split_statements(text)
    with conn.cursor() as cur:
        for i, st in enumerate(stmts, start=1):
            try:
                cur.execute(st + ";")
            except Exception as e:
                raise RuntimeError(
                    f"{path.name}: failed at statement {i}/{len(stmts)}: {e}\n"
                    f"--- snippet ---\n{st[:800]}..."
                ) from e


def main() -> None:
    files = [
        ROOT / "supplymind_db" / "schema.sql",
        ROOT / "supplymind_db" / "seed.sql",
        ROOT / "supplymind_db" / "seed_bulk_100.sql",
    ]
    missing = [p for p in files if not p.exists()]
    if missing:
        print("Missing files:", missing)
        sys.exit(1)

    dsn = get_connection_string()
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        for path in files:
            print(f"Applying {path.name} …")
            _run_sql_file(conn, path)
        print("Database populated successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
