# SupplyMind AI — Codebook

This codebook describes every data point in the SupplyMind AI system: where it comes from, its type and meaning, and where it is used in the application.

---

## 1. Database Tables and Columns

### 1.1 `shipments`

| Column | Type | Description | Used in |
|--------|------|-------------|---------|
| **shipment_id** | String (PK) | Unique shipment identifier (e.g., "SHIP-001") | All pipelines; UI (Needs Attention, Insight Detail Modal, Escalated drawer); joins with stops, insights |
| **material_type** | String | Product category (e.g., "Medical Supplies", "Electronics") | AI payload for Card 1 and Card 3; passed to OpenAI for context |
| **priority_level** | Integer (1–10) | Importance of shipment; 8+ required for Critical flag | AI flag prediction; Critical vs Delayed rule; confidence heuristic |
| **total_stops** | Integer | Total hubs in journey (max 5) | AI payload; display context |
| **current_stop_index** | Integer | Index of current stop (1–5); which stop the shipment is at | Future stop filtering (stop_number > current_stop_index); AI payload |
| **final_deadline** | Timestamp | Target delivery deadline | AI prediction; on-time vs delayed classification; Insight Detail Modal |
| **status** | String | "In Transit" or "Delivered" | Card 1: only "In Transit"; Card 3: only "Delivered" |

---

### 1.2 `stops`

| Column | Type | Description | Used in |
|--------|------|-------------|---------|
| **stop_id** | String (PK) | Unique stop identifier | Schema only (not queried in pipelines) |
| **shipment_id** | String (FK) | Links to shipments.shipment_id | Joins; groups stops by shipment |
| **stop_number** | Integer | Stop sequence (1–5) | Future vs past stop logic; sort order |
| **hub_name** | String (FK) | Links to hubs.hub_name | Hub lookup; risk lookup; map; AI payload |
| **planned_arrival** | Timestamp | Target arrival time | AI payload; confidence heuristic (past stops: actual vs planned) |
| **actual_arrival** | Timestamp | Actual arrival; NULL if future | AI payload; dwell calc; on-time check; delivery_ts (max of last stop) |
| **planned_departure** | Timestamp | Target departure time | AI payload |
| **actual_departure** | Timestamp | Actual departure; NULL if future | AI payload; dwell calc (departure − arrival); delivery_ts |

**Derived from stops:**

| Derived Field | Description | Used in |
|---------------|-------------|---------|
| **delivery_ts** | MAX(actual_arrival, actual_departure) for last stop of delivered shipment | Card 3: date filter, on-time vs delayed split; Card 4: baseline |
| **dwell_hours** | (actual_departure − actual_arrival) per stop, summed | Simulation: dispatch_time_at_hub lever (dwell reduction) |

---

### 1.3 `hubs`

| Column | Type | Description | Used in |
|--------|------|-------------|---------|
| **hub_name** | String (PK) | Unique hub name (e.g., "Chicago-Main") | All joins; map labels; AI payload; simulation target_hub |
| **lat** | Float | Latitude | Map (Plotly scattergeo); hub coordinates |
| **lon** | Float | Longitude | Map (Plotly scattergeo); hub coordinates |
| **current_load** | Integer | Current trucks/pallets at hub | AI payload; simulation (congestion: L in max(0,(L-C)/C)×α) |
| **max_capacity** | Integer | Max trucks/pallets (nominal C) | AI payload; simulation uses C_sim = k × max_capacity (k=1.0 = no change vs this value) |
| **status** | String | "Open", "Congested", "Closed" | AI payload; confidence heuristic (all_open check) |

---

### 1.4 `risks`

| Column | Type | Description | Used in |
|--------|------|-------------|---------|
| **risk_id** | String (PK) | Unique risk identifier | Schema only (not queried) |
| **hub_name** | String (FK) | Links to hubs.hub_name | Join; risks fetched per hub on route |
| **category** | String | "Weather", "Traffic", "Labor" | AI payload; metrics (common_risk_categories); map risk_categories |
| **severity** | Integer (1–10) | Risk intensity | AI payload; confidence heuristic (max_sev); flag rules (≥7 → Delayed) |
| **est_delay_hrs** | Float | Estimated delay in hours | AI payload; simulation (risk_based_buffer lever); congestion decomposition |

---

### 1.5 `insights` (written by pipeline)

| Column | Type | Description | Used in |
|--------|------|-------------|---------|
| **insight_id** | String (PK) | insight_{shipment_id} | Upsert key |
| **shipment_id** | String (FK) | Links to shipments | KPI counts; Needs Attention; map; modal |
| **flag_status** | String | "On Time", "Delayed", "Critical" | KPI cards; donut chart; Needs Attention filter; map hub status |
| **predicted_arrival** | Timestamp | AI-estimated arrival | Insight Detail Modal; AI uses for Delayed/Critical |
| **reasoning** | Text | AI explanation (e.g., "Delays at Chicago-Main due to traffic.") | Needs Attention list; Insight Detail Modal |
| **confidence** | Integer (1–10) | AI/model confidence; heuristic if missing | Donut chart center (avg scaled to 0–100%) |

