# F-12 log — consolidation: cherry-pick F-8/F-9 plumbing onto fortk/t2-coverage

Started: 2026-08-26. Binding charter: WORKLOG "F-12 (consolidation,
pre-registered)". Executed by agent in worktree
/home/m0hawk/Documents/apin/stan/external/stanli-f7 (branch fortk/t2-coverage
@ f8a1f12). Pinned F-8/F-9 measurement worktree /tmp/stanli-b7a3fd5 (detached
@ 833d8de) is READ-ONLY for this task (never modified/reset).

## What is being moved

- d4801b5 "fortk F-8 plumbing: --seed/--chain-id/--sampler for --sample;
  fused draws CSV; SAMPLE_WALL" — tools/fortk/regions.cpp only (138 lines).
- 833d8de "fortk F-9: --init pf — multi-path pathfinder init for
  nuts+walnuts" — runtime/include/stanli/estimate.hpp (+32),
  runtime/src/pathfinder.cpp (+78), tools/fortk/regions.cpp (+89).

## Pre-flight divergence analysis (before cherry-picking)

git diff b7a3fd5..f8a1f12 -- tools/fortk/regions.cpp: 31 hunks, ALL between
base lines 198 and 2140 (emitter/carver/coverage/parallel-clang internals).
The zones the pinned commits touch are textually UNTOUCHED by F-7:

1. include block (base ~30-40): identical (F-7 first hunk at base 198).
2. usage string + arg-parse loop (base ~1801-1832): identical (F-7 hunks
   jump from base 1780 to 1833).
3. sample driver "gate (c)" (base ~2479-2610): identical (F-7 has no hunks
   after base 2140) — F-7 never modified the sampling smoke section.
4. runtime/ tree: ZERO diff b7a3fd5..f8a1f12 — 833d8de's runtime hunks
   apply on identical text.

So the cherry-picks are expected to apply without textual conflicts; the
consolidation risk is SEMANTIC, not textual, and the gates below exist to
prove both sides' features coexist:

- F-7 side that must survive: vecmath emission (fortk-t2r-v4, region key
  suffix "|vm1"), coverage opcodes, obs-chain fusion, CompilePool parallel
  clang, direct path.
- Pinned side that must survive: --seed/--chain-id/--sampler nuts|walnuts,
  SAMPLE_WALL lines, draws CSV (nuts + walnuts), --init pf/--pf-seed +
  run_pathfinder_multi + PF_INIT/PF_WALL + pf_draws CSV, and default-path
  behavior byte-identical to the pinned binary.

## Log

- Preflight: worktree clean at f8a1f12; pinned worktree untouched
  (verified `git status` clean, detached @ 833d8de).

## Conflicts and resolutions

NONE — both cherry-picks applied as clean auto-merges (b070875 = d4801b5,
9b2bf80 = 833d8de; original authors/dates/messages preserved plus git's
"cherry picked from" trailers). This matches the pre-flight analysis: F-7's
regions.cpp evolution (31 hunks) lives entirely in base lines 198-2140
(carver/emitter/vecmath/parallel-clang), while the pinned commits touch the
include block, the usage/arg-parse loop, the "gate (c)" sample driver
(base 2479-2610), and runtime/ (zero F-7 diff). The task brief's "expect
real conflicts in regions.cpp" was the conservative prior; the actual
divergence was file-region-disjoint.

Because "no textual conflict" does not prove coexistence, the semantic
merge was verified explicitly instead:

- F-7 side intact after both picks: emitter_version "fortk-t2r-v4"
  (regions.cpp:2923), region-key suffix "|vm1" (:3018), CompilePool
  parallel clang (:2832 direct + :3013 regions), uses_vecmath plumbing
  (emitters at :733/:1634/:2114/:2262, include injection :2668),
  coverage opcodes, obs-chain fusion. Confirming behavior: verify numbers
  below are bit-for-bit F-7's recorded values; arma11 still carves to
1 region over all 806 ops.
- Pinned side intact: --seed/--chain-id/--sampler walnuts, SAMPLE_WALL
  (both samplers), nuts+walnuts draws CSVs, --init pf/--pf-seed,
  run_pathfinder_multi, PF_INIT/PF_WALL, pf_draws CSV, splitmix64
  chain pick — all present and exercised (gates 4/5).
