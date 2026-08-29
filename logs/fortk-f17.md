# F-17 — Sampler-loop measurement + lever builds (direct-double seam, endpoint threading, hoists)

Lane: sampler-loop optimization per user redirect (WORKLOG "LANE REDIRECT"; F-16 backlog item 1).
Baseline: post-F-10 trunk fortk/t2-coverage @ 4690a00, worktree external/stanli-f7, build-f7
current, ctest 64/64. Reference numbers (F-10/F-15): esnc --sample 200 200 = 2.070 ms sampler
wall, 400 transitions = 5.175 µs/transition, GRAD_COUNTER 4079 (61 cache hits).

Plan (pre-registered in fortk-f17a.md §D): Phase 1 rdtsc probe (G1 >= 80% attribution) +
callgrind 100 transitions + perf stat; Phase 2 levers in order (c) C.5 direct-double seam
(G2), (d) C.1 endpoint threading (G3), (e) H2/H3 hoists only if measured >= 0.3 µs (G4).
After each lever: ctest 64/64 + byte-identity + census walls (esnc, blr, hier_2pl tripwire).
Rules: <=4 cores, CPU only, no upstream, no git add -A, don't touch other worktrees or
/tmp/stanli-b7a3fd5, never push. Raw artifacts: bench/fortk_f17/.

## Session log

### Phase 1a — rdtsc probe build (2026-08-26/27)

Instrument: 3 counters, env-gated. F17_PROBE=1: A = whole `sampler.transition()`
per transition (nuts.cpp step lambda), warmup/sampling split; F17_PROBE=2: + C = the
whole `update_potential_gradient` body (deps/stan base_hamiltonian.hpp; includes
stringstream + var tape + executor) with CI = the init-call subset (transition-start
re-eval); F17_PROBE=3: + B = `ex_->gradient()` inside the adapter. TSC calibrated
per-run vs steady_clock (bug found+fixed: first calibration spanned across run_nuts
invocations via a shared slot — the tool calls run_nuts 8x per --sample for the
extra-seed comparisons; switched to a local t0). mhz stable 3934-4111 (Zen 3 boost).
Probe edits UNCOMMITTED (reverted after Phase 1); diff kept at
bench/fortk_f17/probe.patch. 2 rdtsc/transition at L1 => A(L1) reproduces the
uninstrumented census wall within noise (esnc 4935 vs 4958 ns/trans measured,
SAMPLE_WALL 0.001983 s = F-10/F-15 reference; GRAD_COUNTER 4079/61 exact).

esnc (eight_schools_noncentered) fused arm, quiet reps (medians of 2-3; one load
spike rep excluded, noted):

| bucket | ns/eval | ns/transition (400-trans mean) | % of A |
|---|---|---|---|
| A whole transition (L1) | — | 4935 (warm 5655 / samp 4214) | 100% |
| C = grad machinery (wrapper+executor) | 231 (warm 233 / samp 227) | 2379 | 48.2% |
| B = executor floor (BENCH_EXEC same runs, 34.3-40.1; L3 instrumented 40-48) | 36 | ~371 | 7.5% |
| **H1 wrapper = C - B** | **~195** | **~2008** | **40.7%** |
| rest (H2-H9: Eigen temps, ps_point copies, RNG, log_sum_exp, dispatch, adapt) | — | ~2556 | 51.8% |

- evals/transition: warmup 12.2 (nCw 2443/200), sampling 8.4 (nCs 1684/200); overall
  10.3 incl. construction evals (matches gpi 10.198).
