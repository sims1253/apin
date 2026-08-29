# fused-JIT tier: region codegen, vectorized kernels, direct path, pf-init, batch mode

## Problem

stanli interprets its lowered op graph on every gradient: per-op dispatch, tape bookkeeping and scalar libm dominate small/mid graphs (measured: interpreter 1.60x bridgestan on eight_schools_nc while hand-fused C reaches 2.9x; hier_2pl transcendental-bound at 22 ns/obs). No codegen path existed; the unclaimed delta was per-model fused emission over the graph stanli already computes.

## Evidence

fortk_t1r compiles .stan -> MIR -> region carve -> per-region fused C99 (forward + adjoint sweeps, activity masks/propto/variant bytes specialized per op instance) -> clang -> dlopen, installed through the existing register_kernel mechanism. Runtime diff: one inert opcode line (OP_FORTK_REGION); the tier is opt-in via the tool.

- 64-point verification vs the unmodified executor: 20/21 corpus models at bitwise-to-2.0e-14 (esnc, dogs, bym2, kronecker bitwise; hier_2pl 1.0e-15; lotka nan-ODE documented reject).
- Corpus census, fused vs unfused executor: callgrind Ir per gradient eval 2.55x geomean over the 20 accepted models — the load-stable instrument (busy-box wall 2.09x geomean re-measured at the rebased tip, 2.03x at the 85a8f11 base; graphs byte-identical across bases — same stanc pin, dump_ops unchanged on all 20). esnc 8.98x, arma11 5.97x, hier_2pl 2.74x via vendored AVX2 exp/log1p at 0.82/1.87 ulp; diamonds Ir 2.12x at wall parity — cachegrind: both arms stream the same DRAM data (D-read refs 1.01x, ~7-8 last-level misses/eval each), bandwidth-bound, so wall does not follow Ir there.
- Addendum (kernel-floor branch fortk/f25-kernelfloor, unpushed research branch off this tier, emitter v6): NORMAL_LPDF wide scalar-sigma loops ride the same block-of-4 pattern as the GLM kernels (multi-pass: elementwise y_scaled + pure 4-lane reductions), FMA-backward scalar-cell reductions likewise, and the backward local-adjoint memset is eliminated by first-write conversion. kidscore_momiq fused Ir/eval 11,203 -> 5,172 (ratio 3.60x -> 7.80x; full sampling run Ir 1.80x), logmesq 4.98x -> 6.90x, radon 2.33/2.55x -> 2.55/2.79x; census Ir geomean 2.55x -> 2.74x at 20/20 verify < 1e-9 and byte-identical default-path draws on every model whose graph does not exercise a >=32-lane reassociating loop (9/21 byte-identical incl. esnc; the other 12 differ only through the documented reduction reassociation, all statistical-gated).
- Cold compile 0.15-0.43 s per model, cached path ms-scale; single-region graphs take a direct fortk_grad_direct call (20 ns class).
- With the sampler-loop PR stacked here: 6.24x CmdStan ESS_bulk/s geomean on the small class (paired) at ESS/draw parity; --fits batch mode 508k-1.16M fits/hour in-process.

## Validation

ctest 69/69 at the rebased tip; esnc grad bitwise / logp 2.5e-16, blr 3.2e-16, diamonds 3.9e-16; esnc --sample 200 200 CSV byte-identical to the 85a8f11-base build; --fits 4 smoke.

## References

apin (sims1253/apin) WORKLOG F-3..F-20; logs/fortk-f{3,4,4b,6,7,12,14,19,20}.md; raw census bench/fortk_f{6,7,19,20}/. Rebased onto 33f79dea; wall measurements taken at the 85a8f11 base (pre-rebase) and re-measured at the rebased tip; Ir/cache instruments (callgrind/cachegrind, F-20) measured at the rebased tip. Kernel-floor addendum: WORKLOG F-25, logs/fortk-f25.md, raw bench/fortk_f25/.
