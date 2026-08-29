# fortk-prs log — draft PR split of the fortk trunk onto sims1253/stanli

Started: 2026-08-28. Charter: hub-and-spoke PR topology off the fork's main
(85a8f11). Hub = fortk-pr/jit-tier (the fused-JIT tool, full lineage, no
walnuts/eigh/deps-stan patches). Spokes off the hub: fortk-pr/sampler-loop
(F-10 + F-17), fortk-pr/eigh (F-13.2), fortk-pr/walnuts (F-11.2). Rules: fork
only (origin = git@github.com:sims1253/stanli.git), never push main, never
force-push, trunk fortk/t2-coverage + other worktrees + /tmp/stanli-b7a3fd5
untouched, WORKLOG.md untouched (this file is the lane log). Builds -j2 max
(earlyoom lessons). Gates per branch before its PR opens; never loosened.

## Setup / pre-flight (2026-08-28)

- Commit graph verified (git log --graph): all lineage commits descend from
  85a8f11 linearly; 0243aad (census) and 0af980c (T2 vendor) are SIBLINGS off
  b7a3fd5 (F-7 branched before census landed) — pick order per charter:
  3687e52 f23a9ab a2e8615 | e55ea85 d1f234d | b7a3fd5 0243aad | 0af980c
  a6e537d f8a1f12 | b070875 9b2bf80 | c37b623 | 4690a00-content.
- 4690a00 is NON-merge (parent 921a6fc): regions.cpp +17 only — --delta/
  --max-depth plumbing. One hunk targets the walnuts arm (cfgw.max_depth)
  and the usage-string context references --w-* flags: both must be adapted
  to the jit-tier tree (walnuts-arm hunk dropped; usage line re-anchored).
- Spoke scopes verified from git show --stat: loop spoke = {e750504: deps
  patch 0001 + fetch.sh; 1bfcbb5: model_adapter cache/counters + mallopt;
  feaa4a1: direct_nuts.hpp/model_adapter.hpp/nuts.cpp; 7a6aeee: patch 0002 +
  fetch.sh; 2bc451a: patch 0003} — no regions.cpp hunks expected to conflict
  with jit-tier content. eigh spoke = mir/mir_reader/lower/optable/matrix_fns/
  executor/graph + test_eigen + regions.cpp FORTK_DUMP (+23). walnuts spoke =
  third_party headers + walnuts.{hpp,cpp} + regions.cpp flags (+45) + new
  test — usage/arg-parse conflicts EXPECTED vs jit-tier's --fits/--delta.
- Shared deps/stan (external/stanli/deps/stan, symlinked by all worktrees)
  carried F-17 patches 0001+0002+0003 (base_nuts +212/-35, diag_e_metric,
  expl_leapfrog). RESTORED PRISTINE via git checkout (diff empty) for the
  hub + eigh + walnuts builds; the loop spoke reapplies 0001..0003 from its
  own tracked patches via the fetch.sh hook (idempotent, reverse-checked).
- gh authenticated as sims1253 (repo scope) — PRs can open.
- Worktrees (fresh, off the fork): external/stanli-pr-jit, external/
  stanli-pr-loop, external/stanli-pr-eigh, external/stanli-pr-waln; deps
  symlinks ../../stanli/deps/{math,stan,stanc3} per the established pattern.

## Hub: fortk-pr/jit-tier

### Hub gates @85a8f11 base (2026-08-28) — ALL PASS

- Cherry-picks: 14 commits. 3 conflict rounds, all in tools/fortk/regions.cpp,
  all usage-string/arg-parse unions (b070875 x census; 9b2bf80 x census;
  c37b623 x census; 4690a00 usage re-anchored WITHOUT the --w-* walnuts flags,
  its walnuts-arm max_depth hunk auto-merged into the stock walnuts arm —
  faithful to the original commit which targeted WalnutsConfig.max_depth).
  Census commit (0243aad) coexists with F-8/F-9/F-14 plumbing — new semantic
  combination (trunk never carried census); proven by gates below.
- Build: cmake Release, -j2, fortk_t1r + stanli_run + full test suite: clean.
- ctest: 63/63.
- Verify (64 pts, seed 20260826): esnc 0.0/2.485e-16 bitwise (+DIRECT) —
  EXACT match to F-12's recorded value; blr 3.249e-16/2.423e-16; diamonds
  3.882e-16/2.491e-16 (F-4 class). BENCH esnc 8.78x, blr 3.57x, diamonds
  0.97x (bandwidth-bound, known).
- --sample 200 200 esnc: 200/200 draws, 0 divergences, worst z 2.34, CSV +
  SAMPLE_WALL + SAMPLE_ADAPT (F-16 flags bite) all present.
- --fits 4 blr: FITS_SUMMARY n=4 chains=4, 166,386 fits/h at the 200+200
  smoke scale.
- Pre-pick binary preserved: bench/fortk_prs/loop/fortk_t1r.prepick.

### Spoke: fortk-pr/eigh @85a8f11 base (2026-08-28) — ALL GATES PASS

