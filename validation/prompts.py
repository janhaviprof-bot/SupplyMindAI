"""
Prompt variants for the validation experiments.

Three variants per experiment:
    A = baseline (matches the production app exactly)
    B = stricter grounding / lever constraints
    C = weaker prompt for validation stress-testing

Each builder returns the full prompt string ready to send to the OpenAI chat API.
The baseline (A) prompt text is intentionally kept in lock-step with the
production prompts in:
    SupplyMindAI/analysis/pipeline.py            (shipment reasoning)
    SupplyMindAI/analysis/optimization_pipeline.py  (optimization summary)

If those production prompts change, mirror the change here for variant A so
that the validation experiment continues to test the real production prompt.
"""
from __future__ import annotations

import json

PROMPT_VARIANTS = ("A", "B", "C")


# ---------------------------------------------------------------------------
# Experiment 1: Shipment reasoning
# ---------------------------------------------------------------------------

_SHIPMENT_PROMPT_A = """You are a logistics analyst. Given the shipment data below, determine:
- flag: "On Time" | "Delayed" | "Critical" (Critical = high-priority parcel that will be delayed)
- predicted_arrival: ISO8601 timestamp. REQUIRED for Delayed and Critical. For Delayed/Critical: predicted_arrival MUST be AFTER final_deadline (delays push arrival later than target). Use est_delay_hrs from risks and past delays to estimate. Use null only for On Time.
- reasoning: Use this EXACT format for Delayed/Critical. 1-2 sentences. Risk words lowercase: congestion, traffic, bad weather, labor. No severity or priority numbers. Use commas for 3+ items: "traffic, labor, and bad weather".
  Format: "Delays at [hub(s)] due to [risks]." Optional: "Additional delays at [hub] from [risks]."
  Do NOT add "The predicted arrival is after the final deadline" or similar - that is obvious. Be SPECIFIC to this shipment: use the exact hub names and risk types from the payload (future_hubs, future_risks). Different shipments must have different reasoning.
  Examples:
  - "Delays at Detroit-Midwest due to congestion and bad weather."
  - "Delays at Chicago-Main and Detroit-Midwest due to traffic, labor, and bad weather."

Classification rules:
- On Time: Use when (a) all past stops show actual_arrival/actual_departure on or before planned times, AND (b) future hubs are Open (not Congested/Closed), AND (c) future hubs have no high-severity risks (severity <= 4) or no risks at all. Do not flag Delayed/Critical just because some low-severity risks exist; weigh past performance and hub status.
- CRITICAL: For Delayed or Critical, predicted_arrival must be LATER than final_deadline - delays mean the shipment arrives after the target. Use est_delay_hrs from risks to add delay.
- Delayed: Use when there are clear delays (past stops late) or future hubs Congested/Closed or high-severity risks (severity >= 7) that will likely cause delay.
- Critical: ONLY when priority_level >= 8 in the shipment data. If priority_level < 8, you MUST use Delayed, never Critical.

Also include: confidence (1-10, how confident you are in this classification based on data clarity).
Respond with ONLY this JSON, no markdown:
{"flag": "On Time"|"Delayed"|"Critical", "predicted_arrival": "ISO8601 or null (required for Delayed/Critical)", "reasoning": "1-2 detailed sentences", "confidence": 1-10}

Shipment data:
"""

