# F-24 log — pass-fusion + dot-batching inside the lean NUTS loop (last named loop levers)

Binding charter: WORKLOG "F-24 pre-registered" (2026-08-28). Read order
honored: logs/fortk-f23.md (complete F-23 record — lean loop's current
shape, Eigen-Map-dot discipline: alignment changes load modes NEVER
summation order where bitwise mattered; F-24 is statistical-gated so
summation order MAY change, deliberately), logs/fortk-f22.md (lean loop
Ir attribution: loop self 51.8% = recursion + hand passes + dots),
WORKLOG "F-23 VERDICT" + "F-24 pre-registered".

Setup (boot, 2026-08-29):
- Worktree external/stanli-pr-loop, branch fortk/f24-loopfusion off
  fortk/f23-leanwarm @ 2eb3785. deps/stan patches 0001-0003 verified
  live (+222/-35) before any timing.
- Work: (1) ATTRIBUTE the lean loop's remaining per-transition Ir on
  esnc (F-20 --cg pattern; confirm 51.8% loop-self pool and split:
  recursion vs hand passes vs dots) BEFORE building. (2) PASS-FUSION:
  fuse the lean leapfrog's separate state sweeps (momentum half-step,
  gradient fetch, position update, criterion/H accumulation) into fewer
  sweeps — target ~half the pass count per leapfrog. Where fusion
  reassociates a summation, prefer per-element arithmetic order;
  where unavoidable (dot batching), accept — statistical-gated. (3)
  DOT-BATCHING: batch criterion/rho inner products to cut per-call
  dispatch (fuse rho accumulation with criterion dot; both U-turn
  criteria in one pass). (4) Re-attribute after; verify the levers
  consumed the pool.
- Gates: (a) STATISTICAL equivalence vs arm C (--lean default-off for
  shipping; fused-lean vs arm C): 3 seeds x phase-1 6 models —
  ESS_bulk/draw within noise, all-chain R-hat < 1.01, divergences not
  worse, adapted eps/inv_metric max-rel-diffs reported; (b) full-run
  Ir geomean over esnc/esc/blr/logmesq/kidscore >= 1.30x vs arm C
  (one binary, F-20 shape, iso-grad by construction); 1.23-1.30x =
  honest structural-end verdict; (c) default path (--lean absent)
  byte-identical + ctest 69/69; (d) ESS/s interleaved same-day
  informational.
