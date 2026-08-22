# Open ideas — documented for handoff (2026-08-23)

Framing note: walnutpie IS the sampler; `logp_grad` is the *Stan model*
function it evaluates (via bridgestan .so). So "speed up logp_grad" means
compiling the models better, not changing the sampler.

## A. logp_grad speedup via model-build flags  (W-23 candidate; artifacts prepared)

Measured context: logp_grad = 68–99.7% of walnutpie sampling wall (w17g
logs) → biggest per-call lever that does NOT touch sampler code.

- Prepared: `bs_models_o3/` (local only, NOT in repo) holds 5 models
  (blr, arma11, hier_2pl, kronecker_gp, diamonds) rebuilt with
  `-O3 -march=native -mtune=native` via
  `bridgestan.compile_model(make_args=['CXXFLAGS=...'])`.
- Pending: honest per-call comparison. Method: run stan_cli on both .so
  dirs, parse `time per call` from the sampling stanza (2nd) of each log.
  My quick parse regex grabbed the wrong group ("s" only) — logs live in
  /tmp/lg_{o2,o3}_<model>/log, likely lost across the move, so just re-run.
- CAUTION (from history): the cmdstan `-march=native` memory corruption was
  ROOT-CAUSED as mixed-build ABI (prebuilt main.o + PCH vs user CXXFLAGS —
  sims1253/cmdstan PR #1). The bridgestan path is self-contained (single
  make), so likely safe — but validate: (1) gradient parity spot-check
  vs default build, (2) expect draws to DIFFER bit-wise (FP vectorization
  changes arithmetic) → compare statistically (3 reps), never bit-identity.
- Also note: `stanc --Oexperimental` was already REJECTED (3/21 uncompilable
  + 1 silent miscompile, Phase 0). Flags are the remaining cheap lever.

## B. Mixing-difficulty diagnostic to gate early-exit warmup  (W-24 candidate)

Question: can a mid-warmup signal classify "mixes easy" vs "marginal" so
`--early-exit-warmup` (W-21) turns on automatically without the measured
marginal-class regressions (arma11 −33%, lsat −40%, hier_2pl −58% ESS)?

Evidence in hand (W-21/W-22):
- Step-size drift late in warmup separates hier_2pl/lsat (+170%) from
  easy models — BUT arma11 drifted only +12% and still lost 33% ESS, so
  step-drift alone is NOT sufficient.
- We already hold LABELED DATA: W-21 ran both arms (fixed vs early) on 12
  models × 3 reps — the label "early-exit hurt/helped" exists per model.

Proposed next step (zero new sampling compute for training): extract
features from the EXISTING w21 logs — {step drift (2-window), mass drift,
mean accept stat, mean trajectory depth, lp variance trend} — and fit a
trivial threshold rule against the W-21 outcome labels. If no single
feature separates arma11 from blr, the honest upgrade is a **pilot
sampling burst**: after candidate exit, take 50 draws, compute cross-chain
lag-1 autocorrelation of lp + short R-hat proxy; slow mixing ⇒ resume
warmup. Cost ~10% of sampling budget, preserves the 1.3–2.4× wall win
where mixing is easy. Natural home: the multi-chain `adapt()` controller
(it already has cross-chain machinery), not the CLI.

## C. Repo slimming (DONE for the export)

Removed: `models/*_model.so` stray binaries (~19MB), `results/profile/*/chain.csv`
raw profiling chains (callgrind dumps kept — ATLAS.md evidence). Export now
~57MB incl. .git. `results/ess/` (43MB jsons) KEPT: those back every cited
number. Local `runs/` (139GB) stays local — regenerable per BOOTSTRAP.md;
prune locally whenever disk demands (nothing cites raw chains long-term).

## D. Entrypoints on the new machine (clarified)

- `BOOTSTRAP.md` (repo) = environment/build setup only.
- `HANDOFF.md` (repo, new) = the fresh-session entrypoint: queued work items
  with gates, measurement protocol, gotchas ledger. Same content as the
  local skill `~/.agents/skills/handoff/` (which does NOT travel with the
  machine — install it on the new box by copying HANDOFF.md, or just read
  it from the repo).
- `WORKLOG.md` = append-only experiment ledger (W-1…W-22).
