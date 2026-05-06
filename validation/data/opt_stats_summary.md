# Statistical Comparison: optimization

Source: opt_scores.csv (47 rows)

## 1. Descriptive statistics by prompt

| prompt_id   |   n |   overall_mean |   overall_sd |   lever_compliance_mean |   data_grounding_mean |   specificity_mean |   actionability_mean |   summary_quality_mean |
|:------------|----:|---------------:|-------------:|------------------------:|----------------------:|-------------------:|---------------------:|-----------------------:|
| A           |  17 |           4    |        0     |                       4 |                     4 |                  4 |                4     |                  4     |
| B           |  14 |           4    |        0     |                       4 |                     4 |                  4 |                4     |                  4     |
| C           |  16 |           3.55 |        0.155 |                       4 |                     4 |                  3 |                3.438 |                  3.312 |

## 2. Bartlett's test for variance equality (overall_score)

Bartlett statistic = inf, p = 0.0000
-> Unequal variance (Welch).

## 3. One-way ANOVA on overall_score

Used Welch ANOVA
| Source    |   ddof1 |   ddof2 |   F |   p_unc |      np2 |
|:----------|--------:|--------:|----:|--------:|---------:|
| prompt_id |       2 |      40 |   0 |       1 | 0.855828 |

## 4. Pairwise t-tests (Holm-corrected)

| A   | B   |       T |   hedges |
|:----|:----|--------:|---------:|
| A   | B   | nan     | nan      |
| A   | C   |  11.619 |   4.074  |
| B   | C   |  11.619 |   3.8614 |

## 5. Pairwise equivalence tests (TOST) on overall_score

Equivalence margin: +/- 0.100 points
| A   | B   |   mean_diff_A_minus_B |   delta |   p_lower |   p_upper |   tost_p | equivalent_at_0.05   |
|:----|:----|----------------------:|--------:|----------:|----------:|---------:|:---------------------|
| A   | C   |                  0.45 |     0.1 |         0 |         1 |        1 | False                |
| B   | C   |                  0.45 |     0.1 |         0 |         1 |        1 | False                |

## 6. Per-criterion ANOVA (which dimensions changed?)

| criterion        |   F |   p_value | significant_at_0.05   |   mean_A |   mean_B |   mean_C |
|:-----------------|----:|----------:|:----------------------|---------:|---------:|---------:|
| lever_compliance |   0 |         1 | False                 |        4 |        4 |    4     |
| data_grounding   |   0 |         1 | False                 |        4 |        4 |    4     |
| specificity      |   0 |         1 | False                 |        4 |        4 |    3     |
| actionability    |   0 |         1 | False                 |        4 |        4 |    3.438 |
| summary_quality  |   0 |         1 | False                 |        4 |        4 |    3.312 |

## 7. Linear regression: overall_score ~ prompt + covariates

Covariates: on_time_count, delayed_count, avg_delay_hours, n_top_hubs
| names           |    coef |     se |        T |   pval |     r2 |   adj_r2 |
|:----------------|--------:|-------:|---------:|-------:|-------:|---------:|
| Intercept       |  4.0623 | 0.0336 | 121.027  | 0      | 0.8725 |   0.8636 |
| prompt_B        | -0.0029 | 0.0311 |  -0.0921 | 0.927  | 0.8725 |   0.8636 |
| prompt_C        | -0.4508 | 0.03   | -15.0414 | 0      | 0.8725 |   0.8636 |
| on_time_count   | -0      | 0      |  -2.3714 | 0.0223 | 0.8725 |   0.8636 |
| delayed_count   | -0.0001 | 0      |  -2.3714 | 0.0223 | 0.8725 |   0.8636 |
| avg_delay_hours | -0.0002 | 0.0001 |  -2.3714 | 0.0223 | 0.8725 |   0.8636 |
| n_top_hubs      | -0      | 0      |  -2.3714 | 0.0223 | 0.8725 |   0.8636 |

## 8. Pass-rate analysis: simulatable


### Boolean criterion: simulatable (deterministic)

| prompt_id   |   pass_rate |   n |   n_pass |
|:------------|------------:|----:|---------:|
| A           |           1 |  17 |       17 |
| B           |           1 |  14 |       14 |
| C           |           0 |  16 |        0 |

Chi-squared test of independence: chi2=47.000, dof=2, p=0.0000 -> significant at alpha=0.05.

## 9. Reviewer reliability (intra-class correlation)

Intra-class correlation (reviewer stability on overall_score):
(ICC computation failed: "['Description', 'CI95%'] not in index")

## 10. Verdict

Mean overall_score by prompt (high to low): {'A': np.float64(4.0), 'B': np.float64(4.0), 'C': np.float64(3.55)}
Pairwise equivalence (TOST, delta=0.100): 0/2 pairs equivalent at alpha=0.05.

ANOVA: F = 0.000, p = 1.0000 -> NOT statistically significant at alpha = 0.05. With this dataset we cannot conclude one prompt is better than the others.
Highest-mean prompt: A (mean = 4.0), but the difference may be due to chance.
