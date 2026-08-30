# base_nuts sampler-loop package: scratch-hoist, endpoint threading, hoists

## Problem

With fused gradients, esnc-class NUTS transitions are 92.5% bookkeeping. rdtsc+callgrind attribution of one transition: 40.7% the var-tape wrapper stan builds around every gradient eval (stringstream, arena varis, precomputed_gradients chain walk), 27.7% Eigen momentum temporaries, 6.9% ps_point copies, plus one redundant gradient per transition (each transition re-evaluates the endpoint the previous one ended on).

## Evidence

Three levers, each gated on byte-identical draws:

- 0001 scratch-hoist (carried deps/stan patch): ~630 heap allocs/transition hoisted into init_scratch buffers; esnc 1.17x, blr 1.27x.
- C.5 direct-double seam (stanli-side diag_e_metric_direct + adapt_diag_e_nuts_direct calling the executor's raw-double gradient; zero deps logic change, zero RNG change, STANLI_DIRECT_SEAM=0 kill switch): esnc 1.36x, blr 1.48x, hier_2pl 1.08x.
- 0002 endpoint carry + 0003 momentum/prologue hoists: base_nuts carries (q,V,g) between transitions — log_prob evals drop by transitions-1 exactly (esnc 4079 exec + 61 cache hits -> 3741 + 0) — then buffer-writing twins kill the remaining Eigen temps.

Ir per transition, this binary stack vs the jit-tier binary (callgrind, load-stable, 200+200 seed 20260826): esnc 80,412 -> 36,914 = 2.18x, blr 240,911 -> 119,427 = 2.02x, hier_2pl 94.98M -> 91.45M = 1.04x — that residue is exactly the 399 (= transitions-1) redundant endpoint evals the carry removes (per-eval Ir 6,258 vs 6,185, gradient-bound parity); geomean 1.66x, loop-binary GRAD_COUNTER exec1 = 3741/11081/14785. The C.5 seam alone (STANLI_DIRECT_SEAM 0 -> 1): esnc 56,931 -> 36,912 Ir/trans = 1.54x at identical grads. Busy-box wall ladder for context: esnc 4875 -> 2585 ns/transition = 1.886x (blr 1.533x; hier_2pl parity); 1.59x geomean ESS_bulk/s at campaign scale at identical draws (F-18).

## Validation

Draws byte-identical vs the jit-tier binary on esnc/blr/hier_2pl at both bases; GRAD_COUNTER drop == transitions-1 exactly on all three; ctest 63/63 pre-rebase, 69/69 rebased. deps/stan patches carried as patches/deps-stan/000{1,2,3}.patch, applied idempotently by the deps/fetch.sh hook (reverse-checked, sorted order).

## References

apin WORKLOG F-10/F-17/F-18/F-19/F-20; logs/fortk-f{10,17,18,19,20}.md; attribution tables + rdtsc/callgrind raw in bench/fortk_f17/, Ir-per-transition raw in bench/fortk_f20/loop/. Rebased onto 33f79dea; wall measurements taken at the 85a8f11 base (pre-rebase) and re-measured at the rebased tip; Ir instruments (callgrind, F-20) measured at the rebased tip.

## Beyond byte-identity (research-tool probe, not in this PR)

A follow-up lean NUTS driver in the fortk research tool (default-off `--lean`; arena state, fused leapfrog sweeps, batched U-turn criteria — reductions reassociated, so draws are statistically gated, not byte-identical) measures full-run callgrind Ir geomean **1.360x** vs this package's loop over the esnc-class 5 (esnc 1.558x, esc 1.495x, logmesq 1.373x, blr 1.324x, kidscore 1.098x — gradient-bound floor; 200+200 seed 20260826, one binary, both arms in-binary). This is an upper bound on what non-bitwise loop restructuring could buy beyond the byte-identity levers above; the PR itself keeps its byte-identical guarantee. Statistical equivalence held (ESS_bulk/draw, R-hat, divergences within realization noise across 8 reps x 4 chains; at n=3, where the reference reduction is itself sequential, the driver reproduces stock draws bit-for-bit). Later descendants (arena layout + a direct-call seam for single-region graphs, both bitwise at every step) compose to full-run Ir **1.647x** on the reunited stack (esnc 1.83x, esc 1.79x, logmesq 1.84x, blr 1.55x) and 9.21x CmdStan ESS_bulk/s geomean on the small class — branches fortk/f3{0,2,3}-* on the fork, ledger F-30..F-33.
