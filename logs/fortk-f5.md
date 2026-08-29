# F-5: AVX2 vectorized ulp-accurate exp/log1p kernels (T2 kernel-library lane)

Started: 2026-08-26. Pre-registration: WORKLOG.md "F-5 pre-registered BEFORE building".
Workspace: bench/fortk_t2/ (NOT the fork). Rules: CPU only, <=4 cores, no state-changing
git, no upstream interaction, nothing modified outside bench/fortk_t2/ + this log.

GATES (pre-registered, never loosened):
- (a) accuracy: max rel error <= 2 ulp vs mpmath (50-digit) over grids covering the
  model operating ranges (exp args +-[0,40]; log1p args (0,~1e-12] u [1e-12,1e3];
  extremes documented). Also vector/scalar-path lane consistency.
- (b) perf: >= 1.5x vs scalar glibc libm per function on the model ranges, in-cache,
  taskset-pinned, 3 reps medians; + libmvec direct-call comparison. All builds
  clang -O2 -march=native -ffp-contract=off.
- (c) end-use: hier_2pl_vec.c (COPY of bench/fortk_fused/hier_2pl.c, obs loop batched
  through the kernels) must PASS F-2b verification (64 pts, grad rel-L2 < 1e-9;
  logp rel < 1e-12 original / 1e-9 F-5 floor — report which) and report us/call vs
  the 430.4 us/call hand-fused baseline (informational win <= 366 us; a miss ranks).

Model math pinned from F-2b (logs/fortk-f2b.md): 19200 obs, mid branch does
exp(-nth) + log1p(exp(-nth)) with nth in [-20,20] => exp args in [-20,20] (harness
covers [-45,45]); log1p args = exp(-nth) in [2.1e-9, 4.85e8] (grid extended to 1e9).
NOTE log1p's critical region: args down to ~1e-18 possible when nth near 41+ (Stan's
cutoff=20 keeps log1p args >= e^-20 = 2.06e-9, but the kernel is built for tiny args
regardless; grid goes to 1e-18).

## Log

