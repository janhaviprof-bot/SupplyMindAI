-- SupplyMind AI — up to 200 extra shipments (append after seed.sql SHIP-001..022).
-- Delivered rows (043–122, 143–222): bucketed delay_hours vs deadline, long hub dwells,
-- routes through Chicago/Dallas/NYC/Miami (overloaded hubs) for dramatic optimization curves.
-- Prerequisites: schema.sql + seed.sql (hubs and base rows).
--   SHIP-023 … SHIP-042  → In Transit (20)   | SHIP-123 … SHIP-142 → In Transit (20)
--   SHIP-043 … SHIP-122 → Delivered (80)   | SHIP-143 … SHIP-222 → Delivered (80)
-- Safe to re-run: ON CONFLICT DO NOTHING on PKs.
-- Note: If you previously ran this file with BULK-* IDs, remove those rows or ignore them; new runs only insert SHIP-*.

-- In-transit append (SHIP-023 .. SHIP-042)
INSERT INTO shipments (shipment_id, material_type, priority_level, total_stops, current_stop_index, final_deadline, status)
SELECT
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    (ARRAY[
        'Electronics', 'Retail Goods', 'Medical Supplies', 'Industrial Parts',
        'Cold Chain Food', 'Automotive', 'Chemicals', 'Paper Goods'
    ])[1 + ((ship_n - 23) % 8)],
    3 + ((ship_n - 23) % 8),
    3,
    1,
    NOW() + make_interval(days => 2 + ((ship_n - 23) % 18)),
    'In Transit'
FROM generate_series(23, 42) AS ship_n
ON CONFLICT (shipment_id) DO NOTHING;

-- Stops (same pattern as seed.sql: ST-S023-1, …)
INSERT INTO stops (stop_id, shipment_id, stop_number, hub_name, planned_arrival, actual_arrival, planned_departure, actual_departure)
SELECT
    'ST-S' || LPAD(ship_n::text, 3, '0') || '-' || n,
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    n,
    (ARRAY[
        'Chicago-Main', 'Dallas-Hub', 'Atlanta-South', 'NYC-Port',
        'Phoenix-West', 'Seattle-North', 'Miami-Port'
    ])[1 + ((((ship_n - 23) * 3) + n * 2) % 7)],
    CASE n
        WHEN 1 THEN NOW() - INTERVAL '60 hours' + make_interval(mins => ((ship_n - 23) * 7))
        WHEN 2 THEN NOW() - INTERVAL '4 hours' + make_interval(mins => ((ship_n - 23) * 3))
        ELSE NOW() + INTERVAL '18 hours' + make_interval(mins => ((ship_n - 23) * 5))
    END,
    CASE n
        WHEN 1 THEN NOW() - INTERVAL '60 hours' + make_interval(mins => ((ship_n - 23) * 7))
        WHEN 2 THEN NULL
        ELSE NULL
    END,
    CASE n
        WHEN 1 THEN NOW() - INTERVAL '59 hours' + make_interval(mins => ((ship_n - 23) * 7))
        WHEN 2 THEN NOW() - INTERVAL '3 hours' + make_interval(mins => ((ship_n - 23) * 3))
        ELSE NOW() + INTERVAL '20 hours'
    END,
    CASE n
        WHEN 1 THEN NOW() - INTERVAL '59 hours' + make_interval(mins => ((ship_n - 23) * 7))
        WHEN 2 THEN NULL
        ELSE NULL
    END
FROM generate_series(23, 42) AS ship_n
CROSS JOIN generate_series(1, 3) AS n
ON CONFLICT (stop_id) DO NOTHING;

INSERT INTO insights (insight_id, shipment_id, flag_status, predicted_arrival, reasoning, confidence)
SELECT
    'insight_SHIP-' || LPAD(ship_n::text, 3, '0'),
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    CASE ((ship_n - 23) % 5)
        WHEN 0 THEN 'On Time'
        WHEN 1 THEN 'Delayed'
        WHEN 2 THEN 'Critical'
        WHEN 3 THEN 'On Time'
        ELSE 'Delayed'
    END,
    NOW() + make_interval(hours => 12 + ((ship_n - 23) % 48)),
    'Appended scale seed (in transit).',
    5 + ((ship_n - 23) % 5)
FROM generate_series(23, 42) AS ship_n
ON CONFLICT (insight_id) DO NOTHING;

