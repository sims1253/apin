# Notes — walnutpie robustness trio (W-41/W-42/W-43): ready text for fork PRs or upstream issues

**Status:** all three fixes are implemented and gated on walnutpie fork
branches. These notes are the filing-ready summaries. Whether they go out
as fork PRs (to the walnutpie dev lineage) or upstream issues is the
user's call. Every number below is from the pre-registered gates in the
result docs cited at the end.

---

## 1. Init-protocol guard: never start a chain at a non-finite-logp position

**Branch:** `exp/init-guard` (commit 5aed078).

**Problem (mechanism):** the init protocol hands the sampler positions
whose log density is non-finite (e.g. `-inf` values inside a provided
init file, which pass NaN/shape checks but kill the model). The chain
then pins silently: the acceptance statistic NaNs the step adapter at
iteration 0, the chain never moves, and the run ends in either a
freeze-time abort (`macro_time must be in (0, inf)`) after burning the
whole budget, or a garbage "completing" chain of identical draws.

**Fix:** fail fast and loud.
- FILE-INIT: `InitConfigBuilder::masses()` already evaluates (logp, grad)
  at each chain's provided position, the lp was literally discarded into
  a throwaway variable. Record it, and check finiteness immediately after
  the builder runs, before the step heuristic, before the adapter exists,
  before ANY warmup consumption. Non-finite → multi-line stderr banner
  naming chain, file, and the logp value, then the CLI's existing
  init-error exit convention. Zero new evaluations.
- RANDOM-INIT: the 100-draw rejection loop against non-finite-logp draws
  (the Stan services convention), discovered to already exist one layer
  down. Surfaced/enforced rather than duplicated.

**Evidence:** kronecker_gp rep0 chain 0 (the −inf-init cell, seed
20260819): stock 8.22 s and 31,002 gradient calls ending in a pinned
zero-ESS chain → guarded **0.16 s, 1 evaluation, loud abort** (~98% of
the budget saved, and no zero-ESS/NaN draws to mislead downstream
analysis). Same behavior on the lotka_volterra cell.

---

## 2. Freeze-time step clamp: auditable fallback instead of a NaN abort

**Branch:** `exp/freeze-clamp`.

**Problem (mechanism):** at freeze time the sampler is constructed with
the (possibly degenerate) adapted step as `macro_time`. The constructor's
`validate_positive` throws `macro_time must be in (0, inf)` when the
adapted value is NaN, which is exactly what a pinned/ill-fated warmup
produces (both Hamiltonians `+inf` → NaN → the adapter NaNs on its first
update). The abort names an internal invariant, not the cause.

**Fix:** clamp the just-frozen per-chain `macro_time` into a finite
positive fallback with an explicit warning (auditable: the run completes,
the warning names the chain and the degenerate value), rather than
aborting at construction time on a diagnostic-poor path.

**Evidence:** both W-36 abort cells (kronecker_gp rep0 c0,
lotka_volterra rep1 c0) complete with the warning. The underlying init
pathology is separately eliminated by fix 1. Default-path draws
bit-identity-gated (12/12 cells md5-identical with the clamp code
present but unfired).

---

## 3. blr short-warmup pin: root cause + `find_reasonable_step` was broken 3 ways

**Branch:** `exp/pin-diagnosis` (commits 8853fd7 instrumentation +
468e60f fix).

**Problem (root cause, from an env-gated per-iteration pin trace):** the
pin is a step-size descent race in a saturated-alpha regime. Seeded mass
~1.6e7 at the default init → min-attempt |ΔH| ~ 8e6 → all 5 halvings fail
(31 evals burned per transition, position unchanged) →
`alpha = exp(−|ΔH|)` underflows to exactly 0.0 → Adam descends log-step
at lr/√t (measured `log(step0/step(n)) = 0.100·(√(n+1)−1)` to within 2%
over 948 iterations, the ONLY state that changes during the pin. The
mass estimate is frozen to all printed digits) → escape is the first
tolerance pass of the finest halving, a momentum-driven first-passage
(escape iteration scatters {574, 778, 948, >1000} across seeds on
default inits, clusters {185…200} on Pathfinder inits).

