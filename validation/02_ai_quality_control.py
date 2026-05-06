"""
02_ai_quality_control.py

AI reviewer scores each generated report (from 01_generate_reports.py) using
the custom rubrics defined in validation/rubrics.py.

For each (sample_id, prompt_id) pair we record:
  - 5 AI-judged 0-5 scores (one per AI rubric criterion)
  - 1 deterministic boolean (policy_compliant / simulatable)
  - overall_score = mean of the 5 AI 0-5 scores

A small reliability subset (first 5 reports per experiment) is scored TWICE
so 03_statistical_comparison.py can compute reviewer intra-class correlation.

Reviewer model defaults to gpt-4.1-nano (cheapest with JSON mode); override
with --reviewer-model gpt-4o-mini for stricter scoring.

Outputs:
  validation/data/shipment_scores.csv
  validation/data/opt_scores.csv
  validation/data/reviewer_reliability.csv
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from statistics import mean

import pandas as pd

_THIS = Path(__file__).resolve()
_PROJECT_ROOT = _THIS.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PROJECT_ROOT / "SupplyMindAI") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "SupplyMindAI"))

from validation.rubrics import (  # noqa: E402
    SHIPMENT_AI_CRITERIA,
    OPTIMIZATION_AI_CRITERIA,
    slim_shipment_facts,
    slim_optimization_facts,
    compute_shipment_policy_compliance,
    compute_optimization_simulatable,
    build_shipment_reviewer_prompt,
    build_optimization_reviewer_prompt,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_REVIEWER_MODEL = "gpt-4.1-nano"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 300
DEFAULT_WORKERS = 6
DEFAULT_RELIABILITY_N = 5
DEFAULT_RELIABILITY_REPEATS = 2

DATA_DIR = _THIS.parent / "data"
SHIPMENT_REPORTS_CSV = DATA_DIR / "shipment_reports.csv"
OPT_REPORTS_CSV = DATA_DIR / "opt_reports.csv"
SHIPMENT_SCORES_CSV = DATA_DIR / "shipment_scores.csv"
OPT_SCORES_CSV = DATA_DIR / "opt_scores.csv"
RELIABILITY_CSV = DATA_DIR / "reviewer_reliability.csv"


def _load_env():
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get_openai_client():
    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in .env at project root.")
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def _strip_code_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _call_reviewer(client, model: str, prompt: str, temperature: float,
                   max_tokens: int) -> dict:
    """One reviewer call. Raises on hard error; caller wraps as needed."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system",
             "content": "You are a strict QC validator. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=max_tokens,
    )
    raw = resp.choices[0].message.content or ""
    return json.loads(_strip_code_fences(raw))


def _coerce_score(val, lo: int = 0, hi: int = 5) -> int | None:
    """Clamp val to [lo, hi]. Return None if not parseable."""
    try:
        x = int(round(float(val)))
        return max(lo, min(hi, x))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Shipment scoring
# ---------------------------------------------------------------------------

def _score_shipment_one(
    client,
    model: str,
    report_row: dict,
    temperature: float,
    max_tokens: int,
) -> dict:
    """Score one shipment report -> row for the scores CSV."""
    payload = json.loads(report_row["payload_json"])
    slim = slim_shipment_facts(payload)
    generated = {
        "flag": report_row.get("flag"),
        "predicted_arrival": report_row.get("predicted_arrival"),
        "reasoning": report_row.get("reasoning"),
        "confidence": report_row.get("confidence"),
    }

    # Deterministic boolean check
    try:
        policy_ok = compute_shipment_policy_compliance(payload, generated)
    except Exception:
        policy_ok = False

    err = None
    ai_scores: dict[str, int | None] = {c: None for c in SHIPMENT_AI_CRITERIA}
    details = ""
    try:
        prompt = build_shipment_reviewer_prompt(slim, generated)
        parsed = _call_reviewer(client, model, prompt, temperature, max_tokens)
        for c in SHIPMENT_AI_CRITERIA:
            ai_scores[c] = _coerce_score(parsed.get(c))
        details = (parsed.get("details") or "")[:300]
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    valid = [v for v in ai_scores.values() if v is not None]
    overall = round(mean(valid), 3) if valid else None

    # Covariates for regression
    covariates = {
        "n_future_risks": int(slim.get("n_future_risks") or 0),
        "max_severity": int(slim.get("max_severity") or 0),
        "total_stops": int(slim.get("total_stops") or 0),
        "priority_level": int(payload.get("priority_level") or 0),
    }

    return {
        "experiment": "shipment",
        "sample_id": report_row["sample_id"],
        "shipment_id": report_row["shipment_id"],
        "prompt_id": report_row["prompt_id"],
        "run_id": report_row["run_id"],
        **{k: ai_scores[k] for k in SHIPMENT_AI_CRITERIA},
        "policy_compliant": bool(policy_ok),
        "overall_score": overall,
        "reviewer_details": details,
        "review_ts": datetime.utcnow().isoformat(timespec="seconds"),
        "review_error": err,
        **covariates,
    }


