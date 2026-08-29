# F-8 phase 1 — north-star ESS/s campaign (pre-registered)

Status: BOOTING — reading protocol context (WORKLOG F-8 pre-registered / F-4b VERDICT / F-8 AMENDMENT, logs/fortk-f4b.md, logs/fortk-f6.md).

Plan (from registration):
- 4 arms: (A) CmdStan default NUTS (cmdstan-2.39.0 via cmdstanpy), (B) stanli UNFUSED (build-rel, 13:58 vintage), (C) stanli FUSED NUTS (pinned worktree /tmp/stanli-b7a3fd5, build-f8/fortk_t1r), (D) stanli FUSED WALNUTS (if reachable via tool).
- 6 models (small/dispatch-bound): eight_schools_noncentered, eight_schools_centered, blr, pilots, kidscore_momiq, logmesquite_logvash.
- 4 chains, 1000+1000, seeds 20260826 + 1000*rep + c, 3 reps, medians. Arms interleaved per rep.
- Prep: add --seed/--chain-id to fortk_t1r in pinned worktree (plumbing commit on detached worktree only).

## Log

- (boot) log created; read WORKLOG F-8 pre-reg + F-4b VERDICT + F-8 AMENDMENT,
  logs/fortk-f4b.md (census: fused esnc walnuts 236k draws/s vs nuts 84k;
  grad 6.7/14% of wall → sampler-bound; unfused-walnuts arm omitted per
  amendment), logs/fortk-f6.md (kernel speedups esnc 8.0x / esc 7.2x /
  logmesquite 4.4x / blr 4.0x / pilots 2.9x / kidscore 2.8x).
- Verified present: 6 model+data pairs; pinned worktree /tmp/stanli-b7a3fd5
  @ b7a3fd5 detached, clean; build-f8/fortk_t1r; external/stanli build-rel
  binaries (13:58 vintage, statically linked — no libstanli.so path issue);
  ~/.cmdstan/cmdstan-2.39.0; cmdstanpy 1.3.0; R posterior.
- ARM D reachability: b7a3fd5's tool --sample is nuts-only (no --census;
  that's 0243aad in the F-7-owned main worktree — MUST NOT measure its
  binary). The runtime API run_walnuts (runtime/include/stanli/walnuts.hpp)
  EXISTS at b7a3fd5 → added `--sampler walnuts` to the pinned tool: the same
  path the F-4b census drove (tool → run_walnuts over region-rewritten
  graph). Arm D NOT dropped.
- PREP (pinned worktree only, commit d4801b5 on the detached HEAD, never to
  be merged, explicit staging, --sample path only): --seed N, --chain-id C,
  --sampler nuts|walnuts; SAMPLE_WALL line timing the run_nuts calls
  (sampler phase only); fused (ex1) draws written as CmdStan-ish CSV
  (7 stat cols + constrained columns via cm.views). Defaults reproduce the
  old hardcoded seed=20260826/chain=1/nuts exactly. Bug found+fixed during
  smoke: constraining via ex1 left tau's view slot stale (constrain op
  internal to the region) → constrain through ex0 (unfused, computes every
  slot; F-6-verified same math). Cross-check: tool CSV row 1 for
  seed=20260826/chain=1 is IDENTICAL to stanli_run's same-stream row
  (bit-equal draws through the fused sampler).
- Smoke: two seeds → different draws (protocol check); all 6 models carve,
  VERIFY PASS, sample through the tool (pilots 3 regions, others 1).
