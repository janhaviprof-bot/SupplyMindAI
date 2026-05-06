"""
03_statistical_comparison.py

Statistical comparison of prompt variants A / B / C using the AI reviewer
scores produced by 02_ai_quality_control.py.

For each experiment the script:
  1. Reports descriptive stats per prompt (mean, SD, n).
  2. Runs Bartlett's test for variance equality.
  3. Runs one-way ANOVA (Welch's if variances unequal).
  4. Runs pairwise t-tests with Holm correction.
  5. Runs per-criterion ANOVA to identify which dimensions changed.
  6. Runs a linear regression of overall_score on prompt + covariates.
  7. Tests independence of the boolean criterion (policy_compliant / simulatable)
     across prompts via chi-squared.
  8. Computes reviewer ICC from reviewer_reliability.csv (if available).
  9. Prints a verdict block and writes a Markdown summary.

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
from scipy.stats import bartlett, chi2_contingency, t as t_dist

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


def _pairwise_tost(scores: pd.DataFrame, delta: float) -> pd.DataFrame:
    """
    Two One-Sided Tests (TOST) for pairwise equivalence on overall_score.

    H0: |mu_a - mu_b| >= delta
    H1: |mu_a - mu_b| < delta
    """
    sub = scores.dropna(subset=["overall_score", "prompt_id"]).copy()
    prompts = sorted(sub["prompt_id"].unique())
    rows = []
    alpha = 0.05

    for i in range(len(prompts)):
        for j in range(i + 1, len(prompts)):
            a = prompts[i]
            b = prompts[j]
            xa = sub[sub["prompt_id"] == a]["overall_score"].astype(float).values
            xb = sub[sub["prompt_id"] == b]["overall_score"].astype(float).values
            n1, n2 = len(xa), len(xb)
            if n1 < 2 or n2 < 2:
                continue

            m1, m2 = float(np.mean(xa)), float(np.mean(xb))
            v1, v2 = float(np.var(xa, ddof=1)), float(np.var(xb, ddof=1))
            diff = m1 - m2

            # Welch standard error and Satterthwaite dof
            se_sq = (v1 / n1) + (v2 / n2)
            if se_sq <= 0:
                continue
            se = float(np.sqrt(se_sq))
            num = se_sq ** 2
            den = ((v1 / n1) ** 2) / (n1 - 1) + ((v2 / n2) ** 2) / (n2 - 1)
            dof = num / den if den > 0 else (n1 + n2 - 2)

            # Lower one-sided test: H0 diff <= -delta
            t_low = (diff + delta) / se
            p_low = 1 - t_dist.cdf(t_low, dof)

            # Upper one-sided test: H0 diff >= +delta
            t_high = (diff - delta) / se
            p_high = t_dist.cdf(t_high, dof)

            tost_p = max(p_low, p_high)
            equivalent = (p_low < alpha) and (p_high < alpha)
            rows.append(
                {
                    "A": a,
                    "B": b,
                    "mean_diff_A_minus_B": round(diff, 4),
                    "delta": round(delta, 4),
                    "p_lower": round(float(p_low), 4),
                    "p_upper": round(float(p_high), 4),
                    "tost_p": round(float(tost_p), 4),
                    "equivalent_at_0.05": bool(equivalent),
                }
            )
    return pd.DataFrame(rows)


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

def run_experiment(experiment: str, equiv_delta: float):
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

    # 2. Bartlett
    out.section("2. Bartlett's test for variance equality (overall_score)")
    groups = [
        scores[scores["prompt_id"] == p]["overall_score"].dropna().tolist()
        for p in sorted(scores["prompt_id"].unique())
    ]
    var_equal = True
    if all(len(g) > 1 for g in groups) and len(groups) >= 2:
        try:
            stat, p_val = bartlett(*groups)
            out.write(f"Bartlett statistic = {stat:.4f}, p = {p_val:.4f}")
            var_equal = p_val >= 0.05
            out.write(
                f"-> {'Equal variance assumed' if var_equal else 'Unequal variance (Welch).'}"
            )
        except Exception as e:
            out.write(f"(Bartlett failed: {e}; defaulting to Welch.)")
            var_equal = False
    else:
        out.write("(Insufficient samples per group for Bartlett; defaulting to Welch.)")
        var_equal = False

    # 3. ANOVA
    out.section("3. One-way ANOVA on overall_score")
    try:
        anova_df = (pg.anova(dv="overall_score", between="prompt_id", data=scores)
                    if var_equal else
                    pg.welch_anova(dv="overall_score", between="prompt_id", data=scores))
        out.write("Used " + ("classical ANOVA" if var_equal else "Welch ANOVA"))
        out.write(_df_to_md(anova_df))
        p_col = "p_unc" if "p_unc" in anova_df.columns else "p-unc"
        anova_p = float(anova_df[p_col].values[0])
        anova_f = float(anova_df["F"].values[0])
    except Exception as e:
        out.write(f"(ANOVA failed: {e})")
        anova_p, anova_f = float("nan"), float("nan")

    # 4. Pairwise
    out.section("4. Pairwise t-tests (Holm-corrected)")
    pw = _pairwise(scores)
    if pw.empty:
        out.write("(could not compute pairwise tests)")
    else:
        out.write(_df_to_md(pw.round(4)))

    # 5. Pairwise equivalence (TOST)
    out.section("5. Pairwise equivalence tests (TOST) on overall_score")
    out.write(f"Equivalence margin: +/- {equiv_delta:.3f} points")
    eq = _pairwise_tost(scores, equiv_delta)
    if eq.empty:
        out.write("(could not compute equivalence tests)")
    else:
        out.write(_df_to_md(eq))

    # 6. Per-criterion ANOVA
    out.section("6. Per-criterion ANOVA (which dimensions changed?)")
    per_crit = _per_criterion_anova(scores, cfg["ai_criteria"], var_equal)
    if per_crit.empty:
        out.write("(no AI criteria with usable data)")
    else:
        out.write(_df_to_md(per_crit))

    # 7. Regression
    out.section("7. Linear regression: overall_score ~ prompt + covariates")
    out.write(f"Covariates: {', '.join(cfg['covariates'])}")
    reg = _regression(scores, cfg["covariates"])
    if reg.empty:
        out.write("(regression unavailable)")
    else:
        keep_cols = [c for c in ("names", "coef", "se", "T", "pval", "r2", "adj_r2")
                     if c in reg.columns]
        out.write(_df_to_md(reg[keep_cols].round(4)))

    # 8. Boolean criterion
    out.section(f"8. Pass-rate analysis: {cfg['bool_criterion']}")
    _bool_summary(scores, cfg["bool_criterion"], out)

    # 9. Reviewer reliability
    out.section("9. Reviewer reliability (intra-class correlation)")
    _reliability(experiment, cfg["ai_criteria"], out)

    # 10. Verdict
    out.section("10. Verdict")
    means = (scores.groupby("prompt_id")["overall_score"].mean()
             .sort_values(ascending=False).round(3))
    best_prompt = means.index[0] if len(means) else "?"
    out.write(f"Mean overall_score by prompt (high to low): {dict(means)}")
    if not eq.empty:
        eq_true = eq["equivalent_at_0.05"].sum()
        out.write(
            f"Pairwise equivalence (TOST, delta={equiv_delta:.3f}): "
            f"{eq_true}/{len(eq)} pairs equivalent at alpha=0.05."
        )
        for _, row in eq.iterrows():
            if bool(row["equivalent_at_0.05"]):
                out.write(
                    f"- {row['A']} vs {row['B']}: equivalent "
                    f"(diff={row['mean_diff_A_minus_B']}, tost_p={row['tost_p']})."
                )
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
    p.add_argument(
        "--equiv-delta",
        type=float,
        default=0.10,
        help=(
            "TOST equivalence margin on overall_score (default 0.10 points). "
            "If all pairwise tests are equivalent, prompts are practically tied "
            "within +/-delta."
        ),
    )
    args = p.parse_args()

    if args.experiment == "both":
        for e in ("shipment", "optimization"):
            print("\n" + "=" * 72)
            run_experiment(e, args.equiv_delta)
    else:
        run_experiment(args.experiment, args.equiv_delta)


if __name__ == "__main__":
    main()
