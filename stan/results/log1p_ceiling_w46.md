# W-46 — the libm log1p ceiling in the bernoulli_logit likelihood path of hier_2pl

Date: 2026-08-22/23. Pre-registration: WORKLOG.md W-46. Mission: W-34 left
the likelihood interior as the dominant block of the hier_2pl gradient
(lpmf inclusive ~58%T of the armB form; glibc `log1p` alone 19.9%T =
5.020e9 Ir, the single largest symbol). This item measures the CEILING for
replacing the glibc log1p / fusing the select machinery around it —
evidence for a stan-math packetization proposal. Measurement only; the
patched stan-math tree was restored to pristine (md5-verified) afterwards.

**Headline: the per-observation primitive is `log1p(exp(-x))` evaluated
EAGERLY for ALL N=19,200 elements (glibc, 59.2 Ir/call, 84.7M calls =
19,150/gradient), with the result discarded for |x|>20 — while the exp is
ALREADY Eigen-packetized (glibc exp = 0.02%T). A fused branch-cut kernel
(min-form `min(x,0) - log1p(exp(-|x|))`) with a peeled degree-16 Chebyshev
log1p (≤1 ulp vs glibc on the confined range [e^-20, 1]) and an AVX2+FMA
runtime-dispatch island gives −22.8% Ir/grad and −15.3% per-call wall on
the STOCK hier_2pl formulation, with gradient parity 2.4e-16 rel-L2. At
the model builds' baseline ISA (SSE2, 2-wide, no FMA) the same kernel is
wall-NEUTRAL (latency-bound) and the scalar variant is strictly worse
(+9.4% Ir, +21% wall): the ceiling is real but REQUIRES vector-width + FMA,
i.e. the upstream ask is function-multiversioned packet math inside
stan-math. BONUS FINDING: stan-math's partials for `ntheta > cutoff` have
a missing `signs` factor — a genuine (tiny) gradient sign bug for y=1
observations with logit > 20, still present in develop.**

## 1. What stan-math actually calls today (read from source + callgrind raw)

`bernoulli_logit_lpmf` (stan-math 5.3.0,
prim/prob/bernoulli_logit_lpmf.hpp) per observation, var-mode forward:

```cpp
ntheta = signs * theta_val;            // signs = 2y-1
exp_m_ntheta = exp(-ntheta);           // stan::math::exp -> v.array().exp()
                                       //   = Eigen Packet2d pexp (NOT glibc)
logp = (ntheta > 20).select(-e, (ntheta < -20).select(ntheta,
                    -log1p(e)));       // log1p = apply_scalar_unary per
                                       //   element: is_nan + check_greater_
                                       //   _or_equal + std::log1p (glibc)
partials = (ntheta > 20).select(-e,    // NOTE: no `signs` factor here —
            (ntheta >= -20).select(    //   see the upstream bug in §5
                signs * e / (e + 1), signs));
```

Facts established from the W-34 armB callgrind dump (results/profile/w34/)
and re-confirmed on the W-46 stock rebuild:

- glibc `__log1p` = 5.020e9 Ir (19.92%T armB / 13.16%T stock-form),
  **59.2 Ir/call**, plus the `w_log1p` wrapper 0.42e9 and the stan
  per-element checks (~4 Ir/elem, measured as k0−k1 in the bench).
- **84,697,422 log1p calls / 4,424 var-mode log_prob calls = 19,150 ≈ N**:
  the nested Eigen `Select`s do NOT short-circuit; `apply_scalar_unary`
  eagerly evaluates `stan::math::log1p(e[i])` for EVERY element and the
  result is discarded for |ntheta| > 20. The u = exp(−ntheta) argument
  spans (0, e^{708}] in principle; only u ∈ [e^−20, e^20] is used.
- glibc `exp` = 0.02%T (Eigen packet pexp already vectorizes it) — exp is
  NOT re-measured, per the pre-registration.
- Real x = (2y−1)·alpha_i·(theta_j − beta_i) distribution (replicated
  exactly in numpy from the model transforms; scratch/w46/extract_x.py):
  at POSTERIOR DRAWS (the sampling-phase regime): 100% in-band, |x| ≤ 15.66,
  median 1.27; at pf-init / posterior-cloud / random-unconstrained points:
  99.63–99.65% in-band, |x| ≤ 35.9–68.8. So skipping out-of-band log1p
  buys ≤0.4% of calls — the branch cuts at ±20 are already near-optimal;
  the win must come from a cheaper in-band primitive.