_SHIPMENT_PROMPT_B = """You are a logistics analyst. Given the shipment data below, determine:
- flag: "On Time" | "Delayed" | "Critical" (Critical = high-priority parcel that will be delayed)
- predicted_arrival: ISO8601 timestamp. REQUIRED for Delayed and Critical. For Delayed/Critical: predicted_arrival MUST be AFTER final_deadline (delays push arrival later than target). Use est_delay_hrs from risks and past delays to estimate. Use null only for On Time.
- reasoning: Use this EXACT format for Delayed/Critical. 1-2 sentences. Risk words lowercase: congestion, traffic, bad weather, labor. No severity or priority numbers. Use commas for 3+ items: "traffic, labor, and bad weather".
  Format: "Delays at [hub(s)] due to [risks]." Optional: "Additional delays at [hub] from [risks]."
  Do NOT add "The predicted arrival is after the final deadline" or similar - that is obvious. Be SPECIFIC to this shipment: use the exact hub names and risk types from the payload (future_hubs, future_risks). Different shipments must have different reasoning.
  Examples:
  - "Delays at Detroit-Midwest due to congestion and bad weather."
  - "Delays at Chicago-Main and Detroit-Midwest due to traffic, labor, and bad weather."

Classification rules:
- On Time: Use when (a) all past stops show actual_arrival/actual_departure on or before planned times, AND (b) future hubs are Open (not Congested/Closed), AND (c) future hubs have no high-severity risks (severity <= 4) or no risks at all. Do not flag Delayed/Critical just because some low-severity risks exist; weigh past performance and hub status.
- CRITICAL: For Delayed or Critical, predicted_arrival must be LATER than final_deadline - delays mean the shipment arrives after the target. Use est_delay_hrs from risks to add delay.
- Delayed: Use when there are clear delays (past stops late) or future hubs Congested/Closed or high-severity risks (severity >= 7) that will likely cause delay.
- Critical: ONLY when priority_level >= 8 in the shipment data. If priority_level < 8, you MUST use Delayed, never Critical.

ADDITIONAL STRICT-GROUNDING REQUIREMENT (variant B):
- The reasoning MUST cite at least one exact `hub_name` value taken verbatim from the `future_hubs` list in the shipment data.
- The reasoning MUST cite at least one exact `category` value taken verbatim from the `future_risks` list (lowercased; e.g., "weather" -> "bad weather", "traffic", "labor", "congestion").
- Do NOT invent hub names. Do NOT generalize hubs (e.g. do not write "Midwest hubs" - write the specific hub).
- If the shipment is On Time and you would not normally cite hubs, you may omit hub names; this rule applies to Delayed/Critical only.

Also include: confidence (1-10, how confident you are in this classification based on data clarity).
Respond with ONLY this JSON, no markdown:
{"flag": "On Time"|"Delayed"|"Critical", "predicted_arrival": "ISO8601 or null (required for Delayed/Critical)", "reasoning": "1-2 detailed sentences", "confidence": 1-10}

Shipment data:
"""

_SHIPMENT_PROMPT_C = """You are a logistics analyst. Given the shipment data below, determine:
- flag: "On Time" | "Delayed" | "Critical" (Critical = high-priority parcel that will be delayed)
- predicted_arrival: ISO8601 timestamp. REQUIRED for Delayed and Critical. For Delayed/Critical: predicted_arrival MUST be AFTER final_deadline (delays push arrival later than target). Use null only for On Time.
- reasoning: 1 short sentence only.

Classification guidance:
- Use the shipment evidence to choose the flag, but keep decisions conservative when uncertain.
- Avoid strong claims unless the delay evidence is clearly obvious.

Style requirements for variant C (intentionally weak/general):
- Keep reasoning generic and high-level.
- Do NOT cite specific hub names, risk categories, severity numbers, or detailed evidence chains.
- Keep reasoning minimally actionable.

Also include: confidence (1-10).
Respond with ONLY this JSON, no markdown:
{"flag": "On Time"|"Delayed"|"Critical", "predicted_arrival": "ISO8601 or null (required for Delayed/Critical)", "reasoning": "short generic sentence", "confidence": 1-10}

Shipment data:
"""


def build_shipment_prompt(payload: dict, variant: str) -> str:
    """
    Build the full shipment-reasoning prompt for variant A, B, or C.

    payload is the same dict produced by
    SupplyMindAI/analysis/pipeline.py::_build_shipment_payload().
    """
    variant = variant.upper()
    if variant not in PROMPT_VARIANTS:
        raise ValueError(f"variant must be one of {PROMPT_VARIANTS}, got {variant!r}")

    prompts = {
        "A": _SHIPMENT_PROMPT_A,
        "B": _SHIPMENT_PROMPT_B,
        "C": _SHIPMENT_PROMPT_C,
    }
    return prompts[variant] + json.dumps(payload, indent=2, default=str)


