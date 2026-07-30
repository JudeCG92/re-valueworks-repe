# Public REIT Reference Benchmarks

## What this is

A small, manually compiled table of real, publicly reported financial metrics
for 10 large-cap, publicly traded REITs, spanning the same property types used
in this project's synthetic portfolio. This is used to benchmark the synthetic
property-level data against how real public real estate companies actually
report and perform \u2014 the same role SEC EDGAR data would have played, without
requiring a live API pull.

## Important: verify before relying on these figures

These figures are approximate, drawn from general knowledge of each company's
most recent full-year (10-K) filings at the time this project was built, **not**
pulled live from a filing. Before using any of these numbers in a real
investment memo, client deliverable, or anything beyond a portfolio
demonstration, verify the current figures directly from:

- The company's own Investor Relations page (each publishes its 10-K and
  quarterly supplementals directly)
- SEC EDGAR's full-text search, browsable manually with no coding required:
  **https://www.sec.gov/cgi-bin/browse-edgar** \u2014 search the company name,
  open its most recent 10-K
- `scripts/fetch_sec_reit_data.py` in this repo, if you ever want to pull the
  live, current version programmatically (fully written, not required)

## Reference table (approximate, most recent full fiscal year known at time of writing)

| Ticker | Company | Sector | Revenue ($B, approx.) | Total Assets ($B, approx.) | Notes |
|---|---|---|---|---|---|
| PLD | Prologis | Industrial/Logistics | ~7.9 | ~54 | Largest global industrial REIT; low leverage relative to peers |
| AVB | AvalonBay Communities | Multifamily | ~2.7 | ~18 | Coastal/urban multifamily focus |
| EQR | Equity Residential | Multifamily | ~2.7 | ~17 | Urban multifamily, similar profile to AVB |
| SPG | Simon Property Group | Retail (Malls) | ~5.6 | ~27 | Higher leverage typical of mall REITs |
| O | Realty Income | Retail (Net Lease) | ~4.1 | ~58 | "The Monthly Dividend Company"; diversified net-lease tenants |
| PSA | Public Storage | Self-Storage/Industrial | ~4.6 | ~16 | Historically low leverage, high margins |
| BXP | BXP (fka Boston Properties) | Office | ~2.9 | ~21 | Largest publicly traded office REIT; a useful real-world stress case given office sector headwinds |
| VNO | Vornado Realty Trust | Office | ~1.7 | ~16 | NYC-concentrated office, higher leverage |
| HST | Host Hotels & Resorts | Hospitality | ~5.5 | ~12 | Largest lodging REIT by enterprise value |
| FRT | Federal Realty Investment Trust | Retail (Shopping Centers) | ~1.15 | ~8 | Smallest of this set; longest consecutive dividend-growth streak of any REIT |

## How this is used in the project

This table is referenced in the credit-risk/investment report as a sanity check:
does the synthetic portfolio's directional story (multifamily and industrial
outperforming office) match what's observable in the real public REIT market?
At a high level, yes \u2014 office REITs (BXP, VNO) have faced well-documented
valuation pressure since 2022, while industrial (PLD, PSA) and multifamily
(AVB, EQR) have remained comparatively resilient, which is consistent with the
synthetic portfolio's property-type performance spread. This is a directional
sanity check, not a statistical validation \u2014 the synthetic portfolio is not
calibrated to match these companies' exact figures.
