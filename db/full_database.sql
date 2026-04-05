-- SupplyMind AI — COMPLETE database: schema + ALL rows in one file.
-- Run once in Supabase SQL Editor on an empty database (or after reset below).
-- Timestamps are fixed (reference: 2026-04-04 18:00:00+00 UTC), same as csv/*.csv.

-- Reset (removes existing SupplyMind tables if present)
DROP TABLE IF EXISTS insights CASCADE;
DROP TABLE IF EXISTS stops CASCADE;
DROP TABLE IF EXISTS risks CASCADE;
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS hubs CASCADE;

CREATE TABLE hubs (
    hub_name TEXT PRIMARY KEY,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    max_capacity INTEGER NOT NULL,
    current_load INTEGER NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE shipments (
    shipment_id TEXT PRIMARY KEY,
    material_type TEXT NOT NULL,
    priority_level INTEGER NOT NULL,
    total_stops INTEGER NOT NULL,
    current_stop_index INTEGER NOT NULL,
    final_deadline TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE stops (
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

CREATE TABLE risks (
    risk_id TEXT PRIMARY KEY,
    hub_name TEXT NOT NULL REFERENCES hubs (hub_name) ON DELETE CASCADE,
    category TEXT NOT NULL,
    severity INTEGER NOT NULL,
    est_delay_hrs DOUBLE PRECISION NOT NULL
);

CREATE TABLE insights (
    insight_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments (shipment_id) ON DELETE CASCADE,
    flag_status TEXT NOT NULL,
    predicted_arrival TIMESTAMPTZ,
    reasoning TEXT,
    confidence INTEGER
);

CREATE INDEX idx_stops_shipment_id ON stops (shipment_id);
CREATE INDEX idx_stops_hub_name ON stops (hub_name);
CREATE INDEX idx_risks_hub_name ON risks (hub_name);
CREATE INDEX idx_insights_shipment_id ON insights (shipment_id);

-- === ALL DATA (complete) ===

INSERT INTO hubs (hub_name, lat, lon, max_capacity, current_load, status) VALUES
    ('Chicago-Main', 41.8781, -87.6298, 120, 78, 'Open'),
    ('Dallas-Hub', 32.7767, -96.797, 90, 85, 'Congested'),
    ('Atlanta-South', 33.749, -84.388, 100, 55, 'Open'),
    ('NYC-Port', 40.7128, -74.006, 150, 120, 'Open'),
    ('Phoenix-West', 33.4484, -112.074, 80, 40, 'Open');

INSERT INTO shipments (shipment_id, material_type, priority_level, total_stops, current_stop_index, final_deadline, status) VALUES
    ('SHIP-001', 'Medical Supplies', 9, 4, 2, TIMESTAMPTZ '2026-04-06 18:00:00+00', 'In Transit'),
    ('SHIP-002', 'Electronics', 6, 3, 3, TIMESTAMPTZ '2026-04-02 18:00:00+00', 'Delivered'),
    ('SHIP-003', 'Industrial Parts', 7, 5, 1, TIMESTAMPTZ '2026-04-07 18:00:00+00', 'In Transit'),
    ('SHIP-004', 'Retail Goods', 4, 3, 2, TIMESTAMPTZ '2026-04-05 18:00:00+00', 'In Transit'),
    ('SHIP-005', 'Cold Chain Food', 10, 4, 4, TIMESTAMPTZ '2026-04-04 12:00:00+00', 'Delivered');

INSERT INTO stops (stop_id, shipment_id, stop_number, hub_name, planned_arrival, actual_arrival, planned_departure, actual_departure) VALUES
    ('ST-S001-1', 'SHIP-001', 1, 'Chicago-Main', TIMESTAMPTZ '2026-04-03 12:00:00+00', TIMESTAMPTZ '2026-04-03 12:00:00+00', TIMESTAMPTZ '2026-04-03 13:00:00+00', TIMESTAMPTZ '2026-04-03 13:00:00+00'),
    ('ST-S001-2', 'SHIP-001', 2, 'Dallas-Hub', TIMESTAMPTZ '2026-04-04 12:00:00+00', TIMESTAMPTZ '2026-04-04 11:00:00+00', TIMESTAMPTZ '2026-04-04 14:00:00+00', TIMESTAMPTZ '2026-04-04 13:00:00+00'),
    ('ST-S001-3', 'SHIP-001', 3, 'Phoenix-West', TIMESTAMPTZ '2026-04-05 06:00:00+00', NULL, TIMESTAMPTZ '2026-04-05 08:00:00+00', NULL),
    ('ST-S001-4', 'SHIP-001', 4, 'NYC-Port', TIMESTAMPTZ '2026-04-06 06:00:00+00', NULL, TIMESTAMPTZ '2026-04-06 08:00:00+00', NULL),
    ('ST-S002-1', 'SHIP-002', 1, 'Atlanta-South', TIMESTAMPTZ '2026-04-01 10:00:00+00', TIMESTAMPTZ '2026-04-01 10:00:00+00', TIMESTAMPTZ '2026-04-01 11:00:00+00', TIMESTAMPTZ '2026-04-01 11:00:00+00'),
    ('ST-S002-2', 'SHIP-002', 2, 'Dallas-Hub', TIMESTAMPTZ '2026-04-02 16:00:00+00', TIMESTAMPTZ '2026-04-02 15:00:00+00', TIMESTAMPTZ '2026-04-02 18:00:00+00', TIMESTAMPTZ '2026-04-02 17:00:00+00'),
    ('ST-S002-3', 'SHIP-002', 3, 'Chicago-Main', TIMESTAMPTZ '2026-04-03 22:00:00+00', TIMESTAMPTZ '2026-04-03 22:00:00+00', TIMESTAMPTZ '2026-04-02 18:00:00+00', TIMESTAMPTZ '2026-04-02 18:00:00+00'),
    ('ST-S003-1', 'SHIP-003', 1, 'NYC-Port', TIMESTAMPTZ '2026-04-04 14:00:00+00', TIMESTAMPTZ '2026-04-04 14:00:00+00', TIMESTAMPTZ '2026-04-04 16:00:00+00', TIMESTAMPTZ '2026-04-04 16:00:00+00'),
    ('ST-S003-2', 'SHIP-003', 2, 'Chicago-Main', TIMESTAMPTZ '2026-04-05 02:00:00+00', NULL, TIMESTAMPTZ '2026-04-05 04:00:00+00', NULL),
    ('ST-S003-3', 'SHIP-003', 3, 'Dallas-Hub', TIMESTAMPTZ '2026-04-05 18:00:00+00', NULL, TIMESTAMPTZ '2026-04-05 20:00:00+00', NULL),
    ('ST-S003-4', 'SHIP-003', 4, 'Phoenix-West', TIMESTAMPTZ '2026-04-06 10:00:00+00', NULL, TIMESTAMPTZ '2026-04-06 12:00:00+00', NULL),
    ('ST-S003-5', 'SHIP-003', 5, 'Atlanta-South', TIMESTAMPTZ '2026-04-07 02:00:00+00', NULL, TIMESTAMPTZ '2026-04-07 04:00:00+00', NULL),
    ('ST-S004-1', 'SHIP-004', 1, 'Phoenix-West', TIMESTAMPTZ '2026-04-04 06:00:00+00', TIMESTAMPTZ '2026-04-04 06:00:00+00', TIMESTAMPTZ '2026-04-04 07:00:00+00', TIMESTAMPTZ '2026-04-04 07:00:00+00'),
    ('ST-S004-2', 'SHIP-004', 2, 'Dallas-Hub', TIMESTAMPTZ '2026-04-04 16:00:00+00', TIMESTAMPTZ '2026-04-04 15:00:00+00', TIMESTAMPTZ '2026-04-04 20:00:00+00', NULL),
    ('ST-S004-3', 'SHIP-004', 3, 'Chicago-Main', TIMESTAMPTZ '2026-04-05 12:00:00+00', NULL, TIMESTAMPTZ '2026-04-05 14:00:00+00', NULL),
    ('ST-S005-1', 'SHIP-005', 1, 'Chicago-Main', TIMESTAMPTZ '2026-03-31 18:00:00+00', TIMESTAMPTZ '2026-03-31 18:00:00+00', TIMESTAMPTZ '2026-03-31 19:00:00+00', TIMESTAMPTZ '2026-03-31 19:00:00+00'),
    ('ST-S005-2', 'SHIP-005', 2, 'Atlanta-South', TIMESTAMPTZ '2026-04-01 18:00:00+00', TIMESTAMPTZ '2026-04-01 18:00:00+00', TIMESTAMPTZ '2026-04-01 19:00:00+00', TIMESTAMPTZ '2026-04-01 19:00:00+00'),
    ('ST-S005-3', 'SHIP-005', 3, 'NYC-Port', TIMESTAMPTZ '2026-04-02 18:00:00+00', TIMESTAMPTZ '2026-04-02 18:00:00+00', TIMESTAMPTZ '2026-04-02 19:00:00+00', TIMESTAMPTZ '2026-04-02 19:00:00+00'),
    ('ST-S005-4', 'SHIP-005', 4, 'Dallas-Hub', TIMESTAMPTZ '2026-04-04 10:00:00+00', TIMESTAMPTZ '2026-04-04 10:00:00+00', TIMESTAMPTZ '2026-04-04 12:00:00+00', TIMESTAMPTZ '2026-04-04 12:00:00+00');

INSERT INTO risks (risk_id, hub_name, category, severity, est_delay_hrs) VALUES
    ('RISK-001', 'Dallas-Hub', 'Weather', 7, 4.5),
    ('RISK-002', 'Dallas-Hub', 'Traffic', 5, 2.0),
    ('RISK-003', 'Chicago-Main', 'Labor', 4, 1.5),
    ('RISK-004', 'NYC-Port', 'Weather', 6, 3.0),
    ('RISK-005', 'Phoenix-West', 'Traffic', 3, 1.0);

INSERT INTO insights (insight_id, shipment_id, flag_status, predicted_arrival, reasoning, confidence) VALUES
    ('insight_SHIP-001', 'SHIP-001', 'Delayed', TIMESTAMPTZ '2026-04-06 10:00:00+00', 'Weather and congestion at Dallas-Hub.', 7),
    ('insight_SHIP-003', 'SHIP-003', 'On Time', TIMESTAMPTZ '2026-04-07 14:00:00+00', 'Route clear; hubs within capacity.', 8),
    ('insight_SHIP-004', 'SHIP-004', 'On Time', TIMESTAMPTZ '2026-04-05 16:00:00+00', 'Minor delay absorbed at stop 2.', 6);
