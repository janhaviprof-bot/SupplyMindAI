# SupplyMind AI — AI-Augmented Delivery System

## 1. Project Overview

- **Name:** AI-Augmented Delivery System
- **Purpose:** Help a global logistics company track shipments in real time, predict delivery delays, and optimize warehouse routing across distribution centers
- **Domain flexibility:** Packages, semiconductor supply chains, beanie babies, or anything that ships

A global logistics company is struggling to track shipments in real time, predict delivery delays, and optimize warehouse routing across multiple distribution centers. This system uses synthetic logistics data to create live tracking profiles and generate actionable predictions for operations managers.

---

## 2. Stakeholders

- **Primary:** Supply chain manager
- **Needs:**
  - Track all shipments from their warehouse
  - Understand delay statistics
  - Identify changes to improve the supply chain

---

## 3. Technical Stack

- **Application:** ShinyPy (Python-based Shiny for web dashboards)
- **Data:** Synthetic logistics database (to be created, no real data available)

---

## 4. Core Tasks

| Task | Input | Output |
|------|-------|--------|
| **Task 1: Delay prediction** | Stops, location, times, weather, occupancy of next stops | Flagged shipments likely to be delayed |
| **Task 2: Optimization** | Historic data | Suggestions for supply chain modifications to optimize future operations |

---

## 5. Database Schema (5 Tables)

### shipments

| Field | Type | Key | Description |
|-------|------|-----|-------------|
| shipment_id | String | PK | Unique ID (e.g., "SHIP-001") |
| material_type | String | - | e.g., "Medical Supplies", "Electronics" |
| priority_level | Integer | - | 1 (Low) to 10 (Critical) |
| total_stops | Integer | - | Total hubs in journey (Max 5) |
| current_stop_index | Integer | - | Which stop now (1-5) |
| final_deadline | Timestamp | - | Drop-dead delivery time |

### stops

| Field | Type | Key | Description |
|-------|------|-----|-------------|
| stop_id | String | PK | Unique ID for stop event |
| shipment_id | String | FK | Links to shipments.shipment_id |
| stop_number | Integer | - | Sequence (1-5) |
| hub_name | String | FK | Links to hubs.hub_name |
| planned_arrival | Timestamp | - | Target arrival |
| actual_arrival | Timestamp | - | Real arrival (NULL if future) |
| planned_departure | Timestamp | - | Target departure |
| actual_departure | Timestamp | - | Real departure (NULL if future) |

### hubs

| Field | Type | Key | Description |
|-------|------|-----|-------------|
| hub_name | String | PK | Unique name (e.g., "Chicago-Main") |
| lat | Float | - | Latitude |
| lon | Float | - | Longitude |
| max_capacity | Integer | - | Max trucks/pallets |
| current_load | Integer | - | Current trucks/pallets inside |
| status | String | - | "Open", "Congested", "Closed" |

### risks

| Field | Type | Key | Description |
|-------|------|-----|-------------|
| risk_id | String | PK | Unique ID for threat |
| hub_name | String | FK | Links to hubs.hub_name |
| category | String | - | "Weather", "Traffic", "Labor" |
| severity | Integer | - | 1-10 scale |
| est_delay_hrs | Float | - | AI input: hours of delay added |

### insights

| Field | Type | Key | Description |
|-------|------|-----|-------------|
| insight_id | String | PK | Unique ID |
| shipment_id | String | FK | Links to shipments.shipment_id |
| flag_status | String | - | "On Time", "Delayed", "Escalated", "Critical" |
| predicted_arrival | Timestamp | - | AI-estimated arrival |
| reasoning | Text | - | e.g., "Storm at Stop 3 + Hub Congestion." |

---

## 6. Entity Relationship Summary

- `shipments` → `stops` (1:N via shipment_id)
- `stops` → `hubs` (N:1 via hub_name)
- `risks` → `hubs` (N:1 via hub_name)
- `insights` → `shipments` (N:1 via shipment_id)
