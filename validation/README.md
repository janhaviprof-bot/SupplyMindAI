# SupplyMind AI - Report Validation System

A separate, self-contained validation experiment for the SupplyMind AI app.
It compares **three prompt variants (A / B / C)** for two AI-generated
outputs in the production app, scores them with an AI reviewer using a
**custom domain-specific rubric**, and runs **t-test / ANOVA / regression**
to determine whether one prompt is significantly better than the others.

The plan that drove this implementation lives at
[validation_plan.md](validation_plan.md).

## What it validates

| Experiment | Production source | What we score |
|---|---|---|
| **shipment** | `_call_openai` in [`SupplyMindAI/analysis/pipeline.py`](../SupplyMindAI/analysis/pipeline.py) | The `flag` + `reasoning` for in-transit shipments (Card 1 in the app) |
| **optimization** | `_call_openai_recommendations` in [`SupplyMindAI/analysis/optimization_pipeline.py`](../SupplyMindAI/analysis/optimization_pipeline.py) | The `summary` + `control_parameters` for delivered shipments (Card 3 in the app) |

## Quick start

```powershell
# 1. Install validation-only deps (separate from the app's requirements)
pip install -r validation/requirements.txt

# 2. Make sure .env has OPENAI_API_KEY and POSTGRES_CONNECTION_STRING
#    (same .env the app uses)

# 3. Smoke test (~$0.02): run Phase 1/2 on the first N samples
py validation/run_validation.py --phase 1 --n 3
py validation/run_validation.py --phase 2

# 4. Full run (default N=50 samples per prompt; higher cost/time)
py validation/run_validation.py --phase 1
py validation/run_validation.py --phase 2

# 5. Override sample size (more/less samples per prompt)
py validation/run_validation.py --phase 1 --n 20
py validation/run_validation.py --phase 2
```

All scripts cache their output in `validation/data/` and skip work that is
already done, so re-runs are nearly free.

## Folder layout

```
validation/
  __init__.py
  validation_plan.md               # Original plan (architecture, rubric, stats)
  README.md                        # This file
  requirements.txt                 # openai, pandas, scipy, pingouin, ...
  prompts.py                       # Prompt A / B / C builders
  rubrics.py                       # AI reviewer prompts + deterministic checks
  sampling.py                      # Deterministic sample selection
  01_generate_reports.py           # Generate reports for each prompt variant
  02_ai_quality_control.py         # AI reviewer scores reports
  03_statistical_comparison.py     # t-test, ANOVA, regression, ICC
  run_validation.py                # Two-phase wrapper (generate+review, then stats)
  data/
    shipment_reports.csv           # Generated reports (one row per sample x prompt)
    shipment_scores.csv            # Reviewer scores (one row per sample x prompt)
    shipment_stats_summary.md      # Auto-generated stats writeup
    opt_reports.csv
    opt_scores.csv
    opt_stats_summary.md
    reviewer_reliability.csv       # Repeat scores for ICC
```

## Prompt variants

Each prompt builder takes the production prompt as the **A baseline**, then
adds a small targeted addendum for B and C.

### Shipment experiment
- **A (baseline)** - mirrors the production prompt verbatim.
- **B (strict-grounding)** - reasoning MUST cite an exact `hub_name` from
  `future_hubs` and an exact `category` from `future_risks`.
- **C (self-check)** - perform an internal evidence checklist
  (past_on_time, congested hubs, severity>=7 risks, priority>=8) before
  emitting the JSON.

### Optimization experiment
- **A (baseline)** - mirrors the production recommendation prompt.
- **B (lever-strict)** - every `control_parameters` item MUST start with
  one of the canonical lever prefixes (`Hub <Name>`, `Route <X>`, etc.).
- **C (negative control)** - intentionally weaker comparator for stress-testing
  statistical separation (keeps valid JSON but encourages generic, low-specificity output).

## Custom rubrics (not generic Likert)

### Shipment rubric

| Criterion | Type | Source | What it measures |
|---|---|---|---|
| `policy_compliant` | bool | deterministic | `Critical` only if `priority>=8`; `predicted_arrival > final_deadline` for Delayed/Critical |
| `flag_accuracy` | 0-5 | AI | Does flag match the evidence? |
| `grounding_specificity` | 0-5 | AI | Cites real `hub_name`s and risk categories |
| `format_compliance` | 0-5 | AI | Matches `Delays at [hub] due to [risk].` template |
| `actionability` | 0-5 | AI | Manager can identify which hub / which risk to address |
| `succinctness` | 0-5 | AI | 1-2 sentences, no filler |

### Optimization rubric

