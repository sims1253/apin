# Fix `find_reasonable_step` (3 defects) so `--step-init-heuristic` actually unpins hard inits: blr short-warmup bulk-ESS 5–9 → 779, escape iteration 948 → 1

Branch `robustness/step-heuristic-fix` (off `dev/init-robustness` @
3eddfc4) in the `sims1253/walnutpie` fork. All changes are on the
opt-in, default-off, single-chain `--step-init-heuristic` path — the
default path is bit-identical (gated). Part of the robustness trio with
`robustness/init-guard` and `robustness/freeze-clamp`.

## Problem

At CLI defaults, hard-init models (blr, Bayesian logistic regression)
PIN for the first ~100–1000 warmup iterations: every transition burns 31
evaluations, the acceptance statistic underflows to exactly 0, and all
draws are identical (zero ESS). The in-tree mitigation for exactly this
— the Stan-style step probe behind `--step-init-heuristic` — could not
work because the probe itself was defective.

### Derivation of the pin mechanism (verified by an env-gated per-iteration trace)

- Mass is seeded as `(1-1e-5)·|grad(init)| + 1e-5` ≈ **1.6e7** at blr's
  default init, so a step-1.0 transition carries min-attempt
  `|ΔH| ≈ 8.2e6`: all 5 halvings fail (31 evals burned per transition,
  position unchanged).
- `alpha = exp(−|ΔH|)` **underflows to exactly 0.0**; Adam, blind to
  anything but the 0.8 target, descends the log step at `lr/√t`. Measured:
  `log(step0/step(n)) = 0.100·(√(n+1) − 1)` to within 2% over all 948
  pinned iterations — the ONLY state that changes during the pin
  (inv-mass is exactly frozen: the draw/score variance ratio is constant
  on constant streams).
- Escape is the FIRST iteration where the finest attempt's `|ΔH|` crosses
  the 0.5 cap — a momentum-driven first-passage: escape iteration
  scatters {574, 778, 948, >1000} across default-init seeds (one seed
  stays pinned the full 1000), clusters {185…200} on Pathfinder inits.
  If warmup ends still pinned, the frozen sampler (no adapter) re-pins:
  the CSV is 1 unique row repeated.

### The probe's three defects (`include/walnutpie/warmup_heuristics.hpp`)

1. **Momentum scale inversion**: the probe drew
   `p = z .* sqrt(inv_mass)` (i.e. ~N(0, inv_mass)) while the sampler
   draws `rho = sqrt(mass) .* z` (~N(0, mass)). Under the pin's seeded
   mass ~1.6e7 the probe moved ~1e7× less per step than a real
   transition, always "accepted", and returned `eps ≥ 1` (measured:
   `eps = 2.0` on the `|ΔH| = 8e6` cell). The library's other heuristic
   (`adapt_step` in util.hpp) uses the correct convention — the two
   disagreed.
2. **Fresh momentum per probe**: Hoffman–Gelman Algorithm 4 draws the
   momentum ONCE; the loop redrew z per probe, making the one-step
   error's sign a lottery.
3. **Asymmetric accept statistic**: `exp(−(h1 − h0))` is `inf > 0.5` for
   divergent-direction errors (energy gain), steering the probe UP on
   the pinned cell (error negative at e=1, positive at e=2 → returned
   eps=2 again).

## Fix

Correct scale (`p ~ N(0, mass)`, matching the sampler), ONE momentum
draw for the whole probe, and the symmetric statistic
`exp(−|h1 − h0|)` mirroring the sampler's own alpha/tolerance test.
One file, +29/−6, opt-in path only.

## Validation (pre-registered gates, all PASS)

- **Default-path canary bit-identity: 12/12** — default-path draws
  md5-identical pre vs post binary (arma11, blr, hier_2pl × 4 chains,
  1000+1000, seeds 20260819+c): the fix is invisible with the knob off.
- **Pin elimination + quality** (blr, 3 reps × 4 chains per arm,
  post-fix + `--step-init-heuristic`): **0 of 48 chains pinned**
  (pinned = all 1000 draws identical; base pins 3/4 chains/rep at
  w100-pf):

  | arm | bulk-ESS-min med | tail-ESS-min med | R-hat max med | pinned | base reference |
  |---|---:|---:|---:|---:|---|
  | w100 pf | **779.0** | 769.5 | 1.0048 | **0/12** | base w100: bulk **5–9**, 3/4 chains pinned/rep |
  | w400 pf | **630.4** | 693.7 | 1.0056 | **0/12** | base: 612.4 (rep1 = 86.5 from its pinned chain) |
  | w100 def | 4.2 | 4.6 | 4.56 | **0/12** | full-warmup BASE itself: bulk 4.2, R-hat 5.4, 1/4 pinned |
  | w400 def | 4.3 | 4.6 | 4.29 | **0/12** | (no healthy def-init base exists at any warmup ≤ 1000) |

  On the init class with a healthy reference (Pathfinder, the production
  protocol), the fix restores SHORT warmup to full health: w100 bulk 779
  vs the w1000 base band 432.9–545.5. On the default-init class the pin
  is equally eliminated (chains move from iteration ~1, lp climbs
  −3.347e7 → −2.93e7 over 100 warmup iterations) but short warmup stays
  DRIFT-limited — an init-protocol problem (the init-guard sibling PR's
  territory), recorded honestly as outside this gate.
- **Probe behavior on the pinned cell**: returns `eps ≈ 0.008`
  (vs 2.0 before); escape at iteration ONE with `alpha = 0.84` ≈ target
  (vs escape at iteration 948 on the traced default-init seed — and
  574–1000+ across seeds); warmup cost 937 calls vs 3102 pinned;
  sampling 8.2 evals/draw vs 31.

## Why this matters beyond blr

The saturated-alpha regime is a GENERAL warmup-robustness hazard for any
gradient-seeded-mass sampler whose step adapter consumes an
underflowing acceptance statistic: the adapter is blind (constant-target
descent) for as long as `|ΔH| > ~745`, and the descent pace (`lr/√t`)
sets a seed-dependent minimum warmup of hundreds to >1000 iterations.
A working init-step probe is the cheap escape hatch. In the walnutpie
0.0.1 release thread (discourse 41487, post 11), "Fable"'s analysis
identified Stan's step initialization as the decisive difference vs
WALNUTS on exactly these inits — this PR is that mechanism, made to
work (it was present but broken 3 ways).

## References

- Full mechanism report (escape-boundary tables, pin invariants across 8
  traced runs, per-defect probe measurements) and repro commands:
  https://github.com/sims1253/apin — `stan/results/blr_pin_w43.md`;
  pre-registered protocol in `stan/WORKLOG.md` (W-43).
- Hoffman & Gelman (2014), Algorithm 4 (the one-draw convention the
  probe now follows).
- Siblings: `robustness/init-guard` (root-cause init guard),
  `robustness/freeze-clamp` (auditable freeze fallback; carries this
  same probe fix because its fallback (b) calls the probe).
