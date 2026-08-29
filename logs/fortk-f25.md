# F-25 incremental log — kernel-side gradient floor (kidscore/blr)

Pre-registered: WORKLOG.md "F-25 pre-registered".
Base: worktree external/stanli-pr-jit, branch fortk-pr/jit-tier @ 68c0495.
New branch: fortk/f25-kernelfloor (created off 68c0495, clean).

## Session 2026-08-29

Setup:
- WORKLOG read in order: F-24 VERDICT, F-25 charter, F-7 VERDICT, F-20
  VERDICT (+ full logs f7/f19/f20/f24).
- deps/stan was NOT pristine: loop-branch patches 0001-0003 live
  (+222/-35, 3 files). SAVED to bench/fortk_f25/deps_stan_loop_patches_saved.diff
  (383 lines) and RESTORED via git checkout -- (diff now EMPTY, verified).
  The loop program is finished (F-24 verdict) so pristine is the resting
  state; noted per charter.
- Box quiet (load 0.28-1.6, no foreign bench procs).

## Step 1 — ATTRIBUTION (F-20 instrument, line-level via -gdwarf-4 region .so)

Reused bench/fortk_f20/fortk_t1r_cg_jit (byte-copy of 68c0495 tool + --cg
knob). Graph check vs F-19 census records: dump_ops kidscore_momiq (7 ops:
CONSTRAIN_LOWER, CAUCHY_LPDF, INDEX x2, FMA len434, NORMAL_LPDF len434,
ADD_N) and blr (5 ops: CONSTRAIN_LOWER, NORMAL_LPDF N=5 prior, NORMAL_LPDF
N=1 prior, NORMAL_ID_GLM_LPDF N=100 D=5, ADD_N) — identical to the F-19
fullops records; totals 2,240,621 / 357,621 Ir per 200 fused evals
BYTE-IDENTICAL to F-20's census raw (stanc pin 4d440ee era stands).
Line attribution: precompiled the SAME region .c with -gdwarf-4 into side
cache dirs (FORTK_REGION_CACHE), code identical (Ir totals unchanged);
callgrind_annotate --auto. Raw attr/.

kidscore fused 11,203 Ir/eval (F-20 census row):
| component | Ir/eval | share |
|---|---|---|
| bwd memset(la[440]) — zeroing the bwd local-adjoint array | 3,537 | 31.6% |
| fwd NORMAL_LPDF loop (434 el, scalar: isig div + ys + acc + t3 + sigma-acc) | 4,338 | 38.7% |
| bwd FMA la[3] dot loop (scalar reduction, 434) | 1,326 | 11.8% |
| bwd FMA la[4] sum loop (scalar reduction, 434) | 455 | 4.1% |
| S-snapshot memcpy t3[434] | 353 | 3.1% |
| fwd FMA loop (auto-vectorized, 0.75 Ir/elem) | 325 | 2.9% |
| bwd density la[5+i] += d*S[3+i] (auto-vec, 0.79/elem) | 341 | 3.0% |
| scalar libm (exp 1, log 1, log1p 1 per eval) | 166 | 1.5% |
NOTE (instrument honesty): callgrind counts glibc's ERMS rep-stosb memset
~per BYTE (3,537 Ir for 3,520 B) — the memset's Ir share is inflated vs
hardware; killing it is still exact and still helps real cycles (L1
traffic), but the Ir win overstates the wall win. Recorded.

