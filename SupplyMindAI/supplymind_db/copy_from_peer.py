"""
Copy the public schema from another Postgres (e.g. friend's Supabase) into yours.

Preferred: pg_dump / pg_restore (PostgreSQL client tools on PATH).
Fallback: psycopg2 (same dependency as the app) — copies **data** for tables that exist
on both sides (common columns only), TRUNCATE those tables on the target first.

Set in repo root .env (gitignored) — do NOT paste these URIs into chat:

  SOURCE_POSTGRES_CONNECTION_STRING=postgresql://postgres:...@db.FRIEND_REF.supabase.co:5432/postgres
  POSTGRES_CONNECTION_STRING=postgresql://postgres:...@db.YOUR_REF.supabase.co:5432/postgres

Use direct db.*.supabase.co:5432 URIs when possible. You need permission from the DB owner.

Run from repo root:

  py SupplyMindAI/db/copy_from_peer.py
  py SupplyMindAI/db/copy_from_peer.py --clean   # only affects pg_restore path

Or from the inner SupplyMindAI folder: py db/copy_from_peer.py

Only the public schema is considered (not auth/storage/realtime).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    for base in (ROOT, ROOT.parent):
        env_path = base / ".env"
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
        return


def _norm_table(regclass_or_name: str) -> str:
    s = regclass_or_name.strip().strip('"')
    if "." in s:
        return s.split(".")[-1].strip('"')
    return s


def _list_public_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY c.relname
            """
        )
        return [r[0] for r in cur.fetchall()]


def _table_columns(conn, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return [r[0] for r in cur.fetchall()]


def _fk_edges_public(conn) -> list[tuple[str, str]]:
    """(referenced_table, referencing_table) — parent first for insert order."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT confrelid::regclass::text, conrelid::regclass::text
            FROM pg_constraint
            WHERE contype = 'f'
              AND connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            """
        )
        out = []
        for parent, child in cur.fetchall():
            p, c = _norm_table(parent), _norm_table(child)
            if p != c:
                out.append((p, c))
        return out


def _topo_sort_tables(tables: set[str], edges: list[tuple[str, str]]) -> list[str]:
    """Parents before children."""
    children_of: dict[str, set[str]] = defaultdict(set)
    parents_of: dict[str, set[str]] = defaultdict(set)
    for parent, child in edges:
        if parent in tables and child in tables:
            children_of[parent].add(child)
            parents_of[child].add(parent)
    in_degree = {t: len(parents_of[t]) for t in tables}
    q = deque(sorted(t for t in tables if in_degree[t] == 0))
    order: list[str] = []
    while q:
        t = q.popleft()
        order.append(t)
        for c in sorted(children_of[t]):
            in_degree[c] -= 1
            if in_degree[c] == 0:
                q.append(c)
    if len(order) != len(tables):
        raise RuntimeError("Circular FKs in public schema; use pg_dump/pg_restore instead.")
    return order


def _psycopg2_connect(label: str, dsn: str):
    try:
        import psycopg2
    except ImportError as e:
        print("Install psycopg2-binary: pip install psycopg2-binary", file=sys.stderr)
        raise SystemExit(1) from e
    try:
        return psycopg2.connect(dsn)
    except psycopg2.OperationalError as e:
        err = str(e).lower()
        if "could not translate host name" in err or "name or service not known" in err:
            print(
                f"\nDNS/connect failed for {label}. On Windows, direct `db.<ref>.supabase.co` often fails in Python.\n"
                "Use the Session pooler URI from Supabase Dashboard → Connect (port 5432, user postgres.<ref>).\n"
                "Set both SOURCE_POSTGRES_CONNECTION_STRING and POSTGRES_CONNECTION_STRING to pooler URIs if needed.\n",
                file=sys.stderr,
            )
        raise


