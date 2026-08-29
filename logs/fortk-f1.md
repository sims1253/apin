# F-1: stanli (interpreter, Release) vs bridgestan logp_grad — 5 models

Pre-registered in WORKLOG "fortk lane opened" (2026-08-26 ~10:42).
Gate resolves F-2's deferred decision: F-2 gate passes iff stanli < 1.9x vs
bridgestan on eight_schools_noncentered AND blr.

Protocol: C-ABI-vs-C-ABI via ctypes both arms (matches F-2, ~0.516 µs/call
ctypes overhead measured there), taskset-pinned fixed low core (0-3, away
from core 23), 3 reps, interleaved A/B/A/B per rep, >=2s per rep per arm,
medians. Correctness anchor first: >=8 seeded points (seed 20260826, N(0,1)),
grad rel-L2 <= 1e-9 per model before any timing. Cross-check via
external/stanli/build-rel/bench_grad per model.

Models: eight_schools_noncentered, blr, radon_pp (radon_partially_pooled_
noncentered), hier_2pl, kronecker_gp.

## Setup log

## Setup facts
- stanli lib: external/stanli/build-rel/libstanli.so, build_id=abi1-85a8f11f3c4a-Linux-x86_64-threads, abi=1, embedded_stanc=0 (so MIR via external/stanli/python/stanli/_bin/stanc --O1 --debug-optimized-mir subprocess -> stanli_model_new), exact_lp=1.
- bridgestan: 2.9.0 .so in bs_models/, bs_log_density_gradient(handle, propto=True, jacobian=True, ...) — identical call shape to F-2's bench.py.
- Env: STAN_NUM_THREADS=1, OMP_NUM_THREADS=1; taskset -c 2 (core 2 of 0-3; away from core 23). Load avg at start: 0.35.

## Correctness anchor (8 seeded points, seed 20260826, per-model fresh rng standard_normal((8,dim)), same generator order as F-2 ground_truth.py)

| model | dim_unc | n_ok | max grad rel-L2 | max abs dlp | verdict |
|---|---|---|---|---|---|
| eight_schools_noncentered | 10 | 8/8 | 0.0 | 0.0 | PASS |
| blr | 6 | 8/8 | 2.17e-16 | 4.7e-10 | PASS |
| radon_pp | 389 | 8/8 | 1.76e-14 | 3.5e-9 | PASS |
| hier_2pl | 669 | 8/8 | 0.0 | 7.3e-12 | PASS |
| kronecker_gp | 438 | 8/8 | 2.74e-2 | 1.9e-10 | N/A — degenerate spectrum (see below) |

### kronecker_gp anchor investigation (bench/f1/diag_kronecker.py)
- lp agrees to <=1.9e-10 on every point; sigma1 gradient coord agrees to FD 8e-9;
  disagreements concentrate on var1/L blocks (rel-L2 6e-4..6e-2) that flow through
  eigenvectors_sym/eigenvalues_sym adjoints.
- FD referee (central, h=1e-5/1e-6, stable in h to 8 digits): FD disagrees with
  BOTH bridgestan and stanli by ~1% on eigen-affected coords (e.g. L1: fd=21.135,
  bs=21.543, sl=21.068; L45: fd=-0.878, bs=-1.049, sl=-0.291).
- Mechanism: Sigma1 = var1*exp(xd*bw1) + 1e-5 jitter; the jitter floors the kernel's
  tiny eigenvalues so 16-18 of 30 sit within machine-level gaps (min RELATIVE gap
  7e-19..2.6e-18 at the seeded points). Eigenvector adjoints contain 1/(li-lj) and
  are basis-dependent in exactly-degenerate subspaces; ulp-level primal differences
  (different build paths) rotate that basis. lp is rotation-invariant => matches;
  gradients cannot. stanli mirrors stan/math/rev/fun/eigenvectors_sym.hpp
  "expression for expression" (runtime/kernels/matrix_fns.cpp:702-749) — same
  formula, same Eigen::SelfAdjointEigenSolver. Conclusion: NOT a harness error and
  not attributable to either implementation; the 1e-9 anchor is unattainable for
  ANY implementation pair on this model at these points (structural). Recorded;
  timing proceeds (kernel code path is what is timed), correctness flagged N/A.
- The two GATE models (eight_schools_nc, blr) anchor at 0 / 2.2e-16 — gate
  evaluation is unaffected.

## Timing attempt 1 (core 2, pre-fix: stanli arm had one per-call byref alloc; noop control mis-measured with per-call casts)
- eight_schools_noncentered: bs 1.796, stanli 1.185 us/call, 1.524x (spread 3.3%, ncalls 913518)
- blr: bs 2.365, stanli 1.590, 1.524x (3.6%, 666350)
- radon_pp: bs 339.193, stanli 62.534, 5.424x (3.1%, 15930)
- hier_2pl: bs 673.765, stanli 513.777, 1.311x (spread 6.8% > 5% -> rerun required)
- kronecker_gp: bs 310.079, stanli 321.324, 0.957x (1.6%, 3359)
- noop control printed 1.703 us/call but was INVALID (casts inside loop); fixed harness
  (pre-converted lp pointer for stanli arm, F-2-convention noop) rerun = attempt 2 (final).

