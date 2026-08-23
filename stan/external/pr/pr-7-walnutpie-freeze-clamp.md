# Freeze clamp: auditable fallback instead of a `macro_time must be in (0, inf)` abort when the adapted step is degenerate

Branch `robustness/freeze-clamp` (off `dev/init-robustness` @ 3eddfc4) in
the `sims1253/walnutpie` fork, two commits: the clamp, plus the
`find_reasonable_step` fix from `robustness/step-heuristic-fix`, because
the clamp's fallback (b) calls that probe and the probe was broken in
three ways (see that PR for the diagnostics). Part of the robustness trio
with `robustness/init-guard`. This clamp is the second line of defense
behind that root-cause guard.

## Problem

At the warmup freeze, `AdaptiveWalnuts::sampler()` builds the frozen
sampler with the adapted `step_size()` (the step adapter's `exp(theta_)`)
as `macro_time`. The `WalnutsSampler` constructor runs
`detail::validate_positive` and throws `std::invalid_argument` when the
value is 0, NaN, or +inf, so the whole run aborts at the very end of the
budget.

The degenerate value is NaN, and it comes from a pinned warmup, most often
a non-finite-logp init (see the init-guard PR for the entry mechanism).
Confirmed on both known cells:

1. `lp = -inf` at the init makes both Hamiltonians `+inf`, so the
   acceptance statistic is `inf - inf = NaN`.
2. The adapter becomes NaN on its first update, so `step_size()` is NaN
   for every remaining iteration while the position never changes.
3. At the freeze, `validate_positive(NaN)` throws, after the whole
   warmup budget is spent, taking the other chains' draws with it.

The abort message names an internal invariant, not the cause. And a
whole-run abort is the worst outcome when only one chain is degenerate:
the healthy chains' 3000+ draws are thrown away.

The same exposure exists in `walnuts_with_reinit` (api.hpp), which
reseeds outlier chains with `ar.step_bar` (a geometric mean of per-chain
`exp(log_step)`). That is degenerate if any chain's log step underflowed
to `-inf` or NaN.

This is the tail end of the bug class reported in the walnutpie 0.0.1
release thread (discourse 41487, post 11): a bad initial state cascades
into degenerate adaptation, and the run dies late and cryptically instead
of early and loudly.

## Fix

Clamp the just-frozen `macro_time` to a finite positive fallback and warn,
so the run completes and the degenerate chain is auditable.

At freeze in `sampler()`, validate `step_size()`. If it is not finite and
positive, fall back in order:

(a) the last finite positive step seen during warmup, tracked per
    iteration by a pure read of `opt_.step_size()` (no warmup arithmetic
    changed), seeded with the init step;
(b) a `find_reasonable_step` re-derivation at the current position with
    the current metric, this is why the branch carries the probe fix;
    calling the old broken probe on a fallback path would return `eps >= 1`
    exactly where a tiny step is needed;
(c) a documented hard floor, `1000 * DBL_MIN` (about 2.2e-305).

The value is computed once and cached; `on_warmup_complete` reports the
value actually frozen. One stderr line
`WALNUTS WARNING: freeze step size degenerate (step_size()=…). Falling
back to … (source). Warmup iterations=…` marks the run.

The api.hpp reinit path gets the same guard: a degenerate `step_bar`
falls back to the geometric mean of the just-frozen per-chain
`macro_time()` (finite positive after the clamp), else the round's init
step, else the floor, with the same warning.

Healthy freezes are untouched. The clamp branch is dead code when
`step_size()` is finite and positive. The canary below gates this.

## Validation (pre-registered gates, all passing. Measured on the original
exp/freeze-clamp and port commits, identical content)

- Bit-identity canary, 12/12. Default-path draws (CLI defaults,
  warmup=1000, draws=1000, seeds 20260819+c) are md5-identical pre versus
  post binary on hier_2pl, lsat_model, radon_partially_pooled × 4 chains,
  with no spurious warnings (the clamp never fired).
- Recovery of the two known aborting cells (production settings. Both
  previously rc=134 at the freeze after the full budget):

  | cell | seed | rc | draws | degenerate value | fallback used |
  |---|---|---|---|---|---|
  | kronecker_gp rep0 c0 | 20260819 | 0 | 1000 | NaN (`-nan`) | (a) last finite warmup step (= init seed 1.0) |
  | lotka_volterra rep1 c0 | 20261819 | 0 | 1000 | NaN (`-nan`) | (a) last finite warmup step (= init seed 1.0) |

  The warning line names chain, value, and source. Chains 1–3 of each
  cell rerun clean: rc=0, zero warnings, the clamp is dead code on
  healthy chains, and their draws now land instead of being destroyed by
  the abort.
- Recovery quality, stated plainly: recovered chain 0 never left its
  `-inf` init, so the completed sets measure bulk-ESS-min 5.34 with R-hat
  2.12 (kronecker. Chain 0 all-constant) and NaN estimators (lotka. Every
  constrained draw is NaN in that region). A flagged, pinned chain that
  completes beats a silent whole-run abort, and with
  `robustness/init-guard`, these cells never reach the clamp in the first
  place.
- No collateral: 2 healthy cells outside the canary set are
  md5-identical, 0 warnings.

## References

- Full gate report, the step trajectory evidence (a `WALNUTPIE_DEBUG_WARMUP`
  trace showing `step=-nan` from iteration 0), and repro commands:
  https://github.com/sims1253/apin, `stan/results/freeze_clamp_w41.md`,
  probe-fix gates in `stan/results/blr_pin_w43.md`. Pre-registered
  protocols in `stan/WORKLOG.md` (W-41, W-43).
- Community report of the class: walnutpie 0.0.1 release thread
  (discourse 41487, post 11).
- Siblings: `robustness/init-guard` (root cause, non-finite inits never
  reach the freeze), `robustness/step-heuristic-fix` (the probe fix,
  standalone).
