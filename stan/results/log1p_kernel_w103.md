# W-103 — W-46 fused log1p kernel multiversioned inside `bernoulli_logit_lpmf`: ALL GATES PASS

Executed 2026-08-27/28 per `scratch/w103/integration_memo.md` (pre-registered in
WORKLOG "W-103 PRE-REGISTRATION"). Deliverable:
`scratch/w103/bernoulli_logit_lpmf_targetclones.patch` (+263/−0, 2 hunks, pure
insertion; apply-checked on `external/math_soa` @ v5.3.0-151-g344d7167a0 AND
`external/math_dev_soa` @ math#5 tip 8c63b8f355). Design as memo §3: manual
`__builtin_cpu_supports("avx2")` dispatch + per-function
`__attribute__((target("avx2,fma")))` on all four island functions (NOT
`target_clones` — FMV clones one body for every target and the default clone
cannot compile the hand-intrinsic island; documented as the design decision).
Kernel bodies byte-identical to the validated W-46 artifact (builder-asserted,
`scratch/w103/make_patched_header.py`).

## Arms (proven bundle wiring)

- **stock**: `scratch/w53/bs_w53` as-is (bs 2.9.0, math 5.3.0 + W-53/W-59 SoA
  slice; `bridgestan.o` gcc-rebuilt, SoA symbols verified via
  `make_nochain_vari_array.hpp` presence + `vari` symbols in `nm`).
- **kernel**: `cp -al` hardlink copy `scratch/w103/bs_w103_kernel` + the patched
  develop header dropped in with a **private inode** (`rm` + `cp`, so the
  hardlink set is NOT clobbered; verified: stock md5 `f003c78a…` unchanged,
  kernel copy md5 `2c61408a…`, link count 1). Prim-only header → prebuilt
  `src/bridgestan.o` ABI-fine, no rebuild. Models built per-arm dirs
  (W-27 cache rule) with `CXX=scratch/w46/gxx_fixed TBB_CXX_TYPE=gcc
  MAKEFLAGS=-j2`, `env -u LD_LIBRARY_PATH`, `/usr/bin/make`, nice 19.
- Models: `hier_2pl`, `lsat_model`, `vec_bern` (scalar-call form, n=1 kernel
  arm), `logistic_regression_rhs` (posteriordb, ovarian data). NOTE:
  logistic_regression_rhs uses `bernoulli_logit_glm`, NOT `bernoulli_logit_lpmf`
  — `nm` shows zero `w46::fwd_avx2` symbols in BOTH its arms — it is the
  kernel-inert 4th model / collateral-damage control (memo's "blr" resolution).

## Dispatch verification (this Zen3 box)

`scratch/w103/dispatch_check.cpp` compiled against the EXACT shipped header
(-I the kernel-arm bundle math):
- `__builtin_cpu_supports("avx2")=1024`, `("fma")=16384` (bits set); island
  compiled in (per-function target attributes).
- Runtime dispatch, n=1, 2.5M pts (grid+uniform): **max 1.000 ulp vs glibc**
  (pre-registered bound <=1 ulp; W-46 bench table reproduced).
- Island `fwd_avx2` 4-lane batches: value-sum rel diff vs glibc **4.58e-16**;
  partials vs stock formula **3.39e-16**.
- Definitive in-model proof: callgrind attributes **2,994,415,368 Ir (13.90%)**
  to `stan::math::internal::w46::fwd_avx2` in the kernel-arm hier_2pl run
  (memo's predicted 2.9–3.5e9 band; W-46 measured 2.99e9).

## Gate (a) — gradient parity (rel-L2 <= 1e-12, 100 pts x 4 models): PASS

`scratch/w103/gate_parity_w103.py` (adapted from harness/w53/gate_parity.py;
100 deterministic points, `default_rng(20260822)`, `standard_normal(D)*0.5`;
one .so per process). Gates: grad rel-L2 <= 1e-12 AND rel lp <= 1e-10.

| model | D | max rel lp | max grad rel-L2 | verdict |
|---|---|---|---|---|
| hier_2pl | 669 | 1.124e-14 | **1.473e-16** | PASS |
| lsat_model | 1006 | 1.547e-15 | 2.457e-16 | PASS |
| vec_bern | 2 | 3.215e-16 | 6.614e-16 | PASS |
| logistic_regression_rhs | 3075 | 0.0 (exact) | 0.0 (exact) | PASS (kernel-inert control) |

Same magnitude as W-46 (1.24e-14 / 2.37e-16) — 2+ orders inside the gate.

## Gate (b) — draws, 3-rep ESS medians within stock noise band: PASS

`scratch/w103/run_ess_w103.sh` + `analyze_ess_w103.py` (W-54/W-43 class: 3 reps
x 4 single-chain procs, seeds 20260819+1000·rep+c, warmup 1000 samples 1000
--metric-window 50, DEFAULT inits, serialized; arviz vectorized ESS, degenerate
params masked — hier_2pl's constant Omega.2.2==1 GQ gives NaN rhat in BOTH arms
equally). NOT md5-gated; md5s DO differ (FP disclosure, expected):
stock rep0 `157db21a,25347944,47faaf78,d4f36a46` vs kernel
`9e0d44a5,a4df6b05,ad7dc759,05c73179`.

| metric (min over params, med over 3 reps) | stock | kernel | stock rep band | verdict |
|---|---|---|---|---|
| hier_2pl ess_bulk | 464 | 438 | [391.1, 490.6] | in band |
| hier_2pl ess_tail | 526 | 528 | [495.4, 529.7] | in band |
| hier_2pl rhat_max | 1.0121 | 1.0118 | — | healthy |
| lsat ess_bulk | 665 | 841 | [594.6, 954.5] | in band |
| lsat ess_tail | 1305 | 1368 | [1052.3, 1399.8] | in band |
| lsat rhat_max | 1.0080 | 1.0088 | — | healthy |

lp__ traces (post-hoc via bridgestan unconstrain+log_density, jacobian=False):
hier_2pl per-rep means stock −9919.02/−9919.19/−9919.76 vs kernel
−9921.41/−9918.33/−9918.59 — arm offsets (<=2.4) are within the stock
rep-to-rep spread (0.7) x sd (27); NO systematic shift.

## Gate (c) — callgrind G reduction <= −15% on hier_2pl: PASS at −26.9%

`scratch/w103/run_callgrind_w103.sh` (W-29 protocol verbatim: warmup 100
samples 50, seed 20260819, pf init rep0/chain_0, `--metric-window 50`,
valgrind 3.23 `~/vginstall`, OMP_NUM_THREADS=1, one job at a time).

| metric | stock (bs_w53) | kernel (bs_w103_kernel) |
|---|---|---|
| total program Ir | 29,491,052,342 | 21,547,099,162 |
| grad calls (logp_grad) | 3737 + 756 = 4493 | 3737 + 756 = 4493 (IDENTICAL trajectory) |
| **Ir / grad** | **6,563,777** | **4,795,704 (−26.93%)** |
| glibc `__log1p` | 4,596,520,171 (15.59%) | ~0 (absent from profile) |
| Eigen Select/redux symbol | 2,204,589,439 (7.48%) | 0 |
| lpmf (rev inst.) self | 6,434,460,591 (21.82%) | 2,039,795,800 (9.47%) |
| `w46::fwd_avx2` | — | 2,994,415,368 (13.90%) |

Exceeds the pre-registered −15..−22% band TOP: the memo's own mechanism
(post-SoA the tape is thinner, so the untouched likelihood interior is a LARGER
relative share) applies a fortiori; the lpmf-complex absolute numbers reproduce
W-46 nearly digit-for-digit (6.434e9→2.040e9 self; fwd_avx2 2.99e9). Gate
threshold was <= −15% — PASS with the band overrun disclosed. Absolute G
(29.49e9) vs the W-59 reference 28.09e9: different driver binary (w36exp
stan_cli here vs W-59 wild_driver); arm ratio unaffected.

## Gate (d) — wall, 5 interleaved rounds, ratio <= 0.90: PASS

`scratch/w103/gate_timing_w103.py` (harness/w53/gate_timing.py with 5 outer
rounds; 50 deterministic points x 3 internal reps per subprocess; one arm per
process; `taskset -c 0-3`). LOAD FLAG (W-59 rules): no quiet window existed —
sibling agents (W-97, then W-96-era stan_cli) held 1 core at 99% throughout;
absolute us inflated, ratio is the measurement.

| pass | conditions | stock med | kernel med | ratio |
|---|---|---|---|---|
| 1 | ESS co-run + sibling | 1572.7 | 1170.8 | **0.7445 (−25.6%)** |
| 2 (cleaner) | 1 sibling core | 1183.9 | 1018.8 | **0.8605 (−13.9%)** |

Both <= 0.90. The cleaner pass sits inside the pre-registered −8..−15% wall
expectation; the loaded pass over-performed (contention asymmetry).

## Gate (e) — unit tests: PASS

On develop tree with the patch applied (applied cleanly, result md5
`2c61408a…` = the splice-built header byte-for-byte; restored after):
- `test/unit/math/prim/prob/bernoulli_logit_test.cpp` (includes shared
  `test/prob/bernoulli/bernoulli_logit_test.hpp`, theta = ±25 both cutoff
  branches): **5/5 PASSED** (log: scratch/w103/math_prim_test.log).
- Control `test/unit/math/rev/prob/bernoulli_logit_glm_lpmf_test.cpp`
  (different header, must be unaffected): **22/22 PASSED**
  (scratch/w103/math_rev_glm_test.log).
- Build env: `CXX=scratch/w46/gxx_fixed TBB_CXX_TYPE=gcc` (both needed —
  plain CXX wrapper alone trips `Need to set TBB_CXX_TYPE for non-standard
  compiler`), `/usr/bin/make -j2`, nice 19, `env -u LD_LIBRARY_PATH`.
- W-46 ulp gate re-run (`harness/w46/test_kernel.cpp`, the original W-46-era
  binary — bodies byte-identical by construction): fused sets val <= 3 ulp vs
  stock replica, partials <= 4.4e-16 rel (W-46's recorded values), island
  8.26 ns/elem vs scalar 24.13 (2.92x). The "UNIT prim" line reads 8 ulp —
  that line's reference is the GENERATING w (round-trip through log+exp adds
  ~2 argument ulps); the exact-argument measurement (dispatch_check above, and
  W-46's bench table) is the pre-registered 1.0 ulp. Disclosed.
- cpplint (optional extra): patched file adds exactly ONE finding vs pristine
  (line 161 >80 cols — the disclosed inherited `w46_exp_negabs` return, kept
  byte-identical on purpose); the other 5 findings pre-exist in stock.

## Risks/disclosures (carried from memo §6, all verified in-gate)

- **Bug-compat sign partials** (x>20 → −w without signs) replicated; gate (a)
  passing at 1e-16 level is the proof it matches stock (fixing it would break
  parity by 2·e^−ntheta on affected elements; separate upstream PR).
- FP change: draws md5 differ (expected; gate b is ESS-based).
- Scalar fallback is wall-negative (+9.4% Ir, 1.21x, W-46) — irrelevant here
  (island always engages on AVX2 machines; disclosed for upstreaming).
- Stock bundle `scratch/w53/bs_w53` UNTOUCHED (md5 `f003c78a…` re-verified at
  close); `external/math_soa` RESTORED (md5 `2954671f…`, only the 14-file SoA
  slice remains modified, as before W-103).

## Artifacts

- `scratch/w103/`: integration_memo.md, bernoulli_logit_lpmf_targetclones.patch,
  bernoulli_logit_lpmf.hpp.patched, make_patched_header.py, build_models_w103.py,
  dispatch_check.cpp/.out, gate_parity_w103.py + gate_parity_results.json,
  run_ess_w103.sh + analyze_ess_w103.py + gate_ess_results.json + ess/ (48 CSVs),
  lp_shift_w103.py, run_callgrind_w103.sh + analyze_callgrind_w103.sh +
  profile/{stock,kernel}/ (callgrind.out, ann.txt, cli.log, draws.csv),
  gate_timing_w103.py, math_prim_test.log, math_rev_glm_test.log,
  bs_w103_kernel/ (kernel-arm bundle), model_*_{stock,kernel}/ (8 .so).
