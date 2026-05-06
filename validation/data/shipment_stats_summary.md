# Statistical Comparison: shipment

Source: shipment_scores.csv (60 rows)

## 1. Descriptive statistics by prompt

| prompt_id   |   n |   overall_mean |   overall_sd |   flag_accuracy_mean |   grounding_specificity_mean |   format_compliance_mean |   actionability_mean |   succinctness_mean |
|:------------|----:|---------------:|-------------:|---------------------:|-----------------------------:|-------------------------:|---------------------:|--------------------:|
| A           |  20 |           1.83 |        1.176 |                 4.35 |                         1    |                     1.6  |                 0.6  |                 1.6 |
| B           |  20 |           1.88 |        1.113 |                 4.6  |                         1    |                     1.6  |                 0.6  |                 1.6 |
| C           |  20 |           1.76 |        1.118 |                 4.45 |                         0.75 |                     1.45 |                 0.45 |                 1.7 |

## 2. Bartlett's test for variance equality (overall_score)

Bartlett statistic = 0.0695, p = 0.9658
-> Equal variance assumed

## 3. One-way ANOVA on overall_score

Used classical ANOVA
| Source    |   ddof1 |   ddof2 |         F |    p_unc |       np2 |
|:----------|--------:|--------:|----------:|---------:|----------:|
| prompt_id |       2 |      57 | 0.0563216 | 0.945288 | 0.0019723 |

## 4. Pairwise t-tests (Holm-corrected)

| A   | B   |       T |   hedges |
|:----|:----|--------:|---------:|
| A   | B   | -0.1381 |  -0.0428 |
| A   | C   |  0.193  |   0.0598 |
| B   | C   |  0.3402 |   0.1054 |

## 5. Per-criterion ANOVA (which dimensions changed?)

| criterion             |     F |   p_value | significant_at_0.05   |   mean_A |   mean_B |   mean_C |
|:----------------------|------:|----------:|:----------------------|---------:|---------:|---------:|
| flag_accuracy         | 0.237 |    0.7901 | False                 |     4.35 |      4.6 |     4.45 |
| grounding_specificity | 0.106 |    0.8995 | False                 |     1    |      1   |     0.75 |
| format_compliance     | 0.034 |    0.967  | False                 |     1.6  |      1.6 |     1.45 |
| actionability         | 0.106 |    0.8995 | False                 |     0.6  |      0.6 |     0.45 |
| succinctness          | 0.014 |    0.9857 | False                 |     1.6  |      1.6 |     1.7  |

## 6. Linear regression: overall_score ~ prompt + covariates

Covariates: n_future_risks, max_severity, total_stops, priority_level
| names          |    coef |     se |       T |   pval |    r2 |   adj_r2 |
|:---------------|--------:|-------:|--------:|-------:|------:|---------:|
| Intercept      | -3.0258 | 3.7439 | -0.8082 | 0.4226 | 0.362 |   0.2898 |
| prompt_B       |  0.05   | 0.2978 |  0.1679 | 0.8673 | 0.362 |   0.2898 |
| prompt_C       | -0.07   | 0.2978 | -0.235  | 0.8151 | 0.362 |   0.2898 |
| n_future_risks | -0.7788 | 0.5744 | -1.356  | 0.1809 | 0.362 |   0.2898 |
| max_severity   |  0.4735 | 0.1835 |  2.5808 | 0.0127 | 0.362 |   0.2898 |
| total_stops    |  1.57   | 1.2602 |  1.2459 | 0.2183 | 0.362 |   0.2898 |
| priority_level | -0.0248 | 0.0522 | -0.4747 | 0.637  | 0.362 |   0.2898 |

## 7. Pass-rate analysis: policy_compliant


### Boolean criterion: policy_compliant (deterministic)

| prompt_id   |   pass_rate |   n |   n_pass |
|:------------|------------:|----:|---------:|
| A           |        0.85 |  20 |       17 |
| B           |        0.85 |  20 |       17 |
| C           |        0.85 |  20 |       17 |

Chi-squared test of independence: chi2=0.000, dof=2, p=1.0000 -> not significant at alpha=0.05.

## 8. Reviewer reliability (intra-class correlation)

Intra-class correlation (reviewer stability on overall_score):
(ICC computation failed: "['Description', 'CI95%'] not in index")

## 9. Verdict

Mean overall_score by prompt (high to low): {'B': np.float64(1.88), 'A': np.float64(1.83), 'C': np.float64(1.76)}

ANOVA: F = 0.056, p = 0.9453 -> NOT statistically significant at alpha = 0.05. With this dataset we cannot conclude one prompt is better than the others.
Highest-mean prompt: B (mean = 1.88), but the difference may be due to chance.
