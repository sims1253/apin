# Freeze-time step clamp: auditable fallback instead of a `macro_time must be in (0, inf)` abort when the adapted step is degenerate

Branch `robustness/freeze-clamp` (off `dev/init-robustness` @ 3eddfc4)
in the `sims1253/walnutpie` fork: two commits — the W-41 clamp, plus the
W-43 `find_reasonable_step` fix, because the clamp's fallback (b) calls
that probe and the probe was broken 3 ways (its standalone PR is
`robustness/step-heuristic-fix`, which carries the same fix with full
diagnostics). Part of the robustness trio with `robustness/init-guard`
(this clamp is the second line of defense behind that root-cause guard).

## Problem

At the warmup freeze, `AdaptiveWalnuts::sampler()` constructs the frozen
sampler with the adapted `step_size()` (the step adapter's `exp(theta_)`)
as `macro_time`; the `WalnutsSampler` constructor runs
`detail::validate_positive` and throws `std::invalid_argument` when the
value is 0, NaN or +inf — aborting the WHOLE run at the very end of the
budget.

### Derivation of the failure (verified on both known cells)

The degenerate value is **NaN**, produced by a pinned warmup (typically
a non-finite-logp init — see the init-guard PR for the entry mechanism):

1. `lp = -inf` at the init → both Hamiltonians `+inf` → acceptance
   statistic `inf - inf = NaN`;
2. the adapter NaNs on its FIRST update → `step_size() = NaN` for every
   remaining iteration (position never changes);
3. at the freeze, `validate_positive(NaN)` throws — after 100% of the
   warmup budget is consumed, destroying the other chains' draws with
   it.

The abort message names an internal invariant, not the cause; and a
whole-run abort is the worst possible outcome when only one chain is
degenerate: the healthy chains' 3000+ draws are thrown away.

Same-family exposure: `walnuts_with_reinit` (api.hpp) reseeds outlier
chains with `ar.step_bar` (geometric mean of per-chain `exp(log_step)`)
— degenerate if any chain's log step underflowed to `-inf`/NaN.

This is the tail end of the bug class reported in the walnutpie 0.0.1
release thread (discourse 41487, post 11): a bad initial state cascades
into a degenerate adaptation and the run dies late and cryptically
instead of early and loudly.

## Fix

Clamp the just-frozen `macro_time` into a finite positive fallback with
an explicit warning, so the run completes and the degenerate chain is
AUDITABLE, rather than aborting at construction time on a
diagnostic-poor path:

- At freeze in `sampler()`: validate `step_size()`; if not
  finite-positive, fall back in order:
  (a) the last finite-positive step observed during warmup — tracked per
  iteration by a pure read of `opt_.step_size()` (no warmup arithmetic
  changed), seeded with the init step;
  (b) a `find_reasonable_step` re-derivation at the current position
  with the current metric (this is why the branch carries the W-43 probe
  fix — calling the old broken probe on a fallback path would have
  returned `eps >= 1` exactly where a tiny step is needed);
  (c) a documented hard floor `1000 * DBL_MIN` (~2.2e-305).
- Computed once and cached; `on_warmup_complete` reports the value
  actually frozen; one stderr line
  `WALNUTS WARNING: freeze step size degenerate (step_size()=…); falling
  back to … (source); warmup iterations=…` (the deliberate auditable
  channel).
- Same guard on the api.hpp reinit path: degenerate `step_bar` →
  geometric mean of the just-frozen per-chain `macro_time()` (finite
  positive by construction post-clamp), else the round's init step, else
  the floor; same warning.
- Healthy freezes are untouched: the clamp branch is dead code when
  `step_size()` is finite-positive (gated bit-identical, below).

## Validation (pre-registered gates, all PASS; measured on the original
exp/freeze-clamp + port commits — identical content)

- **Bit-identity canary, 12/12**: default-path draws (CLI defaults,
  warmup=1000 draws=1000, seeds 20260819+c) md5-identical pre vs post
  binary on hier_2pl, lsat_model, radon_partially_pooled × 4 chains;
  0 spurious warnings (the clamp never fired).
- **Recovery of the two known aborting cells** (production settings,
  previously rc=134 at the freeze after the full budget):

  | cell | seed | rc | draws | degenerate value | fallback used |
  |---|---|---|---|---|---|
  | kronecker_gp rep0 c0 | 20260819 | **0** | 1000 | NaN (`-nan`) | (a) last finite warmup step (= init seed 1.0) |
  | lotka_volterra rep1 c0 | 20261819 | **0** | 1000 | NaN (`-nan`) | (a) last finite warmup step (= init seed 1.0) |

  with the warning line naming chain/value/source; chains 1–3 rerun:
  rc=0, **zero warnings** (clamp dead code on healthy chains — their
  draws now land instead of being destroyed by the abort).
- **Recovery quality, recorded honestly**: the recovered chain 0 never
  left its `-inf` init, so the completed sets measure bulk-ESS-min 5.34
  / R-hat 2.12 (kronecker; chain 0 all-constant, ESS ≈ 0) and NaN
  estimators (lotka; every constrained draw NaN in that region). A
  pinned/NaN chain that completes AND is flagged by one loud warning
  beats a silent whole-run abort — and the root cause is now handled at
  entry by `robustness/init-guard` (these cells never reach the clamp
  there).
- **No collateral**: 2 healthy cells outside the canary set
  md5-identical, 0 warnings.

## References

- Full gate report, step-trajectory evidence (`WALNUTPIE_DEBUG_WARMUP`
  trace showing `step=-nan` from iteration 0) and repro commands:
  https://github.com/sims1253/apin — `stan/results/freeze_clamp_w41.md`,
  probe-fix gates in `stan/results/blr_pin_w43.md`; pre-registered
  protocols in `stan/WORKLOG.md` (W-41, W-43).
- Community report of the class: walnutpie 0.0.1 release thread
  (discourse 41487, post 11).
- Siblings: `robustness/init-guard` (root-cause guard — non-finite
  inits never reach the freeze), `robustness/step-heuristic-fix`
  (the probe fix, standalone).
