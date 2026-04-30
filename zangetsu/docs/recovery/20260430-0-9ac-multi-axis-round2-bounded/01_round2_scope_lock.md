# 01 — Round 2 Scope Lock

**ORDER**: 0-9AC-CLOSE — Phase 0 / Workstream A

## Bounded Scope (per 0-9AC §3.2)

Round 2 was limited to four targeted corrections from Round 1 findings:

| Correction | Target | Action Taken |
|---|---|---|
| Numeric blow-up | H | p99 absolute signal clipping in signal_processing.apply_p99_abs_clip |
| No-trade behavior | D | Band-crossing trigger replacing sign-flip in signal_to_trades_band_crossing |
| Limited symbol coverage | D | --d-symbol-mode all14 → 14-symbol universe |
| Gemini unavailable | Review | env-loaded GEMINI_API_KEY + minimized prompt + 120s timeout |

## Out of Scope (No Drift)

- maker-only routing
- VIP-tier optimization
- orderbook / depth / trade-print data capture
- execution architecture buildout
- mission-governance expansion
- new alpha axis
- new data source
- A2_MIN_TRADES adjustment
- Arena threshold change
- production runtime / DB / capital / risk

## Mainline Rule Honored

- 0-9ZB-MARKET-MICROSTRUCTURE-DATA-CAPTURE-SHADOW NOT used as prerequisite
- 0-9AC-CLOSE depends only on 0-9AC Round 2 outputs (already produced)
