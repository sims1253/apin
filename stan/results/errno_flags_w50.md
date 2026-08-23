# W-50 — the `-fno-math-errno` family: does the compiler hand us W-33 for free?

Date: 2026-08-23. Pre-registration: WORKLOG.md W-50 (arms, gates, expectations
registered before any arm was timed). Raw: `results/profile/w50/`; build
scripts, drivers, `.so`s: `scratch/w50/` (untracked, W-33 precedent); sampler
inits: `inits_w50/gp_regr/`. Environment: gcc 16.2.1, glibc 2.44, bridgestan
2.9.0 (stan-math 5.3.0-era, pristine), `env -u LD_LIBRARY_PATH`,
`/usr/bin/make -j2`, Zen 3.

**VERDICT (one line): the flag DOES replicate the W-33 performance win on
pow-heavy models (gp_regr −8.5% Ir/grad, −12.5/−13.8% per-call wall, pow
bucket → 0) — but it is NOT value-neutral: gcc's errno-unblocked
`pow(x,2) → x*x` collides with glibc `pow`'s ≤1-ulp error, which flips the
near-degenerate eigendecomposition on kronecker_gp to O(1) gradient changes
with sign flips (W-35's amplifier), breaks draw reproducibility at full
trajectory length (2/4 chains on gp_regr), and FAILS the pre-registered
bit-identity parity gate on 2 of 3 models. Do not adopt. The same finding
DEMOTEs W-33's "bit-identical end-to-end" claim to trajectory-conditional —
see §6; the upstream ask keeps its performance case but must drop the
bit-identity promise.**

## 1. Mechanics probe (before registration)

gcc 16.2.1, `-O3 -std=c++17 -fPIC` (the bridgestan default set; `O ?= 3`):

| code | default | `-fno-math-errno` |
|---|---|---|
| `pow(x,2)` | `call pow@PLT` | `mulsd %xmm0,%xmm0` (x*x) |
| `pow(x,3)`, `pow(x,0.5)` | `call pow@PLT` | `call pow@PLT` (unchanged) |
| `sqrt(x)` | `ucomisd/ja` errno branch + `sqrtsd` | bare `sqrtsd` (value-exact) |
| elementwise `exp`/`log1p` loops | scalar `@PLT` calls | scalar `@PLT` calls — **no vectorization** |

No libmvec vectorization happens under errno-family flags: glibc guards its
`__DECL_SIMD_*` (libmvec) declarations behind `__FAST_MATH__`, which we will
not define (it implies reassociation). So the honest scope of
`-fno-math-errno` is scalar errno-guarded transforms — exactly W-33's
pow→mul plus a branch-free sqrt — and **not** vectorized elementwise libm
chains. Pre-registered expectation for hier_2pl (log1p-heavy) was therefore
~0; measured ~0 (§4).

## 2. Gate (a) — parity: FAIL on 2 of 3 models (pre-registered gate = exact 0.0)

100 deterministic random unconstrained points (`random.Random('w50-parity-0')`,
W-27 scheme), fresh default build vs `-fno-math-errno` build, logp+gradient:

| model | logp | gradient | verdict |
|---|---|---|---|
| gp_regr | 100/100 bit-identical | 100/100 bit-identical (0.0) | PASS — but see §5: fragile |
| hier_2pl | 100/100 bit-identical | **99/100**; pt43 comp 667 (`tau.2`) 2.0e-15 rel, no sign flips | FAIL (investigated §3) |
| kronecker_gp | 91/100 bit-identical (2.3e-16) | **14/100**; max rel **1.72**, 5 sign flips | FAIL — W-27 `-march=native` signature |

Controls: fresh default build is 100/100 bit-identical to the surviving W-33
stock `.so` (gp_regr); the default `.so` is bit-stable across processes and
when loaded twice in one process. FD spot-checks at AD-noise level.

## 3. Root cause — glibc `pow(x,2)` is NOT correctly rounded

The pre-registration (following W-33) assumed `pow(x,2) == x*x` exactly.
**It is not.** On glibc 2.44, `pow(x,2)` differs from the correctly-rounded
`x*x` by 1 ulp for ~0.08% of doubles (161/200 000 uniform[-10,10]; Python
`math.pow` = same libm). Example from the kronecker_gp data grid:
`d = 0x1.a7b9611a7b948p-1` → `pow(d,2) = 0x1.5eab129180c03p-1` but
`d*d = 0x1.5eab129180c04p-1`. (Note the direction: **x\*x is the correctly
rounded value; glibc pow is the one in error.**)

Isolation (W-35 driver `d4` rebuilt with the two flag arms, then a `d0`
stage printer, `scratch/w35/d0_w50.cpp`):

- Value-level GEMM (`d5`), eigendecomposition of fixed inputs (`d1`),
  cholesky (`d6`), lkj (`d3`): all bit-identical between flag arms.
- Full extracted kronecker model (`d4`): diverges — only `g_bw1`.
- Stage printer: `xd = -square(x1_i - x1_j)` differs on **4/900 entries**
  (two grid pairs, symmetric) — exactly the entries where glibc pow is 1 ulp
  off. Those 4 entries seed a different `Sigma1`; `SelfAdjointEigenSolver`
  then returns a **different but equally valid basis** of the jitter-pinned
  near-degenerate cluster (W-35 §3b), and the eigenvector adjoint
  `F = 1/(w_j−w_i)` amplifies to O(1) with sign flips. Same end-to-end
  signature as `-march=native` (W-27/W-35), different seed (1-ulp pow vs
  256-bit GEMM order).
- hier_2pl pt43: reproduced two-process via a dlopen driver
  (`g[667] = -0x1.fc81397c48e56p+3` vs `...e68p+3`). Full-threshold
  callgrind diff of that single gradient: the default arm executes **2
  libm `pow` calls** (inlined `square()` sites in `log_prob_impl`, matching
  W-29's 8 986/4 493 = exactly 2/grad), the nme arm executes none (inlined
  multiply). One of the two hit a disagreeing double → 1-ulp seed → 2-ulp
  gradient wobble in `tau.2`'s long adjoint accumulation. logp stayed
  bit-identical; the fixed-init 150-iter callgrind trajectory never hits a
  disagreeing square (draws md5-identical across arms on that protocol).
- gp_regr's 11-point data grid: **0/121** kernel pairs disagree (measured) —
  which is why W-33 and this experiment both measured perfect bit-identity
  there: 55 of 57 pow(x,2)/grad are data-fixed constants; only
  `square(sigma)`/`square(l_val)` (2/grad) wander.

## 4. Gate (b) — cost

Native `stan_cli` per-call stanza (build_e27 binary, 3 interleaved reps,
medians; W-33 protocol). Callgrind Ir/grad via system valgrind 3.25.1 (one
job at a time; W-29 protocol warmup/samples/inits).

| model | us/call warmup def→nme | us/call sampling def→nme | Ir/grad def→nme | libm pow Ir def→nme |
|---|---|---|---|---|
| gp_regr | 5.414→4.738 (**0.875**) | 5.320→4.584 (**0.862**) | 66 987→61 310 (**−8.48%**) | 3 473 268→18 975 (sampler-side Adam residual only) |
| hier_2pl | 960.7→959.1 (0.998) | 977.2→986.2 (1.009) | 7 729 155→7 728 967 (−0.002%) | 0→0 (no pow in model gradient) |
| kronecker_gp | 371.0→357.4 (0.963)* | 370.7→365.7 (0.986)* | 5 255 616→5 190 755 (−1.23%)* | 532 130 311→0 |

\* contaminated: the nme arm's trajectory drifts (3910+1184 → 3773+959 grad
calls — the 1-ulp seed changes warmup), so per-call medians compare slightly
different work and totals are not comparable (same situation as W-32's hand
arm). gp_regr and hier_2pl have identical call counts (577, 4493).