| Criterion | Type | Source | What it measures |
|---|---|---|---|
| `simulatable` | bool | deterministic | All `control_parameters` parse via `parse_recommendation_to_sim_param()` |
| `lever_compliance` | 0-5 | AI | Recommendations map cleanly to one of the 5 production levers |
| `data_grounding` | 0-5 | AI | Cites real hubs/categories/numbers from `metrics` |
| `specificity` | 0-5 | AI | Each item names a concrete hub or route |
| `actionability` | 0-5 | AI | Recommendations are implementable |
| `summary_quality` | 0-5 | AI | <=100 words, names the bottleneck |

`overall_score` = mean of the 5 AI 0-5 criteria.

## Statistical tests

For each experiment, `03_statistical_comparison.py` runs:

1. Descriptive stats per prompt (n, mean, SD, per-criterion means).
2. Bartlett's test for variance equality on `overall_score`.
3. One-way ANOVA on `overall_score ~ prompt_id` (Welch's if variances unequal).
4. Pairwise t-tests (A-vs-B, A-vs-C, B-vs-C) with Holm correction.
5. Per-criterion ANOVA so we can see WHICH dimension a prompt improved.
6. Linear regression `overall_score ~ prompt + covariates` so the prompt
   effect is reported after controlling for input difficulty.
7. Chi-squared test of independence for the boolean criterion across prompts.
8. Intra-class correlation on the reliability subset (5 reports x 2 repeats)
   to demonstrate reviewer stability.
9. Verdict block: best prompt + p-value.

## Cost / runtime

| Run | Calls | Approx. cost | Approx. wall-clock |
|---|---|---|---|
| Smoke test (`--n 3`) | ~18 | ~$0.02 | ~30 s |
| Full shipment | ~70 | ~$0.10 | ~3 min |
| Full optimization | ~70 | ~$0.10 | ~3 min |
| Full both experiments | ~140 | ~$0.15-$0.25 | ~5-10 min |

Cost optimizations baked in:
- Reviewer uses **`gpt-4.1-nano`** by default (cheapest model that supports
  JSON mode).
- Reviewer receives a **slim "key facts" extract**, not the full enriched
  payload (~40% fewer reviewer input tokens).
- Both `01_*` and `02_*` are **idempotent** - existing CSV rows are skipped
  on re-run unless `--force` is passed.
- `--n N` smoke-test mode for cheap iteration.
- Reliability subset is just 5 reports x 2 repeats per experiment.
- Reviewer responses are capped at **300 output tokens** (output is small JSON).

## Useful CLI flags

`01_generate_reports.py`:
- `--n N` - run only N samples per prompt (smoke test)
- `--workers K` - concurrent OpenAI calls (default 8)
- `--temperature T` - generator sampling temperature (default 0.3)
- `--force` - ignore cached rows

`02_ai_quality_control.py`:
- `--n N` - score only first N samples
- `--reviewer-model` - default `gpt-4.1-nano`; override with `gpt-4o-mini`
  for stricter scoring
- `--temperature T` - reviewer temperature (default 0.1 for consistency)
- `--max-tokens N` - reviewer output cap (default 300)
- `--reliability-n N` - how many reports get repeat scoring (default 5)
- `--reliability-repeats K` - repeats per reliability report (default 2)
- `--force` - ignore cached scores

`03_statistical_comparison.py`:
- `--experiment shipment | optimization | both`

## How this maps to the assignment rubric

| Rubric criterion | Where it lives |
|---|---|
| Customized validation framework | [`rubrics.py`](rubrics.py) - domain-specific rubric, not generic Likert |
| Qualitative content analysis | [`02_ai_quality_control.py`](02_ai_quality_control.py) - AI reviewer is the systematic evaluator |
| Experimental design | [`prompts.py`](prompts.py) (A/B/C) + [`sampling.py`](sampling.py) (>=20 samples per prompt) -> 60+ scores per experiment |
| Statistical analysis | [`03_statistical_comparison.py`](03_statistical_comparison.py) - Bartlett -> ANOVA -> pairwise t-tests -> regression -> ICC |
| Implementation | This folder. Working CLI scripts that import the existing app pipelines via `sys.path` adjustment, so the production app is unchanged. |

## Notes on a small dataset

The shipped demo DB has 5 shipments. The validation experiment scales by
**replicating each unique input across multiple `run_id`s** at
`temperature=0.3`, so each (shipment, run) pair produces an independent draw.
With 20 samples per prompt that yields 60 generations and 60 reviewer scores
per experiment, which is enough for a one-way ANOVA. If you load a larger
DB, the sampler automatically picks up to 20 unique shipments before
falling back to replication.

`temperature=0.3` is intentionally elevated above the production app's
shipment-classification setting (0) so multi-run sampling produces variation
to test against. Variant A still uses the **same prompt text** as production -
the only difference is sampling temperature for the experiment itself.
