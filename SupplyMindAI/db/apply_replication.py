"""Apply db/schema.sql then db/seed.sql using get_connection_string() from .env."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.supabase_client import get_connection_string  # noqa: E402

try:
    import psycopg2
except ImportError:
    print("pip install psycopg2-binary", file=sys.stderr)
    raise SystemExit(1)


def _statements(sql: str) -> list[str]:
    """Split on ';' outside single-quoted strings (Postgres '' escapes)."""
    lines = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    blob = "\n".join(lines)
    out: list[str] = []
    buf: list[str] = []
    in_quote = False
    i = 0
    while i < len(blob):
        ch = blob[i]
        if ch == "'" and in_quote:
            if i + 1 < len(blob) and blob[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_quote = False
            buf.append(ch)
            i += 1
            continue
        if ch == "'" and not in_quote:
            in_quote = True
            buf.append(ch)
            i += 1
            continue
        if ch == ";" and not in_quote:
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt if stmt.endswith(";") else stmt + ";")
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail if tail.endswith(";") else tail + ";")
    return out


def main() -> None:
    db_dir = Path(__file__).resolve().parent
    for name in ("schema.sql", "seed.sql"):
        path = db_dir / name
        if not path.is_file():
            print(f"Missing {path}", file=sys.stderr)
            raise SystemExit(1)
    conn = psycopg2.connect(get_connection_string())
    try:
        for name in ("schema.sql", "seed.sql"):
            stmts = _statements((db_dir / name).read_text(encoding="utf-8"))
            with conn.cursor() as cur:
                for s in stmts:
                    cur.execute(s.rstrip().rstrip(";"))
            conn.commit()
            print(f"OK: {name} ({len(stmts)} statements)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    conn2 = psycopg2.connect(get_connection_string())
    try:
        with conn2.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
            )
            n = cur.fetchone()[0]
        print(f"Verify: {n} public base tables")
    finally:
        conn2.close()


if __name__ == "__main__":
    main()