blr fused 1,788 Ir/eval:
| component | Ir/eval | share |
|---|---|---|
| fwd GLM GEMV m[n]+=col[n]*b (5x100, auto-vec 0.77 Ir/elem) | 386 | 21.6% |
| bwd 5 beta-column dots (block-of-4 since F-7, 0.68/elem) | 340 | 19.0% |
| fwd t8 compute (auto-vec) | 126 | 7.1% |
| fwd 3 scalar libm logs (log(arena[9]) x2, log(v8)) | 162 | 9.1% |
| S-snapshot memcpy t8[100] | 113 | 6.3% |
| bwd t3[n] = isig*S[8+n] (auto-vec) | 67 | 3.8% |
| fwd m[100] zero-init (memset) | 64 | 3.6% |
| fwd GLM s0..s3 reduction (block-4 since F-7) | 31 | 1.7% |
| fwd priors NORMAL_LPDF N=5 + N=1 (SCALAR — under kMinLanes) | ~30 | 1.7% |
| fwd CONSTRAIN_LOWER exp + rest | ~90 | 5% |
VERDICT (attribution): blr's likelihood is ALREADY at the F-7 vecmath
floor (GEMV + reductions + bwd dots vectorized). What remains scalar =
priors N=5/N=1 (below every lane threshold — deliberately NOT vectorized,
same rule as F-7's bernoulli n>=8 / CONSTRAIN n>=16), 3 scalar libm logs
(no vendored log kernel; log(arena[9]) repeated on the same slot — CSE
would be exact but is not a vectorization lever), snapshot memcpy
(recompute costs more than the copy). kidscore's floor is (i) the la
memset, (ii) the scalar NORMAL_LPDF loop (two FP reductions block
auto-vectorization under -ffp-contract=off/no-fast-math), (iii) the two
scalar FMA-bwd reductions, (iv) INDEX/ADD_N scalar cells.

## Step 2 — DESIGN (recorded before building)

F-7 pattern exactly (block-of-4 with 4 independent lane accumulators +
((s0+s1)+s2)+s3 combine + scalar tail; per-element products identical;
only the reduction structure reassociates — the 1e-9 gate arbitrates):
1. NORMAL_LPDF fwd block-of-4 for N >= 32 (the GLM emitter's own
   threshold convention): lanes for acc and for the scalar-arg partials
   (p0/p1/p2 when the arg is len-1); vector partials stored per lane.
   Blast radius: kidscore 434, logmesq 46, pilots 40, radon_pp 12573,
   radon_vis 85 (all re-verified in the census gate). esnc N=8, blr
   priors 5/1 stay scalar.
2. FMA bwd scalar-cell reductions block-of-4 for n >= 32 (kidscore's
   la[3]/la[4] loops): the exact GLM-bwd dot shape already in the tree.
3. la-memset kill: first-write conversion — a bwd la write onto the
   memset zeros is arithmetically a plain store. Emitter tracks per-slot
   first writes; converted classes: density_bwd, FMA bwd, ADD_N bwd,
   INDEX bwd, CONSTRAIN_LOWER bwd, NORMAL_ID_GLM bwd finals. Everything
   else (bernoulli family incl. fused chains, MVN, LKJ, CHOL_CORR,
   CONSTRAIN_LU, GEMM, SET_*, SLICE, GATHER, binops) pre-marked
   keep-zeros; memset emitted iff any slot still needs zeros. Exact by
   construction in both memset outcomes.
4. Region key version bump fortk-t2r-v4 -> v5 (cache invalidation).
Deliberately NOT touched: blr priors/logs/memcpy (attribution says
floor), S snapshots (recompute > copy), cauchy/student_t fwd loops
(F-7's verdict stands), the executor (unfused arm = oracle, untouched).

## Step 2 — BUILD NOTES (two iterations, recorded honestly)

- v5 (commit 8de7cd7): single block-of-4 NORMAL_LPDF loop. MEASURED
  only 10.0 -> 7.0 Ir/elem: clang reached 2-wide SLP with stack spills
  (12 live values: 2 x 4 lane accumulators + per-lane isig/ys/sd + t3
  stores; it unrolled x12 and packed pairs). Disassembly inspected
  (attr/fwd.asm). The FMA-bwd dots (2 arrays, few lives) DID reach
  4-wide (0.75 Ir/elem) — confirming the live-value-count hypothesis.
- v6 (commit db60cf0): restructured to the F-7 multi-pass shape —
  pass A elementwise y_scaled into a BLOCK-LOCAL array (not a region
  temp: every registered temp gets memcpy'd to S, which would give back
  exactly what it saves) + pass B pure 4-lane reductions over it.
  kidscore 5,996 -> 5,172 Ir/eval. REGION KEY v5 -> v6 (the key hashes
  version+ops, not the emitted body — a version bump is REQUIRED on
  every emitter-output change or stale cached .so load).
- Instrument binary gotcha (hit + fixed): the hand-built --cg binary
  needs -DFORTK_VECMATH_DIR=<abs tools/fortk> (the cmake build defines
  it; without it vecmath regions fail clang './vecmath.c' — hier_2pl/
  lsat/wells census rows initially rc=3, all recovered after rebuild).
- f25base/f25branch paired binaries saved in bench/fortk_f25/ (same
  day, same pristine deps, same libstanli.a).

## GATE (a) VERIFY (never loosened; 64 pts seed 20260826 vs unmodified executor)

- kidscore 1.390e-15 / 4.084e-16 PASS (region AND direct).
- blr 3.249e-16 / 2.423e-16 PASS — BYTE-IDENTICAL to the F-19 record
  values (blr's arithmetic is untouched, as attribution predicted).
- Spot: esnc 0.0/2.485e-16 (bitwise, IDENTICAL record); hier_2pl
  1.042e-15/1.221e-14 (IDENTICAL record); wells 1.631e-15/4.757e-15
  (IDENTICAL record); arma11 2.120e-16/3.698e-16 PASS (was
  7.778e-16/3.958e-15 — its N=200 normal reassociated; still ~3
  orders under the gate).
- Census verify: 20/20 accepted PASS (all < 1e-9; bym2 was "bitwise",
  now 2.040e-15 — its l1921 FMA/normals reassociated; in-gate).
  lotka rc=134 = the documented nan-ODE verify crash, unchanged.

## GATE (b) Ir (callgrind, primary) — census rows, v6 vs F-20 records

Unfused arm byte-matches F-20 on every model checked exactly
(6,560,827 hier_2pl / 1,383,430 lsat / 508,074 wells / 9,646 blr) —
oracle untouched, instrument stable.

| model | Ir/eval unf | fus | ratio | F-20 ratio | fused chg |
|---|---|---|---|---|---|
| kidscore | 40,338 | 5,172 | **7.80** | 3.60 | **-53.8%** |
| logmesq | 10,869 | 1,576 | **6.90** | 4.98 | -27.8% |
| radon_pp | 1,016,118 | 398,316 | 2.55 | 2.33 | -8.6% |
| radon_vis | 139,183 | 49,966 | 2.79 | 2.55 | -8.3% |
| bym2 | 993,660 | 674,737 | 1.47 | 1.40 | -5.3% |
| pilots | 12,691 | 2,825 | 4.49 | 4.33 | -3.7% |
| arma11 | 85,960 | 13,956 | 6.16 | 5.97 | -3.1% |
| dogs | 348,119 | 306,583 | 1.14 | 1.11 | -2.0% |
| lsat | 1,383,430 | 421,217 | 3.28 | 3.25 | -1.1% |
| esnc | 4,686 | 518 | 9.05 | 8.98 | -0.7% |
| blr | 9,646 | 1,787 | 5.40 | 5.39 | -0.1% |
| hier_2pl | 6,560,827 | 2,393,294 | 2.74 | 2.74 | -0.1% |
| (others: accel/esc/garch/gp_regr/diamonds/kronecker/low_dim/wells <=0.2%) | | | | | |
| GEOMEAN (20 accepted) | — | — | **2.737** | 2.546 | +7.5% |

- Ir/grad (the primary per-model numbers): kidscore 11,203 -> 5,172
  (-53.8%); blr 1,788 -> 1,775 (-0.7%, at the attributed floor).
- FULL SAMPLING RUN Ir (cg_sample_run, 200+200 seed 20260826 c1):
  kidscore 466,965,207 -> 259,969,562 = **1.796x**; blr 96,362,004 ->
  96,348,107 = 1.000x. (Grad counters unavailable in-tool on the hub
  branch — F-20 documented the same; per-grad story carried by the
  per-eval rows.) Context: F-24's loop-branch kidscore full-run ratio
  was 1.098x BECAUSE of this kernel floor; with the F-25 kernel the
  fused-loop full-run would re-rate ~2.1x (not re-measured here — the
  loop branch is a different lane).
- Kidscore fused-arm re-attribution (v6): fwd 3,743 + bwd 721 +
  S-memcpy 364 + dispatch/libm ~350 = 5,172/eval (was fwd 4,792 + bwd
  5,703 incl memset + memcpy 364 + ~350). Remaining floor: elementwise
  store/load streams (FMA fwd, pass A, t3 S-snapshot 364 + bwd 222),
  pass B reductions, executor dispatch — the vecmath floor for this
  graph shape.

## GATE (c) ctest + default-path byte-identity

- ctest 69/69 PASS (build-pr, -j2).
- Byte-identity (200+200 sampling CSVs, paired same-day binaries, all
  20 runnable models): 9/20 BYTE-IDENTICAL — blr b6e8df4bde54, diamonds,
  dogs, esc 9d547852e9, esnc 5253067ddd95 (= the recorded F-22/F-23
  value), gp_regr, kronecker, low_dim, wells 5bdde1f6a287 (all md5s
  equal base). 11 DIFF — accel, arma11, bym2, garch11, hier_2pl,
  kidscore, logmesq, lsat, pilots, radon_pp, radon_vis — every one
  confirmed to carry a >=32-lane scalar-sigma NORMAL_LPDF or >=32-lane
  FMA (fullops checked), i.e. exactly the reassociating paths; all
  verify-gated < 1e-9. Gate holds: untouched models byte-identical,
  touched models statistical-gated per the F-24 precedent.

## GATE (d) ESS/s — informational, interleaved same-day, plain fused-nuts

3 reps x 4 chains, 1000+1000, arms B (base emitter) / K (v6),
model-major interleaved. Draws identical on esnc/esc/blr (ESS values
equal to the draw — byte-identity confirmed again end-to-end); kidscore
and logmesq draws differ (reassociation -> draw-branch decorrelation,
F-24's documented mechanism).

| model | ESS/s K/B per rep |
|---|---|
| esnc | 0.550/0.646/0.937 (draws identical; ms-scale wall noise) |
| esc | 1.011/1.041/0.982 (identical) |
| blr | 1.121/0.899/1.253 (identical) |
| logmesq | 1.027/1.043/1.317 |
| kidscore | **1.751/1.302/1.208** (walls 1.615/1.159/1.491) |
| geomean | 1.035 (dragged by esnc's noisy 10-20 ms cells) |

kidscore ESS/s mean ~1.42 brackets the full-run Ir 1.796x from below
(sampler per-grad overhead unchanged) — same instrument-agreement shape
as F-23/F-24.

## PR EDIT (materiality rule)

Census headline moved: kidscore row 3.60x -> 7.80x (+117%), geomean
2.546 -> 2.737 (+7.5%), on real code change (not drift) in this PR's
own subject area. Addendum added to orwell-pr-jit.md + gh pr edit 1
(sims1253/stanli#1) — verified live==local (title-strip + trailing
newline only, the F-20 pattern).

## Rules held

<=4 concurrent procs (4-chain cells; census/Ir serialized), CPU only,
-j2 builds, no upstream, no push (fortk/f25-kernelfloor @ 8de7cd7 +
db60cf0, NOT pushed), deps/stan restored PRISTINE before any
timing/build (loop patches saved to
bench/fortk_f25/deps_stan_loop_patches_saved.diff; verified empty diff
— note the branch rebuild relinked libstanli.a against pristine deps,
matching the jit-tier binary era), other worktrees untouched
(/tmp/review/stanli never accessed), WORKLOG/other logs untouched, raw
under bench/fortk_f25/.

## VERDICT (for WORKLOG, via parent)

fortk/f25-kernelfloor @ db60cf0 (off fortk-pr/jit-tier @ 68c0495),
emitter fortk-t2r-v6, only tools/fortk/regions.cpp touched.