**The intended mitigation was itself broken, `find_reasonable_step`
(= the CLI's `--step-init-heuristic` probe) had three defects:**
1. **Momentum scale inversion**: the probe drew `p = z .* sqrt(inv_mass)`
   (~N(0, inv_mass)) while the sampler draws `rho = sqrt(mass) .* z`
   (~N(0, mass)), under the pin's seeded mass the probe moved ~1e7×
   less per step than a real transition, always "accepted", and returned
   eps ≥ 1 (measured eps = 2.0 on the |ΔH|=8e6 cell). The library's
   other heuristic used the correct convention, the two disagreed.
2. **Fresh momentum per probe**: Hoffman–Gelman Alg 4 draws once. The
   loop redrew z per probe, making the one-step error's sign a lottery.
3. **Asymmetric accept statistic**: `exp(−(h1−h0))` is inf > 0.5 for
   divergent-direction errors, steering the probe UP on the pinned cell;
   now `exp(−|h1−h0|)`, mirroring the sampler's own alpha/tolerance test.

All three live only on the opt-in path (flag default-off, single-chain).

**Evidence:** canary bit-identity 12/12 (default-path draws md5-identical
pre/post fix). Post-fix + `--step-init-heuristic`, blr, 3 reps × 4 chains
per arm:

| arm | bulk-ESS-min med | tail-ESS-min med | R-hat max med | pinned |
|---|---|---|---|---|
| w100 pf | **779.0** | 769.5 | 1.0048 | **0/12** |
| w400 pf | **630.4** | 693.7 | 1.0056 | 0/12 |
| w100 def | 4.2 | 4.6 | 4.56 | 0/12 |
| w400 def | 4.3 | 4.6 | 4.29 | 0/12 |

**0 of 48 chains pinned across all arms** (base pins 3/4 chains/rep at
w100-pf with bulk-ESS 5–9). On the healthy-init class the fix restores
short warmup to full health: w100 bulk 779 vs the w1000 base band
432.9–545.5. On the default-init class the pin is equally eliminated but
short warmup stays *drift*-limited, that is init-protocol territory
(fix 1), not the step probe's.

---

## Filing notes

- The trio composes: 1 removes the non-finite-init entry, 2 makes any
  residual degenerate freeze auditable, 3 makes the step probe actually
  work so short warmups are viable on hard inits.
- Related but separate (its own kit, `external/upstream_pr_kits.md`
  Kit 5 / `WarmupConfig::allow_early_exit`): the controller's default
  cross-chain tolerances can stop warmup at iter 50–80 and destroy
  post-warmup quality (hier_2pl bulk-ESS-min 519 → 61. No
  tolerance-based gate fixes it). Implemented on `exp/safe-adapt-defaults`,
  default-path bit-identity 12/12, default `--chains 4` equals the
  full-warmup baseline 24/24.
- Evidence docs (attachable from the benchmark repo's results/ dir):
  init_guard_w42.md, freeze_clamp_w41.md, blr_pin_w43.md. The
  pre-registered protocol entries live in its WORKLOG.md.

## Cross-references to community reports (added 2026-08-23)

- The stuck-chain bug class documented here is the same one reported in the
  walnutpie 0.0.1 release thread (discourse 41487, post 11: seantalts
  relaying "Fable"'s Lotka-Volterra analysis, uniform(-2,2) init landing at
  lp ≈ -400..-16,000. Continuous mass adaptation from iteration 1 letting
  tail gradients collapse the metric into a self-reinforcing crawl; WALNUTS's
  strict whole-trajectory failure after max halvings turning a bad initial
  step into deadlock). Our series treats it systematically: init guard
  (non-finite inits), freeze clamp (degenerate freeze), and the
  find_reasonable_step fix (the Stan-side mechanism "Fable" identified as
  the decisive difference, our probe was broken 3 ways. Fixing it takes
  the pinned w100 blr class from bulk-ESS 5–9 to 779). The thread's
  init-buffer idea (identity metric for the first ~75 iterations, as Stan
  does) was tested as W-54 arm A and REJECTED: walnutpie's variance-ratio
  collapse happens at the FIRST post-buffer observation, not by
  accumulation, so deferring the estimator does not help (w100 bulk 4.0–5.1
  vs the heuristic fix's 779. Combining them DAMAGES the fix to 165.8).
  Soft gradient clipping (thread 41095's c·asinh(x/c)) was arm B, also
  REJECTED: a numerical identity at thread scales, insufficient at model
  scale, the lever cannot reach the alpha engine from adapter inputs.
  The step-side heuristic fix remains the only effective shield for this
  pin class (results/warmup_shields_w54.md).
- The soft gradient-clipping idea from the "models where Stan outperforms
  nutpie/walnuts" thread (discourse 41095, post 39: aseyboldt's
  c·asinh(x/c)) is likewise under test as W-54 arm B, scoped to
  adapter-visible gradients during early warmup only. Note for that
  thread's tree-size-quantization question: our per-transition
  gradient-accounting instrumentation (exp/grad-accounting branch, results/
  grad_accounting_w38.md) measures evals-per-transition histograms directly
  and can answer it empirically.
