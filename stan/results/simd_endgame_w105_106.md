# W-105/105b/106 — the SIMD endgame: uniform AVX2 builds, the corrected gates, the full-grid lift, and the ALL-LAYERS stack vs true stock

Dates: 2026-08-28. Pre-registrations: W-105 (FD tripwire design), W-105b
(corrected: FD on well-posed models + cross-arm symmetry for the known-
degenerate kronecker), W-106 (conditional endgame). Arms: scratch/w105/
bs_stock (SoA base, default flags) vs bs_avx2 (same + CXXFLAGS="-mavx2
-mfma", uniform per make invocation); all-layers = bs_w53 (SoA+gather) +
the W-103 kernel header + -mavx2 -mfma; true-stock = pristine bundle,
default flags. Walnutpie binary read-only; main-dialect CLI args.

## The gate story

W-105 aborted at its registered FD tripwire on kronecker_gp — correctly
for the gate AS DESIGNED: the stock arm fails identically (19/19 pts,
max 6.85e-2 vs avx2 5.73e-2, same throw), i.e. the KNOWN W-35
eigenvector-adjoint FD-inconsistency, not an ISA effect. W-105b's
corrected instrument: FD 4/4 well-posed models PASS (2.5e-10..3.6e-9);
kronecker logp cross-arm symmetry 2.19e-16 (machine epsilon, PASS); its
grad asymmetry (median 2.4e-3) classified not-avx2-only (healthy models
BIT-IDENTICAL across arms at the same points; kronecker's per-component
pattern = the W-35 ~1e12x amplification of a 2e-16 seed). ESS 9/10
in-band with the single trip FAVORABLE (avx2 above stock's band). Wall
(diamonds/hier_2pl): −20.7%/−11.1%. VERDICT: GREEN, no avx2-adverse
measurement on any instrument.

## Part A — the avx2-only lift on the SoA base (per-model G)

diamonds −67.6% | kronecker −38.0% | accel −24.3% | hier_2pl −11.5% |
lsat −18.5% | bym2 −13.9% | blr +0.5% | dogs −0.4% | radon_var −1.0% |
pilots +44%* (*call-count artifact: ridge-locked model, trajectories
differ run-to-run; per-call cost is not comparable — excluded from the
recommendation, noted honestly). ESS in-band across the 21-model grid
(116/120 chains; 4 aborts in BOTH arms = the known walnutpie#23 class).

## Part B — ALL-LAYERS (SoA + gather views + log1p kernel + avx2) vs TRUE STOCK

| model | G true-stock | G all-layers | ΔG | wall (5 interleaved rounds) |
|---|---:|---:|---:|---:|
| hier_2pl | 34,703,592,143 | 19,011,302,825 | **−45.2%** | 40.88→29.34s = **−28.2%** |
| kronecker_gp | 25,032,752,575 | 14,877,599,245 | **−40.6%** | 15.93→13.20s = **−17.1%** |
| diamonds | 1,861,257,601 | 604,986,686 | **−67.5%** | 1.77→1.33s = **−24.9%** |

THE number of the optimization arc: −40..−68% gradient instructions and
−17..−28% end-to-end sampling wall vs pristine stock, from four
orthogonal math/stan-side mechanisms (tape batching math#5, index views
stan#2, the AVX2 log1p kernel math#6, uniform ISA builds) with ZERO
sampler changes; the sampler-side exp-stack wins stack multiplicatively
on top (W-81).

## Part C — the bridgestan ISA knob

Staged at scratch/w106/bridgestan (branch isa-option, commit 16e7b3e,
+41 lines: Makefile ISA=none|avx2 uniform CXXFLAGS append + getting-
started docs). FP-change + uniformity arguments in the docs; draft PR
filed to sims1253/bridgestan. AVX-512: hardware-gated (Zen 3 box; needs
Zen 5/SPR + the ulp/dispatch harness rerun; post-kernel ceiling ~2-4%).

Artifacts: scratch/w105/ + scratch/w106/ (all drivers, grids, profiles,
wall logs, the bridgestan clone + staged body).