- Column naming: CmdStan writes theta_trans[1]→ mapped to stanli's
  theta_trans.1; CmdStan has params+transformed, stanli_run params+
  transformed (write_array), tool params+live-out views. ESS column basis =
  intersection across all 4 arms per model (esnc: 10 = theta_trans.1-8, mu,
  tau; eta/theta not in every arm's output — stated, consistent across arms).
- CONVENTIONS (picked + stated): wall primary = max-chain SAMPLER wall
  (A: CmdStan per-chain "Elapsed Time (Total)" from CSV comments, excludes
  compile; B: chain proc wall minus pipeline0 where pipeline0 = median of 3
  × `--warmup 0 --samples 0` runs per model — DERIVED, flagged; C/D: tool's
  SAMPLE_WALL exec1_s). Also recorded: proc walls (A: cmdstanpy sample()
  call incl. readback; B/C/D: max chain process wall). ESS_bulk/s = geomean
  of per-param ess_bulk (pooled 4 chains, harness/ess.R) / max-chain sampler
  wall; min-ESS/s also reported. ESS/draw = same ESS / 4000.
- Seeds/streams: pre-registered formula 20260826+1000*rep+c with chain_id=1
  on stanli arms (stream = seed+1, CmdStan's create_rng(seed,id) formula);
  arm A uses seed=base+1000*rep with CmdStan chain_id 1..4 → identical
  streams base+1..base+4 per rep. 4 chains × (1000 warmup + 1000 draws).
- Runner: bench/fortk_f8/run_f8.py — model-major arm-interleaved within rep
  (A,B,C,D per model), 4 concurrent single-chain processes for B/C/D
  (cmdstanpy parallel_chains=4 for A), load+cc1plus recorded per rep,
  canonical ess dirs per model/arm/rep, raw outputs under
  bench/fortk_f8/<model>/rep<r>/{A_cmdstan,B_unfused,C_fused_nuts,
  D_fused_walnuts}/chain<c>/. Region cache shared+prewarmed (compile-once
  doctrine). Mini validation (1 model, 200+200, 3 reps) passed end-to-end
  incl. ess.R.
- (campaign) ran 18:45-18:48 (3 reps, model-major, arms adjacent per model;
  loads 2.23/4.40/4.44, cc1plus=0 at every rep start — no F-7 build overlap).
  pipeline0 (B's fixed-cost subtrahend, median of 3): esnc .0214, esc .0202,
  blr .0222, pilots .0285, kidscore .0235, logmesq .0286 s.
- (analysis bug, found + fixed) my runner's filter_canonical wrote every
  filtered chain to chain_0.csv (per-chain key hardcoded 0) → each ess dir had
  chain_0 = copy of chain_3 and unfiltered 1-3. Walls/div/td in
  results_raw.json unaffected (read pre-filter); ALL ESS numbers recomputed
  after rebuilding canonical CSVs from the raw per-chain outputs
  (bench/fortk_f8/rebuild_canonical.py; verified 0 identical-chain pairs).
  The initial "two identical walnuts chains" scare that exposed it was this
  bug, NOT the tool: raw walnuts CSVs for seeds 20260826/20260829 differ.

## FINAL TABLE (medians of 3 reps; wall = max-chain SAMPLER wall; ESS via
harness/ess.R pooled over 4 chains; div/1k = divergences per 1000 draws
summed over 4 chains; D's div/td structurally n/a — walnuts stats are NaN
by design; proc wall = arm A cmdstanpy call / B/C-D max chain process wall)

| model | arm | wall_s | ESS_bulk/s | vs A | ESS/draw | div/1k | td-hits/4k | rhat_max |
|---|---|---|---|---|---|---|---|---|
| esnc | A cmdstan nuts | 0.0320 | 141,603 | 1.00x | 1.090 | 0 | 0 | 1.002 |
| esnc | B unfused nuts | 0.0288 | 135,032 | 0.95x | 1.007 | 0 | 0 | 1.002 |
| esnc | C fused nuts | 0.0122 | 329,847 | 2.33x | 0.999 | 0 | 0 | 1.003 |
| esnc | D fused walnuts | 0.0047 | 696,974 | 4.92x | 0.812 | n/a | n/a | 1.003 |
| esc | A | 0.0480 | 3,709 | 1.00x | 0.044 | 43 | 0 | 1.079 |
| esc | B | 0.0483 | 17,436 | 4.70x | 0.211 | 14 | 0 | 1.019 |
| esc | C | 0.0314 | 19,213 | 5.18x | 0.171 | 14 | 0 | 1.029 |
| esc | D | 0.0118 | 24,269 | 6.54x | 0.075 | n/a | n/a | 1.084 |
| blr | A | 0.0620 | 21,983 | 1.00x | 0.341 | 0 | 0 | 1.006 |
| blr | B | 0.0476 | 33,006 | 1.50x | 0.394 | 0 | 0 | 1.004 |
| blr | C | 0.0242 | 60,787 | 2.77x | 0.349 | 0 | 0 | 1.004 |
| blr | D | 0.0353 | 176 | 0.01x | 0.003 | n/a | n/a | 4.32 NON-CONV |
| pilots | A | 1.2520 | 32 | 1.00x | 0.010 | 180 | 653 | 1.315 |
| pilots | B | 1.2812 | 69 | 2.14x | 0.022 | 146 | 398 | 1.050 |
| pilots | C | 0.6142 | 96 | 2.99x | 0.018 | 139 | 310 | 1.069 |
| pilots | D | 0.0245 | 565 | 17.6x* | 0.003 | n/a | n/a | 1.81 NON-CONV |
| kidscore | A | 0.3710 | 3,490 | 1.00x | 0.324 | 0 | 0 | 1.003 |
| kidscore | B | 0.2594 | 5,226 | 1.50x | 0.337 | 0 | 0 | 1.003 |
| kidscore | C | 0.1076 | 13,177 | 3.78x | 0.348 | 0 | 0 | 1.003 |
| kidscore | D | 0.1162 | 46 | 0.01x | 0.002 | n/a | n/a | 1.62 NON-CONV |
| logmesq | A | 0.2130 | 9,133 | 1.00x | 0.454 | 0 | 0 | 1.002 |
| logmesq | B | 0.1551 | 11,751 | 1.29x | 0.472 | 0 | 0 | 1.002 |
| logmesq | C | 0.0824 | 23,634 | 2.59x | 0.484 | 0 | 0 | 1.002 |
| logmesq | D | 0.0167 | 24,879 | 2.72x | 0.104 | n/a | n/a | 1.017 |

| AGGREGATE (geomean over 6 models) | ESS_bulk/s | vs A | geomean wall ratio vs A | geomean ESS/draw |
|---|---|---|---|---|
| A cmdstan nuts | 4,772 | 1.00x | 1.00x | 0.169 |
| B stanli unfused nuts | 8,302 | 1.74x | 0.84x | 0.258 |
| C stanli fused nuts | 15,022 | 3.15x | 0.42x | 0.238 |
| D stanli fused walnuts | 3,524 | 0.74x | 0.15x | 0.022 |

*pilots D's 17.6x is a MIRAGE (rhat 1.81, ESS 12 — its 24 ms wall is fast
because chains are stuck, not because it sampled well).

## Cross-arm draw comparability (protocol check, not a gate)

- Posterior sanity (esnc rep0, pooled 4 chains, mu/tau): A 4.402±3.31/3.61±3.17,
  B 4.415±3.30/3.59±3.11, C 4.398±3.28/3.59±3.31, D 4.350±3.31/3.58±3.21 —
  all four arms agree; end-to-end draw pipelines (incl. walnuts + ex0
  constraining in the tool) validated.
- Fused vs unfused nuts, ESS_bulk geomean C/B per model: esnc 0.99, esc 0.81,
  blr 0.89, pilots 0.82, kidscore 1.03, logmesq 1.03 — no systematic ESS loss
  from fusion (esc/pilots are tiny-ESS noisy models). In-tool same-seed
  checks at full 1000+1000 (blr): worst_z 1.2-2.4 over seeds {1,7,42},
  bitwise=NO (last-bit wobble amplification, expected).
- esc anomaly (honest note): CmdStan's esc chains diverge 43/1000 median
  (reps 43/9.5/65) vs stanli's 14 → CmdStan esc ESS 174 vs stanli 842/682.
  Same nominal algorithm/streams; the difference is adaptation internals
  (2.39 vs stanli's reimplementation). Not smoothed over — reported.

## HONEST READ

Arm C (stanli fused NUTS) is the phase-1 winner everywhere it converges:
ESS_bulk/s 2.3-3.8x CmdStan on the five well-behaved models (esnc 330k,
esc 19k, blr 61k, kidscore 13k, logmesq 24k) and 3.0x even on pathological
pilots, at ESS/draw parity with CmdStan (0.24 vs 0.17 geomean — no
statistical loss for the speed). Unfused stanli already beats CmdStan 1.5-
1.7x on the class (sampler-loop efficiency, not kernels), and fusion adds
another ~1.8x on top — consistent with F-6's kernel ratios (4-8x) being
diluted by the F-4b finding that fused esnc-class sampling is 85-95%
bookkeeping: the kernel win is real but the sampler amortizes it.

Fused WALNUTS does NOT hold its census promise at ESS/s. The census (draws/s)
said esnc 2.8x over fused nuts; at ESS/s it is 2.1x on esnc and wins logmesq
(1.05x vs C) and esc — but on blr and kidscore its chains silently stick
(ESS/draw 0.003/0.002, rhat 1.6-4.3; blr's four chains park at sigma 4.8/
2.2/1.7/0.7), and pilots' apparent 17.6x is non-converged rhat-1.8 noise.
Worse, walnuts reports no divergence/treedepth diagnostics (NaN by design),
so these failures are INVISIBLE to its own output — exactly the failure mode
the ESS/draw sanity metric was pre-registered to catch. Aggregate D 0.74x
CmdStan. The esnc-class sampler-bound conclusion stands (fusion moves the
bottleneck to bookkeeping; walnuts' 3x leaner loop is real — 0.0047s walls),
but end-to-end vs CmdStan, default-settings walnuts is not yet a usable
sampler on this class: its warmup (Adam step-size) fails to find mixing
steps on 3 of 6 models. Fixing that is walnutpie-lane work, as F-4b predicted.

## Deviations / notes

- Arm D NOT dropped: walnuts was not CLI-reachable at pinned b7a3fd5 (the
  --census commit 0243aad lives in the F-7-owned main worktree whose binary
  must not be measured), so `--sampler walnuts` was added to the pinned tool
  driving the same runtime API (run_walnuts) the census used.
- Plumbing commit d4801b5 on the detached HEAD of /tmp/stanli-b7a3fd5 only
  (never merge; --sample path only; defaults reproduce old behavior).
- B's sampler wall is DERIVED (proc wall − pipeline0, pipeline0 measured
  with --warmup 0 --samples 0); A's is CmdStan's own per-chain Elapsed Time
  (Total); C/D's is the tool's timed run_nuts window. C/D proc walls
  (~4.5-9.7s) are dominated by the tool's verify+bench+statistical-fallback
  self-checks (left ON per the registered CLI); sampler walls exclude them.
- Arm A chains share the rep seed and split streams via CmdStan chain_id
  1..4; arms B/C/D use the registered per-chain seeds with chain_id=1 —
  both give identical streams base+1..base+4 per rep (create_rng(seed,id)).
- Raw: bench/fortk_f8/{<model>/rep<r>/<arm>/chain<c>/, results_raw.json,
  analysis.json, campaign.out, pipeline0.json, run_f8.py, analyze_f8.py,
  rebuild_canonical.py}.