# ---------------------------------------------------------------------------
# Optimization scoring
# ---------------------------------------------------------------------------

def _score_optimization_one(
    client,
    model: str,
    report_row: dict,
    temperature: float,
    max_tokens: int,
) -> dict:
    n_on = int(report_row.get("on_time_count") or 0)
    n_dly = int(report_row.get("delayed_count") or 0)
    avg_delay = float(report_row.get("avg_delay_hours") or 0)
    top_hubs = json.loads(report_row.get("top_delayed_hubs_json") or "[]")
    risk_cats = json.loads(report_row.get("common_risk_categories_json") or "[]")
    metrics = {
        "avg_delay_hours": avg_delay,
        "top_delayed_hubs": top_hubs,
        "common_risk_categories": risk_cats,
    }
    slim = slim_optimization_facts(
        metrics, n_on, n_dly,
        report_row.get("start_date", ""), report_row.get("end_date", ""),
    )

    control_params = json.loads(report_row.get("control_parameters_json") or "[]")
    top_params = json.loads(report_row.get("top_parameters_json") or "[]")
    generated = {
        "summary": report_row.get("summary"),
        "control_parameters": control_params,
        "top_parameters": top_params,
    }

    simulatable = compute_optimization_simulatable(control_params)

    err = None
    ai_scores: dict[str, int | None] = {c: None for c in OPTIMIZATION_AI_CRITERIA}
    details = ""
    try:
        prompt = build_optimization_reviewer_prompt(slim, generated)
        parsed = _call_reviewer(client, model, prompt, temperature, max_tokens)
        for c in OPTIMIZATION_AI_CRITERIA:
            ai_scores[c] = _coerce_score(parsed.get(c))
        details = (parsed.get("details") or "")[:300]
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    valid = [v for v in ai_scores.values() if v is not None]
    overall = round(mean(valid), 3) if valid else None

    return {
        "experiment": "optimization",
        "sample_id": report_row["sample_id"],
        "range_id": report_row["range_id"],
        "prompt_id": report_row["prompt_id"],
        "run_id": report_row["run_id"],
        **{k: ai_scores[k] for k in OPTIMIZATION_AI_CRITERIA},
        "simulatable": bool(simulatable),
        "overall_score": overall,
        "reviewer_details": details,
        "review_ts": datetime.utcnow().isoformat(timespec="seconds"),
        "review_error": err,
        # Covariates for regression
        "on_time_count": n_on,
        "delayed_count": n_dly,
        "avg_delay_hours": avg_delay,
        "n_top_hubs": len(top_hubs),
    }


# ---------------------------------------------------------------------------
# Driver shared by both experiments
# ---------------------------------------------------------------------------

def _select_reliability_pairs(reports_df: pd.DataFrame, n: int) -> set[tuple]:
    """Pick first N (sample_id, prompt_id) pairs (sorted) for reliability."""
    if reports_df.empty:
        return set()
    df = reports_df.sort_values(["sample_id", "prompt_id"]).reset_index(drop=True)
    return set(zip(df["sample_id"].head(n), df["prompt_id"].head(n)))