Baseline reproduction: gp_regr default T = 47 390 367 (W-29: 47 393 116,
+0.006%), pow Ir **exactly** 3 473 268 (W-29 digit), Ir/grad 66 987 vs
66 990; kronecker default T = 27.635e9 (W-29: 27.630e9), pow Ir exactly
532 130 311; hier_2pl T = 34.951e9 (W-29: 35.024e9). vginstall 3.23 vs
system 3.25.1 on gp_regr default: T differs by 602 Ir (0.001%), pow Ir
identical — tool version immaterial. Python pair-interleaved cross-check on
gp_regr: 0.972 on ~13.4 µs Python-inflated calls (dilution, W-33-consistent).

So on the one model with a big pow bucket, **the flag reproduces W-33 to
within measurement noise** (W-33: −9.09% Ir/grad, −12.9/−15.2% wall; W-50:
−8.48% Ir/grad, −12.5/−13.8% wall). On hier_2pl it does nothing (log1p
stays scalar, as the mechanics probe predicted). On kronecker_gp the pow
bucket (~2%G) also collapses but the arm is disqualified at parity.

## 5. Gate (c) — sampler spot (gp_regr, 1 rep × 4 chains, warmup=1000
samples=1000, seeds 20260819+c, per-chain deterministic inits
`inits_w50/gp_regr/`, serialized)

