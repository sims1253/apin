# Overnight-4 session summary — 2026-08-27 (ridge-guard arc)

The complete arc of the ridge-guard feature: mechanism → implementation
→ validation → composition → calibration. All pre-registered, all gates,
all recorded in WORKLOG (W-85..W-95).

## The headline

**A new sampler feature went from diagnosis to validated 3.3× aggregate
ESS in one session.** Combined posture on the 10-model grid:

| posture | aggregate geoESS | vs baseline |
|---|---:|---:|
| baseline (W-36) | 329.9 | — |
| + robustness stack (W-75) | 609.5 | +84.7% |
| + ridge guard only (W-88) | 519.6 | +57.4% |
| **+ pf inits + ridge guard (W-93)** | **1094.9** | **+231.9%** |

30/30 cells complete — including every historic abort cell.

## What the ridge guard is (PR #22, sims1253/walnutpie, [internal])

86 lines, env-gated (`WALNUTPIE_RIDGE_GUARD`), default-path inert
(bit-identity canaries green throughout). After warmup in multi-chain
mode: per coordinate, cross-chain dispersion of final positions ÷
adapted within-chain scale = F. F > 5 ⇒ chains have locked onto
different points of a likelihood-null ridge (invisible to every
log-mass statistic) ⇒ rebuild frozen samplers with a 128-micro-step
budget. Per-rep conditionality that four dead per-model selectors
couldn't achieve: lock-prone models fire 3/3, healthy models never,
cost lands only on cells that were producing garbage anyway.

## Evidence chain

1. **W-85** pilots lock is trajectory-length-binding (mm128 traverses
   the ridge: rhat 3.37→1.02) — not metric-binding.
2. **W-86** implementation + spot validation (diamonds turned out to be
   a true positive: +13×; eight_schools silent).
3. **W-88** full A/B: +57.4% aggregate, zero harm, 14/14 unfired cells
   bit-identical.
4. **W-93** composition with pf inits: super-additive (+232%; accel_gp
   +8095% — the two fixes address disjoint failure modes).
5. **W-95** calibration: F distribution strongly bimodal under both
   postures; threshold 5 confirmed; silent-F diagnostic added.

## The full decision package for the user

pf-init workflow + walnutpie PRs #7/#8/#9/#10 (robustness) + #22 (ridge
guard) = **+232% aggregate ESS, 30/30 completion, every canary green**.
All are drafts on sims1253/walnutpie awaiting review.

## Incidents & process notes

- A stray W-87 process ran rogue 70+ min (SIGTERM silently failed);
   resolved, apologized on the board, serialization plan adopted.
- ROOT CAUSE found in W-95: the shell's `pkill` is shadowed by the
   ZCode AppImage pgrep — use `/usr/bin/pkill` (added to gotchas).
- W-87 forced-128 map cancelled (hours/cell; superseded by the guard's
   own fire census).

## Addendum: W-96..W-100 (later same session; siblings took 96-98)

- **W-99 — out-of-sample generalization: PASSES.** 11 unseen CORE_SET
  models, same-binary env-toggle A/B: zero false positives (24 unfired
  cells bit-identical; silent max F=4.51), 9/9 fired cells improved
  R-hat (radon_variable_intercept_slope +270% geoESS, kidscore rhat
  2.77→1.54, blr partial). The guard found real coverage breaks my
  priors missed (blr/kidscore/arma11-rep1 vs predicted dogs/garch).
- **W-100 — multi-chain step-init heuristic: REJECTED for flag-lift.**
  radon_vis spectacularly fixed (+650% geoESS, rhat 1.32→1.01) but
  blr/kidscore pins don't reach the ≤1.2 bar — they're coverage locks
  (pf-init territory), not step-init defects. Env-gated knob
  (WALNUTPIE_MC_STEP_HEURISTIC) committed to exp/ridge-guard as
  experimental; the single-chain-only flag restriction stays.
- Package status after the full arc (W-85..W-100): pf inits + PRs
  #7-#10 + #22 = +232% aggregate in-sample, generalizes out-of-sample,
  threshold calibrated, sanitizers green (sibling W-94).

## Addendum 2: W-101 (final caveat closed)

The package's only per-model regressions (kronecker −22.7%, lotka −7.8%
under pf inits) were **rep noise**: 5 fresh reps with a seed offset give
pf/normal geoESS ratios of 1.041 and 1.210 — pf is neutral-or-better on
every model at adequate rep counts. The promote package (pf inits +
PRs #7-#10 + #22) is now unconditionally positive on this suite.
Method note added to the ledger: the ±3% noise band applies to
aggregates; per-model claims need ≥5 reps or large effects.