- CI (transition-start eval) = 244-267 ns vs C mean 216-237: the init re-eval is the
  cache-coldest eval (C.1's target is also the most expensive one).
- warmup-vs-sampling A delta ~1.4-1.6 µs/trans = H7 adaptation + deeper trees
  (evals 12.2 vs 8.4 confounds; H7 bounded by the eval-count difference).
- B(L3 instrumented) 40-48 vs tight-loop floor 34-37 => B-bracket inflation ~5-10
  ns/eval; C(L2) vs C(L3) within noise => C bracket ~2 rdtsc/eval, no measurable
  A inflation at L2 vs L1 beyond run noise.

Scaling discriminators (fused arm, fused exec floor from same-session BENCH or F-7):

| model | A/trans L1 (warm/samp, µs) | C/eval ns | B floor ns/eval | wrapper ns/eval | wrapper share of A |
|---|---|---|---|---|---|
| esnc (d=10, 10.2 ev/tr) | 4.94 (5.66/4.21) | 231 | 36 | ~195 | 40.7% |
| blr (d=6, 28.5 ev/tr) | 20.3 (17.8/23.4) | 538/571 | ~150 | ~390-420 | ~55% (sampling trans: C_s 17.4 of 23.4 µs) |
| hier_2pl (d=669, 37.9 ev/tr) | 11130 µs (L1) | 250,867 | 215,100 | ~35,700 | ~10% of wall (C/A = 97.3%, B/A = 85.5%) |

H1 CONFIRMED as the dominant lever on esnc/blr (wrapper 40-55% of transition wall;
scales with evals/transition exactly as F-17a predicted); per-eval wrapper cost is
~195 ns (esnc) — the LOW end of F-17a's 250-450 estimate, i.e. total H1/trans ≈
2.0 µs vs their 2.3-4.5 µs (magnitude ~half, ranking unchanged). hier_2pl wrapper is
dimension-scaled (~36 µs/eval: 669-var tape) = ~10% of wall — the seam should show
~1.1x there (tripwire becomes parity-or-better, not parity).

### Phase 1b — callgrind (100 esnc transitions) + cache-sim; perf absent (2026-08-27)

Protocol: pre-lever binary, esnc --sample 50 50 (= 100 transitions/main arm; the tool
also runs 3 extra-seed comparison runs -> 8 run_nuts of 100 transitions = 400/arm),
callgrind default + --simulate-cache=yes; base run (--sample 0 0 = 6.85M Ir) subtracted.
Raw: bench/fortk_f17/callgrind/ (esnc.100trans.out, esnc.base.out, esnc.cache.out,
fnlist.txt, attr.py, annotated.txt). Per-function Ir classified to F-17a hypotheses
(regex order fixed after finding base_nuts/leapfrog signatures contain "mixmax_engine":
tree code must be classified before RNG). malloc/free (17.8M Ir = 22.7k Ir/trans, 18% of
sampling Ir!) apportioned to H1/H2/H3 by their non-malloc Ir ratio — the F-10 lesson
(~1.4 ns/alloc-pair) is visible at Ir level too: ~35 surviving alloc-pairs/trans.

FINAL ATTRIBUTION TABLE (esnc fused transition; wall anchor A = 4935 ns = rdtsc L1,
which reproduces the census baseline 4958 ns within 0.5%; executor/wrapper from rdtsc
C/B; the 2556-ns rest bucket split by Ir shares at 0.0535 ns/Ir):

| # | component | ns/trans | % of A | F-17a estimate | verdict vs estimate |
|---|---|---|---|---|---|
| B | executor gradient (fused, 10.2 evals x 36 ns) | 371 | 7.5% | 0.355 | confirmed |
| H1 | var-tape wrapper (stringstream+locale 12.5k Ir/eval, x_var varis, ops vector, precomputed chain walk, nested recover) + its malloc | 2008 | 40.7% | 2.3-4.5 µs | CONFIRMED dominant; magnitude ~45% of their midpoint (their per-eval 250-450 -> measured ~195) |
| H2 | Eigen dynamic momentum ops + return-by-value temps + alloc (Assignment 5.8M, dots 2.9M, DenseStorage ctors, product materializations) | 1369 | 27.7% | 0.6-1.5 | CONFIRMED (upper half) |
| H6 | tree loops/criterion/adapt glue (build_tree 2.8M, evolve driver 2.6M, transition 1.5M, compute_criterion 0.7M) | 507 | 10.3% | 0.1-0.4 | slightly above |
| H3 | ps_point copies/constructions (ps_point::= 0.7M + memmove/memset 2.6M) | 339 | 6.9% | 0.3-0.6 | confirmed (low end) |
| H4 | RNG (mixmax apply_bigskip 0.9M + ziggurat pair 0.4M + uniform_01 + sample_p; exp tail) | 229 | 4.6% | 0.2-0.35 | confirmed |
| H5 | log_sum_exp chain (log1p 1.37M + lse 0.3M) | 112 | 2.3% | 0.2-0.4 | DIED (half their low end) |
| H7 | adaptation (welford/DA; not in top-80 fns; warmup-only residual after eval-count correction ~560 ns/trans warmup-only, incl. init_stepsize re-search) | ~0-300 warmup-only | ~0-6% | 0.05-0.15 | roughly confirmed |
| H11 | icache/DRAM wall | ~0 | — | small | DEAD: I1 miss rate 1.03%, LL-i 0.01%, D1 0.43% (cache-sim) |

G1 VERDICT: PASS. The 3-counter rdtsc decomposition + callgrind split accounts for
100% of A (4935 ns) with A itself reproducing the uninstrumented census wall (99.5%);
every component >= 2% of A is attributed to a named function set.

H1 EXPLICIT VERDICT: CONFIRMED (direction and dominance), REFUTED in magnitude
(2.0 µs measured vs 2.3-4.5 µs pre-registered; the 40.7% share still makes the
C.5 seam the top lever, but the predicted esnc wall ratio drops from their
1.5-1.9x to ~1.7x on A minus wrapper alone, i.e. 4935->~2930).

perf stat: NOT AVAILABLE on this box (no perf binary; WSL2 kernel; consistent with
the WORKLOG environment note). Substitute: callgrind --simulate-cache=yes (I1/D1/LL
miss attribution above) + chrono task-clock (SAMPLE_WALL). Branch-miss simulation
unavailable in valgrind — H6's dispatch share is instead bounded by the Ir
attribution (evolve driver 2.6M Ir = ~140 ns/trans incl. its inlined Eigen op setup).

Trunk re-verified pristine after probe revert: F-10 deps/stan patch intact
(+63/-13 base_nuts.hpp exactly), worktree clean, rebuilt binary's esnc --sample CSV
BYTE-IDENTICAL to the preserved pre-lever binary (bench/fortk_f17/{baseline,pristine}).

### Lever (c) — C.5 direct-double seam: ALL G2 GATES PASS (2026-08-27; commit feaa4a1)

Implementation exactly per pre-registration: stanli-side
ExecutorModel::log_prob_grad_direct (double-path twin of the var path: same theta copy,
same F-10 endpoint cache + counters, same -inf/zeros-on-throw semantics) +
stanli::diag_e_metric_direct shadowing the non-virtual base_hamiltonian
init/update_potential_gradient (static dispatch through the Hamiltonian template
param intercepts base_nuts:85, expl_leapfrog's update_q, and base_hmc::init_stepsize
alike) + adapt_diag_e_nuts_direct = verbatim copy of adapt_diag_e_nuts over base_nuts
with only the Hamiltonian swapped. ZERO deps/stan changes (F-10 patch untouched),
ZERO RNG changes. Kill switch STANLI_DIRECT_SEAM=0 keeps the stock sampler in-binary.

- BYTE-IDENTITY: PASS 3/3 (esnc, blr, hier_2pl --sample 200 200 seed 20260826 chain 1
  vs pre-lever binary; cmp of sample_nuts CSVs). GRAD_COUNTER identical too
  (4079/61, 11418/62, 15166/18) — the direct path reproduces the eval/cache arithmetic
  exactly. Kill-switch arm also byte-identical.
- ctest: 64/64.
- Census walls (taskset -c 2, interleaved 3 reps, SAMPLE_WALL exec1_s medians;
  raw walls_c.txt; rep3 carried a visible load spike — blr pre 0.0145 vs 0.006 —
  medians used, all reps on file):

| model | pre (s) | seam (s) | ratio | prediction from Phase 1 |
|---|---|---|---|---|
| esnc | 0.001904 | 0.001400 | **1.36x** (best rep 0.001224 = 1.55x) | 1.7x (A minus wrapper); best rep hits it |
| blr | 0.006230 | 0.004207 | **1.48x** | sampling-phase predict 23.4->10.5 µs/trans: measured 15.6->10.5 µs/trans overall ✓ |
| hier_2pl (tripwire) | 4.188 | 3.873 | **1.08x** | ~1.10x (the 669-dim wrapper = 36 µs/eval) — tripwire PASSED (better than parity) |

esnc wall target >= 1.3x: PASS at the median. The gap to the 1.7x ideal is the
direct path's own per-eval residue (theta copy + memcmp + grad copy loops,
~30-40 ns/eval) plus rep noise; rep1 (quietest) measured 0.001224 s = 3060
ns/trans vs the predicted 2927.

