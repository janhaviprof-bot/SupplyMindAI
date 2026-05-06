"""
Custom domain-specific rubrics + reviewer prompt builders.

Two independent rubrics:
    SHIPMENT     - 5 AI-scored 0-5 criteria + 1 deterministic boolean
    OPTIMIZATION - 5 AI-scored 0-5 criteria + 1 deterministic boolean

The boolean criteria are computed deterministically (not AI-judged) because
they map to hard production rules (e.g. "Critical only if priority_level >= 8")
where AI judgment would add noise. The 0-5 criteria are AI-judged with anchored
scale descriptions to keep scoring consistent across reports.

To minimize reviewer token cost we send a slim "key facts" extract to the
reviewer instead of the full enriched payload. The slim extract still contains
every signal needed to score the 0-5 criteria.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PROJECT_ROOT / "SupplyMindAI") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "SupplyMindAI"))

from analysis.optimization_pipeline import parse_recommendation_to_sim_param  # noqa: E402


# =============================================================================
# Shipment rubric
# =============================================================================

SHIPMENT_AI_CRITERIA = (
    "flag_accuracy",
    "grounding_specificity",
    "format_compliance",
    "actionability",
    "succinctness",
)
SHIPMENT_BOOL_CRITERIA = ("policy_compliant",)
SHIPMENT_ALL_CRITERIA = SHIPMENT_AI_CRITERIA + SHIPMENT_BOOL_CRITERIA


def slim_shipment_facts(payload: dict) -> dict:
    """
    Extract only the signals the reviewer needs to score a shipment report.
    Cuts reviewer input tokens ~40% vs sending the full enriched payload.
    """
    stops = payload.get("stops", []) or []
    future_hubs = payload.get("future_hubs", []) or []
    future_risks = payload.get("future_risks", []) or []
    current_idx = payload.get("current_stop_index") or 0

    past_on_time = True
    for s in stops:
        if (s.get("stop_number") or 0) <= current_idx:
            actual = s.get("actual_arrival")
            planned = s.get("planned_arrival")
            if actual and planned:
                try:
                    a = datetime.fromisoformat(str(actual).replace("Z", "+00:00"))
                    p = datetime.fromisoformat(str(planned).replace("Z", "+00:00"))
                    if a > p:
                        past_on_time = False
                        break
                except Exception:
                    past_on_time = False

    future_hubs_summary = [
        {"hub_name": h.get("hub_name"), "status": h.get("status")}
        for h in future_hubs[:3]
    ]
    severities = [r.get("severity") or 0 for r in future_risks]
    max_severity = max(severities) if severities else 0
    risk_categories = sorted({r.get("category") for r in future_risks if r.get("category")})

    return {
        "shipment_id": payload.get("shipment_id"),
        "priority_level": payload.get("priority_level"),
        "final_deadline": payload.get("final_deadline"),
        "current_stop_index": current_idx,
        "past_on_time": past_on_time,
        "future_hubs_summary": future_hubs_summary,
        "max_severity": max_severity,
        "risk_categories": risk_categories,
        "n_future_risks": len(future_risks),
        "total_stops": len(stops),
    }


def compute_shipment_policy_compliance(payload: dict, generated: dict) -> bool:
    """
    Deterministic policy check (not AI-judged):
      - Critical flag is allowed only if priority_level >= 8.
      - For Delayed/Critical, predicted_arrival (when present) must be after final_deadline.
    Returns True iff both rules hold.
    """
    flag = (generated.get("flag") or "").strip().lower()
    priority = payload.get("priority_level") or 0
    if flag == "critical" and priority < 8:
        return False

    if flag in ("delayed", "critical"):
        pred = generated.get("predicted_arrival")
        deadline = payload.get("final_deadline")
        if pred and deadline:
            try:
                p = datetime.fromisoformat(str(pred).replace("Z", "+00:00"))
                d = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
                if p <= d:
                    return False
            except Exception:
                # Unparseable timestamp -> treat as policy violation
                return False
    return True


_SHIPMENT_REVIEWER_PROMPT = """You are a strict quality control validator for AI-generated shipment delay reports. Score the report below against the rubric and return ONLY valid JSON.

# Source data (key facts about the shipment)

```json
{slim_facts_json}
```

# Generated report being scored

