# Proposal: fused, packetized value+partials kernel for bernoulli_logit_lpmf — measured −22.8% Ir/gradient, −15.3% wall (AVX2+FMA runtime dispatch)

**Scope:** design proposal with measured evidence and a working reference
implementation (available on request). Not a PR — the kernel sketch below
is complete enough to re-implement independently.

## Problem: what the lpmf executes today

Per observation (var-mode forward, `ntheta = signs·theta`, cutoff 20), the
generated expression tree is:

```cpp
exp_m_ntheta = exp(-ntheta);                  // Eigen packet exp (fast)
logp     = (ntheta > 20).select(-exp_m_ntheta,
             (ntheta < -20).select(ntheta, -log1p(exp_m_ntheta)));
partials = (ntheta > 20).select(-exp_m_ntheta,
             (ntheta >= -20).select(signs*exp_m_ntheta/(exp_m_ntheta+1), signs));
```

`log1p` here is `apply_scalar_unary` — a per-element wrapper
(`is_nan` check + domain check + glibc `std::log1p`) — and **the nested
Eigen `Select`s do not short-circuit**: the log1p is evaluated eagerly for
ALL N elements and its result discarded for `|ntheta| > 20`. Measured on a
hierarchical 2PL IRT model (N = 19,200): **84,697,422 log1p calls /
4,424 var-mode log_prob calls = 19,150 ≈ N per gradient**; glibc
`__log1p` (59.2 Ir/call, correctly rounded, branchy) is the single largest
symbol in the program — 13.2% of total instructions in the stock
formulation (19.9% in the GEMM-formulated variant), plus the Select/redux
machinery around it (6.3%) and the separate partials pass.

Two facts close the remaining doors: the out-of-band skip is worthless on
real data (in-band fraction 99.63–100%: posterior draws are 100% in-band
with |x| ≤ 15.66; even wild random-unconstrained points are 99.6%+), and
`exp` is already Eigen-packetized (0.02%T). **The only remaining lever is
a cheaper in-band log1p and fusing the machinery around it.**

## The math (derivation of the fused kernel)

With `t = |ntheta|` and the softplus identity

```
log1pexp(x) = min(x, 0) + log1p(exp(−|x|))
```

the entire in-band value term collapses to **one** log1p whose argument is
confined:

```
value   = min(ntheta, 0) − log1p(w),     w = exp(−|ntheta|) ∈ [e^−20, 1]
partial(with respect to ntheta):
        w / (1 + w)   if ntheta ≥ 0
        1 / (1 + w)   if ntheta < 0
```

i.e. the primitive need is `log1p(w)` on **w ∈ [2.06e-9, 1]** — a closed,
modest interval. Both outputs (value and partial) come from `w` and one
`log1p(w)`, so a single fused pass over the array can compute value +
partials together, eliminating the eager full-array log1p, both Select
passes, and the separate partials expression.

On that interval, cheap exact-grade kernels are available (all measured at
≤1–2 ulp vs glibc on 2.2M-point grids):

- a peeled degree-16 Chebyshev/minimax polynomial with range reduction at
  w = 0.5 (so the polynomial only sees u ∈ [0, 0.5]; tail-error 2^-60);
- a Kahan-corrected packet `log1p(u) = plog(1+u) + m/(1+u)` with
  `m = ((1+u) − 1) − u` exact (FastTwoSum);
- or simply Eigen's existing `generic_plog1p` packet function (2 ulp) —
  stan-math could get most of the win with no new numerics at all.

## Evidence

**Kernel micro-benchmarks** (real per-observation argument distribution
extracted from the model; 19,200-element blocks; 9 interleaved reps,
medians; Ir/elem from callgrind on the same binaries):

| kernel | prim ulp vs glibc | ns/elem SSE2 (ratio) | ns/elem AVX2+FMA (ratio) | Ir/elem AVX2 |
|---|---|---|---|---|
| stock replica | — | 17.2 (1.00x) | 13.3 (1.00x) | 100.2 |
| Kahan-corrected packet plog | 1.0 | 16.9 (1.02x) | **6.0 (2.20x)** | 32.6 |
| Chebyshev deg-16 packet | 1.0 | 20.2 (0.85x) | **6.9 (1.92x)** | 32.1 |
| Eigen `generic_plog1p` | 2.0 | 17.5 (0.98x) | **6.4 (2.09x)** | 33.5 |

