# Statistical Comparison: optimization

Source: opt_scores.csv (84 rows)

## 1. Descriptive statistics by prompt

| prompt_id   |   n |   overall_mean |   overall_sd |   lever_compliance_mean |   data_grounding_mean |   specificity_mean |   actionability_mean |   formatting_compliance_mean |   summary_quality_mean |
|:------------|----:|---------------:|-------------:|------------------------:|----------------------:|-------------------:|---------------------:|-----------------------------:|-----------------------:|
| A           |  29 |          3.983 |        0.093 |                   4     |                 3.931 |              4     |                4     |                        4     |                  3.966 |
| B           |  29 |          3.937 |        0.237 |                   3.966 |                 3.862 |              3.931 |                3.931 |                        4     |                  3.931 |
| C           |  26 |          3.083 |        0.647 |                   3.231 |                 3.115 |              2.692 |                2.885 |                        3.808 |                  2.769 |

## 2. One-way ANOVA on overall_score

Used classical ANOVA
| Source    |   ddof1 |   ddof2 |       F |       p_unc |      np2 |
|:----------|--------:|--------:|--------:|------------:|---------:|
| prompt_id |       2 |      81 | 45.5806 | 5.47356e-14 | 0.529511 |

## 3. Pairwise t-tests (Holm-corrected)

| A   | B   |      T |   hedges |
|:----|:----|-------:|---------:|
| A   | B   | 0.9711 |   0.2516 |
| A   | C   | 7.0253 |   1.9731 |
| B   | C   | 6.3548 |   1.7653 |

## 4. Verdict

Mean overall_score by prompt (high to low): {'A': np.float64(3.983), 'B': np.float64(3.937), 'C': np.float64(3.083)}

ANOVA: F = 45.581, p = 0.0000 -> prompt choice has a statistically significant effect on overall quality (alpha = 0.05).
Best prompt overall: **A** (mean = 3.983).
