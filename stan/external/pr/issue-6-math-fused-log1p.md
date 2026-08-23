# Proposal: fused, packetized value+partials kernel for bernoulli_logit_lpmf (−22.8% Ir/gradient, −15.3% wall on a test model)

This is a design proposal, not a PR. It comes with measurements and a
working reference implementation that I can attach or turn into a PR.

## Problem: what the lpmf runs today

Per observation in var mode (`ntheta = signs·theta`, cutoff 20), the
generated expression tree is:

```cpp
exp_m_ntheta = exp(-ntheta);                  // Eigen packet exp (fast)
logp     = (ntheta > 20).select(-exp_m_ntheta,
             (ntheta < -20).select(ntheta, -log1p(exp_m_ntheta)));
partials = (ntheta > 20).select(-exp_m_ntheta,
             (ntheta >= -20).select(signs*exp_m_ntheta/(exp_m_ntheta+1), signs));
```

`log1p` here is `apply_scalar_unary`: a per-element wrapper (nan check,
domain check, then glibc `std::log1p`). The nested Eigen `Select`s do not
short-circuit. So the code calls log1p for every one of N elements and
throws the result away whenever |ntheta| > 20.

I measured this on a hierarchical 2PL IRT model (N = 19,200):
84,697,422 log1p calls over 4,424 var-mode log_prob calls. That is about
one log1p per observation per gradient. glibc `__log1p` (59.2 Ir per call,
correctly rounded, branchy) is the largest symbol in the program: 13.2% of
all instructions in the stock formulation, 19.9% in a GEMM-formulated
variant. The Select and redux machinery around it costs another 6.3%.

Skipping the out-of-band elements does not help. On real data the in-band
fraction is 99.63–100% (posterior draws all have |x| ≤ 15.66; even wild
random points are 99.6% in-band). And `exp` is already packetized (0.02%
of instructions). The only lever left is a cheaper in-band log1p, with the
surrounding machinery fused into one pass.

## The math

With `t = |ntheta|` and the softplus identity

```
log1pexp(x) = min(x, 0) + log1p(exp(−|x|))
```

the in-band value term reduces to one log1p with a confined argument:

```
value   = min(ntheta, 0) − log1p(w),     w = exp(−|ntheta|) ∈ [e^−20, 1]
partial with respect to ntheta:
        w / (1 + w)   if ntheta ≥ 0
        1 / (1 + w)   if ntheta < 0
```

So the primitive needed is `log1p(w)` on w ∈ [2.06e-9, 1] — a closed,
modest interval. Value and partial both follow from `w` and one
`log1p(w)`. One fused pass over the array can produce both, and the eager
full-array log1p, both Select passes, and the separate partials expression
all disappear.

On that interval, cheap kernels reach 1–2 ulp against glibc (measured on
2.2M-point grids):

- a degree-16 Chebyshev/minimax polynomial with range reduction at w = 0.5,
  so the polynomial only sees u ∈ [0, 0.5] (tail error 2^-60);
- a Kahan-corrected packet `log1p(u) = plog(1+u) + m/(1+u)` with the
  FastTwoSum correction `m = ((1+u) − 1) − u`;
- or Eigen's existing `generic_plog1p` packet function (2 ulp). This last
  one needs no new numerics at all and may be the right first step.

## Evidence

Kernel micro-benchmarks, on the real per-observation argument distribution
from the model (19,200-element blocks, 9 interleaved reps, medians; Ir per
element from callgrind on the same binaries):

| kernel | ulp vs glibc | ns/elem SSE2 | ns/elem AVX2+FMA | Ir/elem AVX2 |
|---|---|---|---|---|
| stock replica | — | 17.2 (1.00x) | 13.3 (1.00x) | 100.2 |
| Kahan-corrected packet plog | 1.0 | 16.9 (1.02x) | 6.0 (2.20x) | 32.6 |
| Chebyshev deg-16 packet | 1.0 | 20.2 (0.85x) | 6.9 (1.92x) | 32.1 |
| Eigen `generic_plog1p` | 2.0 | 17.5 (0.98x) | 6.4 (2.09x) | 33.5 |

