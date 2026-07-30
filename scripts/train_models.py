"""
train_models.py -- RE ValueWorks data science layer

Two genuinely separate modeling exercises, deliberately kept distinct from
the rule-based Hold/Reposition/Sell tag already in the data:

1. SEGMENTATION (unsupervised): cluster properties into natural performance
   groups using KMeans. No target label involved, so there's no leakage
   question here -- this is exactly what clustering is for.

2. FORWARD NOI GROWTH FORECAST (supervised, genuinely uncertain): predicts
   NEXT YEAR's same-property NOI growth from CURRENT fundamentals. This is
   deliberately NOT a model of the current recommendation tag or the
   already-realized IRR -- those are exact formulas in this synthetic
   dataset (no noise term), so "predicting" them would just be reverse-
   engineering algebra, not real data science. Forward growth is simulated
   with an explicit noise term (mean-reversion + idiosyncratic shock), so
   there is genuine, honest prediction error to report -- same spirit as
   Emma's default model, where the target had real randomness the model
   has to contend with.

3. VALUE-CREATION SCORE (0-100): a transparent, documented combination of
   the forecasted forward growth and the value creation already captured
   (cap rate compression since acquisition) -- not a black box, the
   formula is stated here and in the data dictionary.
"""

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error
import shap
import joblib
import os

np.random.seed(42)
os.makedirs("models", exist_ok=True)
os.makedirs("reports", exist_ok=True)

df = pd.read_csv("data/synthetic_property_portfolio.csv")

# ---------------------------------------------------------------------
# 1. SEGMENTATION
# ---------------------------------------------------------------------
CLUSTER_FEATURES = ["occupancy_pct", "same_property_noi_growth_pct", "interest_coverage",
                     "leverage_pct", "noi_margin"]
X_cluster = StandardScaler().fit_transform(df[CLUSTER_FEATURES])

kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
df["cluster"] = kmeans.fit_predict(X_cluster)

# Interpret clusters by ranking on a simple composite performance score,
# so labels are assigned programmatically rather than eyeballed.
centers = pd.DataFrame(kmeans.cluster_centers_, columns=CLUSTER_FEATURES)
composite = (centers["occupancy_pct"].rank() + centers["same_property_noi_growth_pct"].rank()
             + centers["interest_coverage"].rank() - centers["leverage_pct"].rank())
order = composite.sort_values(ascending=False).index.tolist()
labels_by_rank = ["Core Stabilized", "Mature / Harvest Candidate", "Value-Add Opportunity", "Distressed / Turnaround"]
cluster_label_map = {cluster_id: labels_by_rank[rank] for rank, cluster_id in enumerate(order)}
df["segment"] = df["cluster"].map(cluster_label_map)

print("Segment sizes:")
print(df["segment"].value_counts())
print("\nSegment characteristics (mean):")
print(df.groupby("segment")[CLUSTER_FEATURES].mean().round(2))

# ---------------------------------------------------------------------
# 2. FORWARD NOI GROWTH FORECAST -- simulate a genuinely uncertain target
# ---------------------------------------------------------------------
# Mean-reversion to sector average plus idiosyncratic shock: this is a
# simulation of what NEXT year's growth would be, not a re-derivation of
# data already in the table. The noise term is what makes this a real
# forecasting problem instead of algebra.
sector_avg_growth = df.groupby("property_type")["same_property_noi_growth_pct"].transform("mean")
next_year_growth_pct = (
    0.55 * df["same_property_noi_growth_pct"]
    + 0.45 * sector_avg_growth
    + np.random.normal(0, 1.4, size=len(df))
)
df["next_year_noi_growth_pct_actual"] = np.round(next_year_growth_pct, 2)

FORECAST_FEATURES = ["occupancy_pct", "same_property_noi_growth_pct", "noi_margin",
                      "interest_coverage", "leverage_pct", "hold_years"]
CAT_FEATURES = ["property_type", "market"]
X = pd.get_dummies(df[FORECAST_FEATURES + CAT_FEATURES], columns=CAT_FEATURES, drop_first=True)
y = df["next_year_noi_growth_pct_actual"]

feature_columns = X.columns.tolist()
with open("models/forecast_feature_columns.json", "w") as f:
    json.dump(feature_columns, f, indent=2)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

rf = RandomForestRegressor(n_estimators=300, max_depth=6, min_samples_leaf=4, random_state=42)
rf.fit(X_train, y_train)
pred_test = rf.predict(X_test)

r2 = r2_score(y_test, pred_test)
mae = mean_absolute_error(y_test, pred_test)
print(f"\nForward NOI growth forecast (held-out test, {len(X_test)} properties):")
print(f"  R^2:  {r2:.3f}")
print(f"  MAE:  {mae:.2f} percentage points")

# Baseline comparison: naive forecast = "next year = this year" (no model)
naive_pred = X_test["same_property_noi_growth_pct"] if "same_property_noi_growth_pct" in X_test.columns else None
naive_mae = mean_absolute_error(y_test, X.loc[X_test.index, "same_property_noi_growth_pct"])
print(f"  Naive baseline MAE (persistence forecast): {naive_mae:.2f} points -- model {'beats' if mae < naive_mae else 'does not beat'} the naive baseline")

with open("reports/forecast_metrics.json", "w") as f:
    json.dump({"r2": round(r2, 4), "mae": round(mae, 4), "naive_baseline_mae": round(naive_mae, 4),
               "n_test": len(X_test)}, f, indent=2)

# SHAP explainability
explainer = shap.TreeExplainer(rf)
shap_values = explainer.shap_values(X_test)
plt.figure()
shap.summary_plot(shap_values, X_test, show=False, max_display=10)
plt.tight_layout()
plt.savefig("reports/forecast_shap_summary.png", dpi=150)
plt.close()

# Score the full portfolio
df["predicted_next_year_noi_growth_pct"] = np.round(rf.predict(X), 2)

# ---------------------------------------------------------------------
# 3. VALUE-CREATION SCORE (0-100) -- transparent formula, not a black box
# ---------------------------------------------------------------------
# Two ingredients, each converted to a 0-100 percentile rank, then averaged:
#   (a) value already captured: cap rate compression since acquisition
#   (b) value still ahead: forecasted forward NOI growth
value_captured_pctile = df["value_creation_spread"] if "value_creation_spread" in df.columns else \
    (df["going_in_cap_rate"] - df["current_cap_rate"])
df["value_captured_pctile"] = value_captured_pctile.rank(pct=True) * 100
df["forward_growth_pctile"] = df["predicted_next_year_noi_growth_pct"].rank(pct=True) * 100
df["value_creation_score"] = np.round(
    0.5 * df["value_captured_pctile"] + 0.5 * df["forward_growth_pctile"], 1
)

df.to_csv("data/scored_property_portfolio.csv", index=False)
joblib.dump(rf, "models/noi_forecast_model.joblib")
joblib.dump(kmeans, "models/segmentation_kmeans.joblib")

print("\nDone. Scored portfolio -> data/scored_property_portfolio.csv")
print(df[["property_id", "segment", "value_creation_score", "recommendation"]].head(8).to_string(index=False))
