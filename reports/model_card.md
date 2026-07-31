# Model Card — RE ValueWorks Forward NOI Growth Forecast & Segmentation

## Summary

Two distinct modeling exercises, deliberately kept separate from each other
and from the rule-based Hold/Reposition/Sell tag:

1. **Segmentation** (unsupervised, KMeans) — groups properties by performance
   characteristics into four labeled segments.
2. **Forward NOI growth forecast** (supervised, Random Forest) — predicts next
   year's same-property NOI growth from current fundamentals.

## Why IRR and equity multiple are not modeled directly

In this synthetic dataset, IRR and equity multiple are **exact outputs of a
cash-flow formula** (see `data_dictionary.md`) — there is no noise term. Training
a model to "predict" them from the same inputs that generated them would just
be reverse-engineering algebra and would trivially score near-perfect, which
would not demonstrate anything real about forecasting skill. The forward NOI
growth target was built specifically to avoid this: it includes a genuine,
explicit noise term (see below), so there is real, honest prediction error to
report — the same design principle behind Emma's CRE Sentinel default model,
where the target had real randomness the model has to contend with.

## Segmentation (KMeans, 4 clusters)

**Features:** occupancy, same-property NOI growth, interest coverage, leverage,
NOI margin — standardized before clustering.

**Resulting segments** (labeled by ranking each cluster's composite
performance, not manually eyeballed):

| Segment | Count | Avg NOI Growth | Avg Leverage | Read |
|---|---|---|---|---|
| Core Stabilized | 52 | +3.9% | 55% | Lowest leverage, steady performer |
| Value-Add Opportunity | 77 | +3.3% | 66% | High occupancy, highest leverage — active repositioning profile |
| Mature / Harvest Candidate | 71 | +3.0% | 61% | Stabilized, growth decelerating |
| Distressed / Turnaround | 50 | −1.5% | 63% | Negative growth, weakest fundamentals |

## Forward NOI growth forecast

**Target construction:** next year's growth is simulated as 55% current
same-property growth + 45% sector average growth + random noise (σ = 1.4
points) — a mean-reversion model with an explicit, honest uncertainty term.

**Model:** Random Forest Regressor, 300 trees, max depth 6.

**Features:** occupancy, current NOI growth, NOI margin, interest coverage,
leverage, hold years, property type, market.

**Held-out test set results (63 properties):**

| Metric | Value |
|---|---|
| R² | 0.611 |
| MAE | 1.10 percentage points |
| Naive baseline MAE (persistence: "next year = this year") | 1.52 points |

**The model beats the naive baseline** (1.10 vs. 1.52 points of error), which
is the bar that actually matters here — a forecast that doesn't beat "assume
nothing changes" isn't earning its complexity. An R² of 0.61 means the model
explains a majority but not all of the variance in forward growth, which is
appropriate to report honestly rather than imply near-certainty in a one-year
NOI forecast, which no real model should claim.

## Explainability

SHAP (TreeExplainer) on the Random Forest shows same-property NOI growth,
occupancy, and being an office asset as the dominant drivers of the forecast
(`reports/forecast_shap_summary.png`) — directionally consistent with how the
target was constructed (mean-reversion to current trajectory and sector
average), which is a useful sanity check that the model learned the intended
relationship.

## Value-creation score (0–100)

**Not a machine-learned score.** A transparent, stated formula:

```
value_creation_score = 0.5 × percentile_rank(cap_rate_compression_since_acquisition)
                      + 0.5 × percentile_rank(model_predicted_forward_NOI_growth)
```

Combines value already captured (cap rate compression achieved) with value
still ahead (forecasted growth). Documented here in full rather than
presented as an opaque model output.

## Limitations and why this should not make investment decisions alone

- **Small sample size:** 250 properties, and the forecast model is trained on
  only ~187 in the training fold. Treat performance estimates as directional.
- **One-year horizon only:** the forecast does not extend to a multi-year NOI
  trajectory or a full pro forma; longer-horizon forecasting would need a
  different, more heavily validated approach.
- **Synthetic ground truth:** the "actual" forward growth being predicted is
  itself simulated, not observed real-world outcomes. This model demonstrates
  the forecasting methodology; it would need to be retrained against real
  observed NOI trajectories before being used in an actual investment
  decision.
- **Segmentation is descriptive, not predictive:** clusters describe current
  characteristics: they do not forecast which segment a property will move
  into.
- **Qualitative blind spots:** the model cannot see sponsor/manager quality,
  submarket-specific development pipeline, tenant credit quality, or pending
  lease events not yet reflected in occupancy figures.

**Conclusion:** this system is built to structure and prioritize the
investment committee's discussion — surfacing which assets warrant deeper
underwriting attention — not to replace it. The final hold/reposition/sell
call remains a human investment decision, consistent with the project's
stated design principle.