The SSE2 result is the crux. At stan-math's baseline ISA the packet
kernels use 24% fewer instructions but run latency-bound: 2-wide packets,
no FMA, two packet divisions on the critical path. Wall time does not
improve. The win needs vector width plus FMA. A scalar fused kernel is
worse at every ISA (+9.4% Ir at model level).

Model-level ceiling, with the fused kernel replacing the whole lpmf
interior behind runtime dispatch (hier_2pl stock formulation, matched
protocol, medians of 3, identical 4493-gradient workload in every arm):

| metric | stock | fused, AVX2+FMA island | fused, scalar forced |
|---|---|---|---|
| Ir / gradient | 7.772e6 | 6.004e6 (−22.8%) | 8.500e6 (+9.4%) |
| total program Ir | 34.92e9 | 26.98e9 (−22.7%) | 38.19e9 |
| µs / logp_grad call | 1261.4 | 1068.8 (−15.3%) | 1521.0 (1.206x) |
| glibc `__log1p` + wrapper | 5.02e9 Ir | ~0 | ~0 |
| parity, 100 points | — | lp 1.24e-14 rel, grad 2.37e-16 rel-L2 | 3.7e-16 / 2.45e-16 |

The replaced complex (glibc log1p, wrapper, select/redux, partials
machinery, exp array pass) drops from about 13.7e9 to about 5.0e9 Ir. On
the GEMM-formulated variant the likelihood interior is a larger share of
the program (58.4% vs 42.5%), so the same kernel is worth more there. The
two changes compose.

## The ask: function multiversioning inside stan-math

stan-math builds baseline by design, and global `-march=native` is not an
option for Stan models: on degenerate-spectrum models any FP reordering
moves gradients by O(1) (see the companion issue about eigenvector
adjoints). The contained pattern that gets the win without touching global
codegen:

- one kernel function marked `#pragma GCC target("avx2,fma")` — compiled
  with the wide ISA no matter what flags the translation unit uses — plus
  a plain scalar fallback;
- one runtime dispatch per array, `__builtin_cpu_supports("avx2")`;
- inside the island, only the confined-range polynomial arithmetic. No
  Eigen template machinery, no reordering of anything outside the kernel.

This is the standard multiversioning pattern used by libm, VML, and SLEEF.
bernoulli_logit is the natural first target because the IRT and rating
model class all pass through it. The same shape fits any lpmf whose
interior is elementwise with branch cuts.

## Reference implementation

I have a complete working reference: Cephes-style `exp` transcribed from
Eigen's `pexp_double` with the 3-factor `pldexp` split, degree-16
polynomial log1p, branchless blends, scalar and island paths, and the
parity and timing gates that validated it. Every number above comes from
it. Two kernel bugs the gates caught during development (a 2-factor
instead of 3-factor `pldexp` split; stale polynomial coefficients) are
documented with their gate signatures — a useful precedent for the test
harness such a kernel needs: ulp grids on the confined range, plus
model-level parity against the expression-tree form.

## Related

- The `(ntheta > cutoff)` partials branch is also missing a `signs`
  factor. That is a separate one-line correctness fix, filed as its own PR.
- Eigen's `generic_plog1p` (2 ulp) is a zero-new-numerics starting point
  worth benchmarking first.

## References

- glibc `log1p` (correctly rounded) — the accuracy baseline for all
  kernels above.
- SLEEF and Eigen packet math — prior art for ulp-bounded packet
  transcendental kernels.
- Muller et al., *Handbook of Floating-Point Arithmetic* — range reduction
  and polynomial evaluation (FastTwoSum, minimax).
- Kernel ulp grids, micro-bench data, and model-level gates:
  https://github.com/sims1253/apin (`stan/results/`, `stan/WORKLOG.md`),
  or ask and I will attach them.
