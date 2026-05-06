# SupplyMind AI - Report Validation System

A separate, self-contained validation experiment for the SupplyMind AI app.
It compares **three prompt variants (A / B / C)** for two AI-generated
outputs in the production app, scores them with an AI reviewer using a
**custom domain-specific rubric**, and runs **t-tests + ANOVA**
to determine whether one prompt is significantly better than the others.

The plan that drove this implementation lives at
[validation_plan.md](validation_plan.md).

## What it validates

| Experiment | Production source | What we score |
|---|---|---|
| **shipment** | `_call_openai` in [`SupplyMindAI/analysis/pipeline.py`](../SupplyMindAI/analysis/pipeline.py) | The `flag` + `reasoning` for in-transit shipments (Card 1 in the app) |
| **optimization** | `_call_openai_recommendations` in [`SupplyMindAI/analysis/optimization_pipeline.py`](../SupplyMindAI/analysis/optimization_pipeline.py) | The `summary` + `control_parameters` for delivered shipments (Card 3 in the app) |

## Validation Criteria Table

The validator is **not** a generic Likert rubric ("overall quality 1-5").
Instead, each score dimension is domain-specific and tied to logistics utility.

### Shipment criteria

| Dimension | Description | Scale / Measurement | Benchmark |
|---|---|---|---|
| `flag_accuracy` | Whether On Time / Delayed / Critical matches shipment evidence | AI score 0-5 | Higher is better |
| `grounding_specificity` | Whether reasoning uses real hubs/risks from source data | AI score 0-5 | Higher is better |
| `format_compliance` | Whether reasoning follows required shipment style/constraints | AI score 0-5 | Higher is better |
| `actionability` | Whether ops team can act from the explanation | AI score 0-5 | Higher is better |
| `succinctness` | Whether response is concise without filler | AI score 0-5 | Higher is better |
| `policy_compliant` | Hard-rule check (`Critical` gating, arrival/deadline logic) | Deterministic boolean | `True` preferred |

### Optimization criteria

| Dimension | Description | Scale / Measurement | Benchmark |
|---|---|---|---|
| `lever_compliance` | Whether recommendations map to supported control levers | AI score 0-5 | Higher is better |
| `data_grounding` | Whether summary/recommendations cite real metrics/hubs/categories | AI score 0-5 | Higher is better |
| `specificity` | Whether actions name concrete routes/hubs | AI score 0-5 | Higher is better |
| `actionability` | Whether recommendations are practical to implement | AI score 0-5 | Higher is better |
| `formatting_compliance` | Whether output structure/format follows expected style | AI score 0-5 | Higher is better |
| `summary_quality` | Quality and clarity of optimization summary | AI score 0-5 | Higher is better |
| `simulatable` | Whether `control_parameters` parse into simulator params | Deterministic boolean | `True` preferred |

`overall_score` is computed as the mean of AI-scored numeric criteria.

## Quick start