---

## 2. Enriched / Computed Data Structures

### 2.1 Future hubs (Card 1 pipeline)

| Field | Source | Used in |
|-------|--------|---------|
| stop_number | stops | Future stop filter |
| hub_name | stops | Hub/risk lookup |
| planned_arrival | stops | AI payload |
| planned_departure | stops | AI payload |
| current_load | hubs | AI payload; congestion context |
| max_capacity | hubs | AI payload; congestion context |
| status | hubs | AI payload; confidence heuristic |

### 2.2 Future risks (Card 1 pipeline)

| Field | Source | Used in |
|-------|--------|---------|
| hub_name | risks | Link to stop |
| category | risks | AI payload |
| severity | risks | AI payload; confidence heuristic |
| est_delay_hrs | risks | AI payload |

### 2.3 Enriched stop (Card 3 pipeline)

| Field | Source | Used in |
|-------|--------|---------|
| stop_number | stops | Payload |
| hub_name | stops | Payload; metrics |
| planned_arrival, actual_arrival | stops | Payload |
| planned_departure, actual_departure | stops | Payload; dwell calc |
| current_load, max_capacity, status | hubs | Payload; simulation |
| risks (array) | risks | Payload; simulation (est_delay_hrs) |

### 2.4 Metrics (Card 3)

| Field | Description | Used in |
|-------|-------------|---------|
| avg_delay_hours | Mean delay (hours) for delayed shipments | AI prompt; summary |
| top_delayed_hubs | Hubs most often in delayed shipments | AI prompt; hub_map_data |
| common_risk_categories | Most frequent risk categories in delayed | AI prompt |

### 2.5 status_hubs (map output)

| Field | Description | Used in |
|-------|-------------|---------|
| hub_name | Hub identifier | Map label; tooltip |
| lat, lon | Coordinates | Map position |
| status | "red", "orange", "green" (worst flag at hub) | Map color |
| in_delayed_count | Count of Delayed/Critical shipments visiting hub | Map size; tooltip |

### 2.6 delayed_raw payload (Card 4 simulation)

| Field | Description | Used in |
|-------|-------------|---------|
| shipment_id | Shipment ID | Tracking |
| delay_hours | (delivery_ts − final_deadline) in hours | D_obs in simulation; reclassification |
| stops | Enriched stops with current_load, max_capacity, risks | Congestion calc; dwell calc; risk buffer |

---

## 3. Data Flow by Feature

### Card 1: Current Shipment Delivery Insight

| Data | Flow |
|------|------|
| shipments (In Transit) | → pipeline |
| stops | → past + future; actual vs planned for confidence |
| hubs (future stops only) | → current_load, max_capacity, status |
| risks (future hubs only) | → category, severity, est_delay_hrs |
| AI output | → insights (flag_status, predicted_arrival, reasoning, confidence) |
| insights | → KPI cards, donut, Needs Attention, map |

### Card 2: Prediction Map

| Data | Flow |
|------|------|
| insights | → flag per shipment |
| stops | → which hubs each shipment visits |
| hubs | → lat, lon, hub_name |
| Computed | → status_hubs (status, in_delayed_count) |
| status_hubs | → Plotly map (color, size, tooltip) |

### Card 3: Supply Chain Optimization

| Data | Flow |
|------|------|
| shipments (Delivered) | → date filter by delivery_ts |
| stops | → all stops per shipment |
| hubs | → current_load, max_capacity, status per stop |
| risks | → per hub, per stop |
| Computed | → on_time_raw, delayed_raw, metrics |
| AI | → control_parameters, top_parameters |

### Card 4: Parameter Simulation

| Data | Flow |
|------|------|
| on_time_raw, delayed_raw | → from Card 3 |
| delay_hours | → D_obs in simulate_delays |
| stops (current_load, max_capacity, risks) | → congestion, dwell, risk buffer levers |
| Computed | → curve (value, investment_usd, on_time_count, etc.) |
| AI | → recommendation_1, recommendation_2, recommendation_3 |

---

## 4. Quick Reference: Where Is X Used?

| Data Point | Primary Use |
|------------|-------------|
| shipment_id | Everywhere; joins and display |
| priority_level | Critical vs Delayed rule; AI |
| current_stop_index | Future stop filter (Card 1) |
| final_deadline | On-time vs delayed; AI; modal |
| status | Filter In Transit (Card 1) vs Delivered (Card 3) |
| actual_arrival, actual_departure | Dwell; past performance; delivery_ts |
| planned_arrival, planned_departure | AI; confidence heuristic |
| hub_name | Joins; map; simulation target |
| lat, lon | Map only |
| current_load, max_capacity | Congestion formula; AI |
| hub status | AI; confidence heuristic |
| category, severity, est_delay_hrs | AI; simulation; metrics |
| delivery_ts | Card 3 date filter; on-time split |
| delay_hours | Simulation D_obs; reclassification |
| flag_status | KPI; donut; Needs Attention; map |
| reasoning | Needs Attention; modal |
| confidence | Donut center |
