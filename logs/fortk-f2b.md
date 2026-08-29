# F-2b: size-class extension of the hand-fused logp+grad probe — diamonds + hier_2pl

Started: 2026-08-26. Pre-registration: WORKLOG.md "F-2b pre-registered BEFORE running".
Rules: CPU only, <=4 cores, taskset-pinned timing, 3 reps medians, A/B/A/B interleaved,
no state-changing git, no -ffast-math, do not touch external/stanli or logs/stanli-*.
Gate: logp rel < 1e-12 AND grad rel-L2 < 1e-9 at all 64 seeded points (seed 20260826,
jacobian=True). Never loosen.
Hypotheses (pre-registered): under C-loop protocol diamonds >=4x vs bridgestan,
hier_2pl 2-4x; diamonds <2x => bandwidth-fusion thesis in doubt, F-3 scope narrows.

## Log

- 12:05 — Workspace verified. Predecessor artifacts present in bench/fortk_fused/
  (ground_truth.py, verify.py, bench.py, eight_schools_noncentered.c, blr.c, blr_data.h,
  ref npz, .so libs). bs_models/model_diamonds.so + model_hier_2pl.so present.
- 12:06 — Provenance confirmed via harness/core_manifest.json:
  - diamonds: posterior "diamonds-diamonds" (posteriordb), models/diamonds.stan
    (brms 2.10.0 generated), data/diamonds.json.
  - hier_2pl: posterior "sat-hier_2pl" (posteriordb), models/hier_2pl.stan,
    data/hier_2pl.json.
  Both .so built by harness/compile_bridgestan.py (bridgestan 2.9.0 / Stan 2.39.0,
  per F-2 verification of the same pipeline). No rebuild needed.
- 12:15 — Coordinator notice: stanli release build (cmake -j4, 4 compile jobs, 24-core box)
  running during this window. Per instruction: verification/C-writing proceed; timing on
  pinned cores far from the build jobs is acceptable, will note in benchmark section and
  re-run if 3-rep spread >5% (both attempts recorded).
- 12:20 — ground_truth_f2b.py run. ref_diamonds.npz (dim 26) + ref_hier_2pl.npz (dim 669)
  written, 64 pts, seed 20260826, jacobian=True.
  - Layouts (unc):
    - diamonds: [b.1..b.24, Intercept, sigma_unc] (Kc=24; sigma=exp(sigma_unc)).
    - hier_2pl: [theta.1..600, xi1.1..32, xi2.1..32, mu.1, mu.2, tau.1_unc, tau.2_unc,
      L_Omega.1_unc] (tau=exp, L_Omega 2x2 cholesky-corr -> r=tanh(z)).
  - propto probe p0: diamonds True==False bit-identical (all target += -> constants KEPT,
    matches F-2 blr behavior). hier_2pl propto=False − propto=True = −559.326 (mixed model:
    `~` statements drop constants, target += multi_normal keeps them).
- 12:25 — Exact formula semantics read from the vendored stan math source
  (~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math, same Stan 2.39.0 the .so were built with):
  - lkj_corr_cholesky_lpdf, K=2, eta=4: parameter-dependent part = (2*eta-2)*log(L22) =
    6*log(L22) = 3*log(1-r^2); do_lkj_constant dropped under propto (it depends only on eta).
  - cholesky_corr_constrain, K=2: r = tanh(z); the 0.5*log1m(sum_sqs) term fires only in the
    inner j-loop (empty for row 1), so the ONLY transform jacobian is corr_constrain's
    log(1-tanh^2 z). lkj+jacobian = 4*log(1-r^2), d/dz = -8r.
  - student_t_lpdf: lgamma((nu+1)/2)-lgamma(nu/2)-0.5*log(nu*pi)-log(sigma)
    -(nu+1)/2*log1p(z^2/nu).
  - normal_id_glm_lpdf (scalar sigma): -0.5*N*log(2pi) - N*log(sigma) - 0.5*sum(z^2).
  - multi_normal_cholesky_lpdf (d=2, I obs): -I*log(2pi) - I*(log tau1 + log tau2)
    - 0.5*sum(u1^2 + (u2-r*u1)^2) [L_Sigma = diag(tau)*L_Omega => z = L_Omega^{-1} u].
  - exponential_lpdf propto: -lambda*x. bernoulli_logit: y*eta - log1p(exp(eta)), no constants.

### Formula derivation war log (the gate earning its keep — 5 real errors found)

1. hier_2pl structural bug (mine): assumed 2x2 cholesky-corr L_Omega = [[1,0],[r,1]].
   WRONG — cholesky_corr_constrain fills the diagonal by sqrt(1-sum_sqs):
   L_Omega = [[1,0],[r,sqrt(1-r^2)]]. Correct mn form:
   -log|det L_Sigma| = -(t1+t2) - 0.5*I*log(1-r^2); quad = u1^2 + (u2-r*u1)^2/(1-r^2).
   (Caught by block-delta probes: mu/tau/z blocks wildly off; theta block OK.)