-- Delivered append (SHIP-043 .. SHIP-122)
-- Dramatic simulation: deadline = delivery minus a bucketed lateness (8h–400h) so levers sweep recoveries.
-- Stops use Chicago/Dallas/NYC/Miami (overloaded in seed) + long dwells for dispatch_time_at_hub.
INSERT INTO shipments (shipment_id, material_type, priority_level, total_stops, current_stop_index, final_deadline, status)
SELECT
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    (ARRAY[
        'Electronics', 'Retail Goods', 'Medical Supplies', 'Industrial Parts',
        'Cold Chain Food', 'Automotive', 'Chemicals', 'Paper Goods'
    ])[1 + ((ship_n - 43) % 8)],
    3 + ((ship_n - 43) % 8),
    3,
    3,
    (b.base + INTERVAL '42 hours') - CASE ((ship_n - 43) % 5)
        WHEN 0 THEN INTERVAL '8 hours'
        WHEN 1 THEN INTERVAL '24 hours'
        WHEN 2 THEN INTERVAL '72 hours'
        WHEN 3 THEN INTERVAL '168 hours'
        ELSE INTERVAL '400 hours'
    END,
    'Delivered'
FROM generate_series(43, 122) AS ship_n
CROSS JOIN LATERAL (
    SELECT
        NOW()
        - make_interval(days => 4 + ((ship_n - 43) % 28))
        - make_interval(hours => ((ship_n - 43) % 10))
        AS base
) AS b
ON CONFLICT (shipment_id) DO NOTHING;

INSERT INTO stops (stop_id, shipment_id, stop_number, hub_name, planned_arrival, actual_arrival, planned_departure, actual_departure)
SELECT
    'ST-S' || LPAD(ship_n::text, 3, '0') || '-' || n,
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    n,
    (ARRAY[
        'Chicago-Main', 'Dallas-Hub', 'NYC-Port', 'Miami-Port'
    ])[1 + (((ship_n - 43) + n) % 4)],
    CASE n
        WHEN 1 THEN b.base
        WHEN 2 THEN b.base + INTERVAL '10 hours'
        ELSE b.base + INTERVAL '24 hours'
    END,
    CASE n
        WHEN 1 THEN b.base
        WHEN 2 THEN b.base + INTERVAL '10 hours'
        ELSE b.base + INTERVAL '24 hours'
    END,
    CASE n
        WHEN 1 THEN b.base + INTERVAL '10 hours'
        WHEN 2 THEN b.base + INTERVAL '24 hours'
        ELSE b.base + INTERVAL '42 hours'
    END,
    CASE n
        WHEN 1 THEN b.base + INTERVAL '10 hours'
        WHEN 2 THEN b.base + INTERVAL '24 hours'
        ELSE b.base + INTERVAL '42 hours'
    END
