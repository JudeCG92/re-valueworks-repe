"""
app.py -- RE ValueWorks: Real Estate Equity & Asset-Management Analytics

Three views:
  1. Portfolio Overview - fund-level performance and segmentation
  2. Property Explorer   - single-asset drill-down with forecast explainability
  3. Scenario Analysis   - live sensitivity on rent growth, occupancy, cap rate, capex
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import joblib
import shap


def robust_irr(cashflows):
    """IRR solver that won't silently fail. numpy_financial's irr() uses
    Newton's method seeded from a fixed guess, which fails to converge for
    cash-flow patterns with more than one sign change -- common in stress
    scenarios where interim cash flow is positive but a shocked exit value
    (debt exceeding a depressed sale price) makes the final-year cash flow
    deeply negative. This scans for every sign change in a wide, numerically
    safe range and brackets each with scipy's brentq, which always converges
    once a bracket is found. If NPV never crosses zero at any rate (the deal
    never breaks even under any discount rate -- a real possibility when the
    exit is deeply underwater), this correctly returns NaN rather than a
    fabricated number: that is a genuinely undefined IRR, not a solver bug.
    """
    def npv(rate):
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))
    if all(c < 0 for c in cashflows):
        return np.nan
    growth_factor = np.concatenate([np.geomspace(0.001, 1.0, 400), np.linspace(1.0, 6.0, 100)])
    grid = growth_factor - 1
    vals = [npv(r) for r in grid]
    for i in range(len(grid) - 1):
        v0, v1 = vals[i], vals[i + 1]
        if not (np.isfinite(v0) and np.isfinite(v1)):
            continue
        if v0 == 0:
            return grid[i]
        if v0 * v1 < 0:
            return brentq(npv, grid[i], grid[i + 1], maxiter=300)
    return np.nan

st.set_page_config(page_title="RE ValueWorks", layout="wide", page_icon="\U0001F3E2")

BASE_DIR = Path(__file__).resolve().parent.parent


@st.cache_resource
def load_models():
    rf = joblib.load(BASE_DIR / "models" / "noi_forecast_model.joblib")
    with open(BASE_DIR / "models" / "forecast_feature_columns.json") as f:
        feature_columns = json.load(f)
    return rf, feature_columns


@st.cache_data
def load_data():
    df = pd.read_csv(BASE_DIR / "data" / "scored_property_portfolio.csv",
                      parse_dates=["acquisition_date"])
    return df


@st.cache_resource
def load_explainer(_model):
    return shap.TreeExplainer(_model)


rf_model, FEATURE_COLUMNS = load_models()
df = load_data()
explainer = load_explainer(rf_model)

FORECAST_FEATURES = ["occupancy_pct", "same_property_noi_growth_pct", "noi_margin",
                      "interest_coverage", "leverage_pct", "hold_years"]
CAT_FEATURES = ["property_type", "market"]


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    X = pd.get_dummies(frame[FORECAST_FEATURES + CAT_FEATURES], columns=CAT_FEATURES, drop_first=True)
    for col in FEATURE_COLUMNS:
        if col not in X.columns:
            X[col] = 0
    return X[FEATURE_COLUMNS]


def classify_recommendation(occupancy, noi_growth, irr, equity_multiple, interest_coverage, property_type):
    reposition = (occupancy < 78) & (noi_growth < 1.0) & (property_type != "Multifamily")
    reposition = reposition | ((occupancy < 70) & (interest_coverage < 1.3))
    sell = (irr > 16) & (equity_multiple > 1.8)
    sell = sell | (irr < 0.0) | (interest_coverage < 1.1)
    return np.select([reposition, sell], ["Reposition", "Sell"], default="Hold")


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------
st.sidebar.title("\U0001F3E2 RE ValueWorks")
st.sidebar.caption("Real Estate Equity & Asset-Management Analytics")
page = st.sidebar.radio("View", ["Portfolio Overview", "Property Explorer", "Scenario Analysis"])
st.sidebar.divider()
st.sidebar.caption(
    "Property-level data is synthetic, generated to match realistic private "
    "equity real estate portfolio characteristics. Public REIT reference "
    "benchmarks (reports/reit_reference_benchmarks.md) are real, cited figures. "
    "No real fund or property data is used."
)

# ---------------------------------------------------------------------
# PAGE 1 -- Portfolio Overview
# ---------------------------------------------------------------------
if page == "Portfolio Overview":
    st.title("Portfolio Overview")

    total_value = df["implied_current_value"].sum()
    total_equity = df["equity_invested"].sum()
    median_irr = df["irr_pct"].median()
    median_em = df["equity_multiple"].median()
    avg_score = df["value_creation_score"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Implied Portfolio Value", f"${total_value/1e6:,.0f}M")
    c2.metric("Total Equity Invested", f"${total_equity/1e6:,.0f}M")
    c3.metric("Median IRR", f"{median_irr:.1f}%")
    c4.metric("Median Equity Multiple", f"{median_em:.2f}x")
    c5.metric("Avg Value-Creation Score", f"{avg_score:.0f} / 100")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Portfolio Segments")
        seg_order = ["Core Stabilized", "Value-Add Opportunity", "Mature / Harvest Candidate", "Distressed / Turnaround"]
        seg_counts = df["segment"].value_counts().reindex(seg_order).fillna(0)
        fig = px.bar(seg_counts, x=seg_counts.index, y=seg_counts.values,
                     color=seg_counts.index,
                     color_discrete_map={"Core Stabilized": "#2ca02c", "Value-Add Opportunity": "#3a6fb0",
                                          "Mature / Harvest Candidate": "#f5c542", "Distressed / Turnaround": "#d62728"},
                     labels={"x": "Segment", "y": "Number of Properties"})
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with col2:
        st.subheader("Recommendation Mix")
        rec_counts = df["recommendation"].value_counts()
        fig = px.pie(values=rec_counts.values, names=rec_counts.index, hole=0.45,
                      color=rec_counts.index,
                      color_discrete_map={"Hold": "#7f8fa6", "Sell": "#d62728", "Reposition": "#f5c542"})
        st.plotly_chart(fig, width="stretch")

    st.subheader("IRR by Property Type")
    fig = px.box(df, x="property_type", y="irr_pct", color="property_type",
                 labels={"irr_pct": "IRR (%)", "property_type": ""})
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Exposure by Market")
    exp = df.groupby("market")["implied_current_value"].sum().sort_values() / 1e6
    fig = px.bar(exp, x=exp.values, y=exp.index, orientation="h",
                 labels={"x": "Implied Value ($M)", "y": ""})
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------
# PAGE 2 -- Property Explorer
# ---------------------------------------------------------------------
elif page == "Property Explorer":
    st.title("Property Explorer")

    prop_id = st.selectbox("Select a property", df["property_id"].sort_values())
    prop = df[df["property_id"] == prop_id].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("IRR", f"{prop['irr_pct']:.1f}%")
    c2.metric("Equity Multiple", f"{prop['equity_multiple']:.2f}x")
    c3.metric("Value-Creation Score", f"{prop['value_creation_score']:.0f} / 100")
    c4.metric("Recommendation", prop["recommendation"])

    st.caption(f"Segment: **{prop['segment']}**")
    st.divider()

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Property Detail")
        detail = {
            "Property Type": prop["property_type"], "Market": prop["market"],
            "Acquisition Date": str(prop["acquisition_date"].date()),
            "Hold Period (yrs)": f"{prop['hold_years']:.1f}",
            "Acquisition Price": f"${prop['acquisition_price']:,.0f}",
            "Going-In Cap Rate": f"{prop['going_in_cap_rate']:.2%}",
            "Current NOI": f"${prop['current_noi']:,.0f}",
            "NOI Margin": f"{prop['noi_margin']:.1%}",
            "Occupancy": f"{prop['occupancy_pct']:.1f}%",
            "Same-Property NOI Growth": f"{prop['same_property_noi_growth_pct']:.2f}%",
            "Current Cap Rate": f"{prop['current_cap_rate']:.2%}",
            "Implied Current Value": f"${prop['implied_current_value']:,.0f}",
            "Leverage": f"{prop['leverage_pct']:.1%}",
            "Interest Coverage": f"{prop['interest_coverage']:.2f}x",
            "Cash-on-Cash Return": f"{prop['cash_on_cash_pct']:.2f}%",
        }
        st.table(pd.DataFrame(detail.items(), columns=["Field", "Value"]).set_index("Field"))

    with right:
        st.subheader("What's driving the forward NOI growth forecast")
        single = df[df["property_id"] == prop_id]
        X_single = build_features(single)
        shap_vals = explainer.shap_values(X_single)[0]
        contrib = pd.Series(shap_vals, index=FEATURE_COLUMNS).sort_values(key=abs, ascending=True).tail(8)
        fig = go.Figure(go.Bar(
            x=contrib.values, y=contrib.index, orientation="h",
            marker_color=["#2ca02c" if v > 0 else "#d62728" for v in contrib.values],
        ))
        fig.update_layout(xaxis_title="Impact on predicted growth (SHAP value, pts)", yaxis_title="")
        st.plotly_chart(fig, width="stretch")
        st.metric("Model-predicted next-year NOI growth", f"{prop['predicted_next_year_noi_growth_pct']:.2f}%")
        st.caption("Green = pushes forecast growth up. Red = pushes it down.")

    st.divider()
    st.subheader("Investment discussion points")
    flags = []
    if prop["interest_coverage"] < 1.3:
        flags.append(f"Interest coverage of {prop['interest_coverage']:.2f}x is thin \u2014 refinancing risk if rates rise further or NOI softens.")
    if prop["occupancy_pct"] < 80:
        flags.append(f"Occupancy of {prop['occupancy_pct']:.1f}% is below stabilized levels \u2014 evaluate leasing pipeline and capital needs to stabilize.")
    if prop["same_property_noi_growth_pct"] < 0:
        flags.append("Trailing NOI growth is negative \u2014 confirm whether this reflects a sector-wide or asset-specific issue.")
    if prop["irr_pct"] > 16 and prop["equity_multiple"] > 1.8:
        flags.append("Asset has substantially outperformed \u2014 a harvest sale would realize gains rather than continuing to hold for incremental upside.")
    if not flags:
        flags.append("No material flags \u2014 asset is performing within expected range for its segment.")
    for f in flags:
        st.write(f"- {f}")

# ---------------------------------------------------------------------
# PAGE 3 -- Scenario Analysis
# ---------------------------------------------------------------------
else:
    st.title("Scenario Analysis")
    st.caption("Sensitivity of portfolio returns to rent growth, occupancy, cap rate, and capex assumptions.")

    c1, c2, c3, c4 = st.columns(4)
    rent_shock = c1.slider("NOI / rent growth shock (%)", -20, 20, 0)
    occ_shock = c2.slider("Occupancy shock (%)", -20, 10, 0)
    cap_rate_shock_bps = c3.slider("Exit cap rate shock (bps)", -100, 200, 0, step=25)
    capex_shock = c4.slider("Capex shock (%)", -30, 50, 0)

    s = df.copy()
    occ_factor = 1 + occ_shock / 100
    noi_factor = (1 + rent_shock / 100) * occ_factor
    s["occupancy_pct"] = np.clip(s["occupancy_pct"] * occ_factor, 10, 100)
    s["current_noi"] = s["current_noi"] * noi_factor
    s["annual_capex"] = s["annual_capex"] * (1 + capex_shock / 100)
    s["current_cap_rate"] = np.clip(s["current_cap_rate"] + cap_rate_shock_bps / 10000, 0.03, 0.15)
    s["implied_current_value"] = s["current_noi"] / s["current_cap_rate"]

    annual_interest_expense = s["debt_balance"] * (s["interest_rate_pct"] / 100)
    s["interest_coverage"] = s["current_noi"] / annual_interest_expense
    levered_cf = s["current_noi"] - s["annual_capex"] - annual_interest_expense
    sale_proceeds = s["implied_current_value"] * 0.98 - s["debt_balance"]

    hold_years_int = np.maximum(1, np.round(s["hold_years"]).astype(int))
    irr = np.full(len(s), np.nan)
    equity_multiple = np.full(len(s), np.nan)
    for i in range(len(s)):
        yrs = hold_years_int.iloc[i]
        eq = s["equity_invested"].iloc[i]
        cf = [-eq] + [levered_cf.iloc[i]] * (yrs - 1) + [levered_cf.iloc[i] + sale_proceeds.iloc[i]]
        irr[i] = robust_irr(cf)
        total = levered_cf.iloc[i] * yrs + sale_proceeds.iloc[i]
        equity_multiple[i] = total / eq if eq > 0 else np.nan
    s["irr_pct"] = irr * 100
    s["equity_multiple"] = equity_multiple
    # "Impaired" = negative IRR OR undefined IRR (deal never breaks even at
    # any discount rate -- happens when a shocked exit value is so far below
    # the debt balance that no rate makes the cash flows net to zero). An
    # undefined IRR is a WORSE outcome than a very negative one, not a
    # missing data point, so it must count here rather than be dropped.
    s["impaired"] = s["irr_pct"].isna() | (s["irr_pct"] < 0)

    s["recommendation"] = classify_recommendation(
        s["occupancy_pct"], s["same_property_noi_growth_pct"], s["irr_pct"],
        s["equity_multiple"], s["interest_coverage"], s["property_type"]
    )

    baseline_median_irr = df["irr_pct"].median()
    shocked_median_irr = s["irr_pct"].median()
    baseline_impaired = (df["irr_pct"] < 0).sum() + df["irr_pct"].isna().sum()
    shocked_impaired = s["impaired"].sum()
    baseline_value = df["implied_current_value"].sum()
    shocked_value = s["implied_current_value"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Median Portfolio IRR", f"{shocked_median_irr:.1f}%", delta=f"{shocked_median_irr - baseline_median_irr:+.1f} pts")
    c2.metric("Impaired Properties (negative or undefined IRR)", f"{shocked_impaired}", delta=f"{shocked_impaired - baseline_impaired:+d}", delta_color="inverse")
    c3.metric("Implied Portfolio Value", f"${shocked_value/1e6:,.0f}M", delta=f"{(shocked_value - baseline_value)/1e6:+,.0f}M")

    st.subheader("Recommendation Shift: Baseline vs. Shocked")
    compare = pd.DataFrame({
        "Baseline": df["recommendation"].value_counts().reindex(["Hold", "Reposition", "Sell"]).fillna(0),
        "Shocked": s["recommendation"].value_counts().reindex(["Hold", "Reposition", "Sell"]).fillna(0),
    })
    fig = px.bar(compare, barmode="group", color_discrete_map={"Baseline": "#7f8fa6", "Shocked": "#d62728"})
    st.plotly_chart(fig, width="stretch")

    st.subheader("Properties With the Largest IRR Decline")
    delta_df = pd.DataFrame({
        "property_id": df["property_id"], "property_type": df["property_type"],
        "market": df["market"], "baseline_irr": df["irr_pct"], "shocked_irr": s["irr_pct"],
    })
    delta_df["change"] = delta_df["shocked_irr"] - delta_df["baseline_irr"]
    st.dataframe(delta_df.sort_values("change").head(10), width="stretch")

    st.caption(
        "Modeling simplification: hold period is held constant at each property's current "
        "hold-years value under the shocked scenario (i.e., 'what if these conditions applied "
        "through an exit today'), rather than re-solving a full multi-year forward pro forma. "
        "Debt terms (balance, rate) are held fixed \u2014 shocks affect NOI, value, and coverage, "
        "not financing structure."
    )