- Nothing dropped; no feature was unmergeable, so the charter's
  tie-breaker rules (sampling-plumbing wins CLI, emitter wins internals)
  never had to fire.

## Gates (all PASS, none loosened)

1. Build: `cmake -B build-f7` (re-configured, Release) + `cmake --build
   build-f7 -j4` — exit 0, zero errors; regions.cpp.o, pathfinder.cpp.o
   (both libs), libstanli.so, fortk_t1r all relinked (20:04).
2. ctest -j4 in build-f7: **63/63 passed, 0 failed** (0.69 s).
3. Tool verify (64 pts, seed 20260826; bench/fortk_f12/<model>/run.log):
   - eight_schools_noncentered: grad 0.000e+00 (bitwise), logp 2.485e-16
     (+ VERIFY_DIRECT bitwise PASS)
   - arma11: 7.778e-16 / 3.958e-15 (+ DIRECT PASS) — matches F-7 exactly
   - hier_2pl: 1.042e-15 / 1.221e-14 — matches F-4/F-7 exactly
   - wells_dist100_model: 1.631e-15 / 4.757e-15 (+ DIRECT PASS)
   All << 1e-9.
4. Default-path byte-comparability, esnc `--sample 200 200` (default
   init/seed 20260826): consolidated build-f7/fortk_t1r vs pinned
   /tmp/stanli-b7a3fd5/build-f8/fortk_t1r (run from its own cwd):
   `sample_nuts_seed20260826_chain1.csv` **cmp BYTE-IDENTICAL** (200
   rows x 10 cols; header identical incl. no init= suffix). SAMPLE/
   SAMPLE_CSV stdout lines identical; SAMPLE_WALL differs only in
   timing digits. Zero PF_ lines on the default path. (esnc is
   vecmath-free as the charter anticipated — the byte-identity scope
   is exactly the model the charter named.)
5. --init pf smoke, blr, F-9 protocol verbatim (4 concurrent chains,
   --seed 2026082{6..9} --chain-id 1 --sampler walnuts --init pf
   --pf-seed 20260826, 1000+1000; bench/fortk_f12/g5_blr/):
   - All 4 chains ONE sigma basin, reproducing F-9: per-chain all-draws
     sigma mean 1.0339/1.0482/1.0514/1.0402, last-200 sd 0.067-0.084
     (F-9: 1.0339±0.0743); no parking at 4.8/2.2/1.7/0.7.
   - PF signature matches F-9 exactly: paths_ok=2/4, the same two paths
     fail (line-search/no-start), khat=0.080, pf wall ~2 ms.
   - pf_draws_seed20260826.csv bit-identical across the 4 chain
     processes (shared pf-seed contract holds on the F-7 emitter).
   - Bonus: nuts+pf 200+200 smoke runs clean (same pick=692 as chain0
     for the same (pf,seed,chain) key — splitmix64 keying deterministic);
     statistical-fallback z-scores 0.50-3.67 (normal for 200 draws).

## Final state

Branch fortk/t2-coverage @ 9b2bf80 (NOT pushed):

- 9b2bf80 fortk F-9: --init pf — multi-path pathfinder init for
  nuts+walnuts (cherry-pick of 833d8de)
- b070875 fortk F-8 plumbing: --seed/--chain-id/--sampler for --sample;
  fused draws CSV; SAMPLE_WALL (cherry-pick of d4801b5)
- f8a1f12 + a6e537d + 0af980c (F-7, unchanged)

Pinned /tmp/stanli-b7a3fd5 verified untouched (clean, detached @ 833d8de).
Main worktree external/stanli untouched. WORKLOG and other logs untouched.
Scratch: bench/fortk_f12/ only. The cherry-picked messages retain their
"pinned worktree / never merge" body text — that is now historical
provenance superseded by this F-12 charter; noted here so a future reader
of `git log` is not confused.

F-12 complete; branch ready for F-10 (sampler-loop package) per charter.
