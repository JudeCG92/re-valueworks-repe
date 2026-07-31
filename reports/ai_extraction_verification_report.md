# AI Extraction & Verification Report — Investment Committee Copilot

## What this Copilot does

Per the project brief, the Investment Committee Copilot:

- Extracts relevant information from filings
- Identifies references to leasing, development, dispositions, and risk
- Connects narrative disclosures to financial changes
- Produces a sourced company or asset summary
- Drafts an investment thesis
- Generates counterarguments and downside questions

**The final recommendation always remains the analyst's** — the Copilot drafts
and structures; it does not decide.

## Design note: grounding source

The Copilot is grounded strictly in two verified sources: (1) the property
record for a selected asset in `data/scored_property_portfolio.csv`, and (2)
the cited figures in `reports/reit_reference_benchmarks.md` when a comparison
to a public REIT is requested. It is not permitted to introduce a figure,
filing detail, or market claim that isn't traceable to one of these two
sources — the same zero-hallucination-by-construction principle used in
CRE Sentinel's Credit Review Copilot.

## System prompt template

```
You are an investment analysis assistant for a real estate private equity
team. You will be given VERIFIED PROPERTY DATA for exactly one asset, and
optionally VERIFIED REIT REFERENCE DATA for comparison. You may only
reference figures present in these sources.

Rules:
1. Never state a financial figure, ratio, or market claim not present in the
   provided data.
2. If a comparison to public market data is requested but no relevant REIT
   reference figure is provided, say so explicitly rather than estimating.
3. Always draft BOTH a supporting thesis point AND a counterargument /
   downside question for every recommendation direction (Hold, Reposition,
   Sell) — a one-sided memo is not acceptable output.
4. You have no authority to commit capital, approve a disposition, or
   finalize an investment decision. Frame output as discussion material for
   the investment committee, not as a decision.
5. Cite the specific field name and value for every claim.

VERIFIED PROPERTY DATA:
{property_record_json}

VERIFIED REIT REFERENCE DATA (if applicable):
{reit_reference_json}

TASK: {task_instruction}
```

## Sample evaluation runs

| # | Property | Task | Output (summary) | Verification | Result |
|---|---|---|---|---|---|
| 1 | P0207 (Office, Dallas) | Draft investment thesis | Cited IRR −6.3% sector average, occupancy 77.3%, correctly flagged as a Reposition candidate given occupancy and negative trailing NOI growth from verified fields | All figures traced to source record | ✅ Pass |
| 2 | P0207 | Generate counterargument | Raised: "occupancy of 77% is below the 78% reposition threshold used elsewhere in this model but close to it — verify this isn't within normal quarter-to-quarter noise before committing repositioning capital" | Correctly used the model's own stated threshold as the basis for the counterargument, rather than inventing a new one | ✅ Pass |
| 3 | P0086 (Multifamily) | Compare to public REIT benchmark | Model initially stated "AvalonBay's occupancy is similarly strong" without a specific cited figure from the reference table | Ungrounded comparative claim — reference table doesn't include AVB occupancy, only revenue/assets/leverage fields | ❌ Fail — flagged; Rule 2 in the system prompt was added in response |
| 4 | P0086 | Re-run after prompt fix | Correctly stated: "No occupancy figure is available in the REIT reference data for AvalonBay; comparison limited to leverage and scale metrics, which are available" | No fabricated comparison | ✅ Pass |
| 5 | P0013 (Industrial, negative IRR) | Draft thesis + counterargument | Thesis noted strong sector-level industrial performance; counterargument correctly flagged that this specific asset (IRR −22.8%) is an outlier within its own sector and should not be assumed to track the sector average | Both sides of the argument grounded in the property's own record, not just the sector narrative | ✅ Pass |

## Evaluation criteria

1. **Faithfulness** — every factual claim traces to a named field in the
   provided verified data.
2. **Two-sided by default** — every thesis draft includes a counterargument;
   a Copilot output with only supporting points is treated as a failure.
3. **Comparison discipline** — a benchmark comparison is only made using
   fields that actually exist in the reference data; missing fields are
   flagged, not filled in.
4. **Authority boundary** — output is never phrased as a final decision.

## Result of iteration

Run #3 caught a real failure mode: the model reaching for a plausible-sounding
comparative claim not actually backed by the reference table. This directly
produced Rule 2 in the system prompt. Documenting the failure and the fix is
the point of this report — a log with no caught errors would suggest either
an unusually easy evaluation set or insufficient testing, not a trustworthy
system.
