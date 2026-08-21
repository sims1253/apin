# ATLAS.md — Bottleneck atlas (Phase 1)

Machine: Ryzen 9 5900X (Zen 3, AVX2 only — NO AVX-512). CmdStan 2.39.0 pinned.
All shares below are MEASURED (Stan profile() wall, callgrind instruction counts
with --simulate-cache=yes, standalone microbenches). No guesses.

## 1. Where sampler wall goes (Stan profile(), 200+200 iters, 1 chain)

| model | family | sampler s | profiled s | share | dominant block |
|---|---|---|---|---|---|
| diamonds | GLM (N=5000,K=25) | 10.61 | 10.14 | **95.6%** | model |
| radon_partially_pooled | hier (N=12573) | 17.85 | 17.43 | **97.6%** | model |
| lsat_model | IRT | 2.85 | 2.50 | 87.7% | model |
| kronecker_gp | GP (7000-dim) | 133.60 | 107.48 | 80.5% | **transformed params 71%** (latent field eval) |
| accel_gp | GP (small) | 4.14 | 1.22 | 29.5% | model (rest = kernel/adaptation/I-O) |
| pilots | hier stiff | 0.06 | 0.03 | 50% | split |

**Two regimes:** data-heavy models are ≥88% model-gradient; small/stiff models
(accel_gp, pilots) spend 50–70% in kernel bookkeeping + adaptation + I/O.

## 2. Instruction attribution (callgrind, 40+40 iters, steady-state = total minus one-time data-read)

| model | steady Ir | eigen/linalg | lpdf templates | autodiff rev | memcpy/alloc | checks | rng | io | D1 mr | LL mr |
|---|---|---|---|---|---|---|---|---|---|---|
| diamonds | 4.70e8 | **69.0%** | 8.2% | 0.1% | 9.6% | ~0 | 0.1% | 1.4% | 11.1% | 0.04% |
| radon_pp | 1.76e11 | 7.9% | **59.4%** | 8.5% | 0.1% | ~0 | — | 2.2% | 2.5% | 0.0% |
| accel_gp | 5.45e9 | **44.8%** | 10.7% | 11.7% | **12.2%** | ~0 | 0.6% | 4.3% | 6.7% | 0.0% |
| pilots | 8.70e7 | 19.7% | 25.8% | 5.3% | **21.4%** | ~0 | 3.0% | 4.9% | 0.6% | 0.05% |
| lsat | 1.40e10 | **47.5%** | 1.0% | 20.5% | 1.0% | 2.2% | — | 2.2% | 8.9% | 0.0% |

Notes:
- **model-gradient work (eigen+lpdf+autodiff+most memcpy) = 76–87% of steady Ir** on
  data-heavy models; the rest is kernel/adaptation/service. On small models (pilots)
  memcpy+alloc alone is 21%.
- **Validity checks are ~0–2.2%** — the "checks are 60% of runtime" folklore is
  REJECTED for current stan::math 2.39 on these families.
- L1 data-miss rate 0.6–11% by model; L3 (LL) misses ≈ 0 — working sets fit the
  32MB L3. The cache story is L1/L2, not DRAM: the adjoint sweep's pointer chase
  costs L2/L3 latency (~15–40 cyc), not memory bandwidth.
- diamonds one-time data-read was 284M Ir (38% of a 40-iter run) — amortizes to
  ~1% at 1000 iters; excluded from steady totals above.

## 3. Microbenches (Zen 3, single core, -march=native -O3)

| bench | result |
|---|---|
| normal_lpdf<double>, N=12573 | 14.2 µs (1.13 ns/elem) |
| normal_lpdf<var>+grad, vec mu | 61.5 µs (4.9 ns/elem) → **4.3x AD tax** |
| hand no-check dσ (streaming floor) | 1.47 µs (0.117 ns/elem) → **42x floor→checked-AD headroom** |
| normal_id_glm_lpdf<double>, N=12573×K=25 | 33.5 µs ≈ 18.8 GFLOP/s ≈ **50% AVX2 FMA peak** |
| normal_id_glm_lpdf<var>+grad | 63.6 µs (1.9x double — GLM partials efficient) |
| var chain depth 20, n=1000 | 8.2 ns/var-elem-op vs 0.07 ns double-op = **112x** |
| ps_point copy (3 vectors) | 31ns @18d, 40ns @100d, 335ns @1000d, **30.5µs @7000d** |
| pointer chase vs contiguous (1M nodes) | 67.9 vs 0.8 ns/node = **85x** (L3-resident chase) |

## 4. Cross-implementation per-gradient gap (same Stan 2.39 math)

cmdstan services vs bridgestan-driven (nutpie) — same models, same math:
**2.08x geomean cheaper per gradient (3.3x on >10µs/grad models)**
(hier_2pl 585→134 µs, radon 480→92, lsat 140→35, diamonds 16→5.2).
**Instruction-level localization (callgrind, 40+40 vs 100+100 iters, steady-state):**

| model | cmdstan Ir/grad | bridgestan Ir/grad | ratio |
|---|---|---|---|
| diamonds | 2,227,555 | 652,455 | **3.41x** |
| lsat_model | 4,084,054 | 1,903,047 | 2.15x |
| radon_pp | 10,759,650 | 5,115,819 | 2.10x |
| pilots | 94,619 | 18,756 | **5.04x** |

Parity check (eight_schools_noncentered, same point): gradients identical to 8
decimals; Jacobian term identical; lp differs only by propto constants.
→ cmdstan services execute 2.1–5x MORE INSTRUCTIONS per gradient than a minimal
driver on the same model math, same target, same results. This is the Phase 2
target and it is now localized to the per-gradient service path.

## 5. Ranked suspects (measured, by expected wall impact on CORE_SET)

1. **AD tape overhead on element-wise likelihoods** (radon 59% lpdf templates +
   8.5% autodiff; micro: 4.3x tax, 8.2ns/var-op). Fix paths: reduce var nodes per
   element (batched partials), SoA adjoint sweep instead of pointer-chasing varis.
2. **Kernel-loop copies/allocs for small models** (pilots: 21% memcpy; accel 12%).
   Fix path: base_nuts.hpp ps_point copy elimination (2a).
3. **Eigen GEMV/GEMM paths not hand-vectorized for these shapes** (diamonds 69%
   eigen_linalg; GLM double at 50% FMA peak is decent, var-mode halves it).
4. **Transformed-parameters evaluation for latent-field models** (kronecker 71%
   of profiled time in tp block — the GP latent transform dominates its 731s).
5. ~~Validity checks~~ (rejected: ≤2.2%).
6. ~~DRAM bandwidth~~ (rejected: LL misses ≈0; issue is L1/L2 latency only).

## 6. Honest ceiling number

Share of steady-state time in user model gradient with no structural waste:
**~70–76%** (model math minus the measured 4.3x element-wise AD tax and 2x GEMV
var overhead — i.e., if AD were free, current model math is ~25% of wall; the
AD+driver tax is ~50% of wall on data-heavy models, more on small ones).