def _copy_via_psycopg2(source_dsn: str, target_dsn: str) -> None:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import execute_batch

    src = _psycopg2_connect("SOURCE", source_dsn)
    tgt = _psycopg2_connect("TARGET (POSTGRES_CONNECTION_STRING)", target_dsn)
    try:
        src_tables = set(_list_public_tables(src))
        tgt_tables = set(_list_public_tables(tgt))
        common = sorted(src_tables & tgt_tables)
        if not common:
            print(
                "No common public base tables between SOURCE and TARGET.\n"
                "The psycopg2 path only copies rows into tables that already exist on BOTH sides.\n"
                "If TARGET is empty: run db/schema.sql (or db/full_database.sql / db/replicate_snapshot_full.sql)\n"
                "in YOUR Supabase SQL Editor first, then run this script again.\n",
                file=sys.stderr,
            )
            print(f"  SOURCE public tables ({len(src_tables)}): {', '.join(sorted(src_tables)) or '(none)'}", file=sys.stderr)
            print(f"  TARGET public tables ({len(tgt_tables)}): {', '.join(sorted(tgt_tables)) or '(none)'}", file=sys.stderr)
            raise SystemExit(1)

        missing_on_target = src_tables - tgt_tables
        if missing_on_target:
            print(
                "Warning: these tables exist only on SOURCE (skipped): "
                + ", ".join(sorted(missing_on_target)),
                file=sys.stderr,
            )

        edges = _fk_edges_public(src)
        order = _topo_sort_tables(set(common), edges)
        # Restrict to common tables while preserving order
        order = [t for t in order if t in common]

        with tgt.cursor() as cur:
            idents = [sql.Identifier(t) for t in order]
            cur.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(sql.SQL(", ").join(idents)))
        tgt.commit()

        total_rows = 0
        for tbl in order:
            scols = _table_columns(src, tbl)
            tcols = set(_table_columns(tgt, tbl))
            cols = [c for c in scols if c in tcols]
            if not cols:
                print(f"Skip {tbl}: no common columns.", file=sys.stderr)
                continue
            col_ids = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
            select_sql = sql.SQL("SELECT {} FROM {}").format(col_ids, sql.Identifier(tbl))
            with src.cursor() as sc:
                sc.execute(select_sql)
                rows = sc.fetchall()
            if not rows:
                continue
            placeholders = sql.SQL(", ").join(sql.Placeholder() * len(cols))
            ins = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(tbl), col_ids, placeholders
            )
            with tgt.cursor() as tc:
                execute_batch(tc, ins.as_string(tgt), rows, page_size=500)
            total_rows += len(rows)
            print(f"  {tbl}: {len(rows)} rows")

        tgt.commit()
        print(f"OK: psycopg2 copy — {len(order)} tables, {total_rows} rows total (public, common tables).")
    finally:
        src.close()
        tgt.close()


def _copy_via_pg_dump(source: str, target: str, clean: bool) -> None:
    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    assert pg_dump and pg_restore

    fd, dump_path = tempfile.mkstemp(suffix=".pgdump")
    os.close(fd)
    path = Path(dump_path)
    try:
        subprocess.run(
            [
                pg_dump,
                "--dbname",
                source,
                "--schema=public",
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(path),
            ],
            check=True,
        )
        cmd = [
            pg_restore,
            "--dbname",
            target,
            "--no-owner",
            "--no-acl",
            "--schema=public",
        ]
        if clean:
            cmd.append("--clean")
        cmd.append(str(path))
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(
            "pg_dump or pg_restore failed. If objects already exist on target, try --clean "
            "or run without pg_dump (script will use psycopg2 if you unset PATH to pg_dump).",
            file=sys.stderr,
        )
        raise SystemExit(e.returncode) from e
    finally:
        path.unlink(missing_ok=True)

    print("OK: public schema copied via pg_dump/pg_restore.")


def main() -> None:
    _load_env()
    source = (
        os.environ.get("SOURCE_POSTGRES_CONNECTION_STRING")
        or os.environ.get("SOURCE_DATABASE_URL")
        or os.environ.get("FRIEND_POSTGRES_CONNECTION_STRING")
    )
    target = (
        os.environ.get("POSTGRES_CONNECTION_STRING")
        or os.environ.get("DIRECT_URL")
        or os.environ.get("DATABASE_URL")
    )
    if not source or not target:
        print(
            "Missing source or target URI in .env.\n"
            "  Source (friend's DB): SOURCE_POSTGRES_CONNECTION_STRING=postgresql://postgres:...@db.THEIR_REF.supabase.co:5432/postgres\n"
            "  Target (your DB):     POSTGRES_CONNECTION_STRING=... OR DIRECT_URL=... OR DATABASE_URL=...\n"
            "Use Supabase Connect → ORM: DIRECT_URL (port 5432) for Python on Windows; add SOURCE line for peer copy.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from db.supabase_client import normalize_postgres_uri

    source = normalize_postgres_uri(source)
    target = normalize_postgres_uri(target)

    ap = argparse.ArgumentParser(description="Copy public schema peer → your Supabase.")
    ap.add_argument(
        "--clean",
        action="store_true",
        help="With pg_dump path only: pass --clean to pg_restore (destructive on target public).",
    )
    ap.add_argument(
        "--psycopg2-only",
        action="store_true",
        help="Skip pg_dump; copy overlapping tables with psycopg2 (data only, TRUNCATE first).",
    )
    args = ap.parse_args()

    if args.psycopg2_only:
        print("Using psycopg2 (TRUNCATE common tables on target, then copy rows)...")
        _copy_via_psycopg2(source, target)
        return

    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if pg_dump and pg_restore:
        _copy_via_pg_dump(source, target, args.clean)
        return

    print("pg_dump not on PATH — using psycopg2 fallback (TRUNCATE common tables, copy data)...")
    _copy_via_psycopg2(source, target)


if __name__ == "__main__":
    main()
