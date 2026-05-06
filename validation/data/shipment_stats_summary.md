# Statistical Comparison: shipment

Source: shipment_scores.csv (150 rows)

## 1. Descriptive statistics by prompt

| prompt_id   |   n |   overall_mean |   overall_sd |   flag_accuracy_mean |   grounding_specificity_mean |   format_compliance_mean |   actionability_mean |   succinctness_mean |
|:------------|----:|---------------:|-------------:|---------------------:|-----------------------------:|-------------------------:|---------------------:|--------------------:|
| A           |  50 |          1.736 |        1.091 |                 4.52 |                         1.18 |                     1.12 |                 0.74 |                1.12 |
| B           |  50 |          1.948 |        1.223 |                 4.54 |                         0.98 |                     1.74 |                 0.74 |                1.74 |
| C           |  50 |          0.656 |        1.2   |                 1.2  |                         0.2  |                     0.86 |                 0.14 |                0.88 |

## 2. Bartlett's test for variance equality (overall_score)

Bartlett statistic = 0.7111, p = 0.7008
-> Equal variance assumed

## 3. One-way ANOVA on overall_score

Used classical ANOVA
| Source    |   ddof1 |   ddof2 |       F |       p_unc |      np2 |
|:----------|--------:|--------:|--------:|------------:|---------:|
| prompt_id |       2 |     147 | 17.4463 | 1.59008e-07 | 0.191831 |

## 4. Pairwise t-tests (Holm-corrected)

| A   | B   |       T |   hedges |
|:----|:----|--------:|---------:|
| A   | B   | -0.9144 |  -0.1815 |
| A   | C   |  4.7081 |   0.9344 |
| B   | C   |  5.3309 |   1.058  |

## 5. Pairwise equivalence tests (TOST) on overall_score

Equivalence margin: +/- 0.100 points
| A   | B   |   mean_diff_A_minus_B |   delta |   p_lower |   p_upper |   tost_p | equivalent_at_0.05   |
|:----|:----|----------------------:|--------:|----------:|----------:|---------:|:---------------------|
| A   | B   |                -0.212 |     0.1 |    0.6849 |    0.0908 |   0.6849 | False                |
| A   | C   |                 1.08  |     0.1 |    0      |    1      |   1      | False                |
| B   | C   |                 1.292 |     0.1 |    0      |    1      |   1      | False                |

## 6. Per-criterion ANOVA (which dimensions changed?)

| criterion             |      F |   p_value | significant_at_0.05   |   mean_A |   mean_B |   mean_C |
|:----------------------|-------:|----------:|:----------------------|---------:|---------:|---------:|
| flag_accuracy         | 96.036 |    0      | True                  |     4.52 |     4.54 |     1.2  |
| grounding_specificity |  4.537 |    0.0122 | True                  |     1.18 |     0.98 |     0.2  |
| format_compliance     |  2.819 |    0.0629 | False                 |     1.12 |     1.74 |     0.86 |
| actionability         |  4.382 |    0.0142 | True                  |     0.74 |     0.74 |     0.14 |
| succinctness          |  2.7   |    0.0706 | False                 |     1.12 |     1.74 |     0.88 |

## 7. Linear regression: overall_score ~ prompt + covariates

Covariates: n_future_risks, max_severity, total_stops, priority_level
| names          |    coef |     se |       T |   pval |     r2 |   adj_r2 |
|:---------------|--------:|-------:|--------:|-------:|-------:|---------:|
| Intercept      |  2.5009 | 0.8465 |  2.9545 | 0.0037 | 0.3957 |   0.3703 |
| prompt_B       |  0.212  | 0.2057 |  1.0307 | 0.3044 | 0.3957 |   0.3703 |
| prompt_C       | -1.08   | 0.2057 | -5.2508 | 0      | 0.3957 |   0.3703 |
| n_future_risks | -0.0615 | 0.1601 | -0.3843 | 0.7013 | 0.3957 |   0.3703 |
| max_severity   |  0.2217 | 0.0692 |  3.2037 | 0.0017 | 0.3957 |   0.3703 |
| total_stops    | -0.2609 | 0.2818 | -0.9258 | 0.3561 | 0.3957 |   0.3703 |
| priority_level | -0.0445 | 0.0344 | -1.2921 | 0.1984 | 0.3957 |   0.3703 |

## 8. Pass-rate analysis: policy_compliant


### Boolean criterion: policy_compliant (deterministic)

| prompt_id   |   pass_rate |   n |   n_pass |
|:------------|------------:|----:|---------:|
| A           |        0.86 |  50 |       43 |
| B           |        0.86 |  50 |       43 |
| C           |        0.78 |  50 |       39 |

Chi-squared test of independence: chi2=1.536, dof=2, p=0.4639 -> not significant at alpha=0.05.

## 9. Reviewer reliability (intra-class correlation)

(no reliability rows for experiment=shipment; skipping ICC.)

## 10. Verdict

Mean overall_score by prompt (high to low): {'B': np.float64(1.948), 'A': np.float64(1.736), 'C': np.float64(0.656)}
Pairwise equivalence (TOST, delta=0.100): 0/3 pairs equivalent at alpha=0.05.

ANOVA: F = 17.446, p = 0.0000 -> prompt choice has a statistically significant effect on overall quality (alpha = 0.05).
Best prompt overall: **B** (mean = 1.948).