# ---------------------------------------------------------------------------
# Experiment 2: Optimization summary
# ---------------------------------------------------------------------------

_OPTIMIZATION_PROMPT_A_TEMPLATE = """You are a supply chain optimization expert. Analyze the following delivered shipment data.

**Date range analyzed:** {start_str} to {end_str}

**On-time deliveries ({n_on_time}):** These shipments met their deadline.
**Delayed deliveries ({n_delayed}):** These shipments missed their deadline.

**Delay metrics:**
- Average delay (delayed shipments): {avg_delay} hours
- Hubs most often in delayed shipments: {top_delayed_hubs}
- Most common risk categories in delayed shipments: {common_risk_categories}

**On-time shipment summary (first 10):**
{on_time_json}

**Delayed shipment summary (first 10):**
{delayed_json}

Return ONLY valid JSON with no markdown or extra text:
{{
  "summary": "Max 100 words. Brief overview of supply chain findings and key issues.",
  "control_parameters": [
    "Hub Chicago: Increase capacity",
    "Hub Dallas: Reduce dwell time",
    "Priority shipments: Use faster mode",
    "Route LA-Chicago: Add risk-based ETA buffer"
  ],
  "top_parameters": [
    {{"label": "Short label 1", "detail": "Implementation steps."}},
    {{"label": "Short label 2", "detail": "Implementation steps."}},
    {{"label": "Short label 3", "detail": "Implementation steps."}}
  ]
}}

CRITICAL RULES - Use ONLY these 5 parameter types (no others):
1. Hub capacity: Use phrasings like "Hub X: Increase capacity" or "Hub X: Expand capacity" (name the hub from the data).
2. Dispatch time at hub: "Hub X: Reduce dwell time" or "Hub X: Speed up processing".
3. Transit mode: "Route X: Switch to faster transit" or "Priority shipments: Use faster mode".
4. Earlier dispatch: "Shipments via Hub X: Dispatch earlier" or "Route X: Add buffer time".
5. Risk-based buffer: "Route X: Add risk-based ETA buffer" or "Hub X route: Add predicted-risk buffer".

EXCLUDE (do NOT suggest): alternate routing, material type changes, supplier changes, or any action we cannot simulate with these 5 levers.

Rules:
- control_parameters: Exactly 3-4 items. Format as above. Name the specific hub or route from the data (e.g., use hubs from top_delayed_hubs). Never use vague targets.
- top_parameters: Exactly 2-3 objects. "label" = short button name matching one of the 5 types. "detail" = 1-2 sentences.
- Summary must be at most 100 words."""