```powershell
# 1. Install validation-only deps (separate from the app's requirements)
pip install -r validation/requirements.txt

# 2. Make sure .env has OPENAI_API_KEY and POSTGRES_CONNECTION_STRING
#    (same .env the app uses)

# 3. Smoke test (~$0.02): run Phase 1/2 on the first N samples
py validation/run_validation.py --phase 1 --n 3
py validation/run_validation.py --phase 2

# 4. Full run (default N=30 samples per prompt; moderate cost/time)
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
  03_statistical_comparison.py     # t-tests + ANOVA
  run_validation.py                # Two-phase wrapper (generate+review, then stats)
  data/
    shipment_reports.csv           # Generated reports (one row per sample x prompt)
    shipment_scores.csv            # Reviewer scores (one row per sample x prompt)
    shipment_stats_summary.md      # Auto-generated stats writeup
    opt_reports.csv
    opt_scores.csv
    opt_stats_summary.md
    reviewer_reliability.csv       # Reviewer repeat scores (optional archive)
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

## Experimental Design

- **Prompt comparison:** A (baseline) vs B (stricter) vs C (intentionally weaker comparator).
- **Experiments:** shipment reasoning and optimization recommendations.
- **Target sample size:** default `--n 30` samples per prompt.
- **Target scores per experiment:** `30 x 3 = 90` scored rows (can be lower if API failures occur).
- **Scoring unit:** one scored row per `(sample_id, prompt_id)` pair.

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
2. One-way ANOVA on `overall_score ~ prompt_id`.
3. Pairwise t-tests (A-vs-B, A-vs-C, B-vs-C) with Holm correction.
4. Verdict block: best prompt + p-value.

### Hypothesis used

- **Null (H0):** prompt means are equal (`mu_A = mu_B = mu_C`).
- **Alternative (H1):** at least one prompt mean differs.
- **Decision rule:** reject H0 if ANOVA p-value < 0.05.
- Pairwise t-tests are used after ANOVA to see where differences are strongest.

Interpretation guidance:
- Significant ANOVA + higher mean -> preferred prompt.
- Non-significant ANOVA -> no statistical evidence that prompts differ.

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

## System Design (AI reviewer role)

The system has three stages:

1. **Generation (`01_generate_reports.py`)**  
   Runs prompt A/B/C for each sample and stores raw model outputs.
2. **AI QC (`02_ai_quality_control.py`)**  
   Uses a reviewer model to score each output against the rubric and write structured scores.
3. **Stats (`03_statistical_comparison.py`)**  
   Runs ANOVA + pairwise t-tests and writes markdown summary files.

AI reviewer role:
- Acts as a consistent evaluator for rubric dimensions.
- Produces structured JSON scores (0-5 criteria + details).
- Is combined with deterministic rule checks (`policy_compliant`, `simulatable`) to reduce subjective noise.

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

## Technical Details

- **Runtime:** Python 3.x
- **Primary packages:** `openai`, `pandas`, `scipy`, `pingouin`, `psycopg2-binary`, `python-dotenv`
- **Environment variables required:**
  - `OPENAI_API_KEY`
  - `POSTGRES_CONNECTION_STRING` (or `DIRECT_URL` / `DATABASE_URL` as used by DB client)
- **Data outputs:** `validation/data/*.csv`, `validation/data/*_stats_summary.md`, and plot images.
- **Rate-limit handling:** generation and reviewer calls include retry/backoff for transient 429 errors.

## How this maps to the assignment rubric

| Rubric criterion | Where it lives |
|---|---|
| Customized validation framework | [`rubrics.py`](rubrics.py) - domain-specific rubric, not generic Likert |
| Qualitative content analysis | [`02_ai_quality_control.py`](02_ai_quality_control.py) - AI reviewer is the systematic evaluator |
| Experimental design | [`prompts.py`](prompts.py) (A/B/C) + [`sampling.py`](sampling.py) (>=20 samples per prompt) -> 60+ scores per experiment |
| Statistical analysis | [`03_statistical_comparison.py`](03_statistical_comparison.py) - ANOVA + pairwise t-tests |
| Implementation | This folder. Working CLI scripts that import the existing app pipelines via `sys.path` adjustment, so the production app is unchanged. |

## Usage Instructions (Step-by-step)

1. **Install dependencies**
   ```powershell
   pip install -r validation/requirements.txt
   ```
2. **Set environment**
   - Ensure project root `.env` contains `OPENAI_API_KEY` and DB connection variable.
3. **Run experiment generation + scoring**
   ```powershell
   py validation/run_validation.py --phase 1
   ```
4. **Run statistical analysis**
   ```powershell
   py validation/run_validation.py --phase 2
   ```
5. **Inspect outputs**
   - `validation/data/shipment_stats_summary.md`
   - `validation/data/opt_stats_summary.md`
   - `validation/data/shipment_scores.csv`
   - `validation/data/opt_scores.csv`

Recommended for prompt/rubric edits:
```powershell
py validation/run_validation.py --phase 1 --force
py validation/run_validation.py --phase 2
```

## Interpreting Outputs

### Primary files to review

- `validation/data/shipment_stats_summary.md`  
  Final statistical comparison for shipment prompt variants.
- `validation/data/opt_stats_summary.md`  
  Final statistical comparison for optimization prompt variants.
- `validation/data/shipment_scores.csv` and `validation/data/opt_scores.csv`  
  Row-level rubric scores used as statistical input.

### How to read the summary markdown

1. **Descriptive table** shows mean and spread by prompt.
2. **ANOVA section** answers: "Is there any significant difference among A/B/C?"
3. **Pairwise t-tests** show where largest pair-level differences appear.
4. **Verdict** states best prompt by mean and significance status.

### Expected interpretation pattern

- If ANOVA p-value < 0.05, prompt choice has significant effect.
- Then use pairwise t-tests + means to identify strongest/best variant.
- If ANOVA p-value >= 0.05, treat variants as statistically similar for this run.

## Data Contracts (CSV schemas)

### `shipment_reports.csv` (generation output)

Key columns:
- `experiment`, `prompt_id`, `sample_id`, `shipment_id`, `run_id`
- generated fields: `flag`, `predicted_arrival`, `reasoning`, `confidence`
- debug fields: `raw_response`, `payload_json`, `generation_ts`, `error`

### `shipment_scores.csv` (review output)

Key columns:
- keys: `sample_id`, `prompt_id`, `run_id`
- rubric: `flag_accuracy`, `grounding_specificity`, `format_compliance`,
  `actionability`, `succinctness`, `policy_compliant`
- aggregate/debug: `overall_score`, `reviewer_details`, `review_ts`, `review_error`

### `opt_reports.csv` (generation output)

Key columns:
- `experiment`, `prompt_id`, `sample_id`, `range_id`, `run_id`
- generated fields: `summary`, `control_parameters_json`, `top_parameters_json`
- context fields: `on_time_count`, `delayed_count`, `avg_delay_hours`, metrics JSON columns
- debug fields: `raw_response`, `generation_ts`, `error`

### `opt_scores.csv` (review output)

Key columns:
- keys: `sample_id`, `prompt_id`, `run_id`
- rubric: `lever_compliance`, `data_grounding`, `specificity`,
  `actionability`, `formatting_compliance`, `summary_quality`, `simulatable`
- aggregate/debug: `overall_score`, `reviewer_details`, `review_ts`, `review_error`

## Troubleshooting

### 1) 429 / rate-limit errors

Symptoms:
- Terminal logs show `RateLimitError` with code 429.
- Output CSV contains rows with non-empty `error`.

What to do:
- Re-run with lower concurrency:
  ```powershell
  py validation/run_validation.py --phase 1 --workers 3
  ```
- Keep retries enabled (already implemented in generation and reviewer calls).
- Use `--force` if you changed prompts/rubrics and want a clean rerun.

### 2) Missing scores in stats

Symptoms:
- Fewer rows than expected in `*_scores.csv`.

Causes:
- Generation failures (non-empty `error`) are filtered before scoring.
- Cached old rows reused when `--force` is not passed after code changes.

Fix:
```powershell
py validation/run_validation.py --phase 1 --force
py validation/run_validation.py --phase 2
```

### 3) ANOVA warnings or unstable stats

Symptoms:
- Very low variance in one prompt, or warning messages in output.

What to do:
- Increase sample size (`--n`).
- Check for degenerate prompt behavior (all identical responses).
- Verify prompt outputs are actually distinct across A/B/C.

## Reproducibility Notes

- Sampling is deterministic (`seed=42`) in `sampling.py`.
- Prompt text is versioned in `prompts.py`.
- Rubric logic is versioned in `rubrics.py`.
- Stats are reproducible from stored score CSVs using:
  ```powershell
  py validation/03_statistical_comparison.py --experiment both
  ```

## Suggested Submission Artifacts

For assignment screenshots and links, include:

1. **System in action**: terminal running `--phase 1` or `--phase 2`.
2. **One evaluated report**: one row from `shipment_scores.csv` or `opt_scores.csv`.
3. **Prompt comparison plot**:
   - `validation/data/shipment_scores_boxplot.png`
   - `validation/data/opt_scores_boxplot.png`
4. **Final stats markdown**:
   - `validation/data/shipment_stats_summary.md`
   - `validation/data/opt_stats_summary.md`

## Notes on a small dataset

The shipped demo DB has 5 shipments. The validation experiment scales by
**replicating each unique input across multiple `run_id`s** at
`temperature=0.3`, so each (shipment, run) pair produces an independent draw.
With 30 samples per prompt that yields 90 generations and 90 reviewer scores
per experiment, which is enough for a one-way ANOVA. If you load a larger
DB, the sampler automatically picks up to 20 unique shipments before
falling back to replication.

`temperature=0.3` is intentionally elevated above the production app's
shipment-classification setting (0) so multi-run sampling produces variation
to test against. Variant A still uses the **same prompt text** as production -
the only difference is sampling temperature for the experiment itself.
