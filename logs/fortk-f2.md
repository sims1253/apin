# F-2: hand-fused logp+grad C ceiling probe — eight_schools_noncentered + blr vs CmdStan/bridgestan .so

Started: 2026-08-26 11:19 UTC (resumed after machine reboot killed original run; workspace inherited with ground_truth.py never run).
Rules: CPU only, <=4 cores, timing pinned `taskset -c <cpu>`, 3 reps medians, no state-changing git, no -ffast-math, do not touch external/stanli or logs/stanli-*.
Gate: grad rel-L2 < 1e-9 AND logp rel < 1e-12 at all 64 ref points (never loosen). Perf gate (vs pending F-1 stanli number): >= 1.5x.

## Log

- 11:19 — Workspace verified: bench/fortk_fused/ground_truth.py present; data/eight_schools_noncentered.json + data/blr.json present; bs_models/model_eight_schools_noncentered.so + model_blr.so present. This log created.
- 11:24 — ground_truth.py run (2 API fixes: `m.stan_version`→`bridgestan.__version__`, `dim_unc`→`param_unc_num()`, `param_names(include_unc)`→`include_tp`). ref_eight_schools_noncentered.npz + ref_blr.npz written: 64 pts each, seed 20260826.
  - Layouts (unc): 8schools = [theta_trans.1..8, mu, tau_unc] dim 10; blr = [beta.1..5, sigma_unc] dim 6 (tau,sigma via exp transform, jacobian=True included).
- 11:31 — Provenance: harness/compile_bridgestan.py + harness/core_manifest.json confirm .so built from models/eight_schools_noncentered.stan + models/blr.stan via bridgestan 2.9.0 (Stan 2.39.0). No rebuild needed.
- 11:33 — CRITICAL formula subtlety, resolved empirically: python wrapper default propto=True.
  - 8schools (uses `~` statements): ref = constants-DROPPED form. Verified: formula lp = -0.5*sum(tt^2) - 0.5*sum(((y-tt*tau-mu)/sigma)^2) - mu^2/50 - log1p(tau^2/25) + t matches npz at 4.1e-16 rel logp, 2.4e-16 grad rel-L2 (numpy prototype).
  - blr (uses `target += normal_lpdf`): propto flag makes NO difference (measured True==False bit-for-bit); ref KEEPS all normal constants: lp = -sum(b^2)/200 - sigma^2/200 - 0.5*sum(z^2) - N*s + s - [0.5*(N+D+1)*log2pi + (D+1)*log10], N=100 D=5, X row-major [100][5]. Numpy prototype matches after adding constants (grad rel-L2 2.4e-16 throughout).
- 11:41 — C99 written + compiled: eight_schools_noncentered.c, blr.c (+ blr_data.h tables generated verbatim from data/blr.json), clang Ubuntu 14.0.0-1ubuntu1.1, `clang -std=c99 -O2 -march=native -fPIC -shared`. Exports: eight_schools_noncentered_logp_grad / blr_logp_grad.
- 11:44 — VERIFY GATE PASS (verify.py, all 64 pts):
  - eight_schools_noncentered: logp max rel 4.088e-16 (<1e-12 PASS), grad rel-L2 9.214e-17 (<1e-9 PASS)
  - blr: logp max rel 1.098e-15 (<1e-12 PASS), grad rel-L2 2.597e-16 (<1e-9 PASS)
  - blr first attempt failed (3.5e-4): constant 0.9189... is already log(sqrt(2pi)); had an extra factor 0.5 -> off by exactly 53*log(sqrt(2pi))=48.704. Fixed in blr.c, gate re-run. Never loosened.
  - Call-convention sanity: bs_log_density_gradient via ctypes reproduces npz p0 exactly (grad diff 0.0).

## Results (final)

### Provenance
- bs_models/model_{eight_schools_noncentered,blr}.so built by harness/compile_bridgestan.py from models/{eight_schools_noncentered,blr}.stan (harness/core_manifest.json), bridgestan 2.9.0 / Stan 2.39.0, ~/.bridgestan/bridgestan-2.9.0. No rebuild needed.
- Hand-fused C: bench/fortk_fused/{eight_schools_noncentered.c, blr.c, blr_data.h (tables verbatim from data/blr.json)}; clang Ubuntu 14.0.0-1ubuntu1.1; `clang -std=c99 -O2 -march=native -fPIC -shared` (no -ffast-math). No autodiff/Eigen/BLAS: hand-rolled loops + hand-written reverse-mode adjoints; blr's X*beta is a plain i/d loop (N=100, D=5, X row-major).