FROM generate_series(43, 122) AS ship_n
CROSS JOIN generate_series(1, 3) AS n
CROSS JOIN LATERAL (
    SELECT
        NOW()
        - make_interval(days => 4 + ((ship_n - 43) % 28))
        - make_interval(hours => ((ship_n - 43) % 10))
        AS base
) AS b
ON CONFLICT (stop_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Second batch: SHIP-123 .. SHIP-222 (20 In Transit, 80 Delivered)
-- ---------------------------------------------------------------------------

INSERT INTO shipments (shipment_id, material_type, priority_level, total_stops, current_stop_index, final_deadline, status)
SELECT
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    (ARRAY[
        'Electronics', 'Retail Goods', 'Medical Supplies', 'Industrial Parts',
        'Cold Chain Food', 'Automotive', 'Chemicals', 'Paper Goods'
    ])[1 + ((ship_n - 123) % 8)],
    3 + ((ship_n - 123) % 8),
    3,
    1,
    NOW() + make_interval(days => 2 + ((ship_n - 123) % 18)),
    'In Transit'
FROM generate_series(123, 142) AS ship_n
ON CONFLICT (shipment_id) DO NOTHING;

INSERT INTO stops (stop_id, shipment_id, stop_number, hub_name, planned_arrival, actual_arrival, planned_departure, actual_departure)
SELECT
    'ST-S' || LPAD(ship_n::text, 3, '0') || '-' || n,
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    n,
    (ARRAY[
        'Chicago-Main', 'Dallas-Hub', 'Atlanta-South', 'NYC-Port',
        'Phoenix-West', 'Seattle-North', 'Miami-Port'
    ])[1 + ((((ship_n - 123) * 3) + n * 2) % 7)],
    CASE n
        WHEN 1 THEN NOW() - INTERVAL '60 hours' + make_interval(mins => ((ship_n - 123) * 7))
        WHEN 2 THEN NOW() - INTERVAL '4 hours' + make_interval(mins => ((ship_n - 123) * 3))
        ELSE NOW() + INTERVAL '18 hours' + make_interval(mins => ((ship_n - 123) * 5))
    END,
    CASE n
        WHEN 1 THEN NOW() - INTERVAL '60 hours' + make_interval(mins => ((ship_n - 123) * 7))
        WHEN 2 THEN NULL
        ELSE NULL
    END,
    CASE n
        WHEN 1 THEN NOW() - INTERVAL '59 hours' + make_interval(mins => ((ship_n - 123) * 7))
        WHEN 2 THEN NOW() - INTERVAL '3 hours' + make_interval(mins => ((ship_n - 123) * 3))
        ELSE NOW() + INTERVAL '20 hours'
    END,
    CASE n
        WHEN 1 THEN NOW() - INTERVAL '59 hours' + make_interval(mins => ((ship_n - 123) * 7))
        WHEN 2 THEN NULL
        ELSE NULL
    END
FROM generate_series(123, 142) AS ship_n
CROSS JOIN generate_series(1, 3) AS n
ON CONFLICT (stop_id) DO NOTHING;

INSERT INTO insights (insight_id, shipment_id, flag_status, predicted_arrival, reasoning, confidence)
SELECT
    'insight_SHIP-' || LPAD(ship_n::text, 3, '0'),
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    CASE ((ship_n - 123) % 5)
        WHEN 0 THEN 'On Time'
        WHEN 1 THEN 'Delayed'
        WHEN 2 THEN 'Critical'
        WHEN 3 THEN 'On Time'
        ELSE 'Delayed'
    END,
    NOW() + make_interval(hours => 12 + ((ship_n - 123) % 48)),
    'Appended scale seed batch 2 (in transit).',
    5 + ((ship_n - 123) % 5)
FROM generate_series(123, 142) AS ship_n
ON CONFLICT (insight_id) DO NOTHING;

INSERT INTO shipments (shipment_id, material_type, priority_level, total_stops, current_stop_index, final_deadline, status)
SELECT
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    (ARRAY[
        'Electronics', 'Retail Goods', 'Medical Supplies', 'Industrial Parts',
        'Cold Chain Food', 'Automotive', 'Chemicals', 'Paper Goods'
    ])[1 + ((ship_n - 143) % 8)],
    3 + ((ship_n - 143) % 8),
    3,
    3,
    (b.base + INTERVAL '42 hours') - CASE ((ship_n - 143) % 5)
        WHEN 0 THEN INTERVAL '8 hours'
        WHEN 1 THEN INTERVAL '24 hours'
        WHEN 2 THEN INTERVAL '72 hours'
        WHEN 3 THEN INTERVAL '168 hours'
        ELSE INTERVAL '400 hours'
    END,
    'Delivered'
FROM generate_series(143, 222) AS ship_n
CROSS JOIN LATERAL (
    SELECT
        NOW()
        - make_interval(days => 4 + ((ship_n - 143) % 28))
        - make_interval(hours => ((ship_n - 143) % 10))
        AS base
) AS b
ON CONFLICT (shipment_id) DO NOTHING;

INSERT INTO stops (stop_id, shipment_id, stop_number, hub_name, planned_arrival, actual_arrival, planned_departure, actual_departure)
SELECT
    'ST-S' || LPAD(ship_n::text, 3, '0') || '-' || n,
    'SHIP-' || LPAD(ship_n::text, 3, '0'),
    n,
    (ARRAY[
        'Miami-Port', 'Chicago-Main', 'Dallas-Hub', 'NYC-Port'
    ])[1 + (((ship_n - 143) + n) % 4)],
    CASE n
        WHEN 1 THEN b.base
        WHEN 2 THEN b.base + INTERVAL '10 hours'
        ELSE b.base + INTERVAL '24 hours'
    END,
    CASE n
        WHEN 1 THEN b.base
        WHEN 2 THEN b.base + INTERVAL '10 hours'
        ELSE b.base + INTERVAL '24 hours'
    END,
    CASE n
        WHEN 1 THEN b.base + INTERVAL '10 hours'
        WHEN 2 THEN b.base + INTERVAL '24 hours'
        ELSE b.base + INTERVAL '42 hours'
    END,
    CASE n
        WHEN 1 THEN b.base + INTERVAL '10 hours'
        WHEN 2 THEN b.base + INTERVAL '24 hours'
        ELSE b.base + INTERVAL '42 hours'
    END
FROM generate_series(143, 222) AS ship_n
CROSS JOIN generate_series(1, 3) AS n
CROSS JOIN LATERAL (
    SELECT
        NOW()
        - make_interval(days => 4 + ((ship_n - 143) % 28))
        - make_interval(hours => ((ship_n - 143) % 10))
        AS base
) AS b
ON CONFLICT (stop_id) DO NOTHING;

-- Optional: remove legacy BULK-* rows from an older version of this file (stops/insights cascade).
DELETE FROM shipments WHERE shipment_id LIKE 'BULK-%';
