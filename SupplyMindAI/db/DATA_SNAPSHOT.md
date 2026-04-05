# SupplyMind — complete reference data (all tables, all columns, all rows)

This file is a **full** human-readable copy of the canonical demo database (nothing omitted).  
**Reference time for timestamps:** `2026-04-04 18:00:00+00` (UTC). Empty table cells = **SQL NULL**.

**One-shot SQL (schema + every value in one file):** [`full_database.sql`](full_database.sql) — paste once in Supabase SQL Editor.

For other import paths see [`REPLICATE_DATASET.md`](REPLICATE_DATASET.md). To export **whatever is currently in your live Supabase** to SQL, run `py scripts/dump_supplymind_to_sql.py` from the repo root (uses `.env`).

---

## Table: `hubs`

| hub_name | lat | lon | max_capacity | current_load | status |
|----------|-----|-----|--------------|--------------|--------|
| Chicago-Main | 41.8781 | -87.6298 | 120 | 78 | Open |
| Dallas-Hub | 32.7767 | -96.797 | 90 | 85 | Congested |
| Atlanta-South | 33.749 | -84.388 | 100 | 55 | Open |
| NYC-Port | 40.7128 | -74.006 | 150 | 120 | Open |
| Phoenix-West | 33.4484 | -112.074 | 80 | 40 | Open |

---

## Table: `shipments`

| shipment_id | material_type | priority_level | total_stops | current_stop_index | final_deadline | status |
|-------------|---------------|----------------|-------------|-------------------|----------------|--------|
| SHIP-001 | Medical Supplies | 9 | 4 | 2 | 2026-04-06 18:00:00+00 | In Transit |
| SHIP-002 | Electronics | 6 | 3 | 3 | 2026-04-02 18:00:00+00 | Delivered |
| SHIP-003 | Industrial Parts | 7 | 5 | 1 | 2026-04-07 18:00:00+00 | In Transit |
| SHIP-004 | Retail Goods | 4 | 3 | 2 | 2026-04-05 18:00:00+00 | In Transit |
| SHIP-005 | Cold Chain Food | 10 | 4 | 4 | 2026-04-04 12:00:00+00 | Delivered |

---

## Table: `stops`