- default wall 278.1 ms → nme wall 244.1 ms (**−12.2%**).
- draws md5: chains c1/c3 **identical** across arms; chains c0/c2
  **DIVERGED**. Gate FAIL: full-length trajectories eventually hit a
  disagreeing `square(sigma)`/`square(l_val)` value (2 sites × ~3900
  calls/chain at ≲0.1%/call disagreement probability).
- Cross-check with the **W-33 patched `.so`** (source-level pow→mul, same
  semantics): it ALSO diverges from stock on both tested chains (c0, c2) —
  and on c2 its draws are **md5-identical to the nme arm's** (flag ≡ patch,
  both ≠ stock). The short fixed-init W-29-style protocol (warmup 50,
  samples 50) remains md5-identical across all arms (`32881fbe…`, also under
  valgrind) — bit-identity there is real but trajectory-length-dependent.

## 6. Consequences

1. **Adoption: NO.** `-fno-math-errno` (and, a fortiori, adding
   `-fno-trapping-math` — arm 3 skipped per pre-registration since arm 2
   failed parity; the mechanics probe shows it changes nothing anyway) is a
   reproducibility hazard: our harness discipline (md5-identical draws
   canaries, W-26 through W-43) cannot coexist with silent 1-ulp value
   changes, and on eigendecomposition-heavy models the change is amplified
   to O(1) gradient error with sign flips — the same operational hazard
   class as `-march=native` (W-27/W-35). The performance case was already
   covered better and more safely by the W-33 source patch, which upstream
   controls.
2. **W-33 correction (feeds the upstream ask):** the one-line
   `square(): std::pow(x,2) → x*x` patch is NOT bit-identity-safe even on
   glibc — glibc `pow` can be 1 ulp off the correctly-rounded square
   (~0.08% of doubles; glibc 2.44 measured). W-33's "bit-identical
   end-to-end" holds only for the tested 50+50-iteration fixed-init
   trajectories (gp_regr's data-side squares are grid-fixed and its
   parameter-side squares happened not to hit a disagreeing value); at
   1000+1000 iterations 2/4 chains diverge. The upstream PR should keep the
   performance numbers (full 8.9%G Ir / 13–15% wall bucket on gp_regr,
   replicated here at the model-TU level by a pure build flag) and re-frame
   correctness as: *replaces a ≤1-ulp-error `pow` with the correctly-rounded
   product — a strict accuracy improvement, but not a bit-identity
   guarantee; on models with rounding-degenerate eigendecompositions the
   changed bits can flip the (equally valid) eigenbasis* (cite W-35).
3. **Docs ask:** add `-fno-math-errno`/errno-family flags to the same
   "do not build Stan models with these" list as `-march=native`, with the
   one-line reason: unblocks `pow(x,2)→x*x`, which changes values by up to
   1 ulp on glibc and is amplified to O(1) gradients on
   eigendecomposition-heavy models.

## 7. Artifact map

- `results/profile/w50/{model}_{arm}/` — callgrind.out, ann_exclusive,
  ann_inclusive, cli.log, draws (+ `_vg231` cross-check on gp_regr default);
  `w50_parsed.json`.
- `scratch/w50/` (untracked): `build_w50.sh`, `w50_gatea.py`,
  `w50_gateb_native.sh`, `w50_gateb_py.py`, `w50_callgrind.py`,
  `w50_gatec.sh`, `driver_w50.c` (dlopen gradient driver),
  per-variant build dirs, timing logs, `cg43/` (pt43 callgrind isolation).
- `scratch/w35/d0_w50.cpp` + `d0_w50_{def,nme}{,2}` — stage-level bit
  printer (kronecker isolation); `d{1,3,4,5,6}_w50_*` — W-35 drivers
  rebuilt per flag arm.
- `inits_w50/gp_regr/chain_{0..3}.txt` — W-27-scheme deterministic inits.
- No stan-math or walnutpie tree changes (bridgestan tree pristine; only
  new scratch builds). No pushes.