```json
{generated_json}
```

# Rubric (score each on 0-5; use the anchors below)

1. **flag_accuracy** (0-5) - Does the `flag` ("On Time" / "Delayed" / "Critical") match the evidence?
   - 5: Flag is fully consistent with past_on_time, future hub statuses, and max_severity.
   - 3: Flag is defensible but borderline given the evidence.
   - 0: Flag clearly contradicts the evidence (e.g., "On Time" with past_on_time=false and max_severity>=7).

2. **grounding_specificity** (0-5) - Does the `reasoning` cite real entities from the source data?
   - 5: Names at least one exact hub_name from future_hubs_summary AND a real category from risk_categories.
   - 3: Mentions a hub or risk category but generalizes (e.g., "Midwest hubs" instead of the specific hub).
   - 0: Invents hub names or risk types not present in the source data.

3. **format_compliance** (0-5) - Does reasoning follow "Delays at [hub(s)] due to [risks]." conventions?
   - 5: 1-2 sentences, lowercase risk words (congestion/traffic/labor/bad weather), no severity numbers, no "predicted arrival is after the deadline" boilerplate.
   - 3: Mostly correct but minor format issues (e.g., capitalized risk words).
   - 0: Wrong structure, contains forbidden boilerplate, or contains severity/priority numbers.
   - For an "On Time" report with empty/short reasoning, score 5 if it is concise and 0 if it adds boilerplate.

4. **actionability** (0-5) - Could a supply-chain manager identify which hub / which risk to address?
   - 5: Manager knows immediately where to act and what risk drives the delay.
   - 3: Action is implied but requires reading other data.
   - 0: No actionable signal.

5. **succinctness** (0-5) - 1-2 sentences, no filler.
   - 5: <= 2 sentences, no redundant phrasing.
   - 3: Slightly verbose.
   - 0: Multi-paragraph or repetitive.

# Output schema

Return ONLY this JSON, no markdown:

{{
  "flag_accuracy": 0-5,
  "grounding_specificity": 0-5,
  "format_compliance": 0-5,
  "actionability": 0-5,
  "succinctness": 0-5,
  "details": "<= 40 word justification"
}}
"""


def build_shipment_reviewer_prompt(slim_facts: dict, generated: dict) -> str:
    """Build reviewer prompt for shipment reports."""
    return _SHIPMENT_REVIEWER_PROMPT.format(
        slim_facts_json=json.dumps(slim_facts, indent=2, default=str),
        generated_json=json.dumps(
            {
                "flag": generated.get("flag"),
                "predicted_arrival": generated.get("predicted_arrival"),
                "reasoning": generated.get("reasoning"),
                "confidence": generated.get("confidence"),
            },
            indent=2,
            default=str,
        ),
    )


# =============================================================================
# Optimization rubric
# =============================================================================

OPTIMIZATION_AI_CRITERIA = (
    "lever_compliance",
    "data_grounding",
    "specificity",
    "actionability",
    "summary_quality",
)
OPTIMIZATION_BOOL_CRITERIA = ("simulatable",)
OPTIMIZATION_ALL_CRITERIA = OPTIMIZATION_AI_CRITERIA + OPTIMIZATION_BOOL_CRITERIA


def slim_optimization_facts(
    metrics: dict,
    n_on_time: int,
    n_delayed: int,
    start_str: str,
    end_str: str,
) -> dict:
    """Extract minimal source facts the reviewer needs."""
    return {
        "date_range": f"{start_str} to {end_str}",
        "on_time_count": int(n_on_time),
        "delayed_count": int(n_delayed),
        "avg_delay_hours": metrics.get("avg_delay_hours", 0),
        "top_delayed_hubs": metrics.get("top_delayed_hubs", []),
        "common_risk_categories": metrics.get("common_risk_categories", []),
    }


def compute_optimization_simulatable(control_parameters) -> bool:
    """
    Deterministic check: every control_parameters entry must parse via the
    production parser (parse_recommendation_to_sim_param). Empty list -> False.
    """
    if not control_parameters:
        return False
    if not isinstance(control_parameters, (list, tuple)):
        return False
    for p in control_parameters:
        if not isinstance(p, str):
            return False
        if parse_recommendation_to_sim_param(p) is None:
            return False
    return True


_OPTIMIZATION_REVIEWER_PROMPT = """You are a strict quality control validator for AI-generated supply-chain optimization reports. Score the report below against the rubric and return ONLY valid JSON.

