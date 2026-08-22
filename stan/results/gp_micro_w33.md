# W-33 — stan-math micro-lever ceiling on gp_regr: `pow`→`mul` in the exp-quad kernel (measured), `cholesky_decompose<var>` reverse pass (assessment)

Date: 2026-08-22. Pre-registration: WORKLOG.md W-33. Mission (from W-29 atlas
candidate #3): put numbers on the cheap stan-math patches before proposing
them upstream — the 8.9%G libm `pow` in `gp_exp_quad_cov` kernel distances,
and the cholesky reverse lambda at 17.0%G vs 9.8%G forward.

All numbers below trace to `results/profile/w33/` (this run) or
`results/profile/w29/gp_regr/` (baseline). Patch file:
`scratch/w33/pow_to_mul.patch` (pristine header kept at
`scratch/w33/square.hpp.pristine`; patched + stock .so kept in
`scratch/w33/{stock,patched}_build/`). The stan-math tree
(`~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math`) was RESTORED to
pristine after measurement (verified byte-identical to the backup).

## 1. Where the pow actually lives (source audit)

The pow is NOT in `gp_exp_quad_cov` itself. It is one line in
`stan/math/prim/fun/square.hpp`:

```cpp
template <typename T, require_arithmetic_t<T>* = nullptr>
inline double square(const T x) {
  return std::pow(x, 2);       // <-- line 28; the doc comment directly above
}                              //     says "The implementation of square(x)
                               //      is just x * x"
```

The kernel loop (`squared_distance(x[i], x[j])` → `square(diff)`, both prim
and the rev-mode `gp_exp_quad_cov` overload which computes the distances on
`value_of` data) instantiates this template. W-29 callgrind confirms the
attribution: of 33,078 executed pow calls, **32,889 come from
`gp_exp_quad_cov` = 57 per gradient** (55 kernel pairs for N=11, plus
`square(sigma)` and `square(l_val)`); the other 189 are walnutpie's Adam
optimizer (sampler-side, not stan-math). The rev callback of
`gp_exp_quad_cov` uses products only — the pow is forward-only. Two further
pow-with-2 sites exist in `stan/math/rev/fun/squared_distance.hpp` (scalar
`var` overloads, lines 24/38: `std::pow(a.val() - b.val(), 2)`) — NOT
exercised by gp_regr (its `x` is data), flagged for the upstream PR but not
patched here so the measured diff stays attributable to one line.

Patch (the whole experiment): `return std::pow(x, 2);` → `return x * x;`
One line, header-only, template — instantiated in the model TU, so a
per-model rebuild picks it up.

## 2. Gate (a) — correctness: PASS at bit-identity (stronger than the 1e-12 gate)

- 100 deterministic random unconstrained points (W-27 scheme,
  `random.Random('w33-parity-0')`): **logp max rel diff 0.0; gradients
  bit-identical on 100/100 points; zero sign flips; zero non-finite**.
  Expectation confirmed: glibc `pow` is correctly rounded and `x*x` is the
  correctly rounded square, so `pow(x,2) == x*x` exactly — measured 0, not
  just <1e-12. (On platforms with a non-correctly-rounded pow the change can
  differ by <=1 ulp — worth a sentence in the upstream PR.)
- FD spot-check (central, h=1e-5, 10 points x 3 components, patched .so):
  max rel 4.9e-8 — FD noise level, AD validated.
- **End-to-end canary**: full sampler runs (warmup 50 + samples 50, seed
  20260819, fixed init, walnutpie stan_cli) produce **md5-identical draws
  across stock and patched .so, native AND under valgrind** (all four CSVs
  `32881fbe4b02fc9b6c5665ac2867cb5a`). The patch cannot change any sampler
  behavior.

## 3. Gate (b) — cost: measured ceiling

**Callgrind Ir (deterministic; W-29 protocol: valgrind 3.23, seed 20260819,
init `inits_w27/gp_regr/rep0/chain_0.txt`, warmup 50 / samples 50, 577
gradient calls in both arms; one job at a time):**

| metric | stock | patched | delta |
|---|---|---|---|
| program Ir | 47,344,184 | 43,842,885 | −7.40% |
| logp_grad subtree G | 38,639,990 | 35,138,754 | **−9.06%** |
| **Ir / gradient** | **66,950** | **60,864** | **−6,086 (−9.09%)** |
| pow Ir (in run) | 3,473,268 | 19,923 | −3,453,345 |

The stock arm reproduces the W-29 baseline to the digit (pow Ir exactly
3,453,345; G 38.64e6 vs 38.7e6) — same-model rebuild, deterministic profile.
Residual pow in the patched arm: 19,845 Ir from walnutpie's Adam (189 calls,
sampler-side) — the model's gradient path executes zero pow.