KEY ENABLER (checked before registering): with t = −x,
`log1p(exp(−|x|))` + `min(x,0)` reproduces the whole in-band term — ONE
log1p with argument w = exp(−|x|) ∈ [e^−20, 1] for BOTH sign branches, and
partial = w/(1+w) (x≥0) or 1/(1+w) (x<0). The primitive reduces to
log1p(w) on [2.06e-9, 1].

## 2. Kernel micro-benchmarks (scratch/w46/bench.cpp, cache-resident)

All kernels compute the fused lpmf interior (value term + partial term,
branch cuts at ±20 as in stock) on the real x sets, 19,200-element blocks
(the model's N), 9 interleaved reps, medians, taskset 0-3 (machine shared;
ratios are the measurement). Ir/elem from callgrind on the same binaries
(cb_base/cb_avx2). "prim ulp" = max |Δ|/ulp(result) vs glibc log1p on
2.2M-point grids over w ∈ [e^−20, 1] (log-spaced + uniform + boundary
points); "fused ulp" = value-term ulp vs the stock-expression replica on
the real x sets (partials ≤ 4.4e-16 rel for all exact-grade kernels).

| kernel | prim ulp | fused ulp | ns/elem base (ratio) | Ir/elem base | ns/elem avx2 (ratio) | Ir/elem avx2 |
|---|---|---|---|---|---|---|
| k0 stock replica | — | — | 17.2 (1.00x) | 132.8 | 13.3 (1.00x) | 100.2 |
| k1 std::log1p, no stan checks | — | — | 17.1 (1.01x) | 129.0 | 13.3 (1.00x) | 96.3 |
| k2 branch-cut, glibc, skip OOB | — | **bit-identical** | 16.0 (1.08x) | 121.3 | 12.4 (1.07x) | 98.5 |
| k3 fused scalar min-form, glibc | — | 2 | 15.7 (1.09x) | 132.7 | 12.1 (1.10x) | 104.7 |
| k4 Kahan-corrected packet plog | **1.0** | 3 | 16.9 (1.02x) | 105.0 | **6.0 (2.20x)** | 32.6 |
| k5 peeled Chebyshev deg-16 | **1.0** | 3 | 20.2 (0.85x) | 101.2 | **6.9 (1.92x)** | 32.1 |
| k5b Chebyshev deg-13 | 4.0 | 4 | 17.9 (0.96x) | 95.6 | 6.1 (2.19x) | 30.0 |
| k7 Eigen generic_plog1p (exists!) | 2.0 | 3 | 17.5 (0.98x) | 109.7 | 6.4 (2.09x) | 33.5 |
| k8 Chebyshev deg-10 (APPROX) | 3146 (~2e-13 abs) | 3143 | 15.9 (1.08x) | 90.0 | 5.1 (2.59x) | 28.0 |

Supporting numbers: bare glibc `std::log1p` = 3.6 ns/call (L1-resident);
the stan wrapper tax (is_nan + check) = ~4 Ir/elem ≈ 0 ns (predicted
branches hide under the PLT call); the degree-16 fit error on the peeled
tail S(u) = 2^-60 (mpmath, scratch/w46/fit_log1p.py — log1p(w) =
anchor + u − u²/2 + u³·S, range-reduced at w = 0.5 so the polynomial only
ever sees u ∈ [0, 0.5]).

Readings:
- **At the baseline ISA nothing beats stock on wall** — the 2-wide packet
  kernels are instruction-lighter (−24% Ir) but latency-bound (two packet
  divisions + long dependency chains), and the scalar variants only win
  the discarded-call skip (~8%). glibc's correctly-rounded scalar log1p is
  genuinely good at SSE2.
- **Under AVX2+FMA the packet kernels are 1.9–2.2x** (fused, both outputs);
  the interior Ir drops 3.1x (100→32 Ir/elem). The cheap Eigen option
  (generic_plog1p) also clears 2 ulp and 2.09x — stan-math could get most
  of this just by using Eigen's existing packet log1p in a fused kernel.
- The approximate arm (deg-10, ~3000 ulp = 2e-13 abs) only reaches 2.59x —
  accuracy is cheap here; no reason to accept it (NOT tested at model
  level; the pre-registered conditional arm was not exercised).
- SLEEF: not vendorable trivially (no single-header distribution, not
  installed) — skipped, as pre-registered.

## 3. Model-level measurement (the ceiling, on the stock formulation)

Patch (scratch/w46/bernoulli_logit_lpmf.hpp.patched; pristine backup +
md5 in scratch/w46/): the two `Select` expressions replaced by one fused
kernel `w46_kern::dispatch` — scalar path for any CPU, plus a
`#pragma GCC target("avx2,fma")` island with runtime
`__builtin_cpu_supports("avx2")` dispatch (Cephes exp transcribed from
Eigen's pexp_double with the pldexp 4-factor 2^k split, deg-16 poly log1p,
branchless blendv selects). Measurement-only code, not upstream-ready.

