"""
01_generate_reports.py

Run prompts A / B / C against either(for shipment card & optimization card):
  --experiment shipment        (per-shipment delay reasoning)
  --experiment optimization    (date-range supply-chain summary)

Outputs:
  validation/data/shipment_reports.csv
  validation/data/opt_reports.csv

Caching:
  Existing rows in the output CSV are kept; only missing
  (sample_id, prompt_id) pairs are generated. Use --force to ignore the cache.

Cost / time:
  Generation uses gpt-4o-mini (matching production). 60 calls per experiment
  by default (20 samples x 3 prompts). With --workers 10 parallelism the full
  run is ~1-2 min.
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

import pandas as pd

_THIS = Path(__file__).resolve()
_PROJECT_ROOT = _THIS.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PROJECT_ROOT / "SupplyMindAI") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "SupplyMindAI"))

from analysis.pipeline import (  # noqa: E402
    _build_shipment_payload,
    _fetch_stops_and_enrich,
    _fetch_future_hubs_and_risks,
)
from analysis.optimization_pipeline import (  # noqa: E402
    _fetch_delivered_shipments_by_date,
    _fetch_stops_with_hubs_risks,
    _split_and_metrics,
    _parse_date_range,
)

from validation.prompts import (  # noqa: E402
    PROMPT_VARIANTS,
    build_shipment_prompt,
    build_optimization_prompt,
)
from validation.sampling import (  # noqa: E402
    pick_shipment_samples,
    pick_optimization_samples,
    fetch_all_shipments_for_validation,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEN_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.3  # > 0 so multi-run sampling produces variation
DEFAULT_WORKERS = 8
DATA_DIR = _THIS.parent / "data"
SHIPMENT_CSV = DATA_DIR / "shipment_reports.csv"
OPT_CSV = DATA_DIR / "opt_reports.csv"


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
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


# ---------------------------------------------------------------------------
# Shipment experiment
# ---------------------------------------------------------------------------

def _build_shipment_inputs(samples: list[dict]) -> dict[str, dict]:
    """
    Build the canonical payload (matching production pipeline.py) for each
    unique shipment_id in `samples`. Returns {shipment_id: payload}.
    """
    unique_ids = sorted({s["shipment_id"] for s in samples})

    shipments_all = fetch_all_shipments_for_validation()
    by_id = {s["shipment_id"]: s for s in shipments_all}
    selected = [by_id[i] for i in unique_ids if i in by_id]

    current_idx_by_ship = {
        s["shipment_id"]: s["current_stop_index"] or 0 for s in selected
    }
    stops_by_ship = _fetch_stops_and_enrich(unique_ids)
    future_data_by_ship = _fetch_future_hubs_and_risks(
        unique_ids, current_idx_by_ship
    )

    payloads: dict[str, dict] = {}
    for s in selected:
        sid = s["shipment_id"]
        payloads[sid] = _build_shipment_payload(
            s,
            stops_by_ship.get(sid, []),
            future_data_by_ship.get(sid, {"future_hubs": [], "future_risks": []}),
        )
    return payloads


def _generate_shipment_one(
    client,
    prompt_id: str,
    sample: dict,
    payload: dict,
    temperature: float,
) -> dict:
    """Run one (sample, prompt) generation. Returns a row dict for the CSV."""
    prompt_text = build_shipment_prompt(payload, prompt_id)
    err = None
    flag = predicted_arrival = reasoning = None
    confidence = None
    raw_response = ""
    try:
        resp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[{"role": "user", "content": prompt_text}],
            temperature=temperature,
        )
        raw_response = resp.choices[0].message.content or ""
        parsed = json.loads(_strip_code_fences(raw_response))
        flag = parsed.get("flag")
        predicted_arrival = parsed.get("predicted_arrival")
        reasoning = parsed.get("reasoning")
        confidence = parsed.get("confidence")
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    return {
        "experiment": "shipment",
        "prompt_id": prompt_id,
        "sample_id": sample["sample_id"],
        "shipment_id": sample["shipment_id"],
        "run_id": sample["run_id"],
        "flag": flag,
        "predicted_arrival": predicted_arrival,
        "reasoning": reasoning,
        "confidence": confidence,
        "raw_response": raw_response,
        "payload_json": json.dumps(payload, default=str),
        "generation_ts": datetime.utcnow().isoformat(timespec="seconds"),
        "error": err,
    }


def run_shipment_experiment(
    n: int,
    workers: int,
    temperature: float,
    force: bool,
    out_path: Path,
):
    samples = pick_shipment_samples(target=n)
    print(f"[shipment] {len(samples)} samples x {len(PROMPT_VARIANTS)} prompts "
          f"= {len(samples) * len(PROMPT_VARIANTS)} generations target.")

    payloads = _build_shipment_inputs(samples)
    print(f"[shipment] enriched payloads built for {len(payloads)} unique shipments.")

    cached: pd.DataFrame
    if out_path.exists() and not force:
        cached = pd.read_csv(out_path)
        cached_keys = set(zip(cached["sample_id"], cached["prompt_id"]))
        print(f"[shipment] cache hit: {len(cached_keys)} existing rows in {out_path.name}")
    else:
        cached = pd.DataFrame()
        cached_keys = set()

    todo: list[tuple[str, dict]] = []
    for s in samples:
        for p in PROMPT_VARIANTS:
            if (s["sample_id"], p) in cached_keys:
                continue
            todo.append((p, s))
    print(f"[shipment] {len(todo)} new generations to run.")
    if not todo:
        print("[shipment] nothing to do; cache complete.")
        return

    client = _get_openai_client()
    new_rows: list[dict] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(
                _generate_shipment_one,
                client,
                prompt_id,
                sample,
                payloads[sample["shipment_id"]],
                temperature,
            ): (prompt_id, sample)
            for prompt_id, sample in todo
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            row = fut.result()
            new_rows.append(row)
            err_msg = f" ERROR={row['error']}" if row["error"] else ""
            print(f"  [{i}/{len(todo)}] {row['prompt_id']} {row['sample_id']} "
                  f"flag={row['flag']!r}{err_msg}")

    elapsed = time.time() - started
    print(f"[shipment] generation done in {elapsed:.1f}s.")

    out_df = pd.concat([cached, pd.DataFrame(new_rows)], ignore_index=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"[shipment] wrote {len(out_df)} rows -> {out_path}")


# ---------------------------------------------------------------------------
# Optimization experiment
# ---------------------------------------------------------------------------

def _build_optimization_inputs(samples: list[dict]) -> dict[str, dict]:
    """
    For each unique range_id in `samples`, fetch + enrich + split data and
    return {range_id: {start_str, end_str, on_time, delayed, metrics}}.
    """
    unique_ranges: dict[str, dict] = {}
    for s in samples:
        rid = s["range_id"]
        if rid in unique_ranges:
            continue
        unique_ranges[rid] = {
            "start_date": s["start_date"],
            "end_date": s["end_date"],
        }

    out: dict[str, dict] = {}
    for rid, info in unique_ranges.items():
        start_ts, end_ts = _parse_date_range(
            "custom", info["start_date"], info["end_date"]
        )
        start_str = start_ts.strftime("%b %d, %Y")
        end_str = end_ts.strftime("%b %d, %Y")
        shipments = _fetch_delivered_shipments_by_date(start_ts, end_ts)
        if not shipments:
            out[rid] = {
                "start_str": start_str,
                "end_str": end_str,
                "on_time": [],
                "delayed": [],
                "metrics": {
                    "avg_delay_hours": 0,
                    "top_delayed_hubs": [],
                    "common_risk_categories": [],
                },
            }
            continue
        sids = [s["shipment_id"] for s in shipments]
        stops_by_ship = _fetch_stops_with_hubs_risks(sids)
        on_time, delayed, metrics = _split_and_metrics(shipments, stops_by_ship)
        out[rid] = {
            "start_str": start_str,
            "end_str": end_str,
            "on_time": on_time,
            "delayed": delayed,
            "metrics": metrics,
        }
    return out


def _generate_optimization_one(
    client,
    prompt_id: str,
    sample: dict,
    inputs: dict,
    temperature: float,
) -> dict:
    prompt_text = build_optimization_prompt(
        inputs["on_time"],
        inputs["delayed"],
        inputs["metrics"],
        inputs["start_str"],
        inputs["end_str"],
        prompt_id,
    )
    err = None
    summary = ""
    control_parameters: list = []
    top_parameters: list = []
    raw_response = ""
    try:
        resp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[{"role": "user", "content": prompt_text}],
            temperature=temperature,
        )
        raw_response = resp.choices[0].message.content or ""
        parsed = json.loads(_strip_code_fences(raw_response))
        summary = parsed.get("summary", "") or ""
        control_parameters = parsed.get("control_parameters", []) or []
        top_parameters = parsed.get("top_parameters", []) or []
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    metrics = inputs["metrics"]
    return {
        "experiment": "optimization",
        "prompt_id": prompt_id,
        "sample_id": sample["sample_id"],
        "range_id": sample["range_id"],
        "run_id": sample["run_id"],
        "start_date": str(sample["start_date"]),
        "end_date": str(sample["end_date"]),
        "summary": summary,
        "control_parameters_json": json.dumps(control_parameters, default=str),
        "top_parameters_json": json.dumps(top_parameters, default=str),
        "raw_response": raw_response,
        "on_time_count": len(inputs["on_time"]),
        "delayed_count": len(inputs["delayed"]),
        "avg_delay_hours": metrics.get("avg_delay_hours", 0),
        "top_delayed_hubs_json": json.dumps(metrics.get("top_delayed_hubs", [])),
        "common_risk_categories_json": json.dumps(metrics.get("common_risk_categories", [])),
        "generation_ts": datetime.utcnow().isoformat(timespec="seconds"),
        "error": err,
    }


def run_optimization_experiment(
    n: int,
    workers: int,
    temperature: float,
    force: bool,
    out_path: Path,
):
    samples = pick_optimization_samples(target=n)
    print(f"[optimization] {len(samples)} samples x {len(PROMPT_VARIANTS)} prompts "
          f"= {len(samples) * len(PROMPT_VARIANTS)} generations target.")

    inputs_by_range = _build_optimization_inputs(samples)
    print(f"[optimization] enriched inputs built for "
          f"{len(inputs_by_range)} unique date ranges.")

    cached: pd.DataFrame
    if out_path.exists() and not force:
        cached = pd.read_csv(out_path)
        cached_keys = set(zip(cached["sample_id"], cached["prompt_id"]))
        print(f"[optimization] cache hit: {len(cached_keys)} existing rows.")
    else:
        cached = pd.DataFrame()
        cached_keys = set()

    todo: list[tuple[str, dict]] = []
    for s in samples:
        for p in PROMPT_VARIANTS:
            if (s["sample_id"], p) in cached_keys:
                continue
            todo.append((p, s))
    print(f"[optimization] {len(todo)} new generations to run.")
    if not todo:
        print("[optimization] nothing to do; cache complete.")
        return

    client = _get_openai_client()
    new_rows: list[dict] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(
                _generate_optimization_one,
                client,
                prompt_id,
                sample,
                inputs_by_range[sample["range_id"]],
                temperature,
            ): (prompt_id, sample)
            for prompt_id, sample in todo
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            row = fut.result()
            err_msg = f" ERROR={row['error']}" if row["error"] else ""
            n_cp = len(json.loads(row["control_parameters_json"] or "[]"))
            print(f"  [{i}/{len(todo)}] {row['prompt_id']} {row['sample_id']} "
                  f"n_control_params={n_cp}{err_msg}")
            new_rows.append(row)

    elapsed = time.time() - started
    print(f"[optimization] generation done in {elapsed:.1f}s.")

    out_df = pd.concat([cached, pd.DataFrame(new_rows)], ignore_index=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"[optimization] wrote {len(out_df)} rows -> {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument(
        "--experiment", required=True, choices=("shipment", "optimization"),
        help="Which experiment to run.",
    )
    p.add_argument("--n", type=int, default=20,
                   help="Number of samples per prompt (default 20).")
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                   help="Concurrent OpenAI requests (default 8).")
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE,
                   help="Generator sampling temperature (default 0.3).")
    p.add_argument("--force", action="store_true",
                   help="Ignore cache and regenerate everything.")
    args = p.parse_args()

    if args.experiment == "shipment":
        run_shipment_experiment(
            n=args.n, workers=args.workers, temperature=args.temperature,
            force=args.force, out_path=SHIPMENT_CSV,
        )
    else:
        run_optimization_experiment(
            n=args.n, workers=args.workers, temperature=args.temperature,
            force=args.force, out_path=OPT_CSV,
        )


if __name__ == "__main__":
    main()
