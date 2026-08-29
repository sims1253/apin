# Session summary 2026-08-25/27 — SoA shipping + ESS/s campaigns (W-57…W-85)

For review on return. Companion to OVERNIGHT_2026-08-25_SUMMARY.md (the
sibling cluster's map). Every claim below is gated + recorded in WORKLOG.

## TL;DR

Five fork draft PRs (all `[upstream-candidate]`, never pushed upstream):
**math#5** (SoA eltwise records), **walnutpie#13** (screen gating), **#15**
(depth diagnostics), **#17** (init eval-guard), **#20** (guarded min-micro-2).
One direction closed with a complete mechanism map (low-rank), two of my own
claims retracted loudly, and every remaining lever is either shipped,
closed-with-data, or an explicit user decision.

## 1. Shipped

- **math#5 — SoA eltwise-record migration** (W-53/57/58/59 + audits W-58 +
  checklist W-85): batches 0+1+2 + fused record loop. hier_2pl −17.8% total /
  −19.1% gradient Ir; blr mixed-GEMM forward −46.8%; wall −5..−7% in-sampler.
  Bit-identity proven at every level, culminating in W-81's 112/112-chain
  cross-`.so` grid identity (three-way with W-36 across sessions and
  threads/non-threads builds). Checklist-complete locally (W-85 caught a real
  standalone-include failure pre-CI; fixed in 8c63b8f).
- **walnutpie#20 — guarded min-micro-2** (W-76/79/80/82/84): the two-day arc
  from "lever discovered → selectors falsified → reactive guard". Domain
  table 24 models: 15 silent benefit (1.1–3.9× ESS/grad), 4 bounded economic
  harm, 13/13 MM2-pins restarted md5-exact to MM1, 8 baseline-inherent pins
  detected + neutralized. Zero false fires. Requires the NaN adapter guard
  (#10) in-binary — composition documented.
- **walnutpie#13/#15/#17** — screen-gating fix, depth diagnostics (which
  W-80 proved would have exposed the gpcm pinning in ordinary logs), init
  eval-guard (with the dead-init triage reclassified: only lotka is a true
  init failure).
- **W-81 combined-stack benchmark**: exp-tip sampler × SoA `.so` — draws
  bit-identical, wall 0.964 within-session / 0.913 drift-corrected. THE B''
  promotion evidence: the wins stack.

## 2. Closed with data (mechanisms in WORKLOG)

Low-rank metric (W-62..W-66 + the W-63 wiring-artifact correction): forced
rank rejected 0.25× aggregate; the auto-screen never gated the full operator
(my wiring gap, corrected); the fixed screen rescues sentinels but the
window_cross_ratio ordering is INVERTED vs benefit — direction closed.
Warmup truncation + adapt-freeze (W-74/W-77): both dead; W-74's "over-
adaptation" reading retracted (budget arithmetic, not sampling-state).
Depth-cap pins (W-76): 0/15. Predictive min-micro selectors: median
falsified (lsat), per-chain p90 failed its registered one-shot AND is
init-protocol-unstable.

## 3. Retractions/reclassifications (posted where claimed)

W-74 over-adaptation → W-77 inverse refutation; W-63 "screen inert" → wiring
artifact; W-61 dead-init triage → 1-of-3. W-85's per-op extraction-convention
correction (W-58 agent's numbers vs the annotation files).

## 4. User decisions remaining

B'' exp-stack promotion (evidence complete, see §1 W-81); A'' maintainer
replies; any multimodality-aware selector ambition (the one uncovered min-
micro-2 class is economic harm — the siblings' ridge-guard W-86/88 lane
addresses exactly that; joint test proposed on comms).
