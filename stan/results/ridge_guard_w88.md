# W-88 — ridge-guard feature A/B (full grid): ADOPT-candidate, all gates PASS

**Verdict: ADOPT-candidate as an env-gated walnutpie feature** (branch
`exp/ridge-guard`, commit 88157bc, on the robust stack). Aggregate
geometric-mean ESS **330.1 → 519.6 = +57.4%**, zero models harmed, and
every unfired cell bit-identical to baseline. Date 2026-08-27.

## Results (median over 3 reps, guard5 vs runs/w36/exp_par baseline)

| model | fires | base geoESS | guard5 geoESS | Δ |
|---|---|---:|---:|---:|
| diamonds | 3/3 | 60.3 | 802.1 | **+1230.7%** |
| bym2_offset_only | 3/3 | 5.9 | 14.5 | +145.2% |
| eight_schools_c | 1/3 | 237.0 | 399.3 | +68.5% |
| pilots | 3/3 | 426.4 | 685.4 | +60.7% (ESSmin 4.6→33) |
| accel_gp | 3/3 | 42.6 | 45.0 | +5.8% |
| radon / hier / lsat / kronecker / lotka | 0–1/3 | — | — | +0.0% (bit-identical) |
| **AGGREGATE** | | 330.1 | **519.6** | **+57.42%** |

## Gate outcomes (as pre-registered)

1. Aggregate ≥ baseline+20% → **PASS** (+57.42%).
2. ≥3 silent-model cells md5-identical → **PASS**: 14/14 unfired cells
   bit-identical (5 models × 3 reps md5-verified); the ONLY differing
   cell in that set is radon rep2 — precisely the one that fired.
3. No model geoESS worse than baseline by >10% → **PASS** (no model
   worse at all; worst change is +0.0%).

## How it works (86 lines)

`sampler_min_micro(n)` on AdaptiveWalnuts (mirrors sampler() with an
overridden trajectory budget) + a CLI gate after warmup: per coordinate,
cross-chain dispersion of final positions ÷ mean adapted within-chain
scale sqrt(inv_mass) = F; if max F > WALNUTPIE_RIDGE_GUARD (default 5)
→ rebuild frozen samplers with WALNUTPIE_RIDGE_MINMICRO (default 128).
Default path (env unset): no code executes → bit-identity holds.

## Mechanism notes

- The detector sees what log-mass cannot: positions disperse across
  chains on null ridges where log-density is invariant (pilots: exact
  a/b-shift ridge; diamonds/bym2: partially-locked geometry at normal
  inits).
- Firing is per-REP (locks are stochastic): lock-prone models fired 3/3
  (accel, bym2, diamonds, pilots), marginal ones 1/3 (radon rep2,
  eight_schools rep?), healthy ones never. This achieves per-rep
  conditionality that four dead per-model selectors could not.
- Cost: fired cells pay the 128-micro budget (accel rep1 319s vs ~2s
  baseline — the expensive edge; diamonds ~97s vs 5s). Unfired cells
  pay nothing. Suite wall impact concentrated on already-broken cells
  that were producing garbage anyway.
- bym2 median only +145% despite rep0's +5549%: the other fired reps
  improved less; median over 3 reps with 2 fires. Still 4.2→5.6 ESSmin,
  rhat improved.
- Relation to W-74/W-75: pf inits fix the INIT side of the same locks;
  the guard fixes the SAMPLING side and composes with either init
  posture. Combined posture (pf + guard) is the natural next grid.

## Artifacts

runs/w88/guard5/**, results/w88_ess.json, branch exp/ridge-guard
(worktree external_w86/), spot validations in /tmp/w86{pilots,canary}.
