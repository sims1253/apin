# W-42: init-protocol guard — never start a chain at a non-finite-logp position (results)

Branch `exp/init-guard` (worktree `external/walnutpie_w42`, commit 5aed078),
off `exp/safe-adapt-defaults` @ 43b6435. Pre-change reference = the
exp/safe-adapt-defaults binary (`external/walnutpie/build_w36exp`,
built @ 43b6435); pinned-completion baseline = the W-41 freeze-clamp
binary (`external/walnutpie_w41/build_w41`). Build mirrors build_w36exp
(empty CMAKE_BUILD_TYPE, /usr/sbin/c++, default flags); header edits
rebuilt clean-first.

## Root cause and fix

W-41 established that both W-36 abort cells (kronecker_gp rep0 c0,
lotka_volterra rep1 c0) and both W-41 "recoveries" share one root cause:
the init protocol hands the sampler a position where the model logp is
non-finite. The guard makes that state impossible to enter silently:

- FILE-INIT (`--init-file`): `InitConfigBuilder::masses()` already
  evaluates (logp, grad) at each chain's provided position — the lp was
  literally discarded into `lp_to_discard`. W-42 records it
  (`InitConfig::init_logps()`); the CLI checks finiteness immediately
  after the builder runs, BEFORE the step heuristic probe, before the
  adapter exists, before ANY warmup consumption. Non-finite -> loud
  multi-line stderr banner naming chain, file, and the logp value, then
  `throw std::invalid_argument` (the CLI's existing init-error
  convention, exit code 134 = SIGABRT like a dimension-mismatched init
  file). Zero new evaluations.
- RANDOM-INIT (default): MID-FLIGHT DISCOVERY — the rejection loop
  already existed, INSIDE the model layer: BridgeStan 2.9.0's
  `param_initialize` calls `stan::services::util::initialize` with a
  `max_tries` that walnutpie's `load_stan.hpp` hardcoded to 100 — Stan's
  own random-init protocol (draw, reject non-finite logp, retry), with
  cmdstan-style "Rejecting initial value" messages and a terminal
  "Initialization failed" throw. It was invisible and un-knobbed from
  the CLI. W-42 exposes it (`load_stan::initialize(..., max_tries = 100)`,
  default = historical behavior exactly) and moves the POLICY to the
  CLI: the CLI calls the inner layer with max_tries=1 (one draw per
  call) and owns the budget (`--init-tries`, default 100), the
  per-draw audit lines, and the loud all-failed error. RNG discipline:
  candidates come from the chain's BridgeStan init RNG stream
  (model.make_rng(seed); seed+c multi-chain), exactly one one-draw
  initialize() per attempt, consumed strictly in order and BEFORE any
  warmup consumption (warmup runs on the separate std::mt19937_64{seed}
  stream); the first ACCEPTED draw is the final init-stream consumption.
  Because the inner loop always drew sequentially from the same stream,
  the accepted position is IDENTICAL to what the stock binary would
  have accepted for any run it started — the canary random cells verify
  this bit-for-bit.
- E5-hygiene threading (the "only if trivial" item — it was): masses()
  also records the raw init grad; `InitChainConfig` carries the optional
  (init_grad, init_logp) pair (5-arg ctor; 3-arg ctor unchanged for
  direct users); the `AdaptiveWalnuts` ctor seeds its W-23 endpoint
  cache (`cached_grad_`/`cached_logp_`) from it, so the FIRST warmup
  transition skips its start-position re-evaluation — the same
  (position, function) pair the mass seed already evaluated. Reused
  doubles change no arithmetic (W-23 precedent); effect = 1 fewer
  logp_grad call per chain (visible in the canary stanzas). Builder
  hygiene: recorded evals are invalidated by any later `positions()`
  call so a stale grad can never be threaded.

The library-only `api.hpp` reinit path uses the vector `masses()`
overload (no evaluation) and is unchanged. Library users can guard via
the new `InitConfig::init_logps()` accessor.

## Gate (a): bit-identity canary — PASS

Default single-chain runs (warmup=1000 draws=1000, CLI defaults, seeds
20260819+c), md5 of draw CSVs, exp/safe-adapt-defaults binary vs the
guard binary. 12 file-init cells (hier_2pl + lsat_model rep0 inits_w25
pf, radon_partially_pooled_noncentered rep0 inits_w36, chains 0-3) plus
4 random-init cells (radon, no --init-file):

| cell group            | chains | md5 identical | post warnings |
|-----------------------|--------|---------------|---------------|
| hier_2pl (inits_w25)  | 4      | 4/4           | 0             |
| lsat_model (inits_w25)| 4      | 4/4           | 0             |
| radon (inits_w36)     | 4      | 4/4           | 0             |
| radon (random init)   | 4      | 4/4           | 0             |
| **total**             | **16** | **16/16**     | **0**         |

Multi-chain paths exercised by smoke (not a pre-registered gate):
`--chains 2 --chain-exec serial` file-init (finite, rc=0), random-init
(rc=0), file-init -inf (guard fires naming chain 0 + the RESOLVED file
path), random-init exhaustion at --init 2.5 (100/100 chain-0 rejections
then the loud error, rc=134).

The E5 threading did not move a single draw (e.g. hier_2pl c0 md5
84571e… identical); its only trace is one fewer warmup logp_grad call
per chain — EVERY canary cell shows exactly calls−1 (hier_2pl c0:
20358 -> 20357, lsat c2: 17337 -> 17336, radon random c0: 33252 ->
33251). Random-init cells also landed bit-identically: first draws
were finite (0 retries), so the init-stream consumption and the
accepted position match the stock binary exactly (under the stock
binary these could have involved INVISIBLE inner-layer retries; the
md5 match proves none occurred on these cells).

