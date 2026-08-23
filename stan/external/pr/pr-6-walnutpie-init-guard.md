# Init-protocol guard: never start a chain at a non-finite-logp position (file-init fail-fast + CLI-owned random-init rejection loop, `--init-tries`)

Branch `robustness/init-guard` (off `dev/init-robustness` @ 3eddfc4) in
the `sims1253/walnutpie` fork. Part of a robustness trio with
`robustness/freeze-clamp` (auditable freeze fallback) and
`robustness/step-heuristic-fix` (the `--step-init-heuristic` probe fix);
each is independently valid, and they compose.

## Problem

The init protocol can hand the sampler a position whose log density is
non-finite (for `--init-file`: a draw inside a region where the model
evaluates to `-inf` — NaN/shape checks pass, no exception fires; model
errors are mapped to `lp = -inf`). No finiteness check exists anywhere on
the init path: the first logp evaluation happens in
`InitConfigBuilder::masses()`, and its lp output was literally discarded
into a throwaway variable while only the gradient seeded the mass.

### Derivation of the failure (verified by trace)

Starting a warmup transition at `lp = -inf`:

1. both Hamiltonians are `+inf`, so the within-orbit acceptance
   statistic `exp(-(h1 - h0))` is `inf - inf = NaN`;
2. the step adapter (Adam) NaNs on its very first update —
   `step = -nan` from iteration 0 (per-iteration debug trace);
3. the chain is PINNED for the whole budget: every iteration rejects,
   burns its full 31-eval transition cost, and never moves;
4. at the freeze, `WalnutsSampler`'s `validate_positive(macro_time)`
   throws `macro_time must be in (0, inf)` (a stock abort after the
   ENTIRE budget is consumed), or — with the freeze clamp from the
   sibling PR — the run "completes" with a zero-ESS chain of identical
   draws that silently poisons R-hat/ESS for the whole run.

Both outcomes are strictly worse than an early error: the pinned run
burns ~100% of the budget AND produces garbage draws.

This is the same bug class reported in the walnutpie 0.0.1 release
thread (discourse 41487, post 11: seantalts relaying "Fable"'s
Lotka-Volterra analysis — inits landing at `lp ≈ -400..-16,000`, after
which the chain crawls/deadlocks). Our trace pins the entry mechanism:
a non-finite-logp start NaNs the adapter at iteration 0.

## Fix

Fail fast and loud, in both init modes; finite inits behave exactly as
today (bit-identical draws — gated, below).

- **FILE-INIT (`--init-file`)**: `masses()` already evaluates
  (logp, grad) at each chain's provided position — record the lp it was
  discarding (`InitConfig::init_logps()`), and check finiteness in the
  CLI immediately after the builder runs, BEFORE the step heuristic
  probe, before the adapter exists, before ANY warmup consumption.
  Non-finite → multi-line stderr banner naming the chain, the resolved
  file, and the lp value — the underlying model error surfaces right
  above it (e.g. `lkj_corr_cholesky_lpdf: Random variable[27] is 0`) —
  then `std::invalid_argument` (the CLI's existing init-error
  convention). **Zero new evaluations.**
- **RANDOM-INIT (default)**: Stan's own rejection protocol (draw, reject
  non-finite logp, retry) already existed INSIDE the model layer —
  BridgeStan's `param_initialize` calls
  `stan::services::util::initialize` with a `max_tries` hardcoded to 100
  by walnutpie's `load_stan.hpp`, invisible and un-knobbed from the CLI.
  This PR exposes it (`initialize(..., max_tries = 100)`, default =
  historical behavior) and moves the POLICY to the CLI: the inner layer
  is called with `max_tries = 1` (one draw per call) and the CLI owns
  the budget (`--init-tries`, default 100), the per-draw audit lines,
  and the loud all-failed error. RNG discipline: exactly one one-draw
  `initialize()` per attempt from the chain's BridgeStan init RNG
  stream, consumed strictly in order and before any warmup consumption
  (warmup runs on the separate `std::mt19937_64{seed}` stream); the
  accepted position is therefore IDENTICAL to what the stock binary
  would have accepted for any run it started — verified bit-for-bit by
  the random-init canary cells.

Library users can guard via the new `InitConfig::init_logps()` accessor.

## Validation (pre-registered gates, all PASS)

- **Bit-identity canary, 16/16**: default-path draws (CLI defaults,
  warmup=1000 draws=1000, seeds 20260819+c) md5-identical to the
  pre-change binary: 12 file-init cells (hier_2pl, lsat_model,
  radon_partially_pooled × 4 chains) + 4 random-init cells; 0 spurious
  warnings. (Measured on the original commit 5aed078; this branch is
  that commit minus the W-23-dependent endpoint-cache seeding extra —
  the same gates proved that extra draw-neutral, so removing it cannot
  move draws either.)
- **Fail-fast on the two known `-inf` cells** (kronecker_gp rep0 c0,
  lotka_volterra rep1 c0, `--init-file`, production settings):

  | cell | stock binary | + freeze clamp (sibling PR) | **+ init guard** |
  |---|---|---|---|
  | kronecker_gp rep0 c0 | rc=134 at freeze, 2.97s, 31k calls | rc=0, 8.22s, 31,002 calls, pinned zero-ESS chain | **rc=134, 0.16s, 1 eval** |
  | lotka_volterra rep1 c0 | rc=134, 0.80s | rc=0, 5.28s, 31,000 calls, NaN draws | **rc=134, 0.09s, 1 eval** |

  ~98% of the budget saved and no zero-ESS/NaN draws to mislead
  downstream analysis. (What the unguarded completions produce: the
  recovered chain sets measure bulk-ESS-min 5.34 / R-hat 2.12 with
  chain 0 fully pinned — every draw identical, ESS ≈ 0 at ANY warmup
  length, w100 included — or NaN estimators on the ODE model.)
- **Random-init recovery**: seed trial found a cell whose FIRST draw is
  non-finite (kronecker_gp, `--init 2.2`, seed 20260820): rc=0, one
  audited rejection (`WALNUTS WARNING (init guard): random init draw
  rejected … attempt 1/100 … redrawing`) then acceptance; two identical
  invocations → identical retry counts and md5-identical CSVs.
  Exhaustion (`--init 2.5`): 100/100 audited rejections + loud terminal
  error, rc=134.
- **No collateral**: 2 healthy cells outside the canary set md5-identical,
  0 warnings.

## References

- Full gate report, raw numbers and repro commands:
  https://github.com/sims1253/apin — `stan/results/init_guard_w42.md`,
  pre-registered protocol in `stan/WORKLOG.md` (W-42).
- Community report of the class: walnutpie 0.0.1 release thread
  (discourse 41487, post 11).
- Siblings: `robustness/freeze-clamp` (auditable fallback for
  non-init degeneracies — second line of defense behind this guard),
  `robustness/step-heuristic-fix` (makes `--step-init-heuristic`
  actually work).