2. diamonds constants (mine): TWO student_t priors => 2x C_t (had 1x). Confirmed exactly
   by prior_only=1 data-variant probe (diff 0.000000000000) — the probe method: construct
   the SAME .so with modified JSON (prior_only=1 / N=1/N=2) isolates likelihood/priors.
3. diamonds (empirical, surprising): student_t_lpdf(sigma|3,0,10) in the compiled model
   does NOT contribute -log(sigma) on the unconstrained scale (source says it should:
   logp -= sum(log(sigma_val)) under include_summand<false,...>; measured: net +s only =
   the exp-transform jacobian). Gradient probe: bs grad[sigma_unc] = mine + 1.000000
   exactly, at 5 sigma values. Formulas written to match the .so (the reference), i.e.
   sigma t-prior contributes ONLY -2*log1p(sigma^2/300), jacobian +s, and g[25] += +1.
4. diamonds (mine): prototype lp dropped the sigma t-prior data term -2*log1p(sig^2/300)
   entirely (grad had it) => -0.8038 abs at worst point. Found by worst-point dissection.
5. hier_2pl (Empirical DISCOVERY in Stan 2.39.0 math, replicated to 7.6e-16):
   bernoulli_logit_lpmf uses cutoff=20 tail branches on ntheta=(2y-1)*eta:
     lp:    ntheta>20 -> -exp(-ntheta); ntheta<-20 -> ntheta; else -log1p(exp(-ntheta))
     adjoint(d lp/d theta): ntheta>20 -> -exp(-ntheta); |ntheta|<=20 ->
       (2y-1)*exp(-ntheta)/(exp(-ntheta)+1); ntheta<-20 -> (2y-1) exactly.
   In the ntheta>20 & y=1 corner the adjoint -exp(-ntheta) has the OPPOSITE SIGN of the
   true derivative (+exp(-ntheta)) — inconsistent with Stan's own lp tail formula
   (d/dtheta[-exp(-ntheta)] = +exp(-ntheta)). Magnitude < e^-20 = 2.1e-9 per term,
   7117 saturated terms across our 64 ref points. Negligible for inference, but it was
   the entire 1e-8-scale residual I chased. Source: stan/math/prim/prob/
   bernoulli_logit_lpmf.hpp lines ~74-87 (vendored 2.39.0). Upstream-issue candidate.
   C code replicates these branches exactly (reference = the .so).