## Gate (b): fail-fast on the two known -inf cells — PASS

CLI defaults, warmup=1000 draws=1000, inits_w36 chain_0.txt, single
chain. Before/after (walls measured this session, serialized):

| cell                   | seed    | stock binary (abort at freeze) | W-41 binary (pinned completion) | guard binary (fail fast) |
|------------------------|---------|--------------------------------|---------------------------------|--------------------------|
| kronecker_gp rep0 c0   | 20260819| rc=134, 2.97s, 31k+ calls      | rc=0, 8.22s, 31002 calls, pinned chain 0 (zero ESS) | **rc=134, 0.16s, 1 call** |
| lotka_volterra rep1 c0 | 20261819| rc=134, 0.80s                  | rc=0, 5.28s, 31000 calls, NaN draws chain 0 | **rc=134, 0.09s, 1 call** |

The guard's entire cost is the model load + the single masses() seed
evaluation. Error text (kronecker cell; lotka identical in form):

```
Error in logp_grad: log_density_gradient() failed with exception: Exception:
  lkj_corr_cholesky_lpdf: Random variable[27] is 0, but must be positive!
  (kronecker_gp.stan line 73)                      <- root cause, surfaced
WALNUTS ERROR (init guard): initial position has non-finite log probability:
  chain 0, init source: /…/inits_w36/kronecker_gp/rep0/chain_0.txt,
  logp at init: -inf
  A chain started at a non-finite-logp position cannot adapt: …
  Warmup was refused BEFORE starting; no budget was consumed. …
terminate called after throwing an instance of 'std::invalid_argument'
  what():  initial position has non-finite log probability: chain 0, …
```

lotka's root cause also surfaces (lognormal_lpdf: Location parameter[2]
is -nan — the ODE blows up at that init). Exit code 134 (SIGABRT via
uncaught invalid_argument — the CLI's existing init-file-error
convention); no CSV is written, no warmup stanza exists. Wall saved vs
the W-41 pinned completion: 8.06s/5.19s per invocation (~98% of the
budget), and unlike the pinned run there are no zero-ESS/NaN draws to
poison R-hat — the W-41 clamp remains as a second line of defense for
non-init degeneracies, but these cells now never reach it.

## Gate (c): random-init recovery — PASS

Seed trial on kronecker_gp (random init, warmup=100 samples=100): the
per-draw acceptance has a sharp cliff (radius 2.0: first draw accepted
for all 8 seeds tried; radius >= 2.5: 100/100 rejected for all seeds
tried — the loud all-failed error). Radius 2.2, seed 20260820: FIRST
DRAW REJECTED (logp=-inf), retry accepted.

- Recovery run (production settings, warmup=1000 draws=1000, seed
  20260820, --init 2.2): rc=0, completes; log line
  `WALNUTS WARNING (init guard): random init draw rejected (chain 0,
  seed 20260820, attempt 1/100, logp=-inf; inner: param_initialize()
  failed with exception: Initialization failed.); redrawing` — the
  chain starts from a finite-logp draw by construction.
- Determinism: two identical invocations -> identical retry counts
  (1/1) and md5-identical CSVs.
- Exhaustion (seed 20260819, --init 2.5, default tries): 100/100
  rejections then the loud
  `WALNUTS ERROR (init guard): random initialization failed: all 100
  draws have non-finite log probability …`, rc=134.

## Gate (d): no collateral — PASS

| cell                                      | md5       | post warnings |
|-------------------------------------------|-----------|---------------|
| eight_schools_centered rep1 c2 (20261821) | IDENTICAL | 0             |
| diamonds rep2 c1 (20262820)               | IDENTICAL | 0             |

## Repro

```
# fail-fast (guard binary) / pinned completion (W-41 binary):
OMP_NUM_THREADS=1 external/walnutpie_w42/build_w42/examples/stan_cli \
  bs_models_threads/model_kronecker_gp.so data/kronecker_gp.json \
  --seed 20260819 --init-file inits_w36/kronecker_gp/rep0/chain_0.txt \
  --output <out>.csv --warmup 1000 --samples 1000
# random-init recovery / exhaustion:
… model_kronecker_gp.so data/kronecker_gp.json --seed 20260820 --init 2.2 …
… model_kronecker_gp.so data/kronecker_gp.json --seed 20260819 --init 2.5 …
```

Gates: harness/run_w42.py (raw numbers results/w42_gates.json);
raw runs runs/w42/{pre,post,w41}/ (untracked).

## Notes and caveats

- The random-init rejection criterion is unchanged from Stan's (finite
  logp, jacobian=true — the same quantity the mass seed and the first
  transition use); W-42's contribution there is ownership, a knob, and
  audit lines, not a new rule.
- One evaluation is added per random-init ACCEPTED draw (the CLI
  verification call, outside the timing stanzas) and one per rejected
  draw; the file-init path adds zero. With the E5 threading (one fewer
  call at the first transition), a random-init chain's total eval count
  is unchanged vs stock when no retries fire.
- Exit code is 134 (uncaught invalid_argument -> SIGABRT), matching the
  CLI's existing behavior for unreadable/dimension-mismatched init
  files; the banner is printed to stderr before the throw so the
  message is loud regardless of the terminate handler.
