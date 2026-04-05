-- SupplyMind AI — synthetic seed data (run after schema.sql)
-- Diversified: many In Transit + Delivered rows for dashboard (Card 1) and
-- optimization date ranges (Card 3 uses Delivered + delivery_ts from last stop).
-- Safe to re-run: ON CONFLICT DO NOTHING on PKs.

INSERT INTO hubs (hub_name, lat, lon, max_capacity, current_load, status) VALUES
    ('Chicago-Main', 41.8781, -87.6298, 120, 135, 'Open'),
    ('Dallas-Hub', 32.7767, -96.7970, 90, 98, 'Congested'),
    ('Atlanta-South', 33.7490, -84.3880, 100, 55, 'Open'),
    ('NYC-Port', 40.7128, -74.0060, 150, 162, 'Open'),
    ('Phoenix-West', 33.4484, -112.0740, 80, 40, 'Open'),
    ('Seattle-North', 47.6062, -122.3321, 95, 62, 'Open'),
    ('Miami-Port', 25.7617, -80.1918, 110, 118, 'Congested')
ON CONFLICT (hub_name) DO NOTHING;

INSERT INTO shipments (shipment_id, material_type, priority_level, total_stops, current_stop_index, final_deadline, status) VALUES
    ('SHIP-001', 'Medical Supplies', 9, 4, 2, NOW() + INTERVAL '48 hours', 'In Transit'),
    ('SHIP-002', 'Electronics', 6, 3, 3, NOW() - INTERVAL '4 days', 'Delivered'),
    ('SHIP-003', 'Industrial Parts', 7, 5, 1, NOW() + INTERVAL '72 hours', 'In Transit'),
    ('SHIP-004', 'Retail Goods', 4, 3, 2, NOW() + INTERVAL '24 hours', 'In Transit'),
    ('SHIP-005', 'Cold Chain Food', 10, 4, 4, NOW() - INTERVAL '18 hours', 'Delivered'),
    ('SHIP-006', 'Automotive Parts', 8, 4, 1, NOW() + INTERVAL '60 hours', 'In Transit'),
    ('SHIP-007', 'Chemical Feedstock', 9, 3, 2, NOW() + INTERVAL '36 hours', 'In Transit'),
    ('SHIP-008', 'Apparel Bulk', 4, 3, 1, NOW() + INTERVAL '96 hours', 'In Transit'),
    ('SHIP-009', 'Vaccines', 10, 4, 2, NOW() + INTERVAL '30 hours', 'In Transit'),
    ('SHIP-010', 'Office Furniture', 5, 4, 3, NOW() + INTERVAL '18 hours', 'In Transit'),
    ('SHIP-011', 'Semiconductors', 9, 3, 0, NOW() + INTERVAL '54 hours', 'In Transit'),
    ('SHIP-012', 'Agricultural Seed', 6, 5, 2, NOW() + INTERVAL '120 hours', 'In Transit'),
    ('SHIP-013', 'Pet Food', 3, 2, 1, NOW() + INTERVAL '40 hours', 'In Transit'),
    ('SHIP-014', 'Spare Motors', 7, 4, 1, NOW() + INTERVAL '84 hours', 'In Transit'),
    ('SHIP-015', 'Toys', 5, 3, 3, NOW() - INTERVAL '3 days', 'Delivered'),
    ('SHIP-016', 'Home Appliances', 6, 4, 4, NOW() - INTERVAL '5 days', 'Delivered'),
    ('SHIP-017', 'Paper Goods', 3, 2, 2, NOW() - INTERVAL '12 days', 'Delivered'),
    ('SHIP-018', 'Steel Coil', 7, 4, 4, NOW() - INTERVAL '2 days', 'Delivered'),
    ('SHIP-019', 'Beverages', 4, 3, 3, NOW() - INTERVAL '8 days', 'Delivered'),
    ('SHIP-020', 'Laptops', 8, 3, 3, NOW() - INTERVAL '1 day', 'Delivered'),
    ('SHIP-021', 'Hotel Furniture', 5, 5, 5, NOW() - INTERVAL '22 days', 'Delivered'),
    ('SHIP-022', 'Fertilizer', 6, 3, 3, NOW() - INTERVAL '28 days', 'Delivered')
