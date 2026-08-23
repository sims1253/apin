# Init guard: never start a chain at a non-finite-logp position (file-init fail-fast, CLI-owned random-init retries via --init-tries)

Branch `robustness/init-guard` (off `dev/init-robustness` @ 3eddfc4) in
the `sims1253/walnutpie` fork. Part of a robustness trio with
`robustness/freeze-clamp` and `robustness/step-heuristic-fix`. Each branch
stands alone; they also compose.

## Problem

The init protocol can hand the sampler a position whose log density is
not finite. With `--init-file`, a draw can land in a region where the
model evaluates to `-inf` (shape checks pass, no exception fires; model
errors become `lp = -inf`). Nothing on the init path checks finiteness.
The first logp evaluation happens in `InitConfigBuilder::masses()`, and
that code threw the lp away into a local variable while using only the
gradient to seed the mass.

What follows, confirmed by a per-iteration trace:

1. Both Hamiltonians are `+inf`, so the within-orbit acceptance statistic
   `exp(-(h1 - h0))` is `inf - inf = NaN`.
2. The step adapter (Adam) becomes NaN on its first update: `step = -nan`
   from iteration 0.
3. The chain stays pinned for the whole budget. Every iteration rejects,
   burns its full 31-eval transition cost, and never moves.
4. At the freeze, `WalnutsSampler`'s `validate_positive(macro_time)`
   throws `macro_time must be in (0, inf)`. The run dies after the entire
   budget is spent. With the freeze clamp from the sibling PR, the run
   instead "completes" with a zero-ESS chain of identical draws that
   poisons R-hat and ESS for the whole run.

Both outcomes are worse than an early error. The pinned run wastes the
budget and produces garbage draws.

This is the bug class reported in the walnutpie 0.0.1 release thread
(discourse 41487, post 11: seantalts relaying "Fable"'s Lotka-Volterra
analysis — inits at lp ≈ −400 to −16,000, after which chains crawl or
deadlock). The trace above pins the entry mechanism: a non-finite-logp
start NaNs the adapter at iteration 0.

## Fix

Fail fast and loud in both init modes. Finite inits behave exactly as
today; the gates below show bit-identical draws.

File-init (`--init-file`): `masses()` already evaluates (logp, grad) at
each chain's position. The fix records the lp it was discarding
(`InitConfig::init_logps()`) and checks finiteness in the CLI right after
the builder runs — before the step heuristic, before the adapter exists,
before any warmup work. A non-finite lp prints a multi-line stderr banner
naming the chain, the resolved file, and the lp value, with the model's
own error right above it (for example
`lkj_corr_cholesky_lpdf: Random variable[27] is 0`), then throws
`std::invalid_argument` (the CLI's existing init-error convention). This
adds zero new evaluations.

Random-init (the default): Stan's own rejection protocol (draw, reject
non-finite logp, retry) already exists inside the model layer. BridgeStan's
`param_initialize` calls `stan::services::util::initialize` with
`max_tries` hardcoded to 100 by walnutpie's `load_stan.hpp` — invisible
and un-knobbed from the CLI. This PR exposes it
(`initialize(..., max_tries = 100)`, defaulting to the historical
behavior) and moves the policy to the CLI: the inner layer is called with
`max_tries = 1` and the CLI owns the budget (`--init-tries`, default 100),
the per-draw audit lines, and the loud all-failed error. RNG discipline:
one one-draw `initialize()` per attempt from the chain's BridgeStan init
stream, consumed in order, before any warmup consumption (warmup uses the
separate `std::mt19937_64{seed}` stream). The accepted position is
therefore identical to what the stock binary would accept for any run it
starts — verified bit-for-bit by the random-init canary cells.

Library users can add their own guard through the new
`InitConfig::init_logps()` accessor.

## Validation (pre-registered gates, all passing)

- Bit-identity canary, 16/16. Default-path draws (CLI defaults,
  warmup=1000, draws=1000, seeds 20260819+c) are md5-identical to the
  pre-change binary: 12 file-init cells (hier_2pl, lsat_model,
  radon_partially_pooled × 4 chains) plus 4 random-init cells, with no
  spurious warnings. (Measured on the original commit 5aed078. This
  branch is that commit minus the W-23-dependent endpoint-cache seeding
  extra; the same gates showed that extra was draw-neutral, so removing
  it cannot move draws either.)
- Fail-fast on the two known `-inf` cells (kronecker_gp rep0 c0 and
  lotka_volterra rep1 c0, `--init-file`, production settings):

  | cell | stock binary | + freeze clamp (sibling PR) | + init guard |
  |---|---|---|---|
  | kronecker_gp rep0 c0 | rc=134 at freeze, 2.97s, 31k calls | rc=0, 8.22s, 31,002 calls, pinned zero-ESS chain | rc=134, 0.16s, 1 eval |
  | lotka_volterra rep1 c0 | rc=134, 0.80s | rc=0, 5.28s, 31,000 calls, NaN draws | rc=134, 0.09s, 1 eval |

  That saves about 98% of the budget and leaves no zero-ESS or NaN draws
  to mislead downstream analysis. For reference, the unguarded
  completions measure bulk-ESS-min 5.34 with R-hat 2.12 (kronecker; chain
  0 all-constant, ESS near 0 at any warmup length) or NaN estimators
  (lotka).
- Random-init recovery. A seed trial found a cell whose first draw is
  non-finite (kronecker_gp, `--init 2.2`, seed 20260820): rc=0 with one
  audited rejection, then acceptance. Two identical invocations give
  identical retry counts and md5-identical CSVs. Exhaustion (`--init 2.5`)
  gives 100 audited rejections and a loud terminal error, rc=134.
- No collateral: 2 healthy cells outside the canary set are
  md5-identical, 0 warnings.

## References

- Full gate report, raw numbers, repro commands:
  https://github.com/sims1253/apin — `stan/results/init_guard_w42.md`;
  pre-registered protocol in `stan/WORKLOG.md` (W-42).
- Community report of the class: walnutpie 0.0.1 release thread
  (discourse 41487, post 11).
- Siblings: `robustness/freeze-clamp` (second line of defense behind this
  guard), `robustness/step-heuristic-fix` (makes
  `--step-init-heuristic` work).
