# F-20 log — load-stable PR instruments (callgrind Ir / cachegrind; pre-registered in WORKLOG)

Binding scope: WORKLOG "F-20 pre-registered". Goal: convert the four
[fused jit] PR headline claims from busy-box wall ratios to instruction-
count (callgrind Ir) / cache-model (cachegrind) instruments; update the
orwell-pr-*.md bodies; gh pr edit each. Baselines being converted: F-19
census 2.09x geomean wall (correction 2.03x @85a8f11 stands), kronecker
1.323x wall, loop ladder 2372 ns/trans wall, stanc3-eigh-PR instrument
5.254M -> 4.238M Ir/grad (the instrument to mirror for #3).

Environment (boot, 2026-08-28):
- valgrind 3.18.1 present (callgrind + cachegrind available, no install).
- Worktrees (per PR-lane COMPLETE + F-19): external/stanli-pr-jit @
  68c0495 (hub), external/stanli-pr-loop @ 91046eb, external/stanli-pr-eigh
  @ 9f38119; binaries build-pr/fortk_t1r. deps/stan patch liveness for the
  loop worktree to be re-verified (0001-0003 must show in git diff).
- SHARED BOX: an F-21 sampling agent runs concurrently. OK by design —
  callgrind Ir counts are load-stable (deterministic retired-instruction
  model); noted per the pre-registration. Any wall numbers quoted during
  F-20 are context-only and labeled busy-box.
- Raw under bench/fortk_f20/.

(work in progress — appended incrementally below)

## Instrument (built 14:10-14:30; validated before any campaign)

- fortk_t1r_cg_jit / _loop / _eigh in bench/fortk_f20/: byte-copies of the
  three worktrees' tools/fortk/regions.cpp + an ADDITIVE knob (--cg N
  --cg-arm A; --sample-arm A for the sampler runs) — no worktree source
  touched (all three worktrees left clean). Compiled with the projects' own
  flag set (-O3 -DNDEBUG -ffp-contract=off, same defines/includes) against
  each worktree's prebuilt build-pr/libstanli.a (jit 03:07 pristine-deps
  era, loop 05:07 patched-deps era, eigh 04:36) — the exact sampler/
  executor code each PR lane shipped.
- Gradient-eval Ir: the knob runs exactly N evals on ONE executor inside a
  noinline cg_loop(); `callgrind --toggle-collect='*cg_loop*'` counts that
  loop's inclusive Ir and nothing else (setup/emit/clang excluded; clang
  children not traced by default). Sampler Ir: the arm's run_nuts routed
  through a noinline cg_sample_run(); toggle '*cg_sample_run*' counts
  exactly one full sampling run (400 transitions). NOTE: a bare
  '*run_nuts*' toggle is WRONG — inner lambda names contain run_nuts and
  the XOR toggle cancels (325k vs the true 14.76M on the esnc check).
- Validation: esnc unfused 937,262 / fused 104,421 Ir per 200 evals —
  repeated byte-identical under load avg 3.96 (F-21 agent concurrently
  running; Ir is load-immune as designed). Sampler run repeated
  byte-identical (14,764,986 twice). Path-length sensitivity: changing the
  outdir path shifts totals by ~5e-5 rel (heap-layout effects in Eigen
  aligned allocs) — all comparisons use same-shape outdirs; ratios stable
  to 4 significant digits.

## (a) PR #1 census Ir — hub worktree @ 68c0495, 21 models x 200 evals/arm

run_census_ir.sh; tmir.sexp reused from F-19 (stanc pin 4d440ee, graphs
byte-identical per F-19). rc=0 ALL 21 including lotka_volterra (its F-6/
F-19 verify crash is in the verify phase; at the bench theta the gradient
is finite — Ir measured cleanly, but it stays OUTSIDE the accepted-20
geomean to keep like-for-like with F-19). Raw bench/fortk_f20/census/.

