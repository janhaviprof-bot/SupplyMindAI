# Statistical Comparison: shipment

Source: shipment_scores.csv (90 rows)

## 1. Descriptive statistics by prompt

| prompt_id   |   n |   overall_mean |   overall_sd |   flag_accuracy_mean |   grounding_specificity_mean |   format_compliance_mean |   actionability_mean |   succinctness_mean |
|:------------|----:|---------------:|-------------:|---------------------:|-----------------------------:|-------------------------:|---------------------:|--------------------:|
| A           |  30 |          1.96  |        1.241 |                4.533 |                        1.333 |                    1.533 |                0.867 |               1.533 |
| B           |  30 |          1.627 |        1.059 |                4.467 |                        1.267 |                    0.8   |                0.8   |               0.8   |
| C           |  30 |          0.633 |        1.129 |                1.433 |                        0.1   |                    0.767 |                0.1   |               0.767 |

## 2. One-way ANOVA on overall_score

Used classical ANOVA
| Source    |   ddof1 |   ddof2 |       F |      p_unc |      np2 |
|:----------|--------:|--------:|--------:|-----------:|---------:|
| prompt_id |       2 |      87 | 10.8881 | 6.0238e-05 | 0.200192 |

## 3. Pairwise t-tests (Holm-corrected)

| A   | B   |      T |   hedges |
|:----|:----|-------:|---------:|
| A   | B   | 1.1189 |   0.2852 |
| A   | C   | 4.3309 |   1.1037 |
| B   | C   | 3.5144 |   0.8956 |

## 4. Verdict

Mean overall_score by prompt (high to low): {'A': np.float64(1.96), 'B': np.float64(1.627), 'C': np.float64(0.633)}

ANOVA: F = 10.888, p = 0.0001 -> prompt choice has a statistically significant effect on overall quality (alpha = 0.05).
Best prompt overall: **A** (mean = 1.96).
