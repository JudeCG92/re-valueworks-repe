"""
generate_property_portfolio.py

Creates a synthetic real estate equity/asset-management portfolio for
RE ValueWorks. Every property here is fabricated -- there is no real
asset, owner, or fund represented.

Why synthetic: real private equity real estate portfolios are
proprietary fund-level data, generally not published. Public REIT data
IS available (via SEC EDGAR -- see fetch_sec_reit_data.py) and is used
separately to enrich this project with genuinely real company-level
benchmarks. This file is the property-level layer: individual assets
inside a hypothetical fund, built to behave like a real value-add /
core-plus real estate portfolio.

How this works, in plain terms:
1. Each property gets a type, market, and acquisition date/price.
2. Going-in NOI and cap rate are generated per property type/market
   (office and hospitality trade at wider cap rates than multifamily
   and industrial, matching current market pricing behavior).
3. Occupancy, same-property NOI growth, and market cap-rate movement
   since acquisition determine the property's CURRENT implied value.
4. An actual levered cash-flow stream (equity in, annual cash flow,
   terminal sale proceeds) is built per property and run through IRR
   and equity multiple calculations -- these are not randomly assigned,
   they are the real output of the modeled cash flows.
5. A hold / reposition / sell recommendation is derived from a
   transparent rule set (not a black-box ML classification) comparing
   trailing performance, occupancy, and value-creation potential --
   this mirrors how an asset management team actually screens a
   portfolio before deeper underwriting.
"""

import numpy as np
import pandas as pd
import numpy_financial as npf
from datetime import datetime, timedelta

np.random.seed(42)

N_PROPERTIES = 250

PROPERTY_TYPES = ["Office", "Multifamily", "Retail", "Industrial", "Hospitality", "Mixed-Use"]
PROPERTY_WEIGHTS = [0.16, 0.30, 0.14, 0.24, 0.08, 0.08]

MARKETS = ["New York", "Los Angeles", "Chicago", "Dallas", "Atlanta",
           "Phoenix", "Seattle", "Denver", "Austin", "Miami"]

# Going-in cap rate by property type (reflects relative risk/liquidity
# in the current market -- office and hospitality price cheaper /
# wider because of perceived risk, multifamily and industrial tighter).
CAP_RATE_BY_TYPE = {
    "Office": 0.078, "Hospitality": 0.082, "Retail": 0.068,
    "Mixed-Use": 0.065, "Industrial": 0.058, "Multifamily": 0.052,
}

# Annual same-property NOI growth expectation by type (multifamily and
# industrial have had the strongest fundamentals; office negative).
NOI_GROWTH_BY_TYPE = {
    "Office": -0.015, "Hospitality": 0.015, "Retail": 0.020,
    "Mixed-Use": 0.022, "Industrial": 0.035, "Multifamily": 0.030,
}

TODAY = pd.Timestamp("2026-01-01")


def random_dates(n):
    days_ago = np.random.randint(365, 365 * 8, size=n)  # 1-8 years held
    acquisition = [TODAY - timedelta(days=int(d)) for d in days_ago]
    return acquisition