### Lever (d) — C.1 endpoint threading: ALL G3 GATES PASS (2026-08-27; commit 7a6aeee)

Implementation per F-17a C.1(a): carried deps/stan patch
patches/deps-stan/0002-base_nuts-endpoint-carry.patch (fetch.sh hook generalized to
apply all deps-stan patches in sorted order; idempotent; reverse-check clean; tree ==
0001+0002 exactly). base_nuts records (q,V,g) from z_ in the transition epilogue (z_
== z_sample there) and restores them when the next transition's seeded q is
byte-identical, skipping hamiltonian_.init. Non-matching q (first transition) falls
back to stock init; init_stepsize's own inits untouched; no RNG change anywhere.

- BYTE-IDENTITY: PASS 3/3 vs pre-lever binary (esnc/blr/hier_2pl).
- COUNTER ARITHMETIC (the pre-registered gate): total log_prob evals drop by
  **399 == transitions - 1 EXACTLY on all three models** (first transition is cold —
  no carry exists yet):
  esnc 4140 -> 3741, blr 11480 -> 11081, hier_2pl 15184 -> 14785.
  GRAD_COUNTER exec drops 338/337/381 == 399 minus the 61/62/18 evals the F-10 cache
  used to serve (those inits were already free); hits -> 0 everywhere — the carry
  subsumes every transition-init cache case. gpi esnc 10.198 -> 9.353.
  (The pre-registration's "4079 -> ~3679" assumed all 400 inits were real executor
  calls; the exact bookkeeping is drop_total = 399, drop_exec = 338.)
