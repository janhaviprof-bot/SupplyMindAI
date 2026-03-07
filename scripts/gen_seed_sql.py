"""Generate SQL for 60 delivered shipments (35 delayed, 25 on time) with stops."""
HUB_ROUTES = [
    ("Chicago-Main", "Dallas-Central"),
    ("Dallas-Central", "LA-West"),
    ("LA-West", "NYC-Northeast"),
    ("Atlanta-Southeast", "Phoenix-Southwest"),
    ("NYC-Northeast", "Chicago-Main"),
    ("Phoenix-Southwest", "Atlanta-Southeast"),
]
MATERIALS = ["Medical Supplies", "Electronics", "Raw Materials"]

shipments_sql = "INSERT INTO shipments (shipment_id, material_type, priority_level, total_stops, current_stop_index, final_deadline, status) VALUES "
stops_sql = "INSERT INTO stops (stop_id, shipment_id, stop_number, hub_name, planned_arrival, actual_arrival, planned_departure, actual_departure) VALUES "

ship_rows = []
stop_rows = []

for i in range(1, 61):
    sid = f"SHIP-DEL-{i:03d}"
    mat = MATERIALS[(i - 1) % 3]
    prio = (i % 10) + 1
    days_ago = (i % 20) + 1  # 1-20 days ago
    hours_offset = (i % 6) * 4  # 0,4,8,12,16,20
    delivery_base = f"NOW() - INTERVAL '{days_ago} days' - INTERVAL '{hours_offset} hours'"
    is_on_time = i <= 25
    if is_on_time:
        deadline = f"({delivery_base}) + INTERVAL '2 hours'"
    else:
        deadline = f"({delivery_base}) - INTERVAL '4 hours'"
    ship_rows.append(f"('{sid}', '{mat}', {prio}, 2, 2, {deadline}, 'Delivered')")

    hub1, hub2 = HUB_ROUTES[(i - 1) % len(HUB_ROUTES)]
    # Stop 1: arrive and depart
    arr1 = f"({delivery_base}) - INTERVAL '12 hours'"
    dep1 = f"({delivery_base}) - INTERVAL '10 hours'"
    # Stop 2: arrive and depart (departure = delivery)
    arr2 = f"({delivery_base}) - INTERVAL '2 hours'"
    dep2 = delivery_base
    stop_rows.append(f"('{sid}_stop_1', '{sid}', 1, '{hub1}', {arr1}, {arr1}, {dep1}, {dep1})")
    stop_rows.append(f"('{sid}_stop_2', '{sid}', 2, '{hub2}', {arr2}, {arr2}, {dep2}, {dep2})")

shipments_sql += ",\n  ".join(ship_rows) + ";"
stops_sql += ",\n  ".join(stop_rows) + ";"

with open("seed_shipments.sql", "w") as f:
    f.write("-- 60 delivered shipments (25 on-time, 35 delayed)\n")
    f.write(shipments_sql)
    f.write("\n\n")
    f.write(stops_sql)
print("Generated seed_shipments.sql")
print("Shipments:", len(ship_rows))
print("Stops:", len(stop_rows))
