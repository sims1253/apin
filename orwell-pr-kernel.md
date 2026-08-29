# kernel floor: multi-pass vectorization + backward-memset elimination

## Problem

kidscore_momiq's fused gradient was 11,203 Ir/eval — the highest in the phase-1 class and the floor under every loop win (F-24's kidscore loop ratio 1.098x was kernel-bound, not loop-bound).

## Evidence

- Callgrind line-level attribution: 38.7% a scalar NORMAL_LPDF loop (two FP reductions block auto-vec under -ffp-contract=off), 31.6% the backward local-adjoint memset (3.5 KB), 15.9% scalar FMA-bwd reductions.
- Multi-pass emission replaces the single block-of-4 loop (which only reaches 2-wide SLP with spills — 12 live values) with an elementwise pass into a block-local array + a pure 4-lane reduction pass; FMA-bwd reductions block-of-4 at n>=32; the la-memset is eliminated by first-write conversion (converted classes only; exact in both memset outcomes).
- kidscore 11,203 -> 5,172 Ir/grad (-53.8%), sampling-run Ir 1.796x; census ratio 3.60 -> 7.80; corpus geomean 2.546 -> 2.737x. Verify 1.4e-15; blr byte-identical (at its F-7 floor — priors/logs/memcpy residue, nothing vectorizable, recorded).

## Validation

Region cache key v6 (keys do not hash emitted bodies — version bump on every emitter-output change). Default-path byte-identity 9/20; all 11 differing models confirmed >=32-lane reassociating loops (statistical class). Stacked on #1; the F-24/F-26 loop ratios re-rate ~2.1x with this kernel. apin WORKLOG F-25; raw bench/fortk_f25/.
