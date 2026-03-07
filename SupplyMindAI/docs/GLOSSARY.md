# Glossary — Words and Concepts

Quick lookup for terms used in SupplyMind AI, with plain-language explanations. No technical background required.

---

## A

**API key** — A secret code that lets the app talk to an external service (e.g., OpenAI). You store it in `.env` and never share it.

**AI Confidence** — How sure the AI is about its prediction, from 0% to 100%. High confidence means the data clearly supports the flag; low confidence means the data is mixed or ambiguous. The donut chart center shows the average confidence across all insights.

---

## C

**Confidence** — Same as *AI Confidence*. How sure the AI is about its prediction (1–10 or 0–100%). High means the data clearly supports the flag; low means it's ambiguous.

**control_parameters** — The list of recommended changes from the optimization AI (e.g., "Hub Chicago: Increase capacity").

**Critical** — A flag for high-priority shipments (priority 8–10) that are likely to arrive late. Same as Delayed, but the shipment is high priority, so these need the most attention.

---

## D

**Deadline** — See *Final deadline*.

**Delayed** — A flag for shipments the AI expects to arrive late. Past stops were late, or future hubs have problems (congestion, risks).

**delivery_ts** — The timestamp when a shipment was actually delivered (from the last stop's arrival/departure).

**Dwell time** — The time a shipment spends at a hub between arrival and departure. Reducing dwell time can help deliveries stay on time.

---

## E

**Escalate** — To add a shipment to your personal list of items to follow up on. When you click Escalate, the shipment goes into the Escalated Shipments drawer. Like a to-do list for critical shipments.

**est_delay_hrs** — Estimated delay in hours from a risk (e.g., bad weather at a hub).

---

## F

**Final deadline** — The drop-dead time by which a shipment must arrive. Used to judge on-time vs delayed.

**Flag** — The status the AI assigns to a shipment: On Time, Delayed, or Critical.

---

## H

**Hub** — A warehouse or stop along the route—like a bus stop for packages. Shipments pass through hubs in order. Each hub has a name (e.g., Chicago-Main), a location on the map, a maximum capacity (how much it can hold), and a current load (how full it is now). Hubs can be Open, Congested, or Closed.

---

## I

**In-transit** — A shipment that is still on the road, not yet delivered.

**In-transit vs Delivered** — In-transit means the shipment is still moving. Delivered means it has arrived and its delivery time is known. SupplyMind uses in-transit shipments for predictions (Card 1) and delivered shipments for optimization (Card 3).

**Insight** — One row in the `insights` table: a shipment's flag, predicted arrival, reasoning, and confidence.

---

## L

**Lever** — Something you can control to improve performance. SupplyMind has five levers: hub capacity, dispatch time at hub, transit mode, earlier dispatch, and risk-based buffer. The AI only recommends actions that map to these levers so you can simulate them.

---

## O

**On Time** — A flag for shipments the AI expects to arrive by their deadline. No action needed.

**Optimization** — The process of looking at past deliveries and asking: "What could we change to do better?" The AI looks at on-time vs delayed shipments, which hubs caused the most delays, and what risks were involved, then suggests changes (e.g., increase hub capacity, reduce dwell time).

---

## P

**Predicted arrival** — The AI's estimate of when a shipment will arrive.

**Priority level** — A number 1–10 indicating how important a shipment is. Higher means more urgent. Only shipments with 8+ can be Critical.

---

## R

**Risk** — An external factor that can cause delays: weather, traffic, labor issues. Risks are tied to hubs. The system cannot control risks, but it can suggest ways to reduce their impact (e.g., risk-based buffer, capacity increases).

**ROI** — Return on investment. In simulation, it often means recovered shipments per dollar invested. Higher ROI is better.

---

## S

**Shipment** — One package or pallet moving from point A to point B. Has an ID (e.g., SHIP-001), a type (like Medical Supplies or Electronics), a priority (1–10), and a final deadline by which it must arrive.

**Simulation** — Testing changes on paper. Instead of making changes in the real world, the app asks: "What if we increased capacity at Chicago by 20%? How many more shipments would be on time?" You get a chart and recommendations without spending money yet.

**Status** — For a hub: Open, Congested, or Closed. For a shipment: In Transit or Delivered.

**Stop** — One visit by a shipment to a hub. A shipment has multiple stops in sequence.

**Sweet spot** — The best value for a lever—where you get good results without overspending. On the simulation chart, it's marked with a gold star. It balances investment (cost) and improvement (more on-time shipments).

---

## T

**Transit mode** — How the shipment travels (e.g., truck vs air). Faster transit can reduce delays.

---

## Simple analogies

- **Hub:** Like a bus stop—packages get on and off there.
- **Escalate:** Like adding an item to your to-do list.
- **Simulation:** Like a "what if" calculator—no real changes, just answers.
- **Sweet spot:** The point where you get the most bang for your buck.