**The SSE2 caveat (the crux of the proposal):** at stan-math's baseline
ISA the packet kernels are instruction-lighter (−24% Ir) but
**latency-bound** — 2-wide packets, no FMA, two packet divisions on the
critical path — so wall time does not improve (1.02x / 0.85x). The win
requires **vector width + FMA**. A scalar fused kernel is strictly worse
at any ISA (+9.4% Ir measured at model level).

**Model-level ceiling** (the fused kernel replacing the whole lpmf
interior, runtime-dispatched, hier_2pl stock formulation, matched
protocol, medians of 3; identical 4493-gradient-call workload in all
arms):

| metric | stock | fused (AVX2+FMA island) | fused (scalar forced) |
|---|---|---|---|
| Ir / gradient | 7.772e6 | **6.004e6 (−22.8%)** | 8.500e6 (+9.4%) |
| total program Ir | 34.92e9 | **26.98e9 (−22.7%)** | 38.19e9 |
| µs / logp_grad call | 1261.4 | **1068.8 (−15.3%)** | 1521.0 (1.206x) |
| glibc `__log1p` + wrapper | 5.02e9 Ir | ~0 | ~0 |
| parity (100 points) | — | lp max rel **1.24e-14**, grad max rel-L2 **2.37e-16** | 3.7e-16 / 2.45e-16 |

The whole replaced complex (glibc log1p + wrapper + select/redux +
partials machinery + exp array pass) drops from ≈13.7e9 to ≈5.0e9 Ir.
On the GEMM-formulated variant of the model the likelihood interior is a
larger fraction still (58.4%T vs 42.5%T), so the same kernel is worth
proportionally more there; the two levers compose.

## The design ask: function-multiversioned packet math inside stan-math

stan-math builds baseline by design (portability), and global
`-march=native` is not an option for Stan models — beyond policy, on
degenerate-spectrum models any FP reordering moves gradients O(1) (see the
companion issue about eigenvector adjoints; same session's finding). The
contained pattern that gets the win without touching global codegen:

- one header-local kernel function marked
  `#pragma GCC target("avx2,fma")` (an "island": compiled with the wide
  ISA regardless of the TU's flags), plus a plain scalar fallback;
- runtime dispatch once per array via `__builtin_cpu_supports("avx2")`;
- the island contains only the confined-range polynomial arithmetic —
  no Eigen template machinery, no reordering of anything outside the
  kernel.

This is the standard function-multiversioning pattern libm/VML/SLEEF-using
libraries ship. bernoulli_logit is the natural first target — the IRT /
rating model class funnels through it — but the same shape applies to any
lpmf whose interior is elementwise with branch cuts.

## Reference implementation

A complete working reference (Cephes-style `exp` transcribed from Eigen's
`pexp_double` with the 3-factor `pldexp` split, degree-16 polynomial
log1p, branchless blends, scalar + island paths, plus the parity/timing
gates that validated it) exists and was used for every number above;
happy to attach it or open a PR against a preferred design. Two kernel
bugs the gates caught during development (a 2-factor instead of 3-factor
`pldexp` split; stale polynomial coefficients) are documented with their
gate signatures — useful precedent for the test harness any such kernel
needs (ulp grids on the confined range + model-level parity vs the
expression-tree form).

## Related

- The `(ntheta > cutoff)` partials branch also has a missing `signs`
  factor — a separate one-line correctness fix, filed as its own PR.
- Eigen's `generic_plog1p` (2 ulp) is a zero-new-numerics starting point
  worth benchmarking first.

## References

- glibc `log1p` (correctly rounded) — the accuracy baseline all kernels
  above were measured against.
- SLEEF's and Eigen's packet math functions — prior art for
  ulp-bounded packet transcendental kernels.
- Muller et al., *Handbook of Floating-Point Arithmetic* — range
  reduction / polynomial evaluation methodology (FastTwoSum, minimax).
- Internal evidence trail: our benchmark repo `results/log1p_ceiling_w46.md`
  (W-46) — kernel ulp grids, micro-bench table, model-level gates, and the
  honest SSE2 negative result. Happy to attach.
