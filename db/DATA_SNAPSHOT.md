# SupplyMind database snapshot (readable copy)

This folder holds a **human-readable** picture of the synthetic demo data plus **machine-friendly** files so you can recreate the same database in **any** new Supabase project (or another Postgres).

## Replicate in a new Supabase project (recommended)

1. **Create tables** — In Supabase → **SQL Editor**, run the full contents of [`schema.sql`](schema.sql).
2. **Load rows** — Either:
   - run [`seed.sql`](seed.sql) in **SQL Editor** (timestamps use `NOW()`, so data stays “fresh”), **or**
   - import the CSVs in [`csv/`](csv/) from the **Table Editor** (Import data) in this order: `hubs` → `shipments` → `stops` → `risks` → `insights`.  
     The CSVs use **fixed UTC times** (reference instant **2026-04-04 18:00:00+00**) so the snapshot is reproducible in docs and git.

3. Point your app’s **`.env`** at the new project with `POSTGRES_CONNECTION_STRING`.

## Files in this folder

| File | Purpose |
|------|---------|
| `schema.sql` | `CREATE TABLE` + indexes |
| `seed.sql` | Same logical rows as the CSVs, with `NOW()`-relative timestamps |
| `csv/*.csv` | One file per table for import or spreadsheets |
| `DATA_SNAPSHOT.md` | This document + markdown tables (below) |
| `DATA_SNAPSHOT.txt` | Plain-text, tab-separated copy of the CSVs for quick reading |

## Hubs

| hub_name | lat | lon | max_capacity | current_load | status |
|----------|-----|-----|--------------|--------------|--------|
| Chicago-Main | 41.8781 | -87.6298 | 120 | 78 | Open |
| Dallas-Hub | 32.7767 | -96.797 | 90 | 85 | Congested |
| Atlanta-South | 33.749 | -84.388 | 100 | 55 | Open |
| NYC-Port | 40.7128 | -74.006 | 150 | 120 | Open |
| Phoenix-West | 33.4484 | -112.074 | 80 | 40 | Open |

## Shipments

| shipment_id | material_type | priority_level | total_stops | current_stop_index | status |
|-------------|---------------|----------------|-------------|-------------------|--------|
| SHIP-001 | Medical Supplies | 9 | 4 | 2 | In Transit |
| SHIP-002 | Electronics | 6 | 3 | 3 | Delivered |
| SHIP-003 | Industrial Parts | 7 | 5 | 1 | In Transit |
| SHIP-004 | Retail Goods | 4 | 3 | 2 | In Transit |
| SHIP-005 | Cold Chain Food | 10 | 4 | 4 | Delivered |

`final_deadline` values: see `csv/shipments.csv` or `seed.sql` (relative to load time in `seed.sql`; fixed times in CSV).

## Risks

| risk_id | hub_name | category | severity | est_delay_hrs |
|---------|----------|----------|----------|---------------|
| RISK-001 | Dallas-Hub | Weather | 7 | 4.5 |
| RISK-002 | Dallas-Hub | Traffic | 5 | 2.0 |
| RISK-003 | Chicago-Main | Labor | 4 | 1.5 |
| RISK-004 | NYC-Port | Weather | 6 | 3.0 |
| RISK-005 | Phoenix-West | Traffic | 3 | 1.0 |

## Insights

| insight_id | shipment_id | flag_status | reasoning | confidence |
|------------|---------------|-------------|-----------|------------|
| insight_SHIP-001 | SHIP-001 | Delayed | Weather and congestion at Dallas-Hub. | 7 |
| insight_SHIP-003 | SHIP-003 | On Time | Route clear; hubs within capacity. | 8 |
| insight_SHIP-004 | SHIP-004 | On Time | Minor delay absorbed at stop 2. | 6 |

`predicted_arrival` timestamps: see `csv/insights.csv`.

## Stops

There are **19** stop rows. The full list is easiest to read in **`csv/stops.csv`** or **`DATA_SNAPSHOT.txt`** (too wide for a comfortable markdown table here).

## Copying someone else’s *live* Supabase data

This snapshot matches **this repository’s** demo seed. To duplicate **another** project’s real contents, use a Postgres dump (e.g. `pg_dump`) or Supabase backup/restore from that project—not these files alone.