FINAL prototype status (numpy, all 64 pts vs npz):
- diamonds: rel_lp 1.136e-14, grad rel-L2 5.338e-15 CONFIRMED
- hier_2pl: rel_lp 1.257e-14, grad rel-L2 7.618e-16 CONFIRMED
Numeric-order notes: z = r*(1/sigma) (reciprocal multiply, matching Eigen's inv_sigma);
r = (Y - Xc.b) - Intercept (Stan's subtraction order).

- 12:55 — C written + compiled: bench/fortk_fused/{diamonds.c, hier_2pl.c};
  data via BINARY files (no giant headers): diamonds_data.bin = 1,000,012 B
  (N=5000, Kc=24, Y + precomputed centered Xc row-major), hier_2pl_data.bin = 172,816 B
  (I=32, J=600, N=19200, 0-based int32 ii/jj + uint8 y). Loaded via fopen/fread in
  <model>_init(); per-model logp_grad is allocation-free afterwards.
  clang Ubuntu 14.0.0-1ubuntu1.1, `clang -std=c99 -O2 -march=native -fPIC -shared`
  (no -ffast-math). lib_diamonds.so + lib_hier_2pl.so.
- 13:00 — VERIFY GATE PASS (verify_f2b.py, all 64 seeded points, first compile):
  - diamonds: logp max rel 1.136e-14 (<1e-12), grad rel-L2 5.385e-15 (<1e-9) PASS
  - hier_2pl: logp max rel 6.114e-15 (<1e-12), grad rel-L2 7.746e-16 (<1e-9) PASS
  - C-ABI sanity: bs_log_density_gradient via ctypes reproduces npz p0 grad exactly (0.0).

### Kernel iteration (diamonds) — honest performance work, gates re-run each time

- v1 (1 row/pass): fused 59.4 us/call vs bs 31.7 => 0.53x. Cause: sequential 24-FMA dot
  chain per row (clang cannot reassociate FP without -ffast-math, which is BANNED).
- v2 (4-row tiles, 4 independent dot chains): 32.9 us => parity with bridgestan.
  Gate re-run: PASS (1.116e-14 / 5.557e-15).
- v3 (dot split k%4, 16 chains): 35.4 us — REGRESSED (switch overhead), reverted to v2.
- v2 final: vectorization confirmed in the binary (261 ymm ops, vfmadd231pd on ymm).
- Mechanism finding: diamonds (N=5000, Kc=24) streams 960KB of Xc per call; both arms
  sit at ~30 GB/s effective single-core L3 bandwidth => ~32 us floor for EITHER
  implementation. The fused kernel cannot beat bridgestan on bytes it must also read;
  Stan's autodiff overhead fully overlaps the memory stream at this size.
- hier_2pl kernel is transcendental-bound (19200 obs x {exp,log1p} from libm): ~445 us
  floor; no exact-arithmetic shortcut exists (approximations would break the gate).
  Noted as F-3 headroom: gate-compatible ulp-accurate vectorized exp/log1p could add
  ~2x on hier-class models (rel_lp headroom is ~166x).

### Benchmarks

Context: coordinator's stanli release build (-j4) ran during EARLY exploration (12:05-14:30);
final timed runs below started only after pgrep cc1plus/make == 0. However another lane's
python jobs (up to 279% CPU, load spike 11.9) were active during SOME reps — flagged per
attempt; hier_2pl C-loop re-run per the >5%-spread rule, both attempts recorded.

Protocol b — C-loop driver (bench/fortk_fused/cloop_f2b, internal timing loops for BOTH
arms via dlopen; per-call ctypes overhead absent; spot-check gate re-passed in-driver):

diamonds (ncalls=100000/block, taskset -c 23, 3 reps):
| rep | bridgestan us/call | fused us/call | ratio |
|---|---|---|---|
| 1 | 32.659 | 32.963 | 0.99x |
| 2 | 32.390 | 33.182 | 0.98x |
| 3 | 32.330 | 32.831 | 0.98x |
| median | 32.390 | 32.963 | 0.98x | (spread 1.5%)

hier_2pl attempt 1 (ncalls=4000/block, taskset -c 23):
| 1 | 956.551 | 446.726 | 2.14x |
| 2 | 1013.063 | 468.681 | 2.16x |
| 3 | 1235.116 | 509.407 | 2.42x |  <- both arms inflated (foreign load)
| median | 1013.063 | 468.681 | 2.16x | (spread 13.1% > 5% => re-run)

hier_2pl attempt 2 (taskset -c 22):
| 1 | 1179.958 | 510.198 | 2.31x |  <- rep1 hit the load spike (loadavg 11.9)
| 2 | 957.394 | 439.743 | 2.18x |
| 3 | 972.396 | 445.010 | 2.19x |
| median | 972.396 | 445.010 | 2.19x | (spread 6.2%)
Attempt medians agree within 1.4% (2.16x vs 2.19x); clean-rep ratios cluster 2.14-2.19x.

Protocol a — ctypes C-ABI vs C-ABI (bench_f2b.py, taskset -c 23, A/B/A/B, 3 reps) —
FIRST ATTEMPT RAN DURING RENEWED FOREIGN LOAD (cc1plus=1, loadavg 14.7; the stanli build
resumed + another lane's python): diamonds bs 42.7 / fused 39.0 us => 1.08x (spread 2.6%);
hier_2pl bs 685.0 / fused 453.7 us => 1.49x (spread 10.6%). REJECTED as canonical.

**Measurement-bias finding (important for the verdict):** foreign load inflates the
bridgestan arm MORE than the fused arm (hier_2pl bs: 685 us light-load vs 957-1235 us
heavy-load; fused: 440-510 vs 453-459 us — the fused kernel is allocation-free and
transcendental-bound, hence load-insensitive; bridgestan's autodiff arena/allocator is
not). Ratios measured under load are therefore INFLATED. Canonical numbers below are
re-measured under a quiet box (cc1plus=0, make=0, loadavg<3), both protocols.

**Harness finding #2 (glibc mmap threshold — 300+ us/call of bridgestan overhead):**
in a bare C process, bridgestan's multi-MB AD arena is mmap/munmap'd EVERY call
(default dynamic threshold), adding page-fault cost that a Python embedding (allocator
history raises the threshold) does not pay. hier_2pl bs arm: 929-979 us/call (default
env) vs 621-629 us/call with MALLOC_MMAP_THRESHOLD_=64MB/MALLOC_TRIM_THRESHOLD_=128MB.
The earlier C-loop "2.16-2.19x" hier ratios were inflated by exactly this pathology on
the bs arm (fused arm is allocation-free, unaffected). Canonical protocol-b numbers use
the fair malloc env for BOTH arms (matches ctypes-side conditions; also matches what a
real embedding like nutpie sees). Evidence: this is a Stan-embedding hazard worth an
upstream note on its own — a third of bridgestan's hier_2pl per-gradient time in a
clean C host is allocator overhead, not math.

### CANONICAL RESULTS (quiet box, cc1plus=0, fair malloc env for C-loop)

Protocol b — C-loop driver (cloop_f2b, dlopen both arms, internal timing, A/B/A/B,
taskset -c 23, 3 reps):

diamonds (ncalls=100000/block):
| rep | bridgestan us/call | fused us/call | ratio |
|---|---|---|---|
| 1 | 32.618 | 32.476 | 1.00x |
| 2 | 31.313 | 30.900 | 1.01x |
| 3 | 32.503 | 32.048 | 1.01x |
| **median** | **32.503** | **32.048** | **1.01x** | (spread 1.0%)

hier_2pl (ncalls=6000/block):
| 1 | 627.906 | 431.673 | 1.45x |
| 2 | 621.408 | 430.356 | 1.44x |
| 3 | 619.356 | 430.283 | 1.44x |
| **median** | **621.408** | **430.356** | **1.44x** | (spread 1.1%)

Protocol a — ctypes C-ABI vs C-ABI (bench_f2b.py, taskset -c 23, A/B/A/B, 3 reps,
final quiet run; the 0.5-1 us/call ctypes tax is negligible at these call sizes):
- diamonds: bs 32.642 / fused 32.723 us => **1.00x** (spread 0.3%)
- hier_2pl: bs 624.370 / fused 429.805 us => **1.45x** (spread 1.5%)

Attribution:
- diamonds (N=5000, Kc=24): both arms stream 960KB Xc/call at ~30 GB/s effective
  single-core bandwidth => ~32 us floor for EITHER implementation. Stan's autodiff
  work fully overlaps the memory stream. Parity is a physics result, not a tie.
- hier_2pl (I=32, J=600, N=19200): fused kernel is transcendental-bound: 99.4% of
  obs take the mid branch => 1 exp + 1 log1p per obs (scalar libm, ~22 ns/obs) =>
  430 us floor; the residual 190 us of bridgestan's 621 us is its AD/arena path.
- Cross-check vs WORKLOG Phase-0 "bridgestan diamonds 5.2 us/grad, hier_2pl 134":
  my single-call C-ABI numbers are ~6x higher; the Phase-0 figures were derived from
  4-parallel-chain sampling walls (likely wall/(4*grads) accounting) with warm caches.
  Within-protocol ratios here are unaffected (both arms measured identically); the
  ABSOLUTE discrepancy is recorded honestly.

### VERDICT vs pre-registered hypotheses

- "diamonds >= 4x under C-loop": **FALSIFIED** — measured 1.01x (parity; 0.97-1.02x
  across every protocol/run combination). The <2x trigger fires: the bandwidth-fusion
  thesis is IN DOUBT as pre-registered; F-3 scope narrows accordingly.
- "hier_2pl moderate (2-4x)": **FALSIFIED on the low side** — 1.44-1.49x under fair
  conditions. (2.16x was measurable only by leaving the bare-C malloc pathology on
  the bridgestan arm — not a kernel-level win.)
- Combined with F-2 (eight_schools_nc 2.88x, blr 3.09x, ctypes-bound): the fused-codegen
  advantage does NOT grow with model size. It is largest where per-call overhead
  dominates (tiny models) and vanishes where either (a) memory bandwidth binds
  (diamonds) or (b) exact transcendentals bind (hier_2pl: libm scalar exp/log1p = the
  floor for any gate-passing implementation without hand-rolled ulp-accurate vector
  transcendentals).
- F-3 (if it proceeds at all) narrows to: (1) small/medium graphs (the F-2 size class,
  2-4x band); (2) transcendental-heavy models ONLY with a verified ulp-accurate vector
  exp/log1p kernel (gate headroom exists: current rel_lp 6e-15 vs 1e-12 gate; est.
  additional ~2x); (3) allocator/embedding fixes (the mmap-threshold finding helps ANY
  bridgestan embedder, fused or not — arguably the cheapest Stan-side win measured
  in this probe: 300+ us/call on hier_2pl).

Artifacts (bench/fortk_fused/): ground_truth_f2b.py, prototype_f2b.py (confirmed
formulas), debug_f2b.py (probe harness), make_c_data_f2b.py, diamonds.c, hier_2pl.c,
lib_diamonds.so, lib_hier_2pl.so, diamonds_data.bin (1,000,012 B), hier_2pl_data.bin
(172,816 B), verify_f2b.py, bench_f2b.py, cloop_f2b.c + cloop_f2b binary, pts_*.bin,
ref_{diamonds,hier_2pl}.npz.
