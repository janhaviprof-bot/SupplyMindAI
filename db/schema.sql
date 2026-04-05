-- SupplyMind AI — database schema (PostgreSQL / Supabase)
-- Matches SupplyMindAI/docs/context.md and queries in analysis/pipeline.py,
-- analysis/optimization_pipeline.py.
--
-- Usage: Supabase → SQL Editor → paste → Run.
-- Then run seed.sql for demo rows (optional but recommended).
-- Human-readable / full SQL: DATA_SNAPSHOT.md, DATA_SNAPSHOT.txt, csv/*.csv, full_database.sql

-- Order: hubs → shipments → risks, stops, insights (FKs)

CREATE TABLE IF NOT EXISTS hubs (
    hub_name TEXT PRIMARY KEY,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    max_capacity INTEGER NOT NULL,
    current_load INTEGER NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id TEXT PRIMARY KEY,
    material_type TEXT NOT NULL,
    priority_level INTEGER NOT NULL,
    total_stops INTEGER NOT NULL,
    current_stop_index INTEGER NOT NULL,
    final_deadline TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stops (
    stop_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments (shipment_id) ON DELETE CASCADE,
    stop_number INTEGER NOT NULL,
    hub_name TEXT NOT NULL REFERENCES hubs (hub_name),
    planned_arrival TIMESTAMPTZ,
    actual_arrival TIMESTAMPTZ,
    planned_departure TIMESTAMPTZ,
    actual_departure TIMESTAMPTZ,
    UNIQUE (shipment_id, stop_number)
);

CREATE TABLE IF NOT EXISTS risks (
    risk_id TEXT PRIMARY KEY,
    hub_name TEXT NOT NULL REFERENCES hubs (hub_name) ON DELETE CASCADE,
    category TEXT NOT NULL,
    severity INTEGER NOT NULL,
    est_delay_hrs DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS insights (
    insight_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments (shipment_id) ON DELETE CASCADE,
    flag_status TEXT NOT NULL,
    predicted_arrival TIMESTAMPTZ,
    reasoning TEXT,
    confidence INTEGER
);

CREATE INDEX IF NOT EXISTS idx_stops_shipment_id ON stops (shipment_id);
CREATE INDEX IF NOT EXISTS idx_stops_hub_name ON stops (hub_name);
CREATE INDEX IF NOT EXISTS idx_risks_hub_name ON risks (hub_name);
CREATE INDEX IF NOT EXISTS idx_insights_shipment_id ON insights (shipment_id);