ON CONFLICT (shipment_id) DO NOTHING;

INSERT INTO stops (stop_id, shipment_id, stop_number, hub_name, planned_arrival, actual_arrival, planned_departure, actual_departure) VALUES
    ('ST-S001-1', 'SHIP-001', 1, 'Chicago-Main', NOW() - INTERVAL '30 hours', NOW() - INTERVAL '30 hours', NOW() - INTERVAL '29 hours', NOW() - INTERVAL '29 hours'),
    ('ST-S001-2', 'SHIP-001', 2, 'Dallas-Hub', NOW() - INTERVAL '6 hours', NOW() - INTERVAL '7 hours', NOW() - INTERVAL '4 hours', NOW() - INTERVAL '5 hours'),
    ('ST-S001-3', 'SHIP-001', 3, 'Phoenix-West', NOW() + INTERVAL '12 hours', NULL, NOW() + INTERVAL '14 hours', NULL),
    ('ST-S001-4', 'SHIP-001', 4, 'NYC-Port', NOW() + INTERVAL '36 hours', NULL, NOW() + INTERVAL '38 hours', NULL),
    ('ST-S002-1', 'SHIP-002', 1, 'Atlanta-South', NOW() - INTERVAL '130 hours', NOW() - INTERVAL '130 hours', NOW() - INTERVAL '129 hours', NOW() - INTERVAL '129 hours'),
    ('ST-S002-2', 'SHIP-002', 2, 'Dallas-Hub', NOW() - INTERVAL '110 hours', NOW() - INTERVAL '111 hours', NOW() - INTERVAL '108 hours', NOW() - INTERVAL '109 hours'),
    ('ST-S002-3', 'SHIP-002', 3, 'Chicago-Main', NOW() - INTERVAL '100 hours', NOW() - INTERVAL '100 hours', NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days'),
    ('ST-S003-1', 'SHIP-003', 1, 'NYC-Port', NOW() - INTERVAL '4 hours', NOW() - INTERVAL '4 hours', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours'),
    ('ST-S003-2', 'SHIP-003', 2, 'Chicago-Main', NOW() + INTERVAL '8 hours', NULL, NOW() + INTERVAL '10 hours', NULL),
    ('ST-S003-3', 'SHIP-003', 3, 'Dallas-Hub', NOW() + INTERVAL '24 hours', NULL, NOW() + INTERVAL '26 hours', NULL),
    ('ST-S003-4', 'SHIP-003', 4, 'Phoenix-West', NOW() + INTERVAL '40 hours', NULL, NOW() + INTERVAL '42 hours', NULL),
    ('ST-S003-5', 'SHIP-003', 5, 'Atlanta-South', NOW() + INTERVAL '56 hours', NULL, NOW() + INTERVAL '58 hours', NULL),
    ('ST-S004-1', 'SHIP-004', 1, 'Phoenix-West', NOW() - INTERVAL '12 hours', NOW() - INTERVAL '12 hours', NOW() - INTERVAL '11 hours', NOW() - INTERVAL '11 hours'),
    ('ST-S004-2', 'SHIP-004', 2, 'Dallas-Hub', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '3 hours', NOW() + INTERVAL '2 hours', NULL),
    ('ST-S004-3', 'SHIP-004', 3, 'Chicago-Main', NOW() + INTERVAL '18 hours', NULL, NOW() + INTERVAL '20 hours', NULL),
    ('ST-S005-1', 'SHIP-005', 1, 'Chicago-Main', NOW() - INTERVAL '120 hours', NOW() - INTERVAL '120 hours', NOW() - INTERVAL '119 hours', NOW() - INTERVAL '119 hours'),
    ('ST-S005-2', 'SHIP-005', 2, 'Atlanta-South', NOW() - INTERVAL '96 hours', NOW() - INTERVAL '96 hours', NOW() - INTERVAL '95 hours', NOW() - INTERVAL '95 hours'),
    ('ST-S005-3', 'SHIP-005', 3, 'NYC-Port', NOW() - INTERVAL '72 hours', NOW() - INTERVAL '72 hours', NOW() - INTERVAL '71 hours', NOW() - INTERVAL '71 hours'),
    ('ST-S005-4', 'SHIP-005', 4, 'Dallas-Hub', NOW() - INTERVAL '20 hours', NOW() - INTERVAL '20 hours', NOW() - INTERVAL '18 hours', NOW() - INTERVAL '18 hours'),
    ('ST-S006-1', 'SHIP-006', 1, 'Seattle-North', NOW() - INTERVAL '28 hours', NOW() - INTERVAL '28 hours', NOW() - INTERVAL '27 hours', NOW() - INTERVAL '27 hours'),
    ('ST-S006-2', 'SHIP-006', 2, 'Chicago-Main', NOW() + INTERVAL '10 hours', NULL, NOW() + INTERVAL '12 hours', NULL),
    ('ST-S006-3', 'SHIP-006', 3, 'Atlanta-South', NOW() + INTERVAL '30 hours', NULL, NOW() + INTERVAL '32 hours', NULL),
    ('ST-S006-4', 'SHIP-006', 4, 'Miami-Port', NOW() + INTERVAL '52 hours', NULL, NOW() + INTERVAL '54 hours', NULL),
    ('ST-S007-1', 'SHIP-007', 1, 'Miami-Port', NOW() - INTERVAL '24 hours', NOW() - INTERVAL '24 hours', NOW() - INTERVAL '23 hours', NOW() - INTERVAL '23 hours'),
    ('ST-S007-2', 'SHIP-007', 2, 'Atlanta-South', NOW() - INTERVAL '10 hours', NOW() - INTERVAL '10 hours', NOW() - INTERVAL '9 hours', NOW() - INTERVAL '9 hours'),
    ('ST-S007-3', 'SHIP-007', 3, 'Dallas-Hub', NOW() + INTERVAL '8 hours', NULL, NOW() + INTERVAL '10 hours', NULL),
    ('ST-S008-1', 'SHIP-008', 1, 'Dallas-Hub', NOW() - INTERVAL '18 hours', NOW() - INTERVAL '18 hours', NOW() - INTERVAL '17 hours', NOW() - INTERVAL '17 hours'),
    ('ST-S008-2', 'SHIP-008', 2, 'Chicago-Main', NOW() + INTERVAL '14 hours', NULL, NOW() + INTERVAL '16 hours', NULL),
    ('ST-S008-3', 'SHIP-008', 3, 'NYC-Port', NOW() + INTERVAL '40 hours', NULL, NOW() + INTERVAL '42 hours', NULL),
    ('ST-S009-1', 'SHIP-009', 1, 'Seattle-North', NOW() - INTERVAL '36 hours', NOW() - INTERVAL '36 hours', NOW() - INTERVAL '35 hours', NOW() - INTERVAL '35 hours'),
    ('ST-S009-2', 'SHIP-009', 2, 'Chicago-Main', NOW() - INTERVAL '8 hours', NOW() - INTERVAL '8 hours', NOW() - INTERVAL '7 hours', NOW() - INTERVAL '7 hours'),
    ('ST-S009-3', 'SHIP-009', 3, 'Dallas-Hub', NOW() + INTERVAL '6 hours', NULL, NOW() + INTERVAL '8 hours', NULL),
    ('ST-S009-4', 'SHIP-009', 4, 'Miami-Port', NOW() + INTERVAL '22 hours', NULL, NOW() + INTERVAL '24 hours', NULL),
    ('ST-S010-1', 'SHIP-010', 1, 'Phoenix-West', NOW() - INTERVAL '48 hours', NOW() - INTERVAL '48 hours', NOW() - INTERVAL '47 hours', NOW() - INTERVAL '47 hours'),
    ('ST-S010-2', 'SHIP-010', 2, 'Dallas-Hub', NOW() - INTERVAL '30 hours', NOW() - INTERVAL '30 hours', NOW() - INTERVAL '29 hours', NOW() - INTERVAL '29 hours'),
    ('ST-S010-3', 'SHIP-010', 3, 'Atlanta-South', NOW() - INTERVAL '6 hours', NOW() - INTERVAL '6 hours', NOW() - INTERVAL '5 hours', NOW() - INTERVAL '5 hours'),
    ('ST-S010-4', 'SHIP-010', 4, 'NYC-Port', NOW() + INTERVAL '4 hours', NULL, NOW() + INTERVAL '6 hours', NULL),
    ('ST-S011-1', 'SHIP-011', 1, 'NYC-Port', NOW() + INTERVAL '4 hours', NULL, NOW() + INTERVAL '6 hours', NULL),
    ('ST-S011-2', 'SHIP-011', 2, 'Chicago-Main', NOW() + INTERVAL '20 hours', NULL, NOW() + INTERVAL '22 hours', NULL),
    ('ST-S011-3', 'SHIP-011', 3, 'Seattle-North', NOW() + INTERVAL '44 hours', NULL, NOW() + INTERVAL '46 hours', NULL),
    ('ST-S012-1', 'SHIP-012', 1, 'Chicago-Main', NOW() - INTERVAL '40 hours', NOW() - INTERVAL '40 hours', NOW() - INTERVAL '39 hours', NOW() - INTERVAL '39 hours'),
    ('ST-S012-2', 'SHIP-012', 2, 'Dallas-Hub', NOW() - INTERVAL '20 hours', NOW() - INTERVAL '21 hours', NOW() - INTERVAL '18 hours', NOW() - INTERVAL '19 hours'),
    ('ST-S012-3', 'SHIP-012', 3, 'Phoenix-West', NOW() + INTERVAL '12 hours', NULL, NOW() + INTERVAL '14 hours', NULL),
    ('ST-S012-4', 'SHIP-012', 4, 'Miami-Port', NOW() + INTERVAL '36 hours', NULL, NOW() + INTERVAL '38 hours', NULL),
    ('ST-S012-5', 'SHIP-012', 5, 'Atlanta-South', NOW() + INTERVAL '60 hours', NULL, NOW() + INTERVAL '62 hours', NULL),
    ('ST-S013-1', 'SHIP-013', 1, 'Atlanta-South', NOW() - INTERVAL '8 hours', NOW() - INTERVAL '8 hours', NOW() - INTERVAL '7 hours', NOW() - INTERVAL '7 hours'),
    ('ST-S013-2', 'SHIP-013', 2, 'Chicago-Main', NOW() + INTERVAL '20 hours', NULL, NOW() + INTERVAL '22 hours', NULL),
    ('ST-S014-1', 'SHIP-014', 1, 'Phoenix-West', NOW() - INTERVAL '22 hours', NOW() - INTERVAL '22 hours', NOW() - INTERVAL '21 hours', NOW() - INTERVAL '21 hours'),
    ('ST-S014-2', 'SHIP-014', 2, 'Dallas-Hub', NOW() + INTERVAL '10 hours', NULL, NOW() + INTERVAL '12 hours', NULL),
    ('ST-S014-3', 'SHIP-014', 3, 'Chicago-Main', NOW() + INTERVAL '34 hours', NULL, NOW() + INTERVAL '36 hours', NULL),
    ('ST-S014-4', 'SHIP-014', 4, 'Seattle-North', NOW() + INTERVAL '58 hours', NULL, NOW() + INTERVAL '60 hours', NULL),
    ('ST-S015-1', 'SHIP-015', 1, 'NYC-Port', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days' + INTERVAL '1 hour', NOW() - INTERVAL '5 days' + INTERVAL '1 hour'),
    ('ST-S015-2', 'SHIP-015', 2, 'Dallas-Hub', NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days' + INTERVAL '1 hour', NOW() - INTERVAL '4 days' + INTERVAL '1 hour'),
    ('ST-S015-3', 'SHIP-015', 3, 'Phoenix-West', NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days' + INTERVAL '1 hour', NOW() - INTERVAL '3 days' + INTERVAL '1 hour'),
    ('ST-S016-1', 'SHIP-016', 1, 'Seattle-North', NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days' + INTERVAL '1 hour', NOW() - INTERVAL '8 days' + INTERVAL '1 hour'),
    ('ST-S016-2', 'SHIP-016', 2, 'Chicago-Main', NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days' + INTERVAL '1 hour', NOW() - INTERVAL '7 days' + INTERVAL '1 hour'),
    ('ST-S016-3', 'SHIP-016', 3, 'Atlanta-South', NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days' + INTERVAL '1 hour', NOW() - INTERVAL '6 days' + INTERVAL '1 hour'),
    ('ST-S016-4', 'SHIP-016', 4, 'Miami-Port', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days' + INTERVAL '1 hour', NOW() - INTERVAL '5 days' + INTERVAL '1 hour'),
    ('ST-S017-1', 'SHIP-017', 1, 'Phoenix-West', NOW() - INTERVAL '14 days', NOW() - INTERVAL '14 days', NOW() - INTERVAL '14 days' + INTERVAL '1 hour', NOW() - INTERVAL '14 days' + INTERVAL '1 hour'),
    ('ST-S017-2', 'SHIP-017', 2, 'Chicago-Main', NOW() - INTERVAL '12 days', NOW() - INTERVAL '12 days', NOW() - INTERVAL '12 days' + INTERVAL '1 hour', NOW() - INTERVAL '12 days' + INTERVAL '1 hour'),
    ('ST-S018-1', 'SHIP-018', 1, 'Chicago-Main', NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days' + INTERVAL '1 hour', NOW() - INTERVAL '10 days' + INTERVAL '1 hour'),
    ('ST-S018-2', 'SHIP-018', 2, 'Dallas-Hub', NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days' + INTERVAL '1 hour', NOW() - INTERVAL '8 days' + INTERVAL '1 hour'),
    ('ST-S018-3', 'SHIP-018', 3, 'Atlanta-South', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days' + INTERVAL '1 hour', NOW() - INTERVAL '5 days' + INTERVAL '1 hour'),
    ('ST-S018-4', 'SHIP-018', 4, 'NYC-Port', NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days' + INTERVAL '1 hour', NOW() - INTERVAL '2 days' + INTERVAL '1 hour'),
    ('ST-S019-1', 'SHIP-019', 1, 'Miami-Port', NOW() - INTERVAL '12 days', NOW() - INTERVAL '12 days', NOW() - INTERVAL '12 days' + INTERVAL '1 hour', NOW() - INTERVAL '12 days' + INTERVAL '1 hour'),
    ('ST-S019-2', 'SHIP-019', 2, 'Atlanta-South', NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days' + INTERVAL '1 hour', NOW() - INTERVAL '10 days' + INTERVAL '1 hour'),
    ('ST-S019-3', 'SHIP-019', 3, 'Chicago-Main', NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days' + INTERVAL '1 hour', NOW() - INTERVAL '8 days' + INTERVAL '1 hour'),
    ('ST-S020-1', 'SHIP-020', 1, 'Dallas-Hub', NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days' + INTERVAL '1 hour', NOW() - INTERVAL '3 days' + INTERVAL '1 hour'),
    ('ST-S020-2', 'SHIP-020', 2, 'Phoenix-West', NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days' + INTERVAL '1 hour', NOW() - INTERVAL '2 days' + INTERVAL '1 hour'),
    ('ST-S020-3', 'SHIP-020', 3, 'Seattle-North', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day' + INTERVAL '1 hour', NOW() - INTERVAL '1 day' + INTERVAL '1 hour'),
    ('ST-S021-1', 'SHIP-021', 1, 'Chicago-Main', NOW() - INTERVAL '26 days', NOW() - INTERVAL '26 days', NOW() - INTERVAL '26 days' + INTERVAL '1 hour', NOW() - INTERVAL '26 days' + INTERVAL '1 hour'),
    ('ST-S021-2', 'SHIP-021', 2, 'Dallas-Hub', NOW() - INTERVAL '25 days', NOW() - INTERVAL '25 days', NOW() - INTERVAL '25 days' + INTERVAL '1 hour', NOW() - INTERVAL '25 days' + INTERVAL '1 hour'),
    ('ST-S021-3', 'SHIP-021', 3, 'Phoenix-West', NOW() - INTERVAL '24 days', NOW() - INTERVAL '24 days', NOW() - INTERVAL '24 days' + INTERVAL '1 hour', NOW() - INTERVAL '24 days' + INTERVAL '1 hour'),
    ('ST-S021-4', 'SHIP-021', 4, 'Atlanta-South', NOW() - INTERVAL '23 days', NOW() - INTERVAL '23 days', NOW() - INTERVAL '23 days' + INTERVAL '1 hour', NOW() - INTERVAL '23 days' + INTERVAL '1 hour'),
    ('ST-S021-5', 'SHIP-021', 5, 'Miami-Port', NOW() - INTERVAL '22 days', NOW() - INTERVAL '22 days', NOW() - INTERVAL '22 days' + INTERVAL '1 hour', NOW() - INTERVAL '22 days' + INTERVAL '1 hour'),
    ('ST-S022-1', 'SHIP-022', 1, 'NYC-Port', NOW() - INTERVAL '30 days', NOW() - INTERVAL '30 days', NOW() - INTERVAL '30 days' + INTERVAL '1 hour', NOW() - INTERVAL '30 days' + INTERVAL '1 hour'),
    ('ST-S022-2', 'SHIP-022', 2, 'Chicago-Main', NOW() - INTERVAL '29 days', NOW() - INTERVAL '29 days', NOW() - INTERVAL '29 days' + INTERVAL '1 hour', NOW() - INTERVAL '29 days' + INTERVAL '1 hour'),
    ('ST-S022-3', 'SHIP-022', 3, 'Dallas-Hub', NOW() - INTERVAL '28 days', NOW() - INTERVAL '28 days', NOW() - INTERVAL '28 days' + INTERVAL '1 hour', NOW() - INTERVAL '28 days' + INTERVAL '1 hour')
ON CONFLICT (stop_id) DO NOTHING;

INSERT INTO risks (risk_id, hub_name, category, severity, est_delay_hrs) VALUES
    ('RISK-001', 'Dallas-Hub', 'Weather', 7, 14.0),
    ('RISK-002', 'Dallas-Hub', 'Traffic', 5, 8.0),
    ('RISK-003', 'Chicago-Main', 'Labor', 4, 10.0),
    ('RISK-004', 'NYC-Port', 'Weather', 6, 12.0),
    ('RISK-005', 'Phoenix-West', 'Traffic', 3, 4.0),
    ('RISK-006', 'Atlanta-South', 'Equipment', 5, 6.0),
    ('RISK-007', 'Miami-Port', 'Port Congestion', 8, 16.0),
    ('RISK-008', 'Seattle-North', 'Weather', 5, 4.0),
    ('RISK-009', 'Chicago-Main', 'Capacity', 6, 12.0)
ON CONFLICT (risk_id) DO NOTHING;

INSERT INTO insights (insight_id, shipment_id, flag_status, predicted_arrival, reasoning, confidence) VALUES
    ('insight_SHIP-001', 'SHIP-001', 'Delayed', NOW() + INTERVAL '40 hours', 'Weather and congestion at Dallas-Hub; vaccine-adjacent lane pressure.', 7),
    ('insight_SHIP-003', 'SHIP-003', 'On Time', NOW() + INTERVAL '68 hours', 'Route clear; hubs within capacity after NYC departure.', 8),
    ('insight_SHIP-004', 'SHIP-004', 'Delayed', NOW() + INTERVAL '28 hours', 'Dallas congestion absorbing dwell time; tight window to Chicago.', 6),
    ('insight_SHIP-006', 'SHIP-006', 'Delayed', NOW() + INTERVAL '56 hours', 'Cross-country lane; Seattle handoff on schedule but Midwest risk.', 7),
    ('insight_SHIP-007', 'SHIP-007', 'On Time', NOW() + INTERVAL '32 hours', 'Miami–Atlanta cleared; monitoring Dallas weather.', 8),
    ('insight_SHIP-008', 'SHIP-008', 'On Time', NOW() + INTERVAL '88 hours', 'Low-priority bulk; flexible slotting into Chicago.', 5),
    ('insight_SHIP-009', 'SHIP-009', 'Critical', NOW() + INTERVAL '38 hours', 'High-priority cold chain exposure on Dallas–Miami segment.', 9),
    ('insight_SHIP-010', 'SHIP-010', 'On Time', NOW() + INTERVAL '16 hours', 'Final NYC leg; Atlanta and Dallas on plan.', 7),
    ('insight_SHIP-011', 'SHIP-011', 'Critical', NOW() + INTERVAL '50 hours', 'Semiconductor security lane; NYC origin dwell under watch.', 9),
    ('insight_SHIP-012', 'SHIP-012', 'Delayed', NOW() + INTERVAL '108 hours', 'Agricultural season surge at Phoenix; cascading to Miami.', 6),
    ('insight_SHIP-013', 'SHIP-013', 'On Time', NOW() + INTERVAL '36 hours', 'Short hop; pet food stable demand window.', 6),
    ('insight_SHIP-014', 'SHIP-014', 'Delayed', NOW() + INTERVAL '78 hours', 'Industrial motors; Dallas hub coupling with congestion index.', 7)
ON CONFLICT (insight_id) DO NOTHING;

-- Hub loads over nominal max_capacity so congestion term > 0 and hub_capacity k shows up in simulation.
UPDATE hubs SET current_load = 135 WHERE hub_name = 'Chicago-Main';
UPDATE hubs SET current_load = 98 WHERE hub_name = 'Dallas-Hub';
UPDATE hubs SET current_load = 162 WHERE hub_name = 'NYC-Port';
UPDATE hubs SET current_load = 118 WHERE hub_name = 'Miami-Port';

-- Stronger risk hours so risk_based_buffer lever can recover a visible share of delayed cohort (re-apply if risks existed).
UPDATE risks SET est_delay_hrs = 14.0 WHERE risk_id = 'RISK-001';
UPDATE risks SET est_delay_hrs = 8.0 WHERE risk_id = 'RISK-002';
UPDATE risks SET est_delay_hrs = 10.0 WHERE risk_id = 'RISK-003';
UPDATE risks SET est_delay_hrs = 12.0 WHERE risk_id = 'RISK-004';
UPDATE risks SET est_delay_hrs = 4.0 WHERE risk_id = 'RISK-005';
UPDATE risks SET est_delay_hrs = 6.0 WHERE risk_id = 'RISK-006';
UPDATE risks SET est_delay_hrs = 16.0 WHERE risk_id = 'RISK-007';
UPDATE risks SET est_delay_hrs = 4.0 WHERE risk_id = 'RISK-008';
UPDATE risks SET est_delay_hrs = 12.0 WHERE risk_id = 'RISK-009';

-- Optional scale data: up to 200 more shipments SHIP-023..SHIP-222 (40 In Transit, 160 Delivered) — run seed_bulk_100.sql.