- Rules: <=4 concurrent sampling procs, CPU only, -j2 builds, no
  upstream, no push, explicit staging, do not touch other worktrees'
  sources (/tmp/review/stanli = USER's review checkout — hands-off),
  WORKLOG/other logs untouched, raw bench/fortk_f24/.

(work in progress — appended incrementally below)

## (i) ATTRIBUTION — BEFORE (F-23 binary, esnc lean-full, sampling phase)

Instrument: bench/fortk_f24/fortk_t1r.f23base (= build-pr binary @ 2eb3785,
byte-identical code to fortk/f23-leanwarm), F-20 shape, --sample-arm 1
--lean, toggle '*cg_lean_run*'. Reproduced F-23's cell: 200+200 lean-full
= 9,830,713 Ir (F-23 recorded 9,830,697; 1.6e-6 rel path-length heap
sensitivity), grads exec1=3741 EXACT. Sampling phase = full(200+200) -
(200+1 warmup-dominated) = 3,837,982 Ir / 200 trans = 19,190 Ir/trans
(F-22 recorded ~19.2k — same to 4 digits). Function-level via
callgrind_annotate + grouping (attr/attr_f24.py, raw attr_before.out):

| component | Ir | share | Ir/trans |
|---|---|---|---|
| lean loop self — build_tree (recursion glue + LEAF hand passes + bookkeeping) | 1,093,325 | 28.49% | 5,467 |
| lean loop self — transition (prologue passes + merge crit glue) | 502,556 | 13.09% | 2,513 |
| lean loop self — eval/other | 97,482 | 2.54% | 487 |
| Eigen dot reduction (inner_product: crit dots + H cwise/dot) | 281,934 | 7.35% | 1,410 |
| memcpy (state moves: copy_pt 3n, ps/p endpoint copies) | 405,205 | 10.56% | 2,026 |
| fused kernel + executor dispatch | 412,083 | 10.73% | 2,060 |
| transcendentals (exp 6.71 + log1p 6.38 + lse 1.23) | 549,606 | 14.32% | 2,748 |
| rng (uniform 2.57 + ziggurat 2.07) | 178,117 | 4.64% | 891 |
| memset/malloc/init-evals/regions/unclassified | ~318k | ~8.3% | — |

POOL CONFIRMED: loop self (44.12%) + dots (7.35%) = 51.5% ~= F-22's
51.8% "recursion + hand passes + dots". Split: leaf/prologue hand passes
+ recursion glue 44.1%, Eigen dot dispatches 7.4%. Per-leaf pass count
today: kick1, drift, params memcpy, [kernel], kick2, H (cwise+dot),
copy_pt, ps_beg, memcpy ps_end, rho +=, memcpy p_beg, memcpy p_end =
~10 element sweeps + 5 memcpy dispatches; per merge: 3 compute loops +
up to 6 inner_product dispatches; per while-iter: 3 more memcpys.
Fusion target: ~2 sweeps + 1 memcpy per leaf; 1 sweep per merge.

DESIGN (recorded BEFORE building, per charter):
- Leaf sweep A (pre-gradient): {kick1, drift, executor-param store} —
  per-element arithmetic IDENTICAL to the unfused passes (forward
  fusion, no reassociation); the param store replaces eval_pot's memcpy.
- Leaf sweep B (post-gradient): {kick2, ps_beg/ps_end p_sharp, rho +=,
  p_beg_out/p_end_out, T kinetic accumulation} — one sweep replacing 5
  passes + 4 memcpys. T accumulates sequentially i=0..n-1: THE
  deliberate reassociation (vs Eigen 4-lane packet reduction),
  statistical-gated per charter.
- Merge sweep (dot-batching): the 3 U-turn criteria + rho/rho_ext
  computation + r accumulation in ONE sweep with 6 scalar accumulators;
  rho_sub/rho_ext no longer materialized (d_rs/rho_ext slots deleted);
  per-element products identical, sequential dot order, crit
  short-circuit (plus-dot-first) dropped — all 6 dots always computed.
- Transition prologue: {sample_p, p_ff/fb/bf/bb, ps_ff/fb/bf/bb, rho}
  one sweep (RNG draw order unchanged); direction-branch 3-buffer
  copies folded to one loop each.
- H_working/epilogue energy: sequential T loop, same order as sweep B.
- init_stepsize: leapfrog_pre + plain kick2 (H-only consumer).

## (ii) IMPLEMENTATION + SMOKE

- Implemented in tools/fortk/regions.cpp (fortk_f22::LeanNuts), build
  green (-j2, no new warnings):
  1. eval_pot split: eval_pot_nosync (gradient only) + eval_pot (sync
     wrapper); leapfrog_pre writes the drift directly into
     ex.params_data() inside sweep A (memcpy eliminated).
  2. Leaf sweep A {kick1 + drift + param store} — forward fusion,
     per-element arithmetic IDENTICAL (no reassociation).
  3. Leaf sweep B {kick2 + ps_beg/ps_end p_sharp + rho += + both
     endpoint momenta + T kinetic accumulation} — was 5 passes + 4
     memcpys. T sequential i=0..n-1 (THE deliberate reassociation).
  4. Merge dot-batching: 3 rho sums + 6 criterion dots in ONE sweep with
     6 scalar accumulators, rho_sub/rho_ext never materialized (d_rs +
     rho_ext arena slots deleted); per-element products identical to
     the unfused Eigen dots; plus-dot-first short-circuit dropped.
     Both call sites (build_tree merge, transition while-loop).
  5. Prologue: momentum draw + 4 endpoint pairs + p_sharp + rho in ONE
     sweep (RNG element order unchanged); direction-branch 3-buffer
     memcpys folded to one loop each; H_working/energy -> T_seq
     (sequential, one order everywhere).
- SMOKE (esnc 200+200 seed 20260826 c1): runs, accept 0.8935, 0
  post-warmup divergences, grads 3785 vs stock 3741 (draw branches
  flip — draws differ by design now).
- PHYSICS VALIDATION (STANLI_DEBUG_LEAN_TRACE, fused vs unfused lean,
  same seed): iteration-0 accept_stat differs in the LAST ULP only
  (9.8489582015738567e-06 vs ...8211e-06 — the summation-order change
  and nothing else); qhash IDENTICAL through iteration 6, tree shapes
  (nlf) IDENTICAL in ALL 200 iterations; decorrelation enters via a
  proposal-acceptance draw branch at iteration 7. The per-transition
  physics is ulp-identical; long-run adapted state decorrelates via
  DA feedback (chaotic, by charter).
- ADAPTED-STATE SPOT CHECK (esnc 1000+1000 c1, eps_frozen):
  stock seeds 20260826/1/2/3/4 = 0.4494/0.4350/0.4614/0.4017/0.4431
  (spread 0.40-0.46); fused same seeds = 0.2845/0.4465/0.3926/0.5692/
  0.3688 (spread 0.28-0.57, mean 0.412 vs stock 0.438). Overlapping,
  wider — chaotic realization spread, NOT a systematic shift (fused
  seed-1 eps 0.4465 sits mid-stock-range). Full statistical gate (a)
  below decides.

## (iii) GATE (b) SPEED — full-run Ir — 1.360x GEOMEAN (CROSSES 1.30x)

F-20/F-23 pattern, ONE binary (build-pr @ f24 working tree), 200+200
seed 20260826 chain 1 arm 1, noinline-wrapper toggles; warmup-phase Ir
from 200+1 cells, sampling = difference. Raw ir/ + ir_campaign.out.

| model | stock Ir | fused Ir | full-run | warmup-ph | sampling-ph | grads st/fu |
|---|---|---|---|---|---|---|
| esnc | 13,138,693 | 8,433,068 | **1.558x** | 1.562 | 1.553 | 3741/3785 |
| esc | 35,246,792 | 23,578,351 | **1.495x** | 1.374 | 1.782 | 10749/11193 |
| blr | 43,590,357 | 32,930,201 | **1.324x** | 1.245 | 1.407 | 11081/10856 |
| logmesq | 95,723,984 | 69,705,008 | **1.373x** | 1.294 | 1.456 | 19821/20033 |
| kidscore | 346,390,448 | 315,535,011 | **1.098x** | 1.097 | 1.100 | 25616/25616 |
| GEOMEAN | — | — | **1.360x** | 1.303 | 1.417 | — |

- VERDICT at the 1.30x bar: **CROSSED** (1.360x; F-23 was 1.228x). The
  loop program's finish line is past.
- ISO-GRAD honesty note: grad parity is no longer exact by construction
  (draw branches flip at ulp; tree shapes differ slightly). The fused
  arm did MORE kernel work on esnc (+1.2%)/esc (+4.1%)/logmesq (+1.1%)
  — wins there are UNDERSTATED; blr did LESS (-2.0%); kidscore EXACT.
  Per-GRAD Ir ratios (stock/fused Ir-per-grad): esnc 1.576 / esc 1.555
  / blr 1.297 / logmesq 1.387 / kidscore 1.098 => geomean 1.371x —
  the claim holds under the iso-grad reading too.
- vs F-23 per model: esnc 1.334->1.558, esc 1.297->1.495, blr
  1.185->1.324, logmesq 1.273->1.373, kidscore 1.071->1.098. The
  gradient-bound floor (kidscore 13.5k Ir/grad) moved least, as
  predicted; esc gained most (its trees are deep — loop-side share
  highest).

## (iv) RE-ATTRIBUTION — AFTER (fused loop, same instrument/cells)

Sampling phase 3,837,982 -> 3,344,535 Ir (19,190 -> 16,673 Ir/trans;
-12.9%; the fused arm realized +3% more sampling grads this seed —
deeper trees — so per-grad the gain is slightly larger). Raw
attr/attr_after.out:

| component | before Ir | after Ir | delta |
|---|---|---|---|
| loop self build_tree (now includes the inlined fused sweeps + dot loops) | 1,093,325 | 1,182,339* | *absorbed dots below |
| loop self transition | 502,556 | 477,690 | -4.9% |
| Eigen dot reduction (inner_product) | 281,934 | 0 (inlined into the merged sweeps) | -100% dispatch |
| memcpy (state moves) | 405,205 | 209,695 | **-48%** |
| fused kernel + dispatch | 412,083 | 424,359 | +3% (more grads) |
| transcendentals | 549,606 | 569,872 | +3.7% (more leaves) |

POOL CONSUMPTION: pool+dots+state-memcpy before = 2,380,502 Ir ->
1,869,724 after = **-510,778 (-21.5%)**; the total sampling phase fell
493,447. Loop-self+dots pool 51.5% -> 49.8% share of a smaller total;
absolute pool 1,975,297 -> ~1,660,029 (-16%). What remains is the
recursion structure + the fused sweeps' own element work + copy_pt
memcpys — the pre-declared structural floor (state model), not a
named lever.
PASS COUNT per leaf: 12 element sweeps + 5 memcpy dispatches + 2 dot
dispatches -> 2 sweeps + 1 memcpy (copy_pt). Per merge: 4 compute
loops + up to 6 dot dispatches -> 1 sweep. Per while-iter: 3 memcpys
-> 1 sweep. (Better than the charter's "roughly half".)

LEAN-ARM speed effect: esnc full-run lean 9,830,713 -> 8,433,084 =
1.166x on the lean arm itself; combined with stock 13,138,693 the
full-run ratio is 1.558x (F-23: 1.334x).

## (v) GATE (a) STATISTICAL EQUIVALENCE — PASS

Campaign (raw campaign/ + gate_a_campaign.out + gate_a_extra.out):
2 arms x 6 models x (8 reps on esnc/esc/blr/logmesq, 3 on kidscore/
pilots) x 4 chains, 1000+1000, seeds 20260826+1000r+c, arm C = stock,
arm L = --lean (fused). Draws DIFFER by design (independent realizations
after ~iteration-7 draw-branch decorrelation).

| model | reps | ESSd/draw C | L | ratio | t | rhat max C/L | div C/L |
|---|---|---|---|---|---|---|---|
| esnc | 8 | 1.023 | 1.030 | 1.007 | +0.17 | 1.0046/1.0028 | 6/7 |
| esc | 8 | 0.136 | 0.188 | 1.383 | +1.84 | 1.1525/1.0664 | 944/655 |
| blr | 8 | 0.372 | 0.351 | 0.944 | -1.42 | 1.0117/1.0110 | 0/0 |
| kidscore | 3 | 0.341 | 0.341 | 1.000 | 0 | 1.0067/1.0067 | 0/0 |
| logmesq | 8 | 0.463 | 0.449 | 0.968 | -0.95 | 1.0042/1.0052 | 0/0 |
| pilots | 3 | 0.022 | 0.023 | 1.042 | +0.07 | 1.5552/1.5620 | 2072/1966 |

- ESS_bulk/draw WITHIN NOISE on all 6 (|t| <= 1.84, none significant;
  the first 3-rep read had logmesq -11% — resolved to -3.2% n.s. with 8
  reps; esc +38% is the funnel's realization chaos, C owns the worst
  single rep rhat 1.1525).
- R-hat: < 1.01 BOTH arms on esnc/kidscore/logmesq; blr marginal
  1.0117 (C rep3) vs 1.0110 (L rep5) — one rep of eight EACH arm,
  different reps, symmetric realization noise; esc/pilots exceed 1.01 in
  BOTH arms (funnel/multimodal pathology shared — the F-22 precedent;
  L's max is NOT worse: esc 1.0664 < C 1.1525, pilots 1.5620 ~ 1.5552).
- DIVERGENCES NOT WORSE: aggregate 3022 (C) vs 2628 (L); per-model L
  worse only on esnc (7 vs 6 across 32k draws — noise); esc 655 vs 944
  and pilots 1966 vs 2072 L BETTER; blr/kidscore/logmesq 0/0.
- BONUS VALIDATION: kidscore draws are BITWISE-IDENTICAL C==L (all 3
  reps x 4 chains, canonical-CSV md5 equal) — at n=3 Eigen's dot takes
  the sequential scalar path, T_seq's order matches it exactly, and the
  whole fused driver reproduces stock draws bit-for-bit. The fused
  loop's arithmetic is stock's wherever stock's own reduction is
  sequential.
- ADAPTED STATE (eps/inv_metric, per-seed max-rel-diffs, fused-full vs
  --lean-stock-warmup = stock's own adaptation; raw
  campaign/adapted_diff.json): kidscore 0.0000/0.0000 (bitwise);
  logmesq eps <= 7.8%, metric <= 33.5%; blr eps <= 3.3%, metric <=
  32.5%; esnc eps <= 36.7%, metric <= 59.1%; esc (funnel) eps <=
  139%, metric <= 98%; pilots eps <= 43%, metric <= 46%. These
  per-seed numbers are the chaotic-realization spread, not bias:
  12-seed DISTRIBUTIONS (epsdist/): esnc stock 0.4296+-0.0348 vs fused
  0.4228+-0.0711 (means match -1.6%; fused sd 2x, F=4.2 borderline);
  logmesq stock 0.0797+-0.0096 vs fused 0.0791+-0.0069 (equivalent).
  No downstream effect on ESS/rhat/div anywhere. Reported, per charter.

## (vi) GATE (c) — PASS

- Default path (--lean absent) byte-identity, pre-branch binary
  (fortk_t1r.f23base = build-pr @ 2eb3785) vs branch binary, esnc+blr
  200+200 seed 20260826 c1 arm 1: CSV md5 EQUAL both models —
  5253067ddd95ee9b8dbddf09414aa7ed / b6e8df4bde54722d36ec328cb9fb58b8,
  the exact recorded F-22/F-23 values; grads 3741/11081 identical.
  Raw gate_c/.
- ctest 69/69 PASS (build-pr, -j2). Raw ctest_f24.log.

## (vii) GATE (d) ESS/s END-TO-END — informational

Interleaved same-day (model-major, C then L within rep), 3 reps x 4
chains, 1000+1000, esnc-class 5 (raw gate_d/ + gate_d.out). Draws differ
between arms, so per-arm ESS/per-arm wall:

| model | C/L wall ratio (reps) | ESS/s L/C (reps) |
|---|---|---|
| esnc | 1.044/1.343/1.658 | 1.354/1.482/1.601 |
| esc | 1.260/0.909/2.190 | 1.065/1.239/1.540 |
| blr | 1.728/1.136/1.249 | 1.945/1.007/1.173 |
| logmesq | 1.280/1.195/1.109 | 1.265/1.032/0.911 |
| kidscore | 1.187/1.011/1.064 | 1.187/1.011/1.064 (draws bitwise-equal) |

ESS/s geomean (L/C): **1.232x** — ms-scale walls (4-80 ms cells), noisy
but bracketing Ir 1.360x from below, like F-23. The cleanest cell:
kidscore — draws BITWISE-equal C==L, so its ratio is pure wall speed:
1.011/1.064/1.187 (mean ~1.087) vs its Ir ratio 1.098 — instrument
agreement at the gradient-bound floor.

## VERDICT (for WORKLOG, via parent)

F-24 (fortk/f24-loopfusion @ 4dbbbdd, off fortk/f23-leanwarm @ 2eb3785;
deps/stan patches unchanged +222/-35; NOT pushed):

- ATTRIBUTION before: pool CONFIRMED at 51.5% of the lean sampling
  phase (loop self 44.1% = build_tree 28.5 + transition 13.1 + eval
  2.5; Eigen dot dispatches 7.35%); ~10 element passes + 5 memcpys per
  leaf, 4 loops + up to 6 dot dispatches per merge. After: pool+dots+
  state-memcpy -21.5% absolute; leaf = 2 sweeps + 1 memcpy; merge = 1
  sweep; loop-self share 44.1% -> ~49.8% OF A SMALLER total (absolute
  -16%); what remains is recursion structure + fused-sweep element
  work + copy_pt — the structural floor, no named lever left.
- (a) STATISTICAL: PASS — ESS_bulk/draw within noise all 6 models
  (8 reps esnc/esc/blr/logmesq, 3 kidscore/pilots; ratios 0.944-1.383,
  |t| <= 1.84); R-hat < 1.01 both arms on the well-mixed set (blr's
  two marginal 1.011-1.012 reps are one-per-arm symmetric noise); esc/
  pilots pathology shared with arm C, L max never worse; divergences
  aggregate 3022 C vs 2628 L. BONUS: kidscore (n=3) draws BITWISE C==L
  — where Eigen's own dot is sequential, the fused loop is exactly
  stock. Adapted state: per-seed max-rel-diffs reported (kidscore
  0.0000 bitwise; logmesq/blr eps <= 8%/3%; esnc/esc/pilots tens of
  percent = chaotic realization spread; 12-seed eps DISTRIBUTIONS
  equivalent on means, esnc fused sd 2x stock's — no downstream
  effect).
- (b) SPEED: **1.360x full-run Ir geomean — the 1.30x bar CROSSED**
  (esnc 1.558 / esc 1.495 / logmesq 1.373 / blr 1.324 / kidscore
  1.098; F-23 was 1.228x). Iso-grad caveat: grad parity no longer
  exact (draw branches flip); fused did MORE grads on esnc/esc/
  logmesq (wins understated), -2% on blr, exact on kidscore; per-grad
  ratios geomean 1.371x. THE LOOP PROGRAM IS FINISHED: every named
  lever shipped and the finish line crossed; the residue is the
  gradient kernel floor (kidscore 13.5k Ir/grad) + state-model
  structure (a rewrite, not a lever).
- (c) PASS: default path byte-identical (pre-branch binary vs branch,
  esnc+blr md5 = the recorded F-22/F-23 values; grads identical);
  ctest 69/69.
- (d) INFORMATIONAL: ESS/s geomean 1.232x L/C on interleaved same-day
  walls (ms-scale, noisy, brackets Ir from below); kidscope pure-wall
  cells (bitwise-equal draws) mean ~1.087 vs Ir 1.098 — instrument
  agreement at the floor.
- PR EDIT DONE (bar crossed, F-19 materiality rule): orwell-pr-loops.md
  + gh pr edit 2 (sims1253/stanli#2) — "Beyond byte-identity" section,
  the 1.360x number labeled research-tool/default-off/statistical-
  gated, PR's byte-identity guarantee unchanged.
- SURPRISES: (1) kidscore bitwise C==L — Eigen's dot takes a
  sequential scalar path at tiny n, exactly T_seq's order; a free
  end-to-end correctness proof. (2) The first 3-rep read of gate (a)
  had logmesq ESSd -11% — pure small-sample noise (8 reps: -3.2%,
  t=-0.95); extra reps were run rather than accepting the ambiguity.
  (3) esc gained most (1.297 -> 1.495): deep trees = highest loop-side
  share. (4) esnc fused adapted-eps spread is 2x stock's (F=4.2, n=12,
  borderline) — means equal, no downstream effect, reported as found.
- Rules held: <=4 concurrent sampling procs (4-chain cells only; Ir
  campaign serialized), CPU only, -j2 builds, no upstream, no push,
  other worktrees'/logs' sources and WORKLOG untouched
  (/tmp/review/stanli never accessed), raw under bench/fortk_f24/.