def generate_portfolio(n=N_PROPERTIES):
    property_type = np.random.choice(PROPERTY_TYPES, size=n, p=PROPERTY_WEIGHTS)
    market = np.random.choice(MARKETS, size=n)
    acquisition_date = random_dates(n)
    hold_years_so_far = np.array([(TODAY - d).days / 365 for d in acquisition_date])

    size_base = {
        "Office": 45_000_000, "Multifamily": 32_000_000, "Retail": 18_000_000,
        "Industrial": 24_000_000, "Hospitality": 55_000_000, "Mixed-Use": 38_000_000,
    }
    acquisition_price = np.array([
        max(3_000_000, np.random.lognormal(mean=np.log(size_base[pt]), sigma=0.5))
        for pt in property_type
    ])

    going_in_cap_rate = np.array([
        np.clip(np.random.normal(CAP_RATE_BY_TYPE[pt], 0.006), 0.035, 0.11)
        for pt in property_type
    ])
    going_in_noi = acquisition_price * going_in_cap_rate

    # Same-property NOI growth realized since acquisition (type-level
    # expectation plus per-asset variance -- some assets outperform,
    # some underperform their sector).
    annual_noi_growth_pct = np.array([
        np.random.normal(NOI_GROWTH_BY_TYPE[pt], 0.025) for pt in property_type
    ])
    current_noi = going_in_noi * (1 + annual_noi_growth_pct) ** hold_years_so_far

    occupancy_base = {
        "Office": 76, "Multifamily": 93, "Retail": 88,
        "Industrial": 95, "Hospitality": 70, "Mixed-Use": 86,
    }
    occupancy_pct = np.clip(
        np.array([np.random.normal(occupancy_base[pt], 7) for pt in property_type]), 35, 100
    )

    revenue = current_noi / np.random.normal(0.62, 0.05, size=n).clip(0.45, 0.75)  # NOI margin ~55-70%
    noi_margin = current_noi / revenue

    # Current market cap rate: type-level rate today, drifted slightly
    # from going-in (rates have generally risen since 2022 across most
    # types, more so for office).
    cap_rate_drift = {
        "Office": 0.010, "Hospitality": 0.004, "Retail": 0.003,
        "Mixed-Use": 0.003, "Industrial": 0.002, "Multifamily": 0.002,
    }
    current_cap_rate = np.array([
        np.clip(CAP_RATE_BY_TYPE[pt] + cap_rate_drift[pt] + np.random.normal(0, 0.004), 0.035, 0.12)
        for pt in property_type
    ])
    implied_current_value = current_noi / current_cap_rate

    # Leverage: loan-to-cost at acquisition, typical value-add range
    leverage_pct = np.clip(np.random.normal(0.62, 0.07, size=n), 0.35, 0.80)
    debt_balance = acquisition_price * leverage_pct
    interest_rate_pct = np.clip(np.random.normal(6.1, 0.8, size=n), 3.8, 9.5)
    annual_interest_expense = debt_balance * (interest_rate_pct / 100)
    interest_coverage = current_noi / annual_interest_expense

    annual_capex_pct = np.clip(np.random.normal(0.045, 0.02, size=n), 0.005, 0.15)
    annual_capex = revenue * annual_capex_pct

    equity_invested = acquisition_price - debt_balance
    unlevered_cf = current_noi - annual_capex
    levered_annual_cf = unlevered_cf - annual_interest_expense

    # ---- Cash-flow-based IRR / equity multiple / cash-on-cash ----
    # Simplified but genuine: equity out at t=0, a flat annualized
    # levered cash flow for each year held so far, terminal sale
    # proceeds (implied current value less debt and a 2% cost of sale)
    # realized in the final year. This is a modeling simplification
    # (real underwriting would use a full multi-year pro forma with
    # year-by-year variation) documented as such in the data dictionary.
    hold_years_int = np.maximum(1, np.round(hold_years_so_far).astype(int))
    sale_proceeds = implied_current_value * 0.98 - debt_balance

    irr = np.full(n, np.nan)
    equity_multiple = np.full(n, np.nan)
    for i in range(n):
        yrs = hold_years_int[i]
        cf = [-equity_invested[i]] + [levered_annual_cf[i]] * (yrs - 1) + \
             [levered_annual_cf[i] + sale_proceeds[i]]
        try:
            r = npf.irr(cf)
            irr[i] = r if r is not None and not np.isnan(r) else np.nan
        except Exception:
            irr[i] = np.nan
        total_distributed = levered_annual_cf[i] * yrs + sale_proceeds[i]
        equity_multiple[i] = total_distributed / equity_invested[i] if equity_invested[i] > 0 else np.nan

    cash_on_cash_pct = levered_annual_cf / equity_invested

    # ---- Hold / Reposition / Sell recommendation (transparent rules) ----
    value_creation_spread = going_in_cap_rate - current_cap_rate  # positive = cap rate compression = value gained
    decision = np.select(
        [
            (occupancy_pct < 78) & (annual_noi_growth_pct < 0.01) & (property_type != "Multifamily"),
            (irr > 0.16) & (equity_multiple > 1.8),
            (irr < 0.0) | (interest_coverage < 1.1),
        ],
        ["Reposition", "Sell", "Sell"],
        default="Hold",
    )
    # Reposition beats Sell if both trigger for a distressed-but-not-yet-mature asset
    decision = np.where(
        (occupancy_pct < 70) & (interest_coverage < 1.3), "Reposition", decision
    )

    df = pd.DataFrame({
        "property_id": [f"P{str(i+1).zfill(4)}" for i in range(n)],
        "property_type": property_type,
        "market": market,
        "acquisition_date": [d.date() for d in acquisition_date],
        "hold_years": np.round(hold_years_so_far, 1),
        "acquisition_price": np.round(acquisition_price, 0),
        "going_in_cap_rate": np.round(going_in_cap_rate, 4),
        "going_in_noi": np.round(going_in_noi, 0),
        "current_revenue": np.round(revenue, 0),
        "current_noi": np.round(current_noi, 0),
        "noi_margin": np.round(noi_margin, 4),
        "occupancy_pct": np.round(occupancy_pct, 1),
        "same_property_noi_growth_pct": np.round(annual_noi_growth_pct * 100, 2),
        "current_cap_rate": np.round(current_cap_rate, 4),
        "implied_current_value": np.round(implied_current_value, 0),
        "leverage_pct": np.round(leverage_pct, 4),
        "debt_balance": np.round(debt_balance, 0),
        "interest_rate_pct": np.round(interest_rate_pct, 2),
        "interest_coverage": np.round(interest_coverage, 2),
        "annual_capex": np.round(annual_capex, 0),
        "equity_invested": np.round(equity_invested, 0),
        "cash_on_cash_pct": np.round(cash_on_cash_pct * 100, 2),
        "irr_pct": np.round(irr * 100, 2),
        "equity_multiple": np.round(equity_multiple, 2),
        "recommendation": decision,
    })
    return df


if __name__ == "__main__":
    df = generate_portfolio()
    out_path = "/home/claude/re-valueworks/data/synthetic_property_portfolio.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} properties -> {out_path}")
    print(f"Median IRR: {df['irr_pct'].median():.1f}%  |  Median equity multiple: {df['equity_multiple'].median():.2f}x")
    print(df["recommendation"].value_counts())
    print(df.groupby("property_type")[["irr_pct", "occupancy_pct"]].mean().round(2))
