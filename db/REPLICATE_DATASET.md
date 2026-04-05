# Replicate the SupplyMind dataset (for you or Cursor)

Use this when setting up a **new Supabase project** or a **fresh clone** of the repo so the app has the same tables and demo rows.

## Prerequisites

- A Supabase project (empty or new database).
- This repository cloned locally.
- **Do not** commit secrets. Keep `POSTGRES_CONNECTION_STRING` only in `.env` (already gitignored).

## Step 1 — Create tables and load **all** data (easiest: one file)

**Option A — Complete database in one paste (recommended)**

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project → **SQL Editor**.
2. Open **`db/full_database.sql`**, copy **everything**, paste, **Run**.  
   This **drops** existing SupplyMind tables if present, recreates them, and inserts **every row** with fixed timestamps.

**Option B — Schema only, then data separately**

1. Run **`db/schema.sql`** in SQL Editor (creates empty tables).
2. Continue with Step 2 below.

## Step 2 — Load data (pick one method)

Skip this if you already ran **`full_database.sql`** in Step 1 Option A.

### Method A — SQL seed (relative dates)

1. In **SQL Editor**, open **`db/seed.sql`**, copy all, paste, **Run**.
2. Rows use `NOW()` so deadlines and stop times stay realistic over time.

### Method B — CSV import (fixed timestamps for docs / reproducibility)

1. Ensure Step 1 is done (empty tables or first-time load).
2. Supabase → **Table Editor** → open **`hubs`** → **Insert** → **Import data from CSV** → choose **`db/csv/hubs.csv`** (match column names).
3. Repeat in this **exact order** (foreign keys):  
   **`hubs`** → **`shipments`** → **`stops`** → **`risks`** → **`insights`**.
4. Use the matching file under **`db/csv/`** for each table.

If a table already has rows, clear it first (or use a new project) to avoid duplicates.

## Step 3 — Point the app at this database

1. Supabase → **Project Settings** → **Connect** (or **Database**) → copy the **Postgres URI**.
2. In the repo root, create or edit **`.env`**:

   ```env
   POSTGRES_CONNECTION_STRING=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
   ```

   Replace with your real URI and password from the dashboard.

3. Run the app per the main README (e.g. `py -m shiny run SupplyMindAI/app.py`).

## Reference files in `db/`

| File | Role |
|------|------|
| **`full_database.sql`** | **Complete DB:** DROP + CREATE + **all** INSERTs (single run) |
| `schema.sql` | Table definitions only (`CREATE IF NOT EXISTS`) |
| `seed.sql` | Inserts with `NOW()`-relative times |
| `csv/*.csv` | Same logical data, fixed UTC times (Table Editor import) |
| `DATA_SNAPSHOT.md` | Human-readable: every table, row, column |
| `DATA_SNAPSHOT.txt` | Tab-separated sections |
| `live_complete_dump.sql` | (optional) generated from **your** live DB — see `scripts/dump_supplymind_to_sql.py` |
| `copy_from_peer.py` | Copy **`public`** schema from friend’s Postgres → yours via `pg_dump` / `pg_restore` (see below) |

## Copy from a friend’s Supabase (live `public` schema)

Use only with the database owner’s permission.

1. Add to **`.env`** (never commit; **do not paste full URIs into AI chat** — passwords get logged):
   - `SOURCE_POSTGRES_CONNECTION_STRING` — friend’s **direct** URI (port **5432**, `db.<ref>.supabase.co`).
   - `POSTGRES_CONNECTION_STRING` — **your** URI (same style).
2. Install PostgreSQL **client** tools (`pg_dump`, `pg_restore` on `PATH`).
3. From repo root: `py db/copy_from_peer.py`  
   If restore fails because objects already exist: new empty project, or `py db/copy_from_peer.py --clean` (destructive on target `public`).

Only **`public`** is copied (not `auth`, `storage`, etc.).

## Verify

In **SQL Editor**:

```sql
SELECT COUNT(*) FROM hubs;
SELECT COUNT(*) FROM shipments;
SELECT COUNT(*) FROM stops;
```

Expect: **5** hubs, **5** shipments, **19** stops (with the default seed/CSV).

## For Cursor in a new chat

Paste the block below so the assistant knows what to do without re-deriving it:

---

**Cursor prompt (copy from here):**

```
This repo includes database replication assets under db/.

To replicate the COMPLETE SupplyMind database (schema + all rows) in Supabase:
1. Run db/full_database.sql once in SQL Editor (DROP/CREATE + all INSERTs). OR use db/schema.sql then db/seed.sql or db/csv/*.csv per db/REPLICATE_DATASET.md.
2. Set POSTGRES_CONNECTION_STRING in local .env (never commit .env).

To export live DB to SQL: py scripts/dump_supplymind_to_sql.py

Details: db/REPLICATE_DATASET.md
```

---