- 14:05 — Environment recorded:
  - clang Ubuntu 14.0.0-1ubuntu1.1 (all builds: `clang -std=c99 -O2 -march=native
    -ffp-contract=off`), gcc 11.4.0 present (not used).
  - CPU: Ryzen 9 5900X (Zen 3, AVX2+FMA, no AVX-512), 24 hw threads, L2 512KB/core,
    L3 32MB.
  - libmvec (glibc 2.35, /usr/lib/x86_64-linux-gnu/libmvec.so.1): direct-call GV
    symbols present: _ZGVbN2v_{exp,log,log1p,...} (SSE2 2x double) and
    _ZGVcN4v_{exp,log,log1p,...} (AVX2 4x double). NOTE: the task brief guessed
    "_ZGVdN4v_exp"; on this glibc the 4-double AVX2 symbol is _ZGVcN4v_* — using that.
  - mpmath 1.3.0 + numpy 2.5.2 in project uv venv.
  - Box: load 0.33; ONE other-agent job pinned to core 2 (fortk_t1r sampler). All my
    timing pinned to core 23 (F-2b's core), pgrep-checked before every timed run.

- 14:40 — Kernels implemented (vecmath.h/.c): vexp_pd (hi/lo reduction + Taylor deg
  14, fast |x|<708, per-lane fixup w/ two-part scaling), vlog1p_pd (atanh-Q paths,
  exact-residual u=1+x reduction, exponent-surgery normalization, per-lane fixup for
  NaN/inf/x<=-1/subnormal-u). Coefficients from gen_coeffs.py (mpmath dps=60):
  exp 1/k! k=0..14; Q = 2/(2i+3) i=0..9. ln2 split 0x1.62e42fee00000p-1 /
  0x1.a39ef35793c76p-33 (sum err 1.2e-26).
- 14:55 — Smoke-test iteration caught 3 real bugs before any mpmath run (war log):
  1. log1p path C: forgot exponent-bias subtraction (me is the RAW 11-bit field;
     mh and the 2^-(m+h) scale bits both off by 1023). Symptom: log1p(0.4)=709.4.
  2. log1p path B threshold: |s|=|x|/(2-|x|) on the NEGATIVE side hits 0.231 at
     x=-0.375 (vs 0.158 positive) -> Q truncation 2.3e-16 = 2.3 ulp. Threshold
     moved 0.375 -> 0.3125 (bounds |s| <= 0.185, truncation <= 1.3e-18 = 0.006 ulp).
  3. log1p path C normalization: halving w (w >= sqrt2) must also increment m.
     Symptom: off by exactly +-ln2 on ~half the C-path lanes.
  Plus exp overflow boundary pinned EXACTLY with mpmath: x=709.782712893384
  (0x1.62e42fefa39efp+9) is FINITE (exp = DBL_MAX); inf starts at the next double.
  => overflow check is STRICT x > 709.782712893384. Underflow: x <= -745.1332191019412
  -> 0 (verified tie-to-even; -745.1332191019411 -> 4.94e-324 nonzero).
  Post-fix smoke: exp 16/16 == libm; log1p 14/16 == libm, 2 diffs of 1 ulp
  (0.001, 2.0) — mpmath harness decides.

- 15:20 — First full mpmath run (acc_f5.py, ~98k exp pts + ~105k log1p pts planned,
  pinned core 23):
  - vexp: MAX 0.8165 ulp over 97,830 pts (all grids <= 0.82; 92,678/97,830
    bit-equal to correctly-rounded; underflow/normal boundaries EXACT 0.0 ulp
    incl. the pinned transition doubles). GATE (a) exp side: PASS with margin.
  - vlog1p: max 1.8778 ulp (x=9.4e-7, path B) / 1.86 (path C x=0.472) — passes
    2.0 but only 6% margin. Root cause analysis: s = x/(2+x) carries BOTH the
    division rounding (0.5 ulp) AND the rounded denominator (2+x drops bits of
    x below 2^-51; +~1.2 ulp) — maps ~1:1 into the result since y ~ 2s.
  - Improvement (not gate-forced, margin-seeking): (i) |x| <= 0.01 subpath ->
    direct Taylor deg-9 (division-free; truncation x^11/12 ~ 1e-23; expected
    <= 0.6 ulp — covers the pre-registered critical range (0,1e-12] exactly);
    (ii) FMA quotient correction in both atanh paths: num = fnmadd(q0,b, a)
    exact, db = denominator representation error recovered exactly
    (db = x-(t-2) resp. w-(g-1)), dq = fnmadd(q0,db,num)*rcp with a crude
    1%-accurate reciprocal (dq ~ 2^-53*q0 so its own error is invisible).
    New s error budget ~1.05 ulp -> expected path maxima ~1.3-1.5.

- 15:55 — GATE (a) ACCURACY: **PASS** (two independent seeds, 202,370 + 205,090 pts).
  | kernel | seed 20260826 | seed 987654321 | gate |
  |---|---|---|---|
  | vexp   | 0.8165 ulp   | 0.8244 ulp    | <= 2 PASS |
  | vlog1p | 1.7475 ulp   | 1.8219 ulp    | <= 2 PASS |
  - vexp: 94.7% of points bit-equal to the correctly-rounded value; exp
    underflow/normal-boundary and subnormal-transition grids EXACT (0.0 ulp)
    incl. the pinned doubles 709.782712893384 / 709.7827128933841 / -745.1332191019412.
  - vlog1p after quotient-correction + tiny-Taylor rework: tiny/subnormal-arg
    grids EXACT 0.0; model range [1e-18,1e9] <= 1.57; worst overall lives at
    the negative path-B boundary (-0.3125 band, 1.75-1.82; model never uses
    negative log1p args). Residual error = the two irreducible roundings in
    s = fl(q0+dq) (division + final add); going lower needs double-double s —
    not required by the gate, not done.
  - Lane consistency: BOTH kernels bitwise-identical under all rotations
    (r=1,2,3,5) and all chunkings (1,2,3,5,7 — exercises every tail path).
    (Harness note: initial FAIL was np.array_equal NaN!=NaN, not the kernel.)

- 16:20 — Perf harness v1 (bench_kernels.c, N=19200 in+out = 307KB L2-resident,
  2000 passes/arm, 3 reps medians, taskset -c 23, box quiet cc1plus=0):
  | fn / dataset | scalar libm | F-5 | libmvec cN4 | F-5 speedup | gate 1.5x |
  |---|---|---|---|---|---|
  | exp [-45,45] uniform | 3.861 | 1.386 | 1.536 | 2.78x | PASS |
  | exp model-ish [-41,41]| 3.611 | 1.372 | 1.534 | 2.63x | PASS |
  | log1p model [e-41,1]  | 5.314 | 3.957 | 2.778 | 1.34x | **FAIL** |
  | log1p [e-41,1e3]      | 6.248 | 3.984 | 2.734 | 1.57x | (marginal) |
  - exp also BEATS libmvec (1.386 vs 1.536 ns/elem). log1p slower than libmvec:
  my kernel executes BOTH paths' divisions per vector (2 vdivpd) + corrections.
  - FIX (structural): unify — route 0.01 < |x| through the path-C machinery for
  ALL magnitudes (u=1+x exact-residual reduction is valid for small x: w-1 =
  u-1 exact since u < 1.5; tiny-x exactness preserved by the Taylor path and,
  below 2^-53, result = e*ru = x exactly). ONE division per vector remains.

- 16:55 — GATE (b) PERF: **PASS** (canonical run, core 21, spreads <=5% except
  the informational SSE2 arm; earlier runs on core 23 under a floating foreign
  python job showed 7-10% spreads and 5-10% uniformly slower absolutes —
  re-run per protocol; ratios stable across all runs):
  | fn / dataset | scalar | F-5 | lmv cN4 (AVX2) | lmv bN2 (SSE2) | F-5/scalar |
  |---|---|---|---|---|---|
  | exp [-45,45] uniform  | 4.093 | 1.450 | 1.696 | 1.469 | **2.82x** |
  | exp model-ish [-41,41]| 3.828 | 1.490 | 1.709 |  —     | **2.57x** |
  | log1p model [e-41,1]  | 5.653 | 3.205 | 2.993 | 2.808 | **1.76x** |
  | log1p [e-41,1e3]      | 6.712 | 3.205 | 3.027 |  —     | **2.09x** |
  (ns/element, N=19200, 3-rep medians, 2000 passes/arm.)
  - vexp BEATS glibc's own vectorized exp (1.450 vs 1.696). vlog1p ~7-12%
  behind libmvec (they don't pay my exact-residual machinery; accuracy parity
  unknown — informational, not gated).
  - Unified-rework accuracy re-check (same 200k-pt grids): exp 0.8165,
    log1p 1.8721 (worst at x=0.130 mid-band; still <= 2.0). Lane consistency
    bitwise PASS both.

- 18:10 — End-use probe. hier_2pl_vec.c (COPY of F-2b hier_2pl.c; obs loop ->
  3 passes per 4096-obs block: scalar gather (A=a[i], D=theta[j]-bb[i],
  NTH=(2y-1)aD, SG), vector pass2 (emn=vexp(-nth); lp/adj via BLENDs
  replicating Stan's cutoff=20 branches incl. the saturated-tail sign quirk),
  scalar pass3 accumulating lp/grad in the ORIGINAL m-order).
  - One real bug, caught by the verify gate on first build: the lo mask was
    written `nth < 20` instead of `nth < -20` — all mid-branch obs took the
    low tail (lp/adj = nth/sg). Symptom: logp +4855 vs -20164 at pt0. Fixed;
    standalone branch test (t2.c) then matched libm BITWISE on all 8 branch
    cases (incl. nth=20.0 boundary and sign quirk).
  - VERIFICATION (verify_f5.py, all 64 ref pts, jacobian=True):
    logp max rel = 6.097e-15 (abs 2.18e-10), grad rel-L2 = 7.667e-16.
    => F-5 gate (1e-9) PASS **and the original F-2b gate (1e-12) PASS** —
    the kernels' <= 2-ulp drift is invisible at model level (as predicted:
    lp drift budget ~1e-13 vs 1e-12 gate).
  - In-driver spot re-check inside cloop_f5 also PASS (both fused arms, 64 pts).

- 18:25 — GATE (c) END-USE TIMING: **PASS** (informational win bar <= 366 us
  cleared 1.9x over). cloop_f5 (F-2b protocol b: dlopen 3 arms, A/B/A/B
  interleave, 3 reps, taskset -c 21, fair malloc env 64MB/128MB, box quiet,
  spread(vec arm) 0.5%):
  | arm | us/call | vs F-2b canonical |
  |---|---|---|
  | bridgestan | 649.5 | (F-2b: 621.4; +4.5% same-methodology drift) |
  | fused_orig (F-2b scalar) | 442.9 | (F-2b: 430.4; +2.9% — baseline reproduces) |
  | **fused_vec (F-5)** | **191.9** | **2.243x vs 430.4** (2.31x vs same-session orig) |
  - bridgestan/vec = 3.38x. hier_2pl per-gradient wall: 621 -> 192 us vs Stan
    stack (3.24x vs F-2b's bridgestan measure).
  - Attribution (kernel ns/obs achieved vs expected): total obs-loop now
    191.9-33(non-obs: MVN/priors) = ~159 us = 8.3 ns/obs (was 21.4 in F-2b).
    Vector pass2 ~= vexp 0.36 + vlog1p 0.80 + adj-div 0.2 + blends 0.25 ~= 
    1.6 ns/obs (~31 us) — matches the bench_kernels per-kernel numbers.
    Remaining ~6.7 ns/obs = scalar pass1 gather (3.4) + pass3 grad scatter
    (3.3): the b_* array round-trip through L2. Headroom if pass1 were
    gather-fused into pass2 (~120-140 us/call est.) — NOT done, out of
    pre-registered scope, recorded as follow-up.

### F-5 VERDICT (2026-08-26) — ALL THREE PRE-REGISTERED GATES PASS

| gate | requirement | result |
|---|---|---|
| (a) accuracy | max <= 2 ulp vs 50-digit mpmath | **PASS**: vexp 0.8165/0.8244 ulp, vlog1p 1.8721/1.8462 ulp (2 seeds x ~200k pts); bitwise lane-consistent |
| (b) perf | >= 1.5x vs scalar glibc libm, model ranges | **PASS**: vexp 2.82x ([-45,45]) / 2.57x (model nth); vlog1p 1.76x (model args) / 2.09x ([e-41,1e3]) |
| (c) end-use | verify 64 pts (grad<1e-9; logp<1e-9 floor, 1e-12 original) + report us/call | **PASS at the ORIGINAL 1e-12 gate** (logp 6.1e-15, grad 7.7e-16); **191.9 us/call = 2.243x vs the 430.4 us baseline** (win bar 366 us cleared) |

- hier_2pl end-to-end: bridgestan 649.5 -> F-2b hand-fused 442.9 -> F-5
  vectorized 191.9 us/call (same-session; F-2b canonical numbers 621.4/430.4
  reproduce within 4.5%/2.9%).
- vexp additionally BEATS glibc's own AVX2 vector exp (1.450 vs 1.696
  ns/elem); vlog1p is 7-12% behind libmvec but pays for exact-residual
  reduction + 2-ulp guarantee (libmvec accuracy not audited here).

Surprises / algorithm notes (what bit us):
1. exp overflow boundary needed EXACT bracketing: x=709.782712893384
   (0x1.62e42fefa39efp+9) is finite (=DBL_MAX); inf starts at the NEXT
   double => strict `>`. The naive >= flips one ulp-neighbor to inf.
2. log1p atanh path's |s| bound is asymmetric: |s|=|x|/(2-|x|) on the
   negative side (0.231 at x=-0.375 vs 0.158 at +0.375) — threshold had to
   come from the NEGATIVE side (0.3125). First build had 2.3-ulp truncation
   at x=-0.375.
3. The u=1+x exact-residual reduction generalizes DOWN to x~0.01 (u<1.5 =>
   u-1 exact) — unifying paths cut log1p from 2 divisions/vector to 1 and
   took the kernel from 1.34x (gate FAIL) to 1.76x. Small-|x| exactness is
   preserved by a deg-9 Taylor subpath (|x|<=0.01: division-free, tiny-arg
   grids measure 0.0 ulp; log1p(1e-18) == its argument bit-exact).
4. Exponent-field surgery: forgetting the -1023 bias, and not incrementing m
   when w is halved, each produced clean factor-of-ln2-class signature bugs
   (log1p(0.4)=709.4; off-by-ln2) — caught by libm spot diffs in minutes.
5. Blend polarity: wrote `nth < 20` for the low-tail mask (should be
   < -20): the verify gate caught it instantly (logp sign flip). Lesson
   re-confirmed: gates first, then perf.
6. Scalar glibc log1p is ~40% slower than its exp (5.65 vs 4.09 ns) — the
   F-2b "~22 ns/obs" was exp+log1p+branches+grad-updates; kernels alone now
   cost 1.16 ns/obs of it.

Artifacts (bench/fortk_t2/): vecmath.h/.c (kernels), gen_coeffs.py,
acc_f5.py + lib_acc_f5.so (accuracy), bench_kernels.c + bench_kernels
(perf vs scalar/libmvec), hier_2pl_vec.c + lib_hier_2pl_vec.so,
verify_f5.py, cloop_f5.c + cloop_f5 (3-arm timing), smoke.c, t2.c
(branch-blend test), build commands: all clang Ubuntu 14.0.0-1ubuntu1.1,
`-std=c99 -O2 -march=native -ffp-contract=off` (+ -fPIC -shared for .so,
-lm -lmvec where needed).
Nothing outside bench/fortk_t2/ + logs/fortk-f5.md was modified; no git
state changed; no upstream interaction; <=4 cores throughout (timing
single-core taskset-pinned; the one parallel activity was the box's own
foreign python job, avoided by re-runs).