- ctest 64/64.
- Walls (vs seam-only binary, taskset -c 2, 7 reps medians tiny models / 3 hier_2pl,
  foreign load ~2.0 present all session — a 106%-CPU python; raw walls_d.txt):
  esnc 0.001260 -> 0.001183 (median; per-rep 1.0-1.07x), blr 0.004515 -> 0.004439
  (~1.02x), hier_2pl 3.836 -> 3.986 (parity within its +-10% noise band).
  As predicted in Phase 1: after lever (c) the skipped init eval costs only the
  direct-path ~50 ns (~1.7% of a 2950 ns transition) — the counter gate is (d)'s
  real check and it is exact. Had (d) landed before (c) it would have been worth
  ~4-9% (the wrapper-era init eval at 230-250 ns was also the cache-coldest eval).

### Lever (e) — H2/H3 hoists via patch 0003: G4 PASSES (2026-08-27; commit 2bc451a)

Both targets cleared the pre-registered 0.3 µs attribution bar (H2 1369 ns, H3 339 ns).
Carried patch 0003 (3 files): dtau_dp_into/dphi_dq_into buffer-writing twins in
diag_e_metric (non-virtual, static dispatch — inherited by the direct seam; virtual
return-by-value forms kept for all other callers); expl_leapfrog member buffers for the
two half-kick gradient copies + the cwiseProduct materialization; base_nuts prologue
(4 ps_points, 9 momentum vectors) + rho_fwd/rho_bck hoisted into init_scratch-sized
members; build_tree's p_sharp_beg via dtau_dp_into. Same expressions/element copies,
different storage. fetch.sh applies 0001..0003 in sorted order on fresh checkout
(verified: the forward sequence reproduces the measured tree byte-for-byte; the
rebuilt binary re-verified byte-identical CSV).

- BYTE-IDENTITY: PASS 3/3 (esnc/blr/hier_2pl vs pre-lever binary); GRAD_COUNTER
  unchanged from (d). ctest 64/64. Walnuts D0 smoke also byte-identical (untouched path).
- Walls vs (c)+(d) binary (interleaved, 7 reps medians tiny / 3 hier_2pl; load ~1.7-2.0):
  esnc 0.001266 -> 0.001059 = **1.20x**, blr 0.004371 -> 0.003857 = **1.13x**,
  hier_2pl parity (gradient-bound). Informative target >= 1.05x: MET with margin.
  Per-transition saving ~517 ns — the F-10 "~1.4 ns/alloc-pair" model under-predicted
  this class: the cost was construction + Eigen loop-setup Ir, not just the heap pair.

### FINAL COMBINED RESULT + updated F-4b-style overhead ladder (2026-08-27)

Final walls (pre @4690a00 vs final @2bc451a, interleaved same-session, 7 reps medians
tiny / 3 hier_2pl, taskset -c 2, foreign load 3.0 noted — ratios robust, absolutes
inflated; raw walls_final.txt):

