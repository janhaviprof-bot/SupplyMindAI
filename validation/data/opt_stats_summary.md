# Statistical Comparison: optimization

Source: opt_scores.csv (36 rows)

## 1. Descriptive statistics by prompt

| prompt_id   |   n |   overall_mean |   overall_sd |   lever_compliance_mean |   data_grounding_mean |   specificity_mean |   actionability_mean |   summary_quality_mean |
|:------------|----:|---------------:|-------------:|------------------------:|----------------------:|-------------------:|---------------------:|-----------------------:|
| A           |  12 |          3.95  |        0.09  |                   4     |                 3.75  |                  4 |                4     |                      4 |
| B           |  11 |          3.873 |        0.372 |                   3.909 |                 3.545 |                  4 |                3.909 |                      4 |
| C           |  13 |          3.938 |        0.15  |                   3.923 |                 3.769 |                  4 |                4     |                      4 |

## 2. Bartlett's test for variance equality (overall_score)

Bartlett statistic = 20.2712, p = 0.0000
-> Unequal variance (Welch).

## 3. One-way ANOVA on overall_score

Used Welch ANOVA
| Source    |   ddof1 |   ddof2 |        F |    p_unc |      np2 |
|:----------|--------:|--------:|---------:|---------:|---------:|
| prompt_id |       2 | 18.3215 | 0.229089 | 0.797502 | 0.022239 |

## 4. Pairwise t-tests (Holm-corrected)

| A   | B   |       T |   hedges |
|:----|:----|--------:|---------:|
| A   | B   |  0.6715 |   0.2813 |
| A   | C   |  0.2347 |   0.0891 |
| B   | C   | -0.5497 |  -0.2316 |

## 5. Per-criterion ANOVA (which dimensions changed?)

| criterion        |     F |   p_value | significant_at_0.05   |   mean_A |   mean_B |   mean_C |
|:-----------------|------:|----------:|:----------------------|---------:|---------:|---------:|
| lever_compliance | 0     |    1      | False                 |     4    |    3.909 |    3.923 |
| data_grounding   | 0.137 |    0.8724 | False                 |     3.75 |    3.545 |    3.769 |
| specificity      | 0     |    1      | False                 |     4    |    4     |    4     |
| actionability    | 0     |    1      | False                 |     4    |    3.909 |    4     |
| summary_quality  | 0     |    1      | False                 |     4    |    4     |    4     |

## 6. Linear regression: overall_score ~ prompt + covariates

Covariates: on_time_count, delayed_count, avg_delay_hours, n_top_hubs
| names           |    coef |     se |       T |   pval |     r2 |   adj_r2 |
|:----------------|--------:|-------:|--------:|-------:|-------:|---------:|
| Intercept       |  3.6959 | 0.0711 | 52.0083 | 0      | 0.4564 |   0.4054 |
| prompt_B        | -0.0696 | 0.0726 | -0.9577 | 0.3454 | 0.4564 |   0.4054 |
| prompt_C        | -0.0181 | 0.0697 | -0.2592 | 0.7972 | 0.4564 |   0.4054 |
| on_time_count   |  0.0002 | 0      |  5.0553 | 0      | 0.4564 |   0.4054 |
| delayed_count   |  0.0004 | 0.0001 |  5.0553 | 0      | 0.4564 |   0.4054 |
| avg_delay_hours |  0.001  | 0.0002 |  5.0553 | 0      | 0.4564 |   0.4054 |
| n_top_hubs      |  0      | 0      |  5.0553 | 0      | 0.4564 |   0.4054 |

## 7. Pass-rate analysis: simulatable


### Boolean criterion: simulatable (deterministic)

| prompt_id   |   pass_rate |   n |   n_pass |
|:------------|------------:|----:|---------:|
| A           |           1 |  12 |       12 |
| B           |           1 |  11 |       11 |
| C           |           1 |  13 |       13 |

Chi-squared test of independence: chi2=0.000, dof=0, p=1.0000 -> not significant at alpha=0.05.

## 8. Reviewer reliability (intra-class correlation)

Intra-class correlation (reviewer stability on overall_score):
(ICC computation failed: "['Description', 'CI95%'] not in index")

## 9. Verdict

Mean overall_score by prompt (high to low): {'A': np.float64(3.95), 'C': np.float64(3.938), 'B': np.float64(3.873)}

ANOVA: F = 0.229, p = 0.7975 -> NOT statistically significant at alpha = 0.05. With this dataset we cannot conclude one prompt is better than the others.
Highest-mean prompt: A (mean = 3.95), but the difference may be due to chance.
