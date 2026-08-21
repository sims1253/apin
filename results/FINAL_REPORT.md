# nindan — final consolidated report (Phase 0 → W-10)

Metric: wall-clock to reliable posterior on CORE_SET (21 posteriordb models,
4 chains, 1000+1000, median of 3 reps, ESS = rank-normalized ESS_bulk).
Machine: Ryzen 9 5900X (AVX2 only), ≤4 cores throughout.

## 1. Baseline atlas (where Stan wall-clock goes)

| finding | evidence |
|---|---|
| cmdstan services carry 2.1–5.0× more instructions per gradient than a minimal bridgestan driver on identical math | callgrind, 4 models, parity-checked gradients |
| model-gradient = 76–97% of steady wall on data-heavy models; small/stiff models are kernel-bound (pilots: memcpy 21%) | profile() + callgrind |
| validity checks ≤ 2.2% (folklore rejected); LL misses ≈ 0 (no DRAM wall; L1/L2 latency only) | callgrind cache sim |
| -march=native: NO geomean win (1.13× slower, diamonds-only gain) — and the widely-reported crashes are cmdstan's mixed-build ABI bug, not compilers | validated fix in sims1253/cmdstan PR #1 |
| --Oexperimental: 3/21 uncompilable + 1 silent miscompile; no QA win | Phase 0 |
| nutpie "2×": real per-gradient win (2.6×) but quality-adjusted wash (0.98× ESS/s) | Phase 0 |

## 2. walnutpie adaptation engineering (the main arc)

Failure inventory at session start: 17/21 models R-hat>1.01 (chains frozen at init).

Mechanism chain (each step measured, PR #4 = the full saga):
1. **Freeze-from-init**: gradient-seeded mass ≈ 1e6 → inv_mass 1e-6 throttles all
   motion; no step-size search → every span divergent → transitions return the
   init point unchanged (sd ~1e-14). 6× warmup does not help (absorbing state).
2. **Fix layer 1 (init robustness)**: mass clamp + Stan-style step heuristic +
   typical-set (Pathfinder) inits via --init-file → freeze class resolved
   (blr 4→406 ESS, arma11 3→1381, lsat 7→736).
3. **Fix layer 2 (estimation discipline)**: observation batching (stride 50)
   halves failures 17→9; Fisher-HMC window chopping (memoryless) adds blr
   201→401, kronecker rhat 1.15→1.05. Mass shrinkage, clipping, drift-guard,
   power-mean combination, stall resets: all negative, all documented.
4. **Budget sweep**: no crossover — stock@4000 (15 bad, ESS 93) < full@1000
   (8 bad, 317). The fixes change the asymptote (~4× budget equivalence).
5. **Low-rank Fisher metric**: estimator + exact O(Dr) operator (property-tested:
   reversibility 3e-17, volume 9e-16, exact-Cholesky momentum sampling) + two
   integration bugs found by analytic-target testing (rejection under wrong
   Hamiltonian; metric dropped at freeze) + concentration-based auto-screening.
   W-9/W-10: full>fold 1.21×; screening protects funnels (8schools 1.11×) and
   activates wins (bym2 3.46×); aggregate within noise of diag — optional flag.
6. **Cross-chain mode diagnostic** (log-mass dispersion) shipped as the hook for
   mode-aware reinit; reinit-draw screening evidence recorded.

**Final config: batch-50 + Pathfinder inits + mass clamp + step heuristic + chop-50.**
R-hat failures 17/21 → 8/21 (cmdstan: 4), geo ESS_min 26 → 294 (11×).

## 3. Optimizer research (passes 1+2, with hermes/GLM-5.3)

Muon/Aurora/OKLS structurally inapplicable (scalar + diagonal state; every
production stack routes 1-D to AdamW; flower's own Aurora screen: "do not
deploy"). Transferable: zero-staleness (shaped chopping), closed-loop lr
(AdaGrad-Norm adapter), anti-windup (control-theoretic, rescues collapse),
PI-controller framing. walnutpie's mass rule is Fisher-divergence-optimal
(arXiv 2603.18845 Thm 2.2) — now cited, and its window discipline adopted.
Reports: external/research_optimizer_{sota,pass2}.md + docs/notes in fork.

## 4. Stan-source patches

- sims1253/cmdstan #1: mixed-build corruption guard (validated 3/3 on 2.39.0).
- patches/stan-2a1-rho-hoist.patch: bit-identical, no measurable win (negative
  result; the real 2a needs coordinated z_propose/p_sharp surgery).
- sims1253/walnutpie #1–#5 (+ 8 evidence comments): pluggable optimizers,
  hardening (clip = negative), shrinkage (negative), init robustness (the saga),
  research notes.

## 5. What remains open

- cmdstan per-gradient gap (2.1–5×): kernel-loop copy/alloc surgery (2a, full set).
- walnutpie funnel class (8 vs cmdstan 4 failures): mode-aware warmup via the
  dispersion hook + multi-path init screening.
- ESS/grad 0.06× vs cmdstan even when mixed: sampler-level question (WALNUTS'
  error-cap discipline trades trajectory reuse) — flagged for the Flatiron team.
