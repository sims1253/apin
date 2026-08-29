# F-19 log — post-rebase re-benchmark at 33f79dea (pre-registered in WORKLOG)

Binding scope: WORKLOG "F-19 pre-registered" (post-rebase re-benchmark;
no pass/fail gate — measurement + attribution). Baselines: F-6 census +
F-7 VERDICT rows (the 85a8f11 census), F-8/F-18 ESS/s conventions,
F-17 ladder 2585 ns/trans, F-13 kronecker 232.3/287.7 µs.

Environment (boot, 2026-08-28):
- Worktrees verified: external/stanli-pr-jit @ 68c0495 (hub), external/
  stanli-pr-loop @ 91046eb, external/stanli-pr-eigh @ 9f38119 — all clean,
  no git changes. Binaries build-pr/fortk_t1r newer than all tool/runtime
  sources in each tree (jit 03:07, loop 05:07, eigh 04:36) — reuse, no
  rebuild (sources untouched since builds).
- Shared deps/stan: live git diff == patches 0001+0002+0003 of the loop
  branch (3 files, +222/-35; markers scratch/endpoint/dtau_dp_into/
  prologue all present; 0003 reverse-checks clean) — the loop stack is
  active for the loop worktree; hub/eigh binaries were built with
  pristine deps per fortk-prs.md (their gates at 33f79dea already ran).
- stanc: external/stanli/deps/stanc3/stanc = 4d440ee — SAME pin as the
  F-6/F-7 census era (upstream's new STANC3_SRC_SHA scheme kept the pin;
  fortk-prs cross-base note). Any graph change is upstream stanli
  lowering, not stanc.
- Protocol: taskset -c 2 pinned, 3 reps medians, quiet box (alone),
  verify 64 pts seed 20260826 (grad rel-L2 + logp rel < 1e-9), bench =
  tool's in-C loop reporting fused AND unfused µs/call. Raw under
  bench/fortk_f19/.

## (a) Census re-run — hub worktree (fortk-pr/jit-tier @ 68c0495)

RUN: 3 full sequential passes (run.txt/.run2/.run3, each = tool-internal
3-rep median), taskset -c 2, quiet box (load ~1.2, no foreign bench). 20/21
rc=0 all passes; lotka_volterra rc=134 in verify — the SAME nan-ODE
LOGNORMAL domain-check crash as F-6 (verbatim), not retried per its note.
Verify: 20/20 GATE_CORRECTNESS=PASS; values match the 85a8f11 gate values
where recorded (esnc 0.0/2.485e-16 bitwise, blr 3.249e-16/2.423e-16,
diamonds 3.882e-16/2.491e-16, hier_2pl 1.042e-15/1.221e-14, arma11
7.778e-16/3.958e-15 — ALL identical to F-7/PR-lane records).