**Wall per call (native stan_cli per-call stanza, matched protocol, 3 reps
interleaved, medians):**

| stanza | stock us/call | patched us/call | ratio |
|---|---|---|---|
| warmup (327 calls) | 6.681 | 5.820 | **0.871 (−12.9%)** |
| sampling (250 calls) | 6.655 | 5.640 | **0.848 (−15.2%)** |

Per-rep ranges do not overlap (stock 6.52–6.99, patched 5.61–5.89 across all
6 stanzas). Absolute us/call are inflated vs W-29's 5.4 (a co-running agent
job, load ~1.5); the interleaved A/B ratio is the measurement. The wall win
(13–15%) EXCEEDS the Ir share (9.1%): glibc pow's branchy double path runs
at much worse IPC than the surrounding Eigen/arithmetic code, so removing
57 calls/gradient buys more wall than instructions. A Python-driver
pair-interleaved cross-check (both .so in one process) shows the same
direction at −1.4% on Python-inflated ~13.7 us calls (overhead dilutes).

**Ceiling statement for the upstream proposal:** the one-line patch removes
6,086 Ir/gradient (9.1% of gp_regr's gradient instructions) and measures
0.83–0.87x per-call wall on this model — the full pow bucket, realized.

### Cross-model expectation (indicative, from W-29 dumps, not re-measured)

pow exclusive shares of total program Ir: gp_regr 7.33%, kronecker_gp 1.93%,
accel_gp 0.71%, diamonds 0.08%, hier_2pl below annotate threshold. gp_regr
is the extreme because its gradient is small and kernel-loop-dominated; the
same `square()` line fires in every model that squares arithmetic values
(kernels, normal-type lpdfs) — the PR should carry the gp_regr number as
the demonstrated ceiling.

### Upstream notes for the PR

1. The code contradicts its own doc comment — genuine one-line fix.
2. `square<T>` is enabled for ALL arithmetic T including `int`: `x*x`
   overflows for |int x| > 46341 where `std::pow`'s double promotion would
   not. stan-math models rarely square ints, but the PR should either note
   this or promote (`static_cast<double>(x) * static_cast<double>(x)`).
   The measurement here instantiates `double` only (bit-identity gate).
3. Same-pattern sibling sites to sweep up in the PR:
   `stan/math/rev/fun/squared_distance.hpp:24,38`
   (`std::pow(a.val() - b.val(), 2)`).
4. Bit-exactness: on glibc the patch is bit-identical (measured); on other
   libms results may shift by <=1 ulp per square.

## 4. Cholesky reverse pass — assessment (no patch; numbers from W-29 + this run, identical in both)

gp_regr's N=11 is below stan-math's size threshold, so the reverse pass is
the **unblocked Giles scalar sweep** (`internal::unblocked_cholesky_lambda`,
`stan/math/rev/fun/cholesky_decompose.hpp`; the blocked Murray lambda
switches on only at `rows() > 35`). Measured breakdown (577 gradients,
identical in the W-29 dump and both W-33 dumps — the pow patch does not
touch it):

| part | Ir (run) | Ir/grad | %G |
|---|---|---|---|
| reverse `unblocked_cholesky_lambda` (incl. chain() wrapper) | 6,718,588 | 11,643 | **17.4%** |
| forward `cholesky_decompose<var>` total | 3,787,995 | 6,565 | 9.8% |
| — of which LLT kernel (`llt_inplace::blocked` incl. unblocked recursion, 8 sub-blocks) | 2,078,354 | 3,603 | 5.4% |
| — of which var-glue (vari creation for the 66-elem L, arena matrices, chainstack emplace_back) | ~1,709,600 | ~2,963 | ~4.4% |

Ratio: reverse = 1.77x the total forward call, 3.23x the LLT kernel alone —
the W-29 "1.7x" confirmed and sharpened.

**What the 17%G actually is.** It is not a matrix adjoint multiplication
(the level-3 `transpose(L⁻¹ G L⁻ᵀ)` picture) — on this model it is a
hand-rolled O(n³) scalar double loop with two rank-1 row updates of `adjL`
per (i,j) pair and two divisions per off-diagonal. Flop accounting at n=11:
C(11,3)=165 inner triples x 4 flops + 55x(2 div + 2 flops) + 11 divisions ≈
950 flops + 121 divisions for 11,368 Ir of lambda body (~12 Ir/flop); the
forward LLT does ~443 flops for 3,603 Ir (~8 Ir/flop). The Giles recurrence
is already essentially AT its algorithmic flop floor (~2x a forward
factorization — it must both back-propagate `adjL` through L and accumulate
`adjA`); the 3.2x Ir ratio vs the LLT kernel is loop machinery and the
per-(i,j) divisions, not redundant work. The rev pass does NOT recompute
the factorization (L_A is reused from the forward), so there is no
free "reuse" patch of the kind W-32 prototyped for eigh.

**Measured ceiling of any rewrite on this size.** A perfect implementation
cannot go below ~2x forward factorization flops ≈ 2 x 3,603 Ir-equivalents ≈
7.2k Ir/grad, versus 11,643 today: the gp_regr-sized recoverable headroom is
≤ ~4.4k Ir/grad (≤ 6.6%G) — and realistically much less, because at 11x11
Eigen dispatch/GEMM fixed costs eat vectorization gains (this is exactly why
stan-math's own blocked lambda switches on only above n=35, with
`block_size = max(n/8, 8)`). Two micro-levers exist but do not clear the
bar: hoisting the shared `1/L_A(j,j)` (two divisions per off-diagonal become
one division + multiplies) is worth only ~55 divisions ≈ 1.1k Ir ≈ 1.7%G AND
breaks bit-identity (reassociation/reciprocal rounding), failing the class
of gate this project runs; the `adjL` row-major copy + `adjA` zero-init
allocations are ~160k Ir/run ≈ 0.4%G. Verdict: **no cholesky patch proposed
for the gp_regr size class** — the honest upstream targets are (a) mid-size
models (n in the 36–few-hundred range) where the BLOCKED lambda's adjoint
solves/products could be re-formulated level-3 and should be re-atlas'd on
a representative model before any PR, and (b) the 4.4%G forward var-glue,
which is the general SoA-arena/vari-pool lever W-29 already ranks as
candidate #4 (shared across all var functions, not cholesky-specific).

**Combined statement for upstream candidature:** on gp_regr, the
pow→mul one-liner delivers the full 9.1%G / 13–15% per-call win at zero
risk (bit-identical end-to-end); the cholesky reverse pass, despite being
the single largest gp_regr bucket (17.4%G), has a rewrite ceiling of ~6.6%G
at n=11 and belongs in the mid-size-N agenda instead.

## 5. Reproduction

```bash
# builds (per-variant copied .stan; default flags; env -u LD_LIBRARY_PATH)
env -u LD_LIBRARY_PATH uv run python -c "import bridgestan; \
  bridgestan.compile_model('scratch/w33/stock_build/gp_regr.stan')"    # pristine tree
# apply scratch/w33/pow_to_mul.patch to stan/lib/stan_math, then:
env -u LD_LIBRARY_PATH uv run python -c "import bridgestan; \
  bridgestan.compile_model('scratch/w33/patched_build/gp_regr.stan')"
# gates
env -u LD_LIBRARY_PATH uv run python scratch/w33/w33_gatea.py        # parity + FD
scratch/w33/w33_native_timing.sh                                     # wall us/call
env -u LD_LIBRARY_PATH OMP_NUM_THREADS=1 ~/vginstall/bin/valgrind --tool=callgrind \
  --callgrind-out-file=results/profile/w33/gp_regr_<v>/callgrind.out \
  external/walnutpie/build_e27/examples/stan_cli scratch/w33/<v>_build/gp_regr_model.so \
  data/gp_regr.json --seed 20260819 --init-file inits_w27/gp_regr/rep0/chain_0.txt \
  --warmup 50 --samples 50 --metric-window 50 --output results/profile/w33/gp_regr_<v>/draws.csv
```

Files: `results/profile/w33/gp_regr_{stock,patched}/` (callgrind.out,
ann_{exclusive,inclusive,tree}.txt, draws.csv — the two draws.csv are
md5-identical); drivers `scratch/w33/w33_gatea.py`,
`w33_gateb_time2.py` (Python-driver timing), `w33_native_timing.sh`;
patch `scratch/w33/pow_to_mul.patch`; pristine backup
`scratch/w33/square.hpp.pristine`. stan-math tree restored + verified.
