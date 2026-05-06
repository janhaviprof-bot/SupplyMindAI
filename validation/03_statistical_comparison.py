"""
03_statistical_comparison.py

Statistical comparison of prompt variants A / B / C using the AI reviewer
scores produced by 02_ai_quality_control.py.

For each experiment the script:
  1. Reports descriptive stats per prompt (mean, SD, n).
  2. Runs one-way ANOVA on overall_score.
  3. Runs pairwise t-tests with Holm correction.
  4. Prints a verdict block and writes a Markdown summary.

Outputs:
  validation/data/shipment_stats_summary.md
  validation/data/opt_stats_summary.md
"""
from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import pingouin as pg

_THIS = Path(__file__).resolve()
DATA_DIR = _THIS.parent / "data"

EXPERIMENT_CONFIG = {
    "shipment": {
        "scores_csv": DATA_DIR / "shipment_scores.csv",
        "summary_md": DATA_DIR / "shipment_stats_summary.md",
        "ai_criteria": (
            "flag_accuracy",
            "grounding_specificity",
            "format_compliance",
            "actionability",
            "succinctness",
        ),
        "bool_criterion": "policy_compliant",
        "covariates": ("n_future_risks", "max_severity",
                       "total_stops", "priority_level"),
    },
    "optimization": {
        "scores_csv": DATA_DIR / "opt_scores.csv",
        "summary_md": DATA_DIR / "opt_stats_summary.md",
        "ai_criteria": (
            "lever_compliance",
            "data_grounding",
            "specificity",
            "actionability",
            "formatting_compliance",
            "summary_quality",
        ),
        "bool_criterion": "simulatable",
        "covariates": ("on_time_count", "delayed_count",
                       "avg_delay_hours", "n_top_hubs"),
    },
}

RELIABILITY_CSV = DATA_DIR / "reviewer_reliability.csv"


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------

class TeeBuffer:
    """Print to stdout AND collect a Markdown copy."""

    def __init__(self):
        self.lines: list[str] = []

    def write(self, text: str = ""):
        print(text)
        self.lines.append(text)

    def section(self, title: str):
        self.write("")
        self.write(f"## {title}")
        self.write("")

    def subsection(self, title: str):
        self.write("")
        self.write(f"### {title}")
        self.write("")

    def md(self) -> str:
        return "\n".join(self.lines).rstrip() + "\n"