Rep spreads >5% on first pass (the F-6 re-run rule) → the 2 extra passes;
quoted = median across the 3 pass-medians (raw: bench/fortk_f19/*.run*.txt).

Comparison table (old = F-7-updated census rows; new = F-19):

| model | old ratio | new ratio | d_ratio | old unf µs | new unf µs | d_unf | old fus µs | new fus µs | d_fus |
|---|---|---|---|---|---|---|---|---|---|
| esnc | 8.15 | 9.02 | +10.6% | 0.273 | 0.325 | +19.0% | 0.034 | 0.039 | +13.5% |
| esc | 7.16 | 7.02 | -2.0% | 0.297 | 0.373 | +25.6% | 0.042 | 0.045 | +9.6% |
| logmesq | 4.36 | 4.29 | -1.5% | 0.931 | 1.014 | +8.9% | 0.214 | 0.234 | +9.2% |
| blr | 3.85 | 3.72 | -3.3% | 0.586 | 0.613 | +4.6% | 0.148 | 0.165 | +11.3% |
| pilots | 3.63 | 3.94 | +8.4% | 0.773 | 0.891 | +15.3% | 0.213 | 0.236 | +10.7% |
| kidscore | 2.78 | 2.99 | +7.5% | 2.70 | 3.03 | +12.4% | 0.97 | 1.02 | +4.7% |
| radon_vis | 1.88 | 1.98 | +5.5% | 9.61 | 11.95 | +24.4% | 5.10 | 5.78 | +13.4% |
| radon_pp | 1.58 | 1.60 | +1.6% | 63.2 | 65.6 | +3.8% | 40.1 | 42.2 | +5.2% |
| bym2 | 1.26 | 1.18 | -6.4% | 54.6 | 59.4 | +8.9% | 43.3 | 50.4 | +16.4% |
| accel_gp | 1.14 | 1.18 | +3.2% | 9.98 | 9.49 | -4.9% | 8.72 | 8.51 | -2.4% |
| gp_regr | 1.13 | 1.10 | -2.9% | 5.21 | 6.04 | +16.0% | 4.62 | 5.22 | +13.0% |
| garch11 | 1.09 | 1.01 | -7.0% | 11.1 | 13.2 | +19.1% | 10.2 | 11.6 | +13.4% |
| lsat | 1.84 | 1.79 | -2.9% | 82.0 | 87.4 | +6.6% | 44.5 | 49.9 | +12.1% |
| low_dim | 1.01 | 1.09 | +7.8% | 71.9 | 96.1 | +33.6% | 71.4 | 80.1 | +12.2% |
| hier_2pl | 2.20 | 2.19 | -0.6% | 473.9 | 525.6 | +10.9% | 215.1 | 240.5 | +11.8% |
| kronecker | 1.01 | 1.06 | +5.0% | 285.1 | 345.0 | +21.0% | 281.1 | 325.3 | +15.7% |
| arma11 | 5.47 | 5.61 | +2.5% | 6.66 | 8.05 | +20.9% | 1.22 | 1.51 | +24.0% |
| diamonds | 0.85 | 1.00 | +17.6% | 35.6 | 39.2 | +10.1% | 38.6 | 41.8 | +8.3% |
| dogs | 0.97 | 1.20 | +23.3% | 22.0 | 26.6 | +20.9% | 22.8 | 22.7 | -0.4% |
| wells | 1.46 | 1.48 | +1.4% | 37.7 | 42.7 | +13.4% | 25.8 | 27.4 | +6.3% |
| GEOMEAN | 2.03 | 2.09 | +3.1% | — | — | — | — | — | — |

(Geomean over the 20 accepted. NOTE: recomputing the old-side geomean from
the F-6/F-7 published per-model ratios gives 2.03x, not F-7's quoted "≈2.25x
corpus aggregate" — that 2.25x figure is not reproducible from its own table
(possible different aggregation); the honest like-for-like F-19 comparison is
2.03 -> 2.09 = +3.1%.)

## (a2) Attribution — NO graph changed shape; movers are kernel-time

Evidence (all three independent):
1. stanc pin UNCHANGED (4d440ee both eras) and the tmir.sexp outputs are
   byte-identical to the F-6 artifacts for all 20 models (only diff = the
   prog_path absolute-vs-relative line, an artifact of invocation cwd).
2. dump_ops summaries (.dumpops.txt) byte-IDENTICAL old vs new for all 20
   models; full op listings (.fullops.txt) identical for the movers checked
   (esnc, diamonds, dogs, low_dim).
3. Region structure unchanged: region counts equal to the F-7 D3 rows on
   every model (hier_2pl 2, arma11 1/806 ops, kronecker 33, accel 12, bym2
   5, low_dim 4, garch 2, dogs 2, lsat 1, pilots 1, ...).
=> Upstream's 77 commits did NOT alter any measured graph (the pre-registered
stanc-vectorization worry did not materialize at this pin; new opcodes
(OP_ALGEBRA_SOLVER), Break/Continue MIR kinds are absent from these models).

Ratio movers >10% — ALL attributed to kernel-time change (interpreter
"unfused" arm slowed more than the fused region arm on the same graph):
- esnc +10.6% (8.15->9.02): unf +19.0% vs fus +13.5%.
- diamonds +17.6% (0.85->1.00): unf +10.1% vs fus +8.3%; old 0.85 was F-4's
  own low reading (F-6 measured 0.92) — new 1.00 sits inside the historic
  0.85-0.92 band + day drift.
- dogs +23.3% (0.97->1.20): unf +20.9% vs fus -0.4% (fused arm unchanged).
Borderline (<10%): low_dim +7.8%, pilots +8.4%, kidscore +7.5% — same
pattern (unfused arm drift).

UNFUSED µs/call moved >10% on 14/20 models (upstream's own executor timing,
not ours): low_dim +33.6%, esc +25.6%, radon_vis +24.4%, kronecker +21.0%,
arma11 +20.9%, dogs +20.9%, garch11 +19.1%, esnc +19.0%, gp_regr +16.0%,
pilots +15.3%, kidscore +12.4%, wells +13.4%, hier_2pl +10.9%, diamonds
+10.1%; only accel_gp moved the other way (-4.9%). Since graphs and our
emitted code are unchanged, this is either upstream-interpreter runtime
change or day-to-day box drift (F-18 recorded 1.15-1.41x A-arm day drift
with identical draws); the RATIO column is same-session interleaved and
therefore robust — it moved only +3.1% aggregate.

## (b) Kronecker — eigh worktree + staged F-13 stanc

Setup: /tmp/f19-eigh-fused (deps/stanc3/stanc -> external/stanc3/_build/
default/src/stanc/stanc.exe, the F-13 fusion build) and /tmp/f19-eigh-stock
(-> pinned nightly 4d440ee); kronecker model/data copies; tool =
external/stanli-pr-eigh build-pr/fortk_t1r run from each cwd. 3 interleaved
runs per arm, taskset -c 2, each run = tool-internal 3-rep median
(F-13.2 gate-b protocol). Raw: /tmp/f19-eigh-{fused,stock}/out/*.run.txt.

| arm | run1 | run2 | run3 | median | F-13.2 baseline | delta |
|---|---|---|---|---|---|---|
| fused interpreter (unfused_ns) | 219.5 | 226.6 | 232.1 | **226.6 µs** | 232.3 | -2.4% |
| fused region (fused_ns) | 274.3 | 221.0 | 264.1 | 264.1 | 229.2 | +15% (noisy) |
| stock interpreter (unfused_ns) | 311.1 | 299.7 | 290.0 | **299.7 µs** | 287.7 | +4.2% |
| stock region (fused_ns) | 295.5 | 288.1 | 297.2 | 295.5 | 291.9 | +1.2% |

- Speedup (interpreter arms, the PR #3 headline class): 299.7/226.6 =
  **1.323x** vs F-13.2's 1.239x (+6.8%, within the day-drift band; F-13.2
  itself noted 1.28x under matched noise).
- VERIFY: grad 0.0 / logp 0.0 (BITWISE) on every run, both arms — as
  expected.
- Cross-stanc FORTK_DUMP: dump.ex0 + dump.ex1 byte-identical between arms,
  md5 2d6ae1c66c177e79c75dd3b3c2c80e6f — the SAME single md5 recorded at
  the 85a8f11 gate (draw-level identity preserved across the rebase).
- Graphs: fused arm 221 ops with 2 EIGENDECOMPOSE_SYM, stock 223 ops with
  4 eigh ops; CARVE 33 regions both arms (matches F-13.2).

## (c) ESS/s — loop worktree (full stack arm C) + cmdstan arm A

Campaign: bench/fortk_f19/run_f19.py (adapted verbatim from F-18's runner;
TOOL = external/stanli-pr-loop build-pr/fortk_t1r @ 91046eb, deps/stan
patches 0001-0003 verified live). 6 phase-1 models, arms A (CmdStan 2.39.0
via cmdstanpy, F-8's compile-once exes, uv run python from the workspace) +
C (fortk_t1r default init), 4 chains x 1000+1000, seeds 20260826+1000*rep+c,
3 reps medians, arms interleaved model-major, <=4 concurrent sampling procs,
ESS via harness/ess.R (canonical F-8 column basis), ESS_bulk/s = geomean
per-param / max-chain sampler wall. Ran 10:08-10:10, quiet box, rc=0 all 18
cells. Raw: bench/fortk_f19/{<model>/rep<r>/{A_cmdstan,C_fused_nuts}/,
results_raw.json, analysis.json/out}.

| model | A today | C today | C/A today | F-18 C/A |
|---|---|---|---|---|
| esnc | 140,634 | 500,232 | 3.56x | 5.28x |
| esc | 2,858 | 42,971 | 15.04x | 11.52x |
| blr | 11,752 | 96,830 | 8.24x | 5.30x |
| pilots | 30 | 170 | 5.66x | 6.37x |
| kidscore | 2,779 | 9,399 | 3.38x | 4.73x |
| logmesq | 7,244 | 39,397 | 5.44x | 6.10x |
| GEOMEAN | 3,766 | 22,529 | **5.98x** | **6.24x** |

- NEW HEADLINE: C/A geomean **5.98x** paired today vs F-18's 6.24x (-4.2%,
  under any materiality bar). Cross-normalized C_today/F18-A = 5.91x.
- DRAW IDENTITY AT CAMPAIGN SCALE (strongest check): arm C's 24/24 chain
  CSVs are BYTE-IDENTICAL to F-18's C (esnc..logmesq x 4 chains, rep0,
  cmp-verified); per-rep ESS_bulk geomeans match F-18's C to rel 0.00000 on
  all 6 models; ESS/draw identical (0.999/0.171/0.349/0.018/0.348/0.484);
  div/td identical (esc A 43/1k vs C 14; pilots A 180/653 vs C 139/310);
  GRAD_COUNTER gpi1 medians EXACTLY F-18's (8.741/20.447/16.412/276.353/
  31.920/45.823), hits1 totals 8/3/6/0/3/4 EXACT. Arm A: per-rep ESS rel
  0.00000 vs F-18's A on all 6 (same exes + seeds). => every ESS/s delta
  below is PURE WALL.
- Wall attribution (medians): A today vs F-18's A walls 0.69-1.68x (esnc
  0.69, esc 1.07, blr 1.68, pilots 0.92, kidscore 1.01, logmesq 0.94);
  C today vs F-18's C walls (.0082/.0194/.0134/.3853/.1029/.0497):
  esnc 1.036x (.0084), esc 0.738x (.0143), blr 1.180x (.0158), pilots
  0.739x (.2846), kidscore 1.476x (.1518), logmesq 0.989x (.0492); C/F18-C
  ESS/s geomean 0.946x. C walls moved in BOTH directions with identical
  draws and identical counter arithmetic => environment/code-layout day
  drift, NOT a stack change (the rebase is draws-neutral by gate and by
  this campaign). The per-model C/A moves (esnc -32%, blr +55%, esc +31%,
  kidscore -28%) are the same environment noise acting on the two arms in
  opposite directions (e.g. blr: A wall 1.68x slower today while C 1.18x);
  geomean moves only -4.2%.
- Per-rep spreads >2x flagged: esnc C [862k, 333k, 500k], esc A, pilots C
  [170, 47, 615] — same flags as F-18's campaign on the same cells; medians
  quoted per convention.

## (d) Loop ladder spot — esnc ns/transition, loop worktree

7 reps, --sample 200 200 --seed 20260826 --chain-id 1, taskset -c 2, warm
region cache; ns/trans = SAMPLE_WALL exec1_s x 1e9 / 400 (F-17 ladder
convention). Raw: bench/fortk_f19/ladder/esnc{1..7}.log.
Reps: 2870 / 2335 / 2372 / 2348 / 2565 / 2348 / 3290 -> MEDIAN **2372
ns/trans** vs F-17 final 2585 (quiet band 2480-2750): -8.2%, band overlap;
box slightly faster on this microbench today. GRAD_COUNTER exec1=3741
hits1=0 on EVERY rep — exactly the recorded loop-package values (also the
runtime proof that deps/stan 0001-0003 are live in the timed binary).

## VERDICT (for WORKLOG, via parent)

No pass/fail gate (measurement). Pre-stated expectation "deltas small
unless the stanc pin/vectorization changed graphs" — CONFIRMED SMALL, and
the graph channel is CLOSED: stanc pin unchanged (4d440ee), tmir byte-
identical, dump_ops byte-identical, region structure identical on all 21
models. Headlines: census corpus geomean +3.1% like-for-like (2.03->2.09);
kronecker 1.24x->1.32x; ESS/s 6.24x->5.98x paired (-4.2%, pure wall,
draws byte-identical); ladder 2585->2372 ns (-8.2%). NO headline moved
>10% => per the materiality rule the orwell-pr-*.md bodies are UNTOUCHED
(zero addenda written); all rebased numbers live here. One honest flag for
the record: F-7's published "≈2.25x corpus aggregate" is not reproducible
from its own per-model table (recomputes to 2.03x) — pre-existing ledger
discrepancy, unchanged by the rebase; the PR #1 body's 2.25x should
eventually be re-derived from the per-model rows.

Rules held: <=4 concurrent sampling procs, CPU only, no builds needed
(binaries current), no upstream interaction, no git changes anywhere (all
three worktrees clean at task end), /tmp/stanli-b7a3fd5 untouched (never
accessed), WORKLOG + other logs untouched.