| model | Ir/eval unf | Ir/eval fus | Ir ratio | F-19 wall ratio |
|---|---|---|---|---|
| esnc | 4,686 | 522 | 8.98 | 9.02 |
| esc | 5,061 | 594 | 8.52 | 7.02 |
| arma11 | 85,960 | 14,403 | 5.97 | 5.61 |
| blr | 9,646 | 1,788 | 5.39 | 3.72 |
| logmesq | 10,869 | 2,182 | 4.98 | 4.29 |
| pilots | 12,691 | 2,934 | 4.33 | 3.94 |
| kidscore | 40,338 | 11,203 | 3.60 | 2.99 |
| lsat | 1,383,430 | 425,884 | 3.25 | 1.79 |
| hier_2pl | 6,560,827 | 2,396,120 | 2.74 | 2.19 |
| wells | 508,074 | 196,531 | 2.59 | 1.48 |
| radon_vis | 139,183 | 54,485 | 2.55 | 1.98 |
| radon_pp | 1,016,118 | 435,648 | 2.33 | 1.60 |
| diamonds | 600,289 | 283,566 | 2.12 | 1.00 |
| bym2 | 993,660 | 712,164 | 1.40 | 1.18 |
| accel_gp | 143,772 | 120,970 | 1.19 | 1.18 |
| gp_regr | 87,689 | 75,989 | 1.15 | 1.10 |
| dogs | 348,119 | 312,810 | 1.11 | 1.20 |
| garch11 | 126,973 | 115,409 | 1.10 | 1.01 |
| kronecker | 4,839,269 | 4,791,355 | 1.01 | 1.06 |
| low_dim | 1,098,252 | 1,095,697 | 1.00 | 1.09 |
| GEOMEAN (20 accepted) | — | — | 2.546 | 2.094 |

(lotka_volterra measured 903,198/900,342 = 1.00, outside the accepted set;
21-model geomean 2.436.)

READING: Ir ratios sit ABOVE the busy-box wall ratios almost everywhere
(geomean 2.55 vs 2.09) and track them closely only where both arms are
compute-bound (esnc 8.98/9.02). The fused tier removes instructions
(vectorized fused kernels, no dispatch); on memory-bound models the wall
does not follow Ir because the DRAM stream is unchanged — quantified for
diamonds in (b). The Ir column is the load-stable instrument; wall stays
as labeled context.

## (b) PR #1 diamonds cachegrind — D refs/misses per eval

cachegrind has no toggle-collect, so: prep-only run (--cg 0, same setup
path) subtracted from the 100-eval arms (all deterministic; two identical
config runs differed by 16 Ir in 430M = 3.7e-8). Raw
bench/fortk_f20/diamonds_cg/.

| metric per eval | unfused | fused | f/u |
|---|---|---|---|
| Ir | 600,364 | 283,591 | 0.472 |
| D refs read | 165,914 | 167,007 | 1.007 |
| D refs write | 51,806 | 112,847 | 2.178 |
| D1 misses | 40,446 | 66,450 | 1.643 |
| LLd (DRAM-model) misses | 6.8 | 8.3 | ~1.2 |

LINE FOR THE BODY: fused and unfused touch the same DRAM streams — D-read
refs within 1%, LL/last-level misses ~7-8 per eval on BOTH arms (write-
dominated), so the 2.12x Ir cut cannot buy wall on diamonds (F-19 wall
1.00x); the fused kernel's extra L1 misses (1.64x) and writes (2.18x)
are cache-resident (LLd unchanged). Bandwidth parity explained.

## (d) PR #3 eigh Ir — kronecker, eigh worktree @ 9f38119, 100 evals/arm

FORTK_STANC selects the compiler directly (no staging cwd needed): fused
= external/stanc3/_build/default/src/stanc/stanc.exe (the F-13 build),
stock = external/stanli/deps/stanc3/stanc (4d440ee pin). Graph check:
fused 221 ops -> 94 (33 regions), stock 223 -> 96 — EXACTLY the F-19(b)
counts; grad0/sink identical across stancs at the bench theta. Raw
bench/fortk_f20/eigh/.

| arm | stock stanc Ir/grad | fused stanc Ir/grad | ratio |
|---|---|---|---|
| interpreter (the PR's arm) | 4,839,871 | 3,810,092 | 1.270x |
| region/fused | 4,786,000 | 3,762,284 | 1.272x |

Mirrors the stanc3 eigh PR's own instrument class (5.254M -> 4.238M
Ir/grad there; here 4.840M -> 3.810M on the stanli interpreter). F-19
busy-box wall: 1.323x (rebased) / 1.24x at base.

## (c) PR #2 sampler-loop Ir — hub binary vs loop binary, 200+200, seed 20260826, chain 1

Arm = the fused executor's sampler run (--sample-arm 1; the F-19 ladder
convention SAMPLE_WALL exec1_s / 400). Toggle '*cg_sample_run*' = exactly
one run_nuts = 400 transitions. run_loop_ir.sh; raw bench/fortk_f20/loop/.
Hub grad counts unavailable in-tool at 68c0495 (GRAD_COUNTER is a loop-
branch addition); hub hier_2pl exec1 count obtained via the hub binary's
own --census mode (exact counter, grads_per_iter 37.96 -> 15,184 evals).

| model | hub Ir/run | loop Ir/run | hub Ir/trans | loop Ir/trans | hub/loop | loop exec1 grads |
|---|---|---|---|---|---|---|
| esnc | 32,164,908 | 14,765,686 | 80,412 | 36,914 | 2.178x | 3741 |
| blr | 96,364,435 | 47,770,602 | 240,911 | 119,427 | 2.017x | 11081 |
| hier_2pl | 37,990,069,753 | 36,579,475,209 | 94,975,174 | 91,448,688 | 1.039x | 14785 |