## Timing attempt 2 (FIXED harness: pre-converted lp pointer on stanli arm — zero per-call
## Python allocs on both arms, F-2 convention; core 2; STAN_NUM_THREADS=1 OMP_NUM_THREADS=1)

noop ctypes control: 0.479 us/call (F-2 measured 0.516 — protocol comparable).
Per-arm per-rep totals >= 2 s on both arms, all models (rep-side prints x2).

| model | dim | ncalls | bs us/call | stanli us/call | stanli_speed | rep spread |
|---|---|---|---|---|---|---|
| eight_schools_noncentered | 10 | 933028 | 1.758 | 1.097 | 1.602x | 2.7% |
| blr | 6 | 649999 | 2.371 | 1.446 | 1.612x | 3.5% |
| radon_pp | 389 | 16112 | 333.674 | 63.241 | 5.304x | 2.5% |
| hier_2pl | 669 | 1870 | 662.396 | 515.090 | 1.281x | 2.4% |
| kronecker_gp | 438 | 3270 | 303.486 | 305.683 | 0.993x | 20.3% -> rerun |

## Timing attempt 3 (kronecker_gp + hier_2pl rerun, same core 2, other agent still on core 6)

| model | bs us/call | stanli us/call | stanli_speed | rep spread |
|---|---|---|---|---|
| kronecker_gp | 307.472 | 323.458 | 0.958x (RECORDED) | 1.3% (attempt 2: 0.993x, 20.3%) |
| hier_2pl | 651.489 | 521.234 | 1.250x (attempt 3; attempts: 1.311 pre-fix, 1.281, 1.250) | 3.3% |

Recorded finals = attempt 2 for the three clean models, attempt 3 for kronecker_gp
(quiet rerun after >5% disagreement), hier_2pl range 1.25-1.31x across attempts.

## bench_grad cross-check (external/stanli/build-rel/bench_grad, in-C loop, no ctypes,
## its own fixed point; MIRs in bench/f1/mir/; core 2)

| model | bench_grad us/call | my ctypes stanli us/call |
|---|---|---|
| eight_schools_noncentered | 0.283 | 1.097 (ctypes tax 0.479 dominates) |
| blr | 0.597 | 1.446 |
| radon_pp | 62.534 | 63.241 (0.7% apart — protocol-identical) |
| hier_2pl | 494.546 | 515.090 (4% — different eval point) |
| kronecker_gp | 278.995 | 323.458 (14% — different eval point/eigen conditioning) |

No harness artifact: large models agree closely; small models are overhead-dominated
exactly as F-2 found.

## F-1 RESULTS (recorded finals)

| model | anchor max grad rel-L2 | bs us/call | stanli us/call | stanli_speed |
|---|---|---|---|---|
| eight_schools_noncentered | 0.0 | 1.758 | 1.097 | 1.602x |
| blr | 2.2e-16 | 2.371 | 1.446 | 1.612x |
| radon_pp | 1.8e-14 | 333.674 | 63.241 | 5.304x |
| hier_2pl | 0.0 | 651.489 | 521.234 | 1.250x (range 1.25-1.31) |
| kronecker_gp | N/A (2.7e-2, structural degeneracy, see anchor section) | 307.472 | 323.458 | 0.958x |

## F-2 GATE (pre-registered decision rule, applied mechanically)

Rule: F-2's deferred >=1.5x-over-stanli gate PASSES iff stanli < 1.9x vs bridgestan
on eight_schools_noncentered AND blr.
- eight_schools_noncentered: stanli_speed = 1.602x < 1.9x
- blr: stanli_speed = 1.612x < 1.9x

**F-2 GATE: PASS**

Direct cross-check of the same rule: F-2 fused (0.675 / 0.803 us/call recorded) vs
F-1 stanli (1.097 / 1.446) = fused 1.62x / 1.80x faster than the stanli interpreter
(both >= 1.5x), on near-identical bridgestan baselines (1.915/1.758 and 2.496/2.371
across sessions). The interpreter is NOT at the fused ceiling for this size class.

Interpretation notes (no gate attached):
- stanli's headline ~2.9x median does NOT reproduce on this box for 4/5 models;
  only radon_pp (5.3x) exceeds it. The two tiny F-2 models sit at ~1.6x, where the
  0.48 us ctypes floor is ~44% of the stanli arm's 1.1-1.4 us (kernel-only estimates:
  stanli ~0.62 us vs F-2 fused ~0.16 us on 8schools => kernel-level fused/stanli ~3.9x;
  F-2b's C-loop protocol will pin this properly).
- kronecker_gp: stanli is a WASH (0.96x, slightly slower). Both sides spend their time
  in the same 30x30 eigendecompositions + matrix kernels; nothing interpreter-specific
  dominates. Also the only model where the 1e-9 gradient anchor is structurally
  unattainable (machine-degenerate eigenvalues from the +1e-5 jitter floor).
- hier_2pl only 1.25-1.31x despite 669 params — worth an F-3-tier look before assuming
  uniform interpreter headroom across model classes.

Artifacts: bench/f1/{anchor.py, diag_kronecker.py, bench.py, anchor_results.json,
bench_results_final.json, mir/*.sexp}. bench_results.json holds only the last
invocation (2-model rerun); bench_results_final.json is the merged record.