Builds (per-variant dirs, W-27 cache gotcha; default CXXFLAGS; env -u
LD_LIBRARY_PATH; /usr/bin/make -j2). TOOLCHAIN NOTE: the system g++ driver
lost its internal search paths mid-session (fresh GCC 16.2.1 package,
self-identifies as a ZCode AppImage); worked around with the
scratch/w46/gxx_fixed wrapper (restores -B and the stdlib include paths;
compiler identity unchanged). Continuity proof: the rebuilt STOCK .so is
**bit-identical to W-34's stock build** on 20 random points (lp and full
gradients) — all comparisons below are like-for-like.

Three arms: stock / patched (island active on this Zen3 machine) /
patched_base (scalar path forced).

- **Gate (a) parity** (50 random + 50 posterior-cloud unconstrained
  points, maxima): island max rel lp **1.24e-14**, max grad rel-L2
  **2.37e-16**; base 3.7e-16 / 2.45e-16. PASS (≤1e-12, pre-registered).
  (k2-style bit-identity is available in principle but was not the
  model arm; the fused min-form reorders the x<0 branch at ulp level.)
- **Gate (b) wall** (100 identical cloud points, 3 interleaved reps,
  medians, taskset; absolute values inflated by co-running agents):
  stock 1261.4 → island **1068.8 µs/call (0.847x, −15.3%)**; base
  1521.0 µs (1.206x — the scalar arm is a NEGATIVE result: packetization
  is essential).
- **Gate (b) callgrind** (W-29 protocol: warmup 100 + samples 50, seed
  20260819, pf init rep0/chain_0, one job at a time; IDENTICAL workload
  3737+756 = 4493 gradient calls in all three arms):

| metric | stock | island | base |
|---|---|---|---|
| total program Ir | 34.92e9 | **26.98e9 (−22.7%)** | 38.19e9 (+9.4%) |
| Ir / gradient | 7.772e6 | **6.004e6 (−22.8%)** | 8.500e6 |
| glibc __log1p + wrapper | 4.60e9 + 0.42e9 | ~0 | ~0 |
| Select/redux symbol | 2.20e9 (6.31%) | 0 | 0 |
| fused kernel (fwd_avx2 / log1p_poly) | — | 2.99e9 (11.10%T) | 7.76e9 (20.31%T) |
| lpmf exclusive (rest) | 6.43e9 | 2.04e9 | 5.33e9 |

  The whole replaced complex {glibc log1p + wrapper + select/redux +
  partials machinery + exp array pass} ≈ 13.7e9 Ir → ~5.0e9. Stock
  reproduces W-34 digit-for-digit to 0.35% (7.772M vs 7.745M Ir/grad —
  rebuild codegen drift). Draws: md5 differs across arms (ulp-level
  gradient differences; same 4493-call trajectory workload), as expected.
- Two kernel bugs were caught by the gates and fixed before any reported
  number: (i) the island's pldexp used TWO 2^b factors instead of Eigen's
  THREE (error = 2^b; visible as a 2x scale error at the fx knee and 2^15
  at |x|≈39) — caught by the 50-point parity gate failing at 14%; (ii)
  hand-transcribed polynomial coefficients were stale (caught by the
  unit-test ulp check, fixed by regenerating from the mpmath output).

**Ceiling statement**: replacing the lpmf interior with a correct ≤1-ulp
packetized kernel is worth **−22.8% Ir/grad / −15.3% wall on the STOCK
formulation of hier_2pl**. On the W-34 armB (GEMM) formulation the
likelihood interior is a LARGER fraction (58.4%T vs 42.5%T), so the same
kernel is worth proportionally more there (the log1p complex alone was
19.9%T of armB). This is on top of the −28% from the plumbing fix — the
two levers are independent and compose.

## 4. What stan-math could adopt (the upstream proposal)

1. **Fuse + packetize the bernoulli_logit forward kernel.** The measured
   primitive need is log1p(w) on w ∈ [e^−20, 1] (after the softplus
   identity `log1pexp(x) = min(x,0) + log1p(exp(−|x|))` folds both sign
   branches and keeps the argument ≤ 1). A peeled deg-16 Chebyshev (or
   Kahan-corrected packet log — or even Eigen's existing generic_plog1p,
   2 ulp) delivers ≤1–2 ulp vs glibc, and one fused pass computing value +
   partials removes the eager full-array log1p, both Select passes, and
   the separate partials expression: −22.8% Ir/grad on hier_2pl.