### Unconstrained layouts (from ref npz / param_unc_names)
- eight_schools_noncentered: [theta_trans.1..8, mu, tau_unc] (dim 10; tau = exp(tau_unc))
- blr: [beta.1..5, sigma_unc] (dim 6; sigma = exp(sigma_unc); X row-major [100][5])

### Verification (verify.py, all 64 seeded N(0,1) points, seed 20260826)
- GATE (logp rel < 1e-12, grad rel-L2 < 1e-9): PASS both, at machine precision:
  - eight_schools_noncentered: logp max rel 4.088e-16, grad rel-L2 9.214e-17
  - blr: logp max rel 1.098e-15, grad rel-L2 2.597e-16
- Semantics note (matters for any re-implementation): ref uses propto=True default. 8schools (`~` statements) -> constants dropped. blr (`target += normal_lpdf`) -> compiled model keeps normalization constants regardless of propto flag (verified True==False bit-identical): lp includes -[0.5*(N+D+1)*log2pi + (D+1)*log10].

### Benchmark (C-call vs C-ABI via ctypes, taskset -c 23, interleaved A/B/A/B, 3 reps; box quiet: cc1plus=0, make=0)
8schools ncalls=1.6M/block (fused side 2.16 s/rep), blr ncalls=1.3M/block (fused side 2.09 s/rep):

| model | rep | bridgestan us/call | fused us/call | ratio |
|---|---|---|---|---|
| eight_schools_nc | 1 | 1.915 | 0.756 | 2.53x |
| eight_schools_nc | 2 | 1.971 | 0.675 | 2.92x |
| eight_schools_nc | 3 | 1.851 | 0.643 | 2.88x |
| **eight_schools_nc** | **median** | **1.915** | **0.675** | **2.88x** |
| blr | 1 | 2.478 | 0.803 | 3.09x |
| blr | 2 | 2.503 | 0.820 | 3.05x |
| blr | 3 | 2.496 | 0.790 | 3.16x |
| **blr** | **median** | **2.496** | **0.803** | **3.09x** |

Preliminary 400k-call run agrees (2.98x / 3.00x). Python-wrapper crosscheck: 7.45 (8sch) / 7.81 (blr) us/call -> wrapper adds ~5.4 us/call (~3.9x/3.1x over direct C-ABI); kernel comparisons must use the C ABI.

ctypes 3-arg call overhead (noop_logp_grad, same signature, 2M calls, best of 3): 0.516 us/call. Both sides pay comparable (bridgestan's 7-arg call slightly more), so measured ratios are LOWER bounds; kernel-only estimates: 8schools ~ (1.915-0.52)/(0.675-0.52) ~ 8.9x, blr ~ (2.496-0.52)/(0.803-0.52) ~ 7.0x.

### Verdict vs F-2 gate
F-2 gate: >= 1.5x over the stanli interpreter. stanli baseline (F-1) still pending (build in flight at time of this run). vs bridgestan (CmdStan-compiled, C ABI direct): hand-fused C is 2.88x (eight_schools_nc) / 3.09x (blr) per measured C-call protocol, and ~7-9x kernel-only after ctypes overhead. F-2 passes the 1.5x-over-stanli gate iff stanli's logp_grad on these models is < ~1.9x faster than bridgestan (0.675/1.5 = 0.45 us floor). If stanli delivers its claimed ~2.9x-over-CmdStan on these small models, it lands at ~0.65-0.86 us/call — statistically indistinguishable from the hand-fused kernels under the ctypes protocol, and the gate would FAIL as pre-registered (a written negative result: the interpreter's precompiled kernels already sit at the hand-fused C-call ceiling for models this small; the fused advantage over stanli would then be protocol-overhead-sized, not kernel-sized). Decision deferred to F-1 numbers; both this file's numbers and the harness (bench/fortk_fused/{verify.py,bench.py}) are reusable for that comparison.

Artifacts: bench/fortk_fused/{ground_truth.py, ref_*.npz, eight_schools_noncentered.c, blr.c, blr_data.h, lib_esnc.so, lib_blr.so, noop.c, verify.py, bench.py}.
