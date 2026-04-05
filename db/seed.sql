-- SupplyMind AI — synthetic seed data (run after schema.sql)
-- Safe to re-run: uses ON CONFLICT DO NOTHING where applicable.

INSERT INTO hubs (hub_name, lat, lon, max_capacity, current_load, status) VALUES
    ('Chicago-Main', 41.8781, -87.6298, 120, 78, 'Open'),
    ('Dallas-Hub', 32.7767, -96.7970, 90, 85, 'Congested'),
    ('Atlanta-South', 33.7490, -84.3880, 100, 55, 'Open'),
    ('NYC-Port', 40.7128, -74.0060, 150, 120, 'Open'),
    ('Phoenix-West', 33.4484, -112.0740, 80, 40, 'Open')
ON CONFLICT (hub_name) DO NOTHING;

INSERT INTO shipments (shipment_id, material_type, priority_level, total_stops, current_stop_index, final_deadline, status) VALUES
    ('SHIP-001', 'Medical Supplies', 9, 4, 2, NOW() + INTERVAL '48 hours', 'In Transit'),
    ('SHIP-002', 'Electronics', 6, 3, 3, NOW() - INTERVAL '2 days', 'Delivered'),
    ('SHIP-003', 'Industrial Parts', 7, 5, 1, NOW() + INTERVAL '72 hours', 'In Transit'),
    ('SHIP-004', 'Retail Goods', 4, 3, 2, NOW() + INTERVAL '24 hours', 'In Transit'),
    ('SHIP-005', 'Cold Chain Food', 10, 4, 4, NOW() - INTERVAL '6 hours', 'Delivered')
ON CONFLICT (shipment_id) DO NOTHING;

INSERT INTO stops (stop_id, shipment_id, stop_number, hub_name, planned_arrival, actual_arrival, planned_departure, actual_departure) VALUES
    ('ST-S001-1', 'SHIP-001', 1, 'Chicago-Main', NOW() - INTERVAL '30 hours', NOW() - INTERVAL '30 hours', NOW() - INTERVAL '29 hours', NOW() - INTERVAL '29 hours'),
    ('ST-S001-2', 'SHIP-001', 2, 'Dallas-Hub', NOW() - INTERVAL '6 hours', NOW() - INTERVAL '7 hours', NOW() - INTERVAL '4 hours', NOW() - INTERVAL '5 hours'),
    ('ST-S001-3', 'SHIP-001', 3, 'Phoenix-West', NOW() + INTERVAL '12 hours', NULL, NOW() + INTERVAL '14 hours', NULL),
    ('ST-S001-4', 'SHIP-001', 4, 'NYC-Port', NOW() + INTERVAL '36 hours', NULL, NOW() + INTERVAL '38 hours', NULL),
    ('ST-S002-1', 'SHIP-002', 1, 'Atlanta-South', NOW() - INTERVAL '80 hours', NOW() - INTERVAL '80 hours', NOW() - INTERVAL '79 hours', NOW() - INTERVAL '79 hours'),
    ('ST-S002-2', 'SHIP-002', 2, 'Dallas-Hub', NOW() - INTERVAL '50 hours', NOW() - INTERVAL '51 hours', NOW() - INTERVAL '48 hours', NOW() - INTERVAL '49 hours'),
    ('ST-S002-3', 'SHIP-002', 3, 'Chicago-Main', NOW() - INTERVAL '20 hours', NOW() - INTERVAL '20 hours', NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'),
    ('ST-S003-1', 'SHIP-003', 1, 'NYC-Port', NOW() - INTERVAL '4 hours', NOW() - INTERVAL '4 hours', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours'),
    ('ST-S003-2', 'SHIP-003', 2, 'Chicago-Main', NOW() + INTERVAL '8 hours', NULL, NOW() + INTERVAL '10 hours', NULL),
    ('ST-S003-3', 'SHIP-003', 3, 'Dallas-Hub', NOW() + INTERVAL '24 hours', NULL, NOW() + INTERVAL '26 hours', NULL),
    ('ST-S003-4', 'SHIP-003', 4, 'Phoenix-West', NOW() + INTERVAL '40 hours', NULL, NOW() + INTERVAL '42 hours', NULL),
    ('ST-S003-5', 'SHIP-003', 5, 'Atlanta-South', NOW() + INTERVAL '56 hours', NULL, NOW() + INTERVAL '58 hours', NULL),
    ('ST-S004-1', 'SHIP-004', 1, 'Phoenix-West', NOW() - INTERVAL '12 hours', NOW() - INTERVAL '12 hours', NOW() - INTERVAL '11 hours', NOW() - INTERVAL '11 hours'),
    ('ST-S004-2', 'SHIP-004', 2, 'Dallas-Hub', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '3 hours', NOW() + INTERVAL '2 hours', NULL),
    ('ST-S004-3', 'SHIP-004', 3, 'Chicago-Main', NOW() + INTERVAL '18 hours', NULL, NOW() + INTERVAL '20 hours', NULL),
    ('ST-S005-1', 'SHIP-005', 1, 'Chicago-Main', NOW() - INTERVAL '96 hours', NOW() - INTERVAL '96 hours', NOW() - INTERVAL '95 hours', NOW() - INTERVAL '95 hours'),
    ('ST-S005-2', 'SHIP-005', 2, 'Atlanta-South', NOW() - INTERVAL '72 hours', NOW() - INTERVAL '72 hours', NOW() - INTERVAL '71 hours', NOW() - INTERVAL '71 hours'),
    ('ST-S005-3', 'SHIP-005', 3, 'NYC-Port', NOW() - INTERVAL '48 hours', NOW() - INTERVAL '48 hours', NOW() - INTERVAL '47 hours', NOW() - INTERVAL '47 hours'),
    ('ST-S005-4', 'SHIP-005', 4, 'Dallas-Hub', NOW() - INTERVAL '8 hours', NOW() - INTERVAL '8 hours', NOW() - INTERVAL '6 hours', NOW() - INTERVAL '6 hours')
ON CONFLICT (stop_id) DO NOTHING;

INSERT INTO risks (risk_id, hub_name, category, severity, est_delay_hrs) VALUES
    ('RISK-001', 'Dallas-Hub', 'Weather', 7, 4.5),
    ('RISK-002', 'Dallas-Hub', 'Traffic', 5, 2.0),
    ('RISK-003', 'Chicago-Main', 'Labor', 4, 1.5),
    ('RISK-004', 'NYC-Port', 'Weather', 6, 3.0),
    ('RISK-005', 'Phoenix-West', 'Traffic', 3, 1.0)
ON CONFLICT (risk_id) DO NOTHING;

-- Optional starter insights (pipeline upserts by insight_id = insight_<shipment_id>)
INSERT INTO insights (insight_id, shipment_id, flag_status, predicted_arrival, reasoning, confidence) VALUES
    ('insight_SHIP-001', 'SHIP-001', 'Delayed', NOW() + INTERVAL '40 hours', 'Weather and congestion at Dallas-Hub.', 7),
    ('insight_SHIP-003', 'SHIP-003', 'On Time', NOW() + INTERVAL '68 hours', 'Route clear; hubs within capacity.', 8),
    ('insight_SHIP-004', 'SHIP-004', 'On Time', NOW() + INTERVAL '22 hours', 'Minor delay absorbed at stop 2.', 6)
ON CONFLICT (insight_id) DO NOTHING;