2. **The win requires AVX2+FMA at the kernel level.** At the default
   baseline ISA the same kernel is wall-neutral (2-wide, latency-bound,
   no FMA) and scalar is worse. stan-math builds baseline by design
   (portability; W-27 additionally showed global -march=native miscompiles
   Eigen GEMM paths on this toolchain) — but a contained
   `#pragma GCC target("avx2,fma")` island with `__builtin_cpu_supports`
   runtime dispatch inside one header is exactly the
   function-multiversioning pattern libm/VML/SLEEF-using libraries
   already ship. That is the concrete ask: multiversioned packet math
   kernels for the hot lpmf interiors (bernoulli_logit first: the IRT/
   rating class all funnel through it).
3. **Fix the partials sign bug** (§5) in the same PR — one line.
4. **Do not chase exp**: already Eigen-packetized (0.02%T); and do not
   chase the out-of-band skip: 99.6–100% of calls are in-band on real
   data (the ±20 cuts are already right); and the stan log1p wrapper
   checks are ~free (~4 Ir/elem). glibc log1p itself (59.2 Ir/call,
   branchy, correctly-rounded) is the entire cost.

## 5. BONUS upstream finding: missing `signs` factor in the ntheta>cutoff partials

The edge partials are
`(ntheta > cutoff).select(-exp_m_ntheta, (ntheta >= -cutoff).select(signs * e/(e+1), signs))`.
Derivation: value(ntheta) for ntheta>20 is −exp(−ntheta), so
d lp/d theta = signs · d/dntheta = signs · (+exp(−ntheta)) — the first
branch should be `signs * exp_m_ntheta`, not `-exp_m_ntheta`. As written
it is correct only for y=0 (signs=−1); for **y=1 observations with
ntheta > 20 (logit > 20) the partial has the wrong sign** (error 2·e^−ntheta
≤ 4e-9 per element). Still present in stan-math develop (checked
2026-08-23). Numerically negligible in most uses (that is presumably why
it survived), but it is a correctness bug, trivially fixable, and it was
found BECAUSE the W-46 parity harness was tight: the first patched build
differed from stock by exactly 2·e^−ntheta on the affected elements
(max |Δpartial| 4.08e-9 at ntheta=20.011), which propagated to
max 1.4e-6 absolute (5e-10 relative) on alpha-gradients at wild random
points. The final patched kernel is bug-COMPATIBLE (replicates the stock
partial) so the measured arms isolate the performance effect; the
bug-correcting change is a separate one-line upstream PR.

## 6. Reproduction

```
# x distribution (real ntheta values from the model):
env -u LD_LIBRARY_PATH uv run python scratch/w46/extract_x.py
# polynomial fit (mpmath):
env -u LD_LIBRARY_PATH uv run --with mpmath python scratch/w46/fit_log1p.py
# micro-bench (baseline + avx2 builds) + unit tests of the model kernel:
cd scratch/w46 && SM=$HOME/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math
./gxx_fixed -O3 -std=c++17 -I$SM -I$SM/lib/eigen_3.4.0 -I$SM/lib/boost_1.87.0 \
  -I$SM/lib/tbb_2020.3/include -I$SM/lib/sundials_6.1.1/include bench.cpp -o bench_base
./gxx_fixed -O3 -std=c++17 -mavx2 -mfma <same includes> bench.cpp -o bench_avx2
env -u LD_LIBRARY_PATH taskset -c 0-3 ./bench_base   # and ./bench_avx2
# model builds (g++ driver workaround + TBB_CXX_TYPE, see §3):
env -u LD_LIBRARY_PATH CXX=<abs>/scratch/w46/gxx_fixed TBB_CXX_TYPE=gcc \
  BRIDGESTAN=$HOME/.bridgestan/bridgestan-2.9.0 MAKEFLAGS=-j2 \
  uv run python -c "import bridgestan; bridgestan.compile_model('scratch/w46/<arm>_build/hier_2pl.stan')"
# wall gate:
env -u LD_LIBRARY_PATH taskset -c 0-3 uv run python scratch/w46/w46_timing.py
# callgrind (W-29 protocol): results/profile/w46/{stock,patched,patched_base}/
```

Artifacts: this file; results/profile/w46/ (callgrind.out, cli.log,
draws.csv per arm); harness/w46/ (scripts + kernel sources, committed);
scratch/w46/ (builds, .so files, patched + pristine headers, bench
binaries, x_*.npy, untracked). stan-math tree RESTORED (md5
f003c78a165c2be67ce22b30c046c0e2 verified). walnutpie untouched; no pushes.