def run_experiment(
    experiment: str,
    n: int | None,
    workers: int,
    reviewer_model: str,
    temperature: float,
    max_tokens: int,
    force: bool,
    reliability_n: int,
    reliability_repeats: int,
):
    if experiment == "shipment":
        reports_path = SHIPMENT_REPORTS_CSV
        scores_path = SHIPMENT_SCORES_CSV
        score_one = _score_shipment_one
        criteria = SHIPMENT_AI_CRITERIA
    else:
        reports_path = OPT_REPORTS_CSV
        scores_path = OPT_SCORES_CSV
        score_one = _score_optimization_one
        criteria = OPTIMIZATION_AI_CRITERIA

    if not reports_path.exists():
        raise SystemExit(
            f"Missing {reports_path}. Run 01_generate_reports.py first."
        )

    reports_df = pd.read_csv(reports_path)
    if n is not None:
        # Smoke-test: reduce to N samples worth of rows (still all 3 prompts).
        keep_ids = (
            reports_df.sort_values(["sample_id", "prompt_id"])["sample_id"]
            .drop_duplicates()
            .head(n)
            .tolist()
        )
        reports_df = reports_df[reports_df["sample_id"].isin(keep_ids)].copy()

    reports_df = reports_df.dropna(subset=["raw_response"]).reset_index(drop=True)
    reports_df = reports_df[reports_df["error"].isna()].reset_index(drop=True)
    print(f"[{experiment}] reports to consider: {len(reports_df)}")

    cached_scores = pd.DataFrame()
    cached_keys: set[tuple] = set()
    if scores_path.exists() and not force:
        cached_scores = pd.read_csv(scores_path)
        cached_keys = set(zip(cached_scores["sample_id"], cached_scores["prompt_id"]))
        print(f"[{experiment}] scores cache: {len(cached_keys)} existing rows.")

    todo: list[dict] = []
    for _, row in reports_df.iterrows():
        key = (row["sample_id"], row["prompt_id"])
        if key in cached_keys:
            continue
        todo.append(row.to_dict())
    print(f"[{experiment}] new reviews to run: {len(todo)}")

    reliability_pairs = _select_reliability_pairs(reports_df, reliability_n)
    if reliability_repeats > 1:
        print(f"[{experiment}] reliability subset: {len(reliability_pairs)} pairs "
              f"x {reliability_repeats} repeats.")

    cached_reliability = pd.DataFrame()
    if RELIABILITY_CSV.exists() and not force:
        cached_reliability = pd.read_csv(RELIABILITY_CSV)

    client = _get_openai_client()
    new_score_rows: list[dict] = []
    new_reliability_rows: list[dict] = []
    started = time.time()

    def _do_score(row_dict, repeat_id):
        return repeat_id, score_one(
            client, reviewer_model, row_dict, temperature, max_tokens
        )

    futures = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for row in todo:
            futures[ex.submit(_do_score, row, 0)] = ("main", row)
        for _, row in reports_df.iterrows():
            key = (row["sample_id"], row["prompt_id"])
            if key not in reliability_pairs:
                continue
            for r in range(1, reliability_repeats):
                futures[ex.submit(_do_score, row.to_dict(), r)] = ("reliability", row)

        total = len(futures)
        for i, fut in enumerate(as_completed(futures), start=1):
            kind, row = futures[fut]
            try:
                repeat_id, scored = fut.result()
            except Exception as e:
                print(f"  [{i}/{total}] FAILED {kind} {row['sample_id']} "
                      f"{row['prompt_id']}: {e}")
                continue
            tag = f"{scored['prompt_id']} {scored['sample_id']} overall={scored['overall_score']}"
            err_msg = f" ERROR={scored.get('review_error')}" if scored.get("review_error") else ""
            print(f"  [{i}/{total}] {kind:<11} repeat={repeat_id} {tag}{err_msg}")
            if kind == "main":
                new_score_rows.append(scored)
            new_reliability_rows.append({
                "experiment": experiment,
                "sample_id": scored["sample_id"],
                "prompt_id": scored["prompt_id"],
                "repeat_id": repeat_id,
                "overall_score": scored["overall_score"],
                **{c: scored.get(c) for c in criteria},
                "review_ts": scored["review_ts"],
                "review_error": scored.get("review_error"),
            })

    elapsed = time.time() - started
    print(f"[{experiment}] reviewer done in {elapsed:.1f}s.")

    # Save scores
    out_scores = pd.concat([cached_scores, pd.DataFrame(new_score_rows)], ignore_index=True)
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    out_scores.to_csv(scores_path, index=False)
    print(f"[{experiment}] wrote {len(out_scores)} score rows -> {scores_path}")

    # Save reliability rows (append, dedupe by experiment+sample+prompt+repeat)
    if new_reliability_rows:
        out_rel = pd.concat(
            [cached_reliability, pd.DataFrame(new_reliability_rows)],
            ignore_index=True,
        )
        out_rel = out_rel.drop_duplicates(
            subset=["experiment", "sample_id", "prompt_id", "repeat_id"], keep="last"
        )
        RELIABILITY_CSV.parent.mkdir(parents=True, exist_ok=True)
        out_rel.to_csv(RELIABILITY_CSV, index=False)
        print(f"[{experiment}] reliability file: {len(out_rel)} rows -> {RELIABILITY_CSV}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument(
        "--experiment", required=True, choices=("shipment", "optimization"),
        help="Which experiment to score.",
    )
    p.add_argument("--n", type=int, default=None,
                   help="Smoke test: score only first N samples.")
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                   help="Concurrent reviewer requests (default 6).")
    p.add_argument("--reviewer-model", default=DEFAULT_REVIEWER_MODEL,
                   help=f"Reviewer model (default {DEFAULT_REVIEWER_MODEL}). "
                        "Override with gpt-4o-mini for stricter scoring.")
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE,
                   help="Reviewer temperature (default 0.1 for consistency).")
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
                   help="Reviewer max output tokens (default 300).")
    p.add_argument("--force", action="store_true",
                   help="Ignore cache and re-score everything.")
    p.add_argument("--reliability-n", type=int, default=DEFAULT_RELIABILITY_N,
                   help="How many reports to score multiple times (default 5).")
    p.add_argument("--reliability-repeats", type=int,
                   default=DEFAULT_RELIABILITY_REPEATS,
                   help="Number of repeated scorings for the reliability subset "
                        "(default 2).")
    args = p.parse_args()

    run_experiment(
        experiment=args.experiment,
        n=args.n,
        workers=args.workers,
        reviewer_model=args.reviewer_model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        force=args.force,
        reliability_n=args.reliability_n,
        reliability_repeats=args.reliability_repeats,
    )


if __name__ == "__main__":
    main()