GEOMEAN hub/loop Ir per transition: 1.659x.

- Seam toggle (loop binary, esnc): STANLI_DIRECT_SEAM=1 (default) 36,912
  Ir/trans vs seam=0 (stock sampler) 56,931 -> the C.5 direct-double seam
  alone is 1.542x Ir on esnc; grads identical 3741/3741.
- hier_2pl attribution: hub 15,184 evals vs loop 14,785 = exactly 399 =
  transitions-1 fewer (the 0002 endpoint carry; same relation the body
  claims for esnc at the 85a8f11 base). Per-eval-slot Ir 94,975,174/
  15,184 = 6,258 (hub) vs 91,448,688/14,785 = 6,185 (loop) = 1.012x —
  gradient-bound parity per eval (each hier_2pl fused grad is 2.40M Ir,
  dwarfing bookkeeping), the whole 1.039x being the removed redundant
  endpoint evals. Matches the body's "hier_2pl parity, gradient-bound".
- Busy-box wall context (F-17 ladder, quiet box): esnc 4875 -> 2585
  ns/trans = 1.886x; F-19 re-spot 2372. Ir ratio (2.18x) exceeds the
  wall ratio — the removed instructions were partly hidden under memory
  stalls / box noise; the Ir column is the stable instrument.

## Body updates + PR edits (15:2x)

- orwell-pr-jit.md: census bullet now headlines "callgrind Ir per gradient
  eval 2.55x geomean over the 20 accepted models — the load-stable
  instrument" with busy-box wall kept as labeled context (2.09x rebased /
  2.03x @85a8f11 — correction history intact); per-model Ir extremes
  (esnc 8.98x, arma11 5.97x, hier_2pl 2.74x); diamonds Ir 2.12x at wall
  parity + the cachegrind DRAM line (D-read refs 1.01x, ~7-8 LL misses/
  eval both arms). References extended to f19/f20 + raw paths.
- orwell-pr-loops.md: ladder paragraph now headlines Ir per transition
  (esnc 2.18x, blr 2.02x, hier_2pl 1.04x = the 399 removed endpoint evals
  at per-eval parity; geomean 1.66x; GRAD_COUNTER 3741/11081/14785) +
  seam 1.54x; wall ladder kept as "busy-box wall ladder for context".
- orwell-pr-eigh.md: kronecker interpreter arm now "4.840M -> 3.810M
  callgrind Ir per gradient eval = 1.27x, the load-stable instrument
  (busy-box wall 1.24x at base, 1.32x rebased)"; region arm noted 1.27x.
- orwell-pr-walnuts.md: one sentence added — quality gates are draw-based
  (rhat, ESS/draw, byte-identity) and load-immune; no Ir needed.
- gh pr edit 1..4 --repo sims1253/stanli --body-file: ALL OK, verified
  live == local (title line stripped, trailing newline only diff):
  https://github.com/sims1253/stanli/pull/1 .. /pull/4.

## Rules held

No git changes (all three worktrees + shared external/stanli verified
clean at end — instrument binaries and all raw live under
bench/fortk_f20/, built against the worktrees' prebuilt libs); no
upstream interaction (fork PRs only, body edits); WORKLOG.md and other
logs untouched (this file only); F-21 sampling agent ran concurrently
throughout (load avg 3.9-7.8 observed) — Ir instruments are load-stable
by design and repeats were byte-identical under that load; wall numbers
quoted nowhere new except as pre-existing labeled context.

## VERDICT (for WORKLOG, via parent)

All four PR headline claims now have load-stable instruments measured at
the rebased tips: #1 census Ir 2.55x geomean (wall 2.09x busy-box; Ir>wall
expected — instruction cuts exceed wall gains on memory-bound models,
diamonds quantified via cachegrind: same DRAM stream); #2 sampler Ir per
transition esnc 2.18x / blr 2.02x / hier_2pl 1.04x (geomean 1.66x; seam
alone 1.54x; hier_2pl residue == the 399 transitions-1 endpoint evals);
#3 kronecker interpreter Ir 4.840M -> 3.810M = 1.27x (mirrors the stanc3
PR's own instrument); #4 unchanged numerics (draw-based gates, one-line
note added). Determinism demonstrated by byte-identical Ir repeats under
external load. One instrument subtlety recorded for reuse: bare
--toggle-collect='*run_nuts*' UNDERCOUNTS (nested lambda names toggle the
XOR off) — always wrap the measured phase in a uniquely-named noinline fn.