def _df_to_md(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except Exception:
        # tabulate not installed; fall back to plain text
        buf = StringIO()
        df.to_string(buf, index=False)
        return "```\n" + buf.getvalue() + "\n```"


def _describe(scores: pd.DataFrame, ai_criteria) -> pd.DataFrame:
    grp = scores.groupby("prompt_id")
    rows = []
    for prompt, sub in grp:
        rec = {
            "prompt_id": prompt,
            "n": len(sub),
            "overall_mean": round(sub["overall_score"].mean(), 3),
            "overall_sd": round(sub["overall_score"].std(ddof=1), 3),
        }
        for c in ai_criteria:
            rec[f"{c}_mean"] = round(sub[c].mean(), 3) if c in sub else None
        rows.append(rec)
    return pd.DataFrame(rows).sort_values("prompt_id").reset_index(drop=True)


def _per_criterion_anova(scores: pd.DataFrame, ai_criteria,
                         var_equal: bool) -> pd.DataFrame:
    out = []
    for c in ai_criteria:
        if c not in scores or scores[c].dropna().empty:
            continue
        sub = scores.dropna(subset=[c, "prompt_id"])
        try:
            res = (pg.anova(dv=c, between="prompt_id", data=sub)
                   if var_equal else
                   pg.welch_anova(dv=c, between="prompt_id", data=sub))
            f = float(res["F"].values[0])
            p_col = "p_unc" if "p_unc" in res.columns else "p-unc"
            p = float(res[p_col].values[0])
        except Exception as e:
            f, p = np.nan, np.nan
            print(f"  ! ANOVA failed for {c}: {e}")
        means_by_prompt = sub.groupby("prompt_id")[c].mean().round(3).to_dict()
        out.append({
            "criterion": c,
            "F": round(f, 3) if f == f else None,
            "p_value": round(p, 4) if p == p else None,
            "significant_at_0.05": (p == p) and (p < 0.05),
            **{f"mean_{k}": v for k, v in means_by_prompt.items()},
        })
    return pd.DataFrame(out)


def _pairwise(scores: pd.DataFrame) -> pd.DataFrame:
    sub = scores.dropna(subset=["overall_score", "prompt_id"])
    if sub.empty:
        return pd.DataFrame()
    res = pg.pairwise_tests(
        data=sub, dv="overall_score", between="prompt_id",
        padjust="holm", parametric=True,
    )
    keep = [c for c in ("A", "B", "T", "p-unc", "p-corr", "hedges") if c in res.columns]
    return res[keep].copy()


def _regression(scores: pd.DataFrame, covariates) -> pd.DataFrame:
    """Linear regression: overall_score ~ prompt + covariates."""
    sub = scores.dropna(subset=["overall_score"]).copy()
    if sub.empty:
        return pd.DataFrame()
    # One-hot encode prompt with A as reference category
    dummies = pd.get_dummies(sub["prompt_id"], prefix="prompt", drop_first=True)
    X = pd.concat([dummies, sub[list(covariates)].astype(float)], axis=1)
    X = X.astype(float)
    y = sub["overall_score"].astype(float)
    try:
        return pg.linear_regression(X, y, add_intercept=True)
    except Exception as e:
        print(f"  ! regression failed: {e}")
        return pd.DataFrame()


def _bool_summary(scores: pd.DataFrame, bool_col: str,
                  out: TeeBuffer) -> None:
    if bool_col not in scores.columns:
        return
    out.subsection(f"Boolean criterion: {bool_col} (deterministic)")
    rates = (scores.groupby("prompt_id")[bool_col]
             .agg(["mean", "count", "sum"])
             .rename(columns={"mean": "pass_rate", "count": "n", "sum": "n_pass"})
             .reset_index())
    rates["pass_rate"] = rates["pass_rate"].round(3)
    out.write(_df_to_md(rates))

    # Chi-square test of independence: prompt_id x bool_col
    try:
        contingency = pd.crosstab(scores["prompt_id"], scores[bool_col].astype(bool))
        chi2, p, dof, _ = chi2_contingency(contingency)
        out.write("")
        out.write(f"Chi-squared test of independence: chi2={chi2:.3f}, "
                  f"dof={dof}, p={p:.4f} -> "
                  f"{'significant' if p < 0.05 else 'not significant'} at alpha=0.05.")
    except Exception as e:
        out.write(f"Chi-squared test could not be computed: {e}")


def _reliability(experiment: str, ai_criteria, out: TeeBuffer) -> None:
    if not RELIABILITY_CSV.exists():
        out.write("(reviewer_reliability.csv not found; skipping ICC.)")
        return
    rel = pd.read_csv(RELIABILITY_CSV)
    rel = rel[rel["experiment"] == experiment].copy()
    if rel.empty:
        out.write(f"(no reliability rows for experiment={experiment}; skipping ICC.)")
        return
    # Need >=2 repeats per (sample_id, prompt_id) target
    rel = rel.dropna(subset=["overall_score"])
    counts = rel.groupby(["sample_id", "prompt_id"])["repeat_id"].nunique()
    keep_pairs = counts[counts >= 2].index
    if len(keep_pairs) == 0:
        out.write("(insufficient repeats for ICC; need >=2 per target.)")
        return
    rel["target_id"] = rel["sample_id"].astype(str) + "::" + rel["prompt_id"].astype(str)
    keep_targets = {f"{s}::{p}" for s, p in keep_pairs}
    rel = rel[rel["target_id"].isin(keep_targets)].copy()
    try:
        icc = pg.intraclass_corr(
            data=rel, targets="target_id", raters="repeat_id",
            ratings="overall_score", nan_policy="omit",
        )
        out.write("Intra-class correlation (reviewer stability on overall_score):")
        out.write(_df_to_md(icc[["Type", "Description", "ICC", "F", "pval", "CI95%"]]))
    except Exception as e:
        out.write(f"(ICC computation failed: {e})")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run_experiment(experiment: str):
    cfg = EXPERIMENT_CONFIG[experiment]
    scores_path: Path = cfg["scores_csv"]
    if not scores_path.exists():
        raise SystemExit(f"Missing {scores_path}. Run 02_ai_quality_control.py first.")

    scores = pd.read_csv(scores_path)
    scores = scores[scores["overall_score"].notna()].copy()
    scores["prompt_id"] = scores["prompt_id"].astype(str)
    if scores.empty:
        raise SystemExit(f"{scores_path} contains no scored rows.")

    out = TeeBuffer()
    out.write(f"# Statistical Comparison: {experiment}")
    out.write("")
    out.write(f"Source: {scores_path.name} ({len(scores)} rows)")

    # 1. Descriptive
    out.section("1. Descriptive statistics by prompt")
    desc = _describe(scores, cfg["ai_criteria"])
    out.write(_df_to_md(desc))

    # 2. ANOVA
    out.section("2. One-way ANOVA on overall_score")
    try:
        anova_df = pg.anova(dv="overall_score", between="prompt_id", data=scores)
        out.write("Used classical ANOVA")
        out.write(_df_to_md(anova_df))
        p_col = "p_unc" if "p_unc" in anova_df.columns else "p-unc"
        anova_p = float(anova_df[p_col].values[0])
        anova_f = float(anova_df["F"].values[0])
    except Exception as e:
        out.write(f"(ANOVA failed: {e})")
        anova_p, anova_f = float("nan"), float("nan")

    # 3. Pairwise
    out.section("3. Pairwise t-tests (Holm-corrected)")
    pw = _pairwise(scores)
    if pw.empty:
        out.write("(could not compute pairwise tests)")
    else:
        out.write(_df_to_md(pw.round(4)))

    # 4. Verdict
    out.section("4. Verdict")
    means = (scores.groupby("prompt_id")["overall_score"].mean()
             .sort_values(ascending=False).round(3))
    best_prompt = means.index[0] if len(means) else "?"
    out.write(f"Mean overall_score by prompt (high to low): {dict(means)}")
    out.write("")
    if anova_p == anova_p and anova_p < 0.05:
        out.write(f"ANOVA: F = {anova_f:.3f}, p = {anova_p:.4f} -> "
                  f"prompt choice has a statistically significant effect on overall quality "
                  f"(alpha = 0.05).")
        out.write(f"Best prompt overall: **{best_prompt}** "
                  f"(mean = {means.iloc[0]}).")
    elif anova_p == anova_p:
        out.write(f"ANOVA: F = {anova_f:.3f}, p = {anova_p:.4f} -> "
                  f"NOT statistically significant at alpha = 0.05. "
                  f"With this dataset we cannot conclude one prompt is better than the others.")
        out.write(f"Highest-mean prompt: {best_prompt} "
                  f"(mean = {means.iloc[0]}), but the difference may be due to chance.")
    else:
        out.write("ANOVA could not be computed; see warnings above.")

    cfg["summary_md"].parent.mkdir(parents=True, exist_ok=True)
    cfg["summary_md"].write_text(out.md(), encoding="utf-8")
    print(f"\nSummary written to {cfg['summary_md']}")


def main():
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument(
        "--experiment", required=True, choices=("shipment", "optimization", "both"),
        help="Which experiment to analyze (or both).",
    )
    args = p.parse_args()

    if args.experiment == "both":
        for e in ("shipment", "optimization"):
            print("\n" + "=" * 72)
            run_experiment(e)
    else:
        run_experiment(args.experiment)


if __name__ == "__main__":
    main()