| model | pre (s) | final (s) | ratio |
|---|---|---|---|
| esnc | 0.001950 | 0.001034 | **1.886x** (quiet reps 0.000993-0.001101 = 2480-2750 ns/trans) |
| blr | 0.006251 | 0.004077 | **1.533x** |
| hier_2pl | 3.826 | 3.888 | 0.98x median, full overlap of ±8% spread ((c)-only measured 1.08x; the ~11% wrapper share is real but load-masked at this size) |

Composition: measured combined 1.886x vs product of individually-measured lever ratios
1.36 x 1.065 x 1.20 = 1.74x — mild super-additivity within each median's noise
(per-lever sessions were noisier); consistent with F-16's composition finding.

esnc overhead ladder (fused arm, 400-transition --sample 200 200 run, ns/transition):

| rung | ms/run | ns/trans | vs pre | grad share |
|---|---|---|---|---|
| pre = F-10/F-15/F-16 stack @4690a00 | 0.001950 | 4875 | 1.00x | 7.5% (371/4935, rdtsc frame) |
| + (c) C.5 direct-double seam | 0.001400 | 3500 | 1.36x | ~10% |
| + (d) C.1 endpoint threading | 0.001183 | 2958 | 1.65x | ~11% |
| + (e) H2/H3 hoists = FINAL | 0.001034 | 2585 | **1.886x** | **13.0%** (9.35 evals x 36 ns of 2585) |

End-to-end attribution validation: Phase 1 predicted final = A(4935) − wrapper(2008) −
init evals(~60) − hoists(~517) ≈ 2350 ns/trans; measured 2585 (quiet reps 2480-2750) —
within 10%, the residue being the direct path's own per-eval copies + load. The
attribution table is validated by construction, not just correlation.

Kernel ladder (unchanged, for reference, F-4b): direct 20.1 < region fns 25.5 < fused
exec 34.3-40.1 (this session's BENCH) < unfused 327-387 ns/call. The bookkeeping side
between kernel and transition wall is what F-17 attacked: 4875 -> 2585 ns/trans.

## DELIVERABLES / STATE (session close)

- Trunk fortk/t2-coverage @ 2bc451a (= 4690a00 + feaa4a1 + 7a6aeee + 2bc451a). NOT pushed.
- deps/stan (shared tree) carries exactly 0001+0002+0003 (M base_nuts.hpp +212/-35
  cumulative, diag_e_metric.hpp +17, expl_leapfrog.hpp +28/-6); reproduced from patches.
- ctest 64/64 at every lever; byte-identity held at EVERY step (9/9 model-lever pairs +
  walnuts D0 + kill-switch arm).
- bench/fortk_f17/: fortk_t1r.{pre,seam,cd,cde} binaries, walls_{c,d,e,final}.txt,
  probe.{stanli,deps-stan}.patch, callgrind/ (raw .out files + fnlist + attr.py),
  {baseline,pristine,pre_csv,g2_seam,g3_carry,g4_hoist}/ CSVs.
- What died vs F-17a estimates: H5 (log_sum_exp 0.2-0.4 µs est -> 0.11 measured, dead);
  H11 icache (dead, 1% I1 miss); H1 magnitude (2.3-4.5 µs est -> 2.0 measured: direction
  and dominance confirmed, size ~half their midpoint); H4/H6 within their ranges;
  H7 confirmed small; H2/H3 confirmed (H2 upper half).
- Remaining esnc-class transition budget (2585 ns): H2-residual Eigen loop executions
  (~800), H6 tree glue (~500), H4 RNG (~230), H3-residual copies (~150), H5 (~110),
  executor+direct-residue (~400). The next lever class would be fixed-size Eigen or a
  lean loop (C.4) — out of F-17 scope per the pre-registration.

  esnc 0.001260 -> 0.001183 (median; per-rep 1.0-1.07x), blr 0.004515 -> 0.004439
  (~1.02x), hier_2pl 3.836 -> 3.986 (parity within its +-10% noise band).
  As predicted in Phase 1: after lever (c) the skipped init eval costs only the
  direct-path ~50 ns (~1.7% of a 2950 ns transition) — the counter gate is (d)'s
  real check and it is exact. Had (d) landed before (c) it would have been worth
  ~4-9% (the wrapper-era init eval at 230-250 ns was also the cache-coldest eval).




