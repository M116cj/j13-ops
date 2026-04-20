# V9 Integration Retrospective — 2026-04-17

## What Went Right
- AKASHA Rust API upgrade with confidence + memory_relations deployed cleanly
- 14 V8 bug fixes + 1 float32 critical fix all verified
- 13 coldstart seeds truly pass all Arena lower bounds (no fabrication)
- Seeds fully isolated via engine_hash + card_status + evolution_operator
- 6 subagents executed in parallel, completed in ~1 hour

## Where It Stalled
- Initial V9 modules built but not integrated → 90% dead code for hours
- Float32 conversion broke Rust indicator engine (silent failure in except blocks)
- Project rename zangetsu_v5 → zangetsu caused import path confusion
- cuDF install downgraded Numba → cache needed clearing

## Adversarial Catches
- Gemini identified dead-code integration gap early
- Markl flagged 44% WR as structural issue (below cost breakeven)

## Research Impact
- CPCV for A3, Optuna TPE, Wavelet denoising (+25-41 dB SNR), attention aggregation all identified as signal quality levers

## One Thing to Change Next Time
- Test each module integration in isolation BEFORE bulk 'all completed' claim
