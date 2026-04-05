# Replicate the SupplyMind dataset (for you or Cursor)

Use this when setting up a **new Supabase project** or a **fresh clone** of the repo so the app has the same tables and demo rows.

## Prerequisites

- A Supabase project (empty or new database).
- This repository cloned locally.
- **Do not** commit secrets. Keep `POSTGRES_CONNECTION_STRING` only in `.env` (already gitignored).

## Step 1 — Create tables

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project → **SQL Editor**.
2. Open the file **`db/schema.sql`** from this repo.
3. Copy **the entire file**, paste into the SQL Editor, click **Run**.
4. Confirm there are no errors. You should have tables: `hubs`, `shipments`, `stops`, `risks`, `insights`.

## Step 2 — Load data (pick one method)

### Method A — SQL seed (recommended: relative dates)

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
| `schema.sql` | Table definitions |
| `seed.sql` | Inserts (Method A) |
| `csv/*.csv` | Same logical data, fixed UTC times (Method B) |
| `DATA_SNAPSHOT.md` | **Full** human-readable copy: every table, every row, every column |
| `DATA_SNAPSHOT.txt` | Same data, tab-separated (sections per table) |

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

To replicate the SupplyMind dataset in Supabase:
1. Run db/schema.sql in Supabase SQL Editor (creates tables).
2. Load data with EITHER db/seed.sql in SQL Editor OR import db/csv/*.csv via Table Editor in order: hubs, shipments, stops, risks, insights.
3. Set POSTGRES_CONNECTION_STRING in local .env from Supabase Connect → Postgres URI (never commit .env).

Details: db/REPLICATE_DATASET.md
```

---
