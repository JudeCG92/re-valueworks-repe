# Data Dictionary — RE ValueWorks Property Portfolio

## Origin of the data

**No real fund, property, or investor data appears anywhere in this repository.**

Private equity real estate portfolio data is proprietary fund-level information,
not published. This project instead uses two clearly separated data sources:

1. **Synthetic property portfolio** (`data/synthetic_property_portfolio.csv`,
   `data/scored_property_portfolio.csv`) — 250 fabricated properties, generated
   to match realistic private equity real estate return dynamics. Generation
   logic: `scripts/generate_property_portfolio.py`.
2. **Public REIT reference benchmarks** (`reports/reit_reference_benchmarks.md`)
   — real, cited financial metrics for 10 large-cap publicly traded REITs,
   manually compiled from company filings (see that file for sourcing and
   verification notes). Used as a directional sanity check, not to calibrate
   the synthetic data statistically.

## How the synthetic portfolio was generated (summary)

1. Each property gets a type, market, and acquisition date/price. Going-in cap
   rate and NOI are drawn from distributions calibrated per property type,
   reflecting how the market actually prices risk today (office and hospitality
   trade at wider/cheaper cap rates than multifamily and industrial).
2. Same-property NOI growth since acquisition is generated per property, with
   type-level expectations (multifamily and industrial trending positive,
   office trending negative) plus per-asset variance.
3. Current implied value is calculated from current NOI and a current market
   cap rate that has drifted since acquisition (more so for office, reflecting
   real post-2022 market conditions).
4. **IRR and equity multiple are not randomly assigned** — they are the actual
   output of a levered cash-flow model built per property (equity invested at
   entry, annual levered cash flow, terminal sale proceeds), run through
   `numpy_financial.irr()`. This means these figures are internally consistent
   with every other field, the same way a real underwriting model works.
5. Hold/Reposition/Sell is a **transparent rule** (not a machine-learned
   classification) comparing occupancy, NOI growth, IRR, equity multiple, and
   interest coverage against thresholds — mirroring how an asset management
   team actually screens a portfolio. See "Two meanings of 'Sell'" below.

## Field reference

### `data/synthetic_property_portfolio.csv` (raw, 250 properties)

| Field | Type | Description |
|---|---|---|
| `property_id` | string | Unique identifier, `P0001`–`P0250` |
| `property_type` | categorical | Office, Multifamily, Retail, Industrial, Hospitality, Mixed-Use |
| `market` | categorical | One of 10 major US metros |
| `acquisition_date` | date | 1–8 years before Jan 2026 |
| `hold_years` | float | Years held as of Jan 2026 |
| `acquisition_price` | float ($) | Purchase price |
| `going_in_cap_rate` | float | NOI at acquisition / acquisition price |
| `going_in_noi` | float ($) | Annual NOI at acquisition |
| `current_revenue` | float ($) | Current annual revenue |
| `current_noi` | float ($) | Current annual NOI |
| `noi_margin` | float | current_noi / current_revenue |
| `occupancy_pct` | float | Current occupancy |
| `same_property_noi_growth_pct` | float | Annualized NOI growth since acquisition |
| `current_cap_rate` | float | Current market cap rate for this asset type/market |
| `implied_current_value` | float ($) | current_noi / current_cap_rate |
| `leverage_pct` | float | Debt / acquisition price (loan-to-cost) |
| `debt_balance` | float ($) | Outstanding debt |
| `interest_rate_pct` | float | Debt interest rate |
| `interest_coverage` | float | current_noi / annual interest expense |
| `annual_capex` | float ($) | Annual capital expenditure |
| `equity_invested` | float ($) | acquisition_price − debt_balance |
| `cash_on_cash_pct` | float | Levered annual cash flow / equity invested |
| `irr_pct` | float | **Calculated** via levered cash-flow model, not assigned |
| `equity_multiple` | float | **Calculated**: total equity distributed / equity invested |
| `recommendation` | categorical | Hold / Reposition / Sell — rule-based, see below |

### `data/scored_property_portfolio.csv` (adds model output)

Adds:

| Field | Type | Description |
|---|---|---|
| `cluster` / `segment` | categorical | KMeans cluster (4 segments), labeled by ranked composite performance |
| `next_year_noi_growth_pct_actual` | float | **Simulated** forward growth (mean-reversion + noise) — see Model Card |
| `predicted_next_year_noi_growth_pct` | float | **Model output** — Random Forest forecast of the above |
| `value_captured_pctile` / `forward_growth_pctile` | float | Percentile ranks feeding the value-creation score |
| `value_creation_score` | float, 0–100 | 0.5 × value_captured_pctile + 0.5 × forward_growth_pctile |

## Two meanings of "Sell" — read this before using the recommendation column

The `recommendation` field's "Sell" tag fires for two structurally different
reasons, and they should not be treated as the same signal:

1. **Harvest sale**: IRR > 16% and equity multiple > 1.8x — a stabilized asset
   that has already outperformed; the recommendation is to realize gains, not
   that anything is wrong with it.
2. **Distressed exit**: IRR < 0% or interest coverage < 1.1x — a genuinely
   underperforming asset where continuing to hold is the risk.

Any report or dashboard built on this data should split these two cases
visually (e.g., color or subgroup), not present "Sell" as a single undifferentiated
bucket — conflating them would misrepresent roughly a third of the portfolio.

## Directional sanity check against real REIT data

Property-type performance in the synthetic portfolio (mean IRR): Multifamily
+12.3%, Industrial +8.0%, Office **−6.3%**. This matches the real, observable
pattern in public REITs since 2022 — office REITs (BXP, VNO in the reference
table) have faced well-documented valuation pressure, while industrial (PLD)
and multifamily (AVB, EQR) have been comparatively resilient. This is a
directional check, not a statistical calibration.