# Source data (key facts about the analyzed period)

```json
{slim_facts_json}
```

# Generated report being scored

```json
{generated_json}
```

# Reference: the 5 simulatable levers
1. Hub capacity        - "Hub <Name>: Increase / Expand capacity"
2. Dispatch time       - "Hub <Name>: Reduce dwell time" / "Speed up processing"
3. Transit mode        - "Route <X>: Switch to faster transit" / "Priority shipments: Use faster mode"
4. Earlier dispatch    - "Shipments via Hub <Name>: Dispatch earlier" / "Add buffer time"
5. Risk-based buffer   - "Route <X>: Add risk-based ETA buffer" / "Add predicted-risk buffer"

# Rubric (score each on 0-5; use the anchors below)

SCORING DISCIPLINE (important):
- Use the full 0-5 scale; avoid defaulting to 4.
- Score 5 only when the criterion is fully satisfied with no material gaps.
- Score 4 only when there is exactly one minor issue.
- Score 3 when there are clear but moderate issues.
- Score 2 or below when the output is generic, weakly grounded, or hard to execute.

1. **lever_compliance** (0-5) - How well do the `control_parameters` map to one of the 5 levers above?
   - 5: Every item maps cleanly to one of the 5 levers and uses canonical phrasing.
   - 4: All items map, but one item has minor phrasing ambiguity.
   - 3: At least one item is ambiguous/non-canonical OR one item weakly maps.
   - 2: Multiple items are ambiguous or only loosely map to levers.
   - 1-0: Un-simulatable actions appear (alternate routing, supplier/material changes).

2. **data_grounding** (0-5) - Do the `summary` and `control_parameters` cite real values from the source data?
   - 5: Cites >=2 exact hubs from top_delayed_hubs, >=1 exact risk category, and >=1 numeric metric from source data.
   - 4: Cites >=2 exact hubs and >=1 numeric metric, but misses category OR has one weak reference.
   - 3: Cites at least one real hub/category/number but grounding is partial.
   - 2: Mostly generic statements with minimal concrete citations.
   - 1-0: Fabricates values or omits concrete source references.

3. **specificity** (0-5) - Does each control_parameter name a concrete hub or route, not a vague target?
   - 5: Every control item names a concrete hub/route from the source data.
   - 4: One item is slightly generic but still operationally specific.
   - 3: One item is vague ("Shipments:", "All hubs:") or lacks concrete target.
   - 2: Multiple vague targets.
   - 1-0: Predominantly generic recommendations.

4. **actionability** (0-5) - Could a supply-chain manager implement these recommendations directly?
   - 5: Clear owner + lever for each item, and top_parameters include concrete implementation steps.
   - 4: Mostly implementable; one detail is underspecified.
   - 3: Understandable actions but several missing operational details.
   - 2: Abstract actions with weak implementation guidance.
   - 1-0: Not actionable in practice.

5. **summary_quality** (0-5) - Is the `summary` concise (<=100 words) and informative about findings?
   - 5: <=100 words, identifies main bottleneck, cites concrete evidence, and links to recommendation direction.
   - 4: Concise and informative but misses one evidence/linkage element.
   - 3: Concise but generic, with limited insight.
   - 2: Vague summary or weakly connected to recommendations.
   - 1-0: Over-length, vacuous, or contradictory.

# Output schema

Return ONLY this JSON, no markdown:

{{
  "lever_compliance": 0-5,
  "data_grounding": 0-5,
  "specificity": 0-5,
  "actionability": 0-5,
  "summary_quality": 0-5,
  "details": "<= 40 word justification"
}}
"""


def build_optimization_reviewer_prompt(slim_facts: dict, generated: dict) -> str:
    """Build reviewer prompt for optimization reports."""
    return _OPTIMIZATION_REVIEWER_PROMPT.format(
        slim_facts_json=json.dumps(slim_facts, indent=2, default=str),
        generated_json=json.dumps(
            {
                "summary": generated.get("summary"),
                "control_parameters": generated.get("control_parameters"),
                "top_parameters": generated.get("top_parameters"),
            },
            indent=2,
            default=str,
        ),
    )