| stop_id | shipment_id | stop_number | hub_name | planned_arrival | actual_arrival | planned_departure | actual_departure |
|---------|-------------|-------------|----------|-----------------|----------------|-------------------|------------------|
| ST-S001-1 | SHIP-001 | 1 | Chicago-Main | 2026-04-03 12:00:00+00 | 2026-04-03 12:00:00+00 | 2026-04-03 13:00:00+00 | 2026-04-03 13:00:00+00 |
| ST-S001-2 | SHIP-001 | 2 | Dallas-Hub | 2026-04-04 12:00:00+00 | 2026-04-04 11:00:00+00 | 2026-04-04 14:00:00+00 | 2026-04-04 13:00:00+00 |
| ST-S001-3 | SHIP-001 | 3 | Phoenix-West | 2026-04-05 06:00:00+00 | | 2026-04-05 08:00:00+00 | |
| ST-S001-4 | SHIP-001 | 4 | NYC-Port | 2026-04-06 06:00:00+00 | | 2026-04-06 08:00:00+00 | |
| ST-S002-1 | SHIP-002 | 1 | Atlanta-South | 2026-04-01 10:00:00+00 | 2026-04-01 10:00:00+00 | 2026-04-01 11:00:00+00 | 2026-04-01 11:00:00+00 |
| ST-S002-2 | SHIP-002 | 2 | Dallas-Hub | 2026-04-02 16:00:00+00 | 2026-04-02 15:00:00+00 | 2026-04-02 18:00:00+00 | 2026-04-02 17:00:00+00 |
| ST-S002-3 | SHIP-002 | 3 | Chicago-Main | 2026-04-03 22:00:00+00 | 2026-04-03 22:00:00+00 | 2026-04-02 18:00:00+00 | 2026-04-02 18:00:00+00 |
| ST-S003-1 | SHIP-003 | 1 | NYC-Port | 2026-04-04 14:00:00+00 | 2026-04-04 14:00:00+00 | 2026-04-04 16:00:00+00 | 2026-04-04 16:00:00+00 |
| ST-S003-2 | SHIP-003 | 2 | Chicago-Main | 2026-04-05 02:00:00+00 | | 2026-04-05 04:00:00+00 | |
| ST-S003-3 | SHIP-003 | 3 | Dallas-Hub | 2026-04-05 18:00:00+00 | | 2026-04-05 20:00:00+00 | |
| ST-S003-4 | SHIP-003 | 4 | Phoenix-West | 2026-04-06 10:00:00+00 | | 2026-04-06 12:00:00+00 | |
| ST-S003-5 | SHIP-003 | 5 | Atlanta-South | 2026-04-07 02:00:00+00 | | 2026-04-07 04:00:00+00 | |
| ST-S004-1 | SHIP-004 | 1 | Phoenix-West | 2026-04-04 06:00:00+00 | 2026-04-04 06:00:00+00 | 2026-04-04 07:00:00+00 | 2026-04-04 07:00:00+00 |
| ST-S004-2 | SHIP-004 | 2 | Dallas-Hub | 2026-04-04 16:00:00+00 | 2026-04-04 15:00:00+00 | 2026-04-04 20:00:00+00 | |
| ST-S004-3 | SHIP-004 | 3 | Chicago-Main | 2026-04-05 12:00:00+00 | | 2026-04-05 14:00:00+00 | |
| ST-S005-1 | SHIP-005 | 1 | Chicago-Main | 2026-03-31 18:00:00+00 | 2026-03-31 18:00:00+00 | 2026-03-31 19:00:00+00 | 2026-03-31 19:00:00+00 |
| ST-S005-2 | SHIP-005 | 2 | Atlanta-South | 2026-04-01 18:00:00+00 | 2026-04-01 18:00:00+00 | 2026-04-01 19:00:00+00 | 2026-04-01 19:00:00+00 |
| ST-S005-3 | SHIP-005 | 3 | NYC-Port | 2026-04-02 18:00:00+00 | 2026-04-02 18:00:00+00 | 2026-04-02 19:00:00+00 | 2026-04-02 19:00:00+00 |
| ST-S005-4 | SHIP-005 | 4 | Dallas-Hub | 2026-04-04 10:00:00+00 | 2026-04-04 10:00:00+00 | 2026-04-04 12:00:00+00 | 2026-04-04 12:00:00+00 |

---

## Table: `risks`

| risk_id | hub_name | category | severity | est_delay_hrs |
|---------|----------|----------|----------|---------------|
| RISK-001 | Dallas-Hub | Weather | 7 | 4.5 |
| RISK-002 | Dallas-Hub | Traffic | 5 | 2.0 |
| RISK-003 | Chicago-Main | Labor | 4 | 1.5 |
| RISK-004 | NYC-Port | Weather | 6 | 3.0 |
| RISK-005 | Phoenix-West | Traffic | 3 | 1.0 |

---

## Table: `insights`

| insight_id | shipment_id | flag_status | predicted_arrival | reasoning | confidence |
|------------|-------------|-------------|---------------------|-----------|------------|
| insight_SHIP-001 | SHIP-001 | Delayed | 2026-04-06 10:00:00+00 | Weather and congestion at Dallas-Hub. | 7 |
| insight_SHIP-003 | SHIP-003 | On Time | 2026-04-07 14:00:00+00 | Route clear; hubs within capacity. | 8 |
| insight_SHIP-004 | SHIP-004 | On Time | 2026-04-05 16:00:00+00 | Minor delay absorbed at stop 2. | 6 |

---

## Plain-text twin

The same rows in **tab-separated** form (one section per table) are in **`DATA_SNAPSHOT.txt`** next to this file.

---

## Row counts

| Table | Rows |
|-------|------|
| hubs | 5 |
| shipments | 5 |
| stops | 19 |
| risks | 5 |
| insights | 3 |