- Picks 53db89a/844ad46/08db4b6: ALL CLEAN (auto-merge; regions.cpp FORTK_DUMP
  hunks landed away from census/fits/delta zones).
- Build -j2 clean; ctest 63/63 incl. test_eigen (fused kernel vs math oracle
  + stock two-op pair).
- Kronecker 64-pt BITWISE cross-stanc (FORTK_STANC=F-13 built stanc vs pinned
  nightly 4d440ee; FORTK_DUMP): grad 0.0 / logp 0.0; ONE md5
  (2d6ae1c66c177e79c75dd3b3c2c80e6f) across all four dump files
  (fused/stock x ex0-interpreter/ex1-fortk-region).
- dump_ops: fused graph = 2 EIGENDECOMPOSE_SYM (out len900 + out2 len30 x2);
  stock = 4 ops (2 EIGENVECTORS_SYM + 2 EIGENVALUES_SYM).
- Non-fusion neutrality: esnc verify UNCHANGED vs hub (0.0/2.485e-16, default
  stanc path) — tuple grammar inert without tuple nodes.

### Spoke: fortk-pr/walnuts picks (2026-08-28)

- 316afe2 clean; 7d7c9da CONFLICT x2 in regions.cpp (usage + arg-parse) —
  the jit-tier's --census/--fits/--delta lines vs the --w-* flag block;
  resolved as full union (all flags coexist); 58ec219 clean after.
  cfgw knob wiring + SAMPLE_W_ADAPT + f112() CSV tag verified present.

### Spoke: fortk-pr/walnuts @85a8f11 base (2026-08-28) — ALL GATES PASS

- Build -j2 clean; ctest 64/64 (63 + test_walnuts_adapt property suite).
- D0 all-off byte-identity vs the jit-tier pre-pick binary: 8/8 BODY-IDENTICAL
  (esnc+blr x seeds {20260826,7} x init {u,pf}, 200+200, 202 rows each).
  Header-only diff = the f112(chop=0,...,batch=1,decay=0.5) provenance tag
  7d7c9da adds (documented knob-provenance line, values all-default) —
  draws themselves byte-identical. (First cmp round flagged 8/8: header tag;
  also the pf arms were silently skipped by zsh no-word-split on $EXTRA —
  rerun with explicit args, lesson logged.)
- --w-batch 10 one-chain kidscore smoke (1000+1000, walnuts+pf): clean run,
  SAMPLE_W_ADAPT batch=10 active, chain in the F-9 basin (beta.1 26.31,
  sigma 18.24, frozen stepsize 0.294); walnuts' NaN sampler-diagnostic
  columns are stock behavior (tool prints divergences=0(n/a-NaN)).

### Spoke: fortk-pr/sampler-loop @85a8f11 base (2026-08-28) — ALL GATES PASS

- Picks e750504/1bfcbb5/feaa4a1/7a6aeee/2bc451a: ALL CLEAN (file-disjoint from
  jit-tier-only content, as pre-flighted; no regions.cpp conflicts).
- Two-stage build for the counter arithmetic: stage 1 = detached f9c3165
  (jit + F-10) + deps/stan patch 0001 only; stage 2 = branch tip (F-17
  seam/threading/hoists) + patches 0001+0002+0003 (shared deps/stan,
  progressive application, matching the F-10/F-17 atomic-deps discipline).