_OPTIMIZATION_PROMPT_B_TEMPLATE = """You are a supply chain optimization expert. Analyze the following delivered shipment data.

**Date range analyzed:** {start_str} to {end_str}

**On-time deliveries ({n_on_time}):** These shipments met their deadline.
**Delayed deliveries ({n_delayed}):** These shipments missed their deadline.

**Delay metrics:**
- Average delay (delayed shipments): {avg_delay} hours
- Hubs most often in delayed shipments: {top_delayed_hubs}
- Most common risk categories in delayed shipments: {common_risk_categories}

**On-time shipment summary (first 10):**
{on_time_json}

**Delayed shipment summary (first 10):**
{delayed_json}

Return ONLY valid JSON with no markdown or extra text:
{{
  "summary": "Max 100 words. Brief overview of supply chain findings and key issues.",
  "control_parameters": [
    "Hub Chicago: Increase capacity",
    "Hub Dallas: Reduce dwell time",
    "Priority shipments: Use faster mode",
    "Route LA-Chicago: Add risk-based ETA buffer"
  ],
  "top_parameters": [
    {{"label": "Short label 1", "detail": "Implementation steps."}},
    {{"label": "Short label 2", "detail": "Implementation steps."}},
    {{"label": "Short label 3", "detail": "Implementation steps."}}
  ]
}}

CRITICAL RULES - Use ONLY these 5 parameter types (no others):
1. Hub capacity: Use phrasings like "Hub X: Increase capacity" or "Hub X: Expand capacity" (name the hub from the data).
2. Dispatch time at hub: "Hub X: Reduce dwell time" or "Hub X: Speed up processing".
3. Transit mode: "Route X: Switch to faster transit" or "Priority shipments: Use faster mode".
4. Earlier dispatch: "Shipments via Hub X: Dispatch earlier" or "Route X: Add buffer time".
5. Risk-based buffer: "Route X: Add risk-based ETA buffer" or "Hub X route: Add predicted-risk buffer".

EXCLUDE (do NOT suggest): alternate routing, material type changes, supplier changes, or any action we cannot simulate with these 5 levers.

Rules:
- control_parameters: Exactly 3-4 items. Format as above. Name the specific hub or route from the data (e.g., use hubs from top_delayed_hubs). Never use vague targets.
- top_parameters: Exactly 2-3 objects. "label" = short button name matching one of the 5 types. "detail" = 1-2 sentences.
- Summary must be at most 100 words.

ADDITIONAL LEVER-STRICT REQUIREMENT (variant B):
Every item in `control_parameters` MUST start with one of these exact prefixes (followed by ": <action>"):
  - "Hub <HubName>"
  - "Route <Origin>-<Destination>"
  - "Shipments via Hub <HubName>"
  - "Priority shipments"

You MUST reject any vague target. In particular, do NOT use: "Shipments:", "Deliveries:", "All hubs:", "Operations:", or any prefix that does not name a specific hub or route from the input data.

If you cannot identify a specific hub or route for a recommendation, omit it rather than emitting a vague one. control_parameters may have fewer than 3 items only if no valid hub/route grounding exists for an additional item."""

_OPTIMIZATION_PROMPT_C_TEMPLATE = """You are an operations assistant. Give a very brief, high-level recommendation summary from the delivered shipment data below.

Date range: {start_str} to {end_str}
On-time deliveries: {n_on_time}
Delayed deliveries: {n_delayed}
Average delay hours: {avg_delay}
Top delayed hubs: {top_delayed_hubs}
Top delayed risk categories: {common_risk_categories}

Return ONLY valid JSON:
{{
  "summary": "Max 60 words, very general.",
  "control_parameters": [
    "Operations: Improve planning",
    "Priority shipments: Increase attention"
  ],
  "top_parameters": [
    {{"label": "General action", "detail": "Short generic recommendation."}},
    {{"label": "General action", "detail": "Short generic recommendation."}}
  ]
}}

Rules:
- Keep output concise and generic.
- Do not include exact numbers in recommendations.
- Avoid specific hub- or route-level instructions.
"""


def build_optimization_prompt(
    on_time: list,
    delayed: list,
    metrics: dict,
    start_str: str,
    end_str: str,
    variant: str,
) -> str:
    """
    Build the full optimization-summary prompt for variant A, B, or C.

    Inputs match the call site in
    SupplyMindAI/analysis/optimization_pipeline.py::_call_openai_recommendations().
    """
    variant = variant.upper()
    if variant not in PROMPT_VARIANTS:
        raise ValueError(f"variant must be one of {PROMPT_VARIANTS}, got {variant!r}")

    prompts = {
        "A": _OPTIMIZATION_PROMPT_A_TEMPLATE,
        "B": _OPTIMIZATION_PROMPT_B_TEMPLATE,
        "C": _OPTIMIZATION_PROMPT_C_TEMPLATE,
    }
    return prompts[variant].format(
        start_str=start_str,
        end_str=end_str,
        n_on_time=len(on_time),
        n_delayed=len(delayed),
        avg_delay=metrics.get("avg_delay_hours", 0),
        top_delayed_hubs=metrics.get("top_delayed_hubs", []),
        common_risk_categories=metrics.get("common_risk_categories", []),
        on_time_json=json.dumps(on_time[:10], indent=2, default=str),
        delayed_json=json.dumps(delayed[:10], indent=2, default=str),
    )
