# lean NUTS loop (research, default-off): warmup-inclusive lean traversal

## Problem

After #2, the remaining esnc-class transition Ir is structure, not waste (Eigen Dense2Dense 23.3%, base_nuts recursion 13.1%, inner_product 8.9% — callgrind, F-22). Warmup was 55-65% of run Ir and stayed on the stock loop.

## Evidence

- Minimal NUTS traversal over the executor's raw-double seam: leaf 10 passes + 5 memcpys -> 2 sweeps + 1 memcpy; merges -> 1 sweep, 6 scalar accumulators; Eigen dot dispatches 7.35% -> 0.
- Warmup runs lean from iteration 0, driving the SAME vendored adaptation objects at the same window boundaries. Full-run draws are BYTE-IDENTICAL to the stock loop on esnc/blr/hier_2pl (md5s in the lane log; 15/15 campaign cells; window-rescale edges equal) — own RNG stream, matched exactly. A last-ulp dot-summation-order bug vs Eigen 5.0.1 packets was found and fixed by the bitwise gate (Eigen Map dots: alignment changes load modes, never order).
- Full-run Ir vs stock loop (one binary): esnc 1.558x, esc 1.495x, logmesq 1.373x, blr 1.324x, kidscore 1.098x (gradient-kernel floor) = 1.360x geomean; end-to-end ESS/s 1.22x at identical draws.
- Deliberate reassociations (sweep B, batched dots) are statistical-class: 3-seed ESS/draw parity, |t| <= 1.84, divergences not worse. kidscore (n=3) bitwise for free.

## Validation

--lean default OFF: flag absent = byte-identical (md5); ctest 69/69. Stacked on #2. apin WORKLOG F-22..F-24; logs/fortk-f{22,23,24}.md; raw bench/fortk_f2{2,3,4}/.