- ctest: 63/63 (both stages; this spoke adds no tests).
- GRAD_COUNTER ARITHMETIC EXACT: stage-1 esnc exec1=4079 hits1=61 (F-10/F-15/
  F-16's recorded value EXACTLY); final esnc 3741/0, blr 11081/0, hier_2pl
  14785/0 — the last two EXACTLY F-17's recorded post-(d) values; esnc total
  drop 4140->3741 = 399 = transitions-1 exactly, hits->0.
- BYTE-IDENTITY vs the jit-tier pre-pick binary (pristine deps) on
  esnc/blr/hier_2pl --sample 200 200: 3/3 IDENTICAL — the pooled F-10+F-17
  bit-neutrality holds across the whole stack in one comparison.

### Rebase round (base 33f79dea) — pre-rebase tips recorded

- Pre-rebase tips: hub 5ce8903, sampler-loop f8a97b7, eigh c4c8b74,
  walnuts 7527808 (all gated above at 85a8f11).
- origin/main verified 33f79deaf5a9 (77 commits ahead of 85a8f11). Overlap
  surface pre-flighted: deps/fetch.sh (upstream replaced the stanc3 nightly
  download with a STANC3_SRC_SHA provenance scheme — our patch hook must
  re-anchor between `fetch stan` and their new stanc3 block), optable.hpp
  (upstream X(OP_ALGEBRA_SOLVER) mid-list vs our PLAIN(OP_FORTK_REGION)
  append at the tail macro — different hunks), mir.hpp (+2 Break/Continue
  stmt kinds), executor.cpp (+2 register_algebra_kernels), CMakeLists
  (source lists + new tests ~line 256-510 vs our tool targets ~516+),
  compile.hpp/capi.h comment/additive only. graph.hpp/model_adapter.hpp/
  nuts.cpp/walnuts.cpp/matrix_fns.cpp/tools/fortk/* NOT touched upstream.

### Rebase execution (2026-08-28)

- Shared deps/stan restored pristine before rebased builds (patches live in
  the loop branch's tracked patches/deps-stan/ + fetch.sh hook; re-applied
  for the loop build only).
- fortk-pr/jit-tier: rebase --onto origin/main(33f79dea) 85a8f11 — ALL 14
  COMMITS CLEAN, zero conflicts (our zones were file/region-disjoint from
  upstream's 77 commits: optable tail vs mid-list X(OP_ALGEBRA_SOLVER),
  CMakeLists tool-target tail vs source-list head, tools/fortk/* new files).
- fortk-pr/eigh + fortk-pr/walnuts: rebase --onto rebased-hub 5ce8903 —
  all clean (3/3 each).
- fortk-pr/sampler-loop: ONE conflict, exactly the pre-flighted one —
  e750504's fetch.sh hook vs upstream's stanc3 provenance rewrite. Resolved:
  patch hook re-anchored between `fetch stan` and upstream's new
  STANC3_SRC_SHA block; the old nightly-download block dropped (upstream's
  replacement kept verbatim). 7a6aeee's sorted-loop generalization then
  applied clean on top. bash -n verified.
- Topology after: hub = 14 commits on 33f79dea (merge-base exact); spokes
  5/3/3 commits stacked on the rebased hub.

### Rebase re-gates (fast gates per branch at 33f79dea)

- HUB: fresh build clean; ctest 69/69 (upstream grew 63->69). esnc verify
  0.0/2.485e-16 (+DIRECT), blr 3.249e-16/2.423e-16 — IDENTICAL to the
  85a8f11 numbers. esnc --sample 200 200: CSV BYTE-IDENTICAL to the
  85a8f11-base CSV (cross-base identity holds — same stanc pin, upstream
  lowering changes did not alter this path's graph or draws).
- WALNUTS: build clean; ctest 70/70 (69 + test_walnuts_adapt). D0 all-off
  body-byte-identical vs the REBASED hub binary 4/4 (esnc+blr x 2 seeds,
  within-rebase comparison; header f112 tag the only diff). --w-batch 10
  kidscope smoke clean (batch=10 active).

### Rebase re-gates (continued) — ALL PASS

- EIGH: build clean; first ctest run 5 FAILURES in upstream's test_mir_decode
  ("unknown expression tag" at byte 14/18). ROOT CAUSE (real finding, not a
  hack-around): portable-MIR v2 wire expression tags are Expr::Kind ENUM
  ORDINALS (test encoder writes static_cast<uint8_t>(kind); reader maps via
  positional kExprTags where tag 10 == Unsupported is the last decodable).
  The F-13.2 insert of TupleProjection BEFORE Unsupported shifted the
  ordinal — invisible at 85a8f11 (no v2 codec existed), exposed by upstream's
  new decoder. FIX: moved TupleProjection AFTER Unsupported (commit 9f38119
  on the branch, with the invariant documented in-mir.hpp); the kind is
  produced only by the legacy-sexp reader, all consumers switch on the
  enumerator. After fix: ctest 69/69 incl. test_eigen AND test_mir_decode.
  Kronecker cross-stanc at the rebased tip: 0.0/0.0, dumps byte-identical
  (ex0+ex1); esnc neutrality bitwise/2.485e-16; dump_ops 2 EIGENDECOMPOSE_SYM.
- LOOP (patches 0001+0002+0003 re-applied to shared deps/stan from the
  branch's tracked patches): build clean; ctest 69/69. Draws byte-identical
  vs the REBASED hub binary 3/3 (esnc/blr/hier_2pl, within-rebase gate);
  GRAD_COUNTER esnc 3741/0, blr 11081/0, hier_2pl 14785/0 — EXACTLY the
  85a8f11-base values.
- Cross-base note: the hub's esnc --sample CSV is byte-identical across the
  85a8f11 and 33f79dea bases (same stanc pin, upstream lowering changes did
  not alter this path), so the 85a8f11-byte-identity gates carry over.

### PR round (2026-08-28)

### PR round COMPLETED (2026-08-28, by parent after agent usage-limit death at the "PR round" header)

Agent died (5h usage limit) after pushing branches but before creating
PRs. Parent verified tips on remote (hub 68c0495, loop 91046eb, eigh
9f38119, walnuts 6d59215 — all merge-base 33f79dea), trimmed the two
longest bodies into the References line (all <=23 lines), created:

- #1 [fused jit] fused-JIT tier ... (fortk-pr/jit-tier -> main) DRAFT
- #2 [fused jit] base_nuts sampler-loop package ... (-> fortk-pr/jit-tier) DRAFT
- #3 [fused jit] eigendecompose_sym ... (-> fortk-pr/jit-tier) DRAFT
- #4 [fused jit] walnuts adaptation knobs ... (-> fortk-pr/jit-tier) DRAFT

Bodies: orwell-pr-{jit,loops,eigh,walnuts}.md (editable pre-undraft).
LANE COMPLETE.
