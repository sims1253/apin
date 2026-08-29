# W-114: assembly/combined-posture-v2 — the W-96 multi-chain dispatch defect fixed (2026-08-29)

Agent W-114. Pre-registration: the W-110 CLOSE-OUT entry ("W-96 ASSEMBLY
DEFECT") in WORKLOG.md. Inputs studied before any code:
scratch/w61/PROMOTION_ASSEMBLY_MAP.md (Package A lineage semantics),
assembly/combined-posture @ 472609b (worktree scratch/w61/walnutpie_w96,
FROZEN, untouched), exp/ridge-guard @ 7dd0f71 (worktree
external_w86/walnutpie_w86, READ-ONLY, untouched).

## The defect (recap, from W-110)

v1's examples/stan_cli.cpp DEFINES run_walnuts_multi (with the merged #22
ridge guard inside) but main() never calls it — only the single-chain
run_chain path is dispatched, so `--chains 4` parses and dies opening the
literal `chain_{c}.txt` at the single-chain init site; the ridge guard is
unreachable code.

## Approach chosen: Option A (merge 7dd0f71 INTO the assembly) + one surgical dispatch-restoration commit

Why: `git merge-base 472609b 7dd0f71` = 4b1cdb8, and only TWO commits are
unique to exp/ridge-guard past that base — ba48c57 (W-100 per-chain
find_reasonable_step probe, +29/-1) and 7dd0f71 (W-102 graduated ridge
budget, +12) — both touching ONLY examples/stan_cli.cpp, both inside
run_walnuts_multi, both in regions DISJOINT from the W-96 assembly's edits
there (the W-77 init-screen pass-through). So the merge preserves the whole
W-96 assembly merge topology (PROMOTION_ASSEMBLY_MAP's intent) and lands
the adopted guard variant. Option B (replaying ~16 assembly-unique commits,
most of them merges, onto 7dd0f71) would dissolve that topology and re-ask
every conflict the assembly already answered — strictly worse.

One caveat made explicit: the merge ALONE cannot fix the defect. The
dispatch block was dropped by the ASSEMBLY's own conflict resolution
(relative to 4b1cdb8 the assembly deleted it; 7dd0f71 does not touch it),
so git keeps the deletion. The fix therefore has exactly two commits.

## Branch / commits (pushed to the fork as an ARTIFACT ONLY — no PR anywhere)

Repo git@github.com:sims1253/walnutpie.git, branch
`assembly/combined-posture-v2`:

- a4ea22c (merge, parents 472609b + 7dd0f71) "W-114 assembly v2: merge
  exp/ridge-guard tip 7dd0f71 (W-100 MC step heuristic + W-102 graduated
  ridge budget)". AUTO-MERGE WAS CLEAN — zero conflicts. Verified hunk by
  hunk: the merged run_walnuts_multi guard region is byte-identical to the
  external_w86 side, i.e. exactly ONE ridge guard copy remains, the
  graduated-budget (W-102-adopted) variant; the assembly's unreachable
  fixed-128 copy is superseded in place.
- 5a797d0 "W-114: restore the multi-chain dispatch in main()" (+69 lines):
  the dispatch block ported verbatim from 7dd0f71 stan_cli.cpp:1331-1389
  (multi-chain-only flag validations, {c} pattern checks, the run_multi
  lambda + optimizer ladder, `return 0`) with ONE adaptation: the assembly's
  run_walnuts_multi signature carries `bool init_screen` (W-77) ahead of
  init_tries, so the call passes `init_screen_enabled()`. One cosmetic
  reformat of the output-{c} check's line wrapping (semantically identical).
  Inserted between the SamplingConfig build and the W-82 micro-guard setup.

Both commits: `Signed-off-by: Maximilian Scholz <dev.scholz@mailbox.org>`
plus an explicit AI-generated note. Worktree:
scratch/w114/walnutpie_v2 (fresh; w96/w86 worktrees untouched).

## Package A piece verification (symbol level, in v2)

- init guard family #7/#17/#18: initialize_finite/--init-tries (W-42/W-78),
  WALNUTPIE_INIT_SCREEN x4 sites — single-chain run_chain AND inside
  run_walnuts_multi (lines 876-880).
- NaN guard #10: include/walnutpie/step_optimizers.hpp + walnuts.hpp
  (ef524a5) — headers byte-identical to v1 (tree diff below).
- ridge guard WITH dispatch: WALNUTPIE_RIDGE_GUARD at stan_cli.cpp:1039,
  called via run_walnuts_multi<Opt> at :1713 — REACHABLE (proved by fire,
  canary c). Graduated budget + WALNUTPIE_RIDGE_MINMICRO override +
  WALNUTPIE_MC_STEP_HEURISTIC inherited from the merge.
- mm2-guard #20: MicroGuardSpec wiring present at ALL EIGHT run_walnuts
  call sites (the 8-callsite gotcha; grep count = 8). Multi-chain path has
  no mm2 guard by W-96 design (it is a CLI single-chain feature).

## Canary gates

(a) BUILD green. scratch/w114/build_v2, cmake -S walnutpie_v2 -B build_v2
-DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/sbin/c++ (replicates
build_w96's cache; both prior builds used /usr/sbin/c++, which is healthy —
the W-46 gxx_fixed wrapper is only needed for /usr/bin/g++), /usr/bin/make
stan_cli -j2, nice 19, env -u LD_LIBRARY_PATH, single build stream.
Pre-build load 2.72 (< 6). rc=0, warnings only (Eigen template notes).

(b) SINGLE-CHAIN DEFAULT-PATH BIT-IDENTITY vs v1: PASS, both models,
W-29 short protocol (--seed 20260819 --warmup 100 --samples 50
--metric-window 50, no --chains). hier_2pl: bs_models/model_hier_2pl.so
(w109 alllayers .so missing on disk — fallback per plan, disclosed) +
data/hier_2pl.json + inits_w25/hier_2pl/rep0/chain_0.txt:
md5 f5db6c5284e65a63ed99a210f539d5ee (v1 == v2). pilots:
w109/model_pilots_alllayers/pilots_model.so + data/pilots.json +
inits_w36/pilots/rep0/chain_0.txt: md5 75e719297ddea4fb235a21ec243a6370
(v1 == v2). Scripts: scratch/w114/run_canary_b.sh; outputs
scratch/w114/canary_b/.

(c) MULTI-CHAIN DISPATCH + GUARD REACHABLE: PASS on the PRIMARY shape
(w200 — no fallback needed). v2 binary, pilots, `--chains 4 --chain-exec
serial --fixed-warmup --warmup 200 --samples 50 --metric-window 50 --seed
20260820`, init/output {c} patterns, env WALNUTPIE_RIDGE_GUARD=5:
rc=0, 4 csvs written, log line 1 = `chain exec: serial`, and the guard
FIRED: `ridge guard: cross-chain position F=21.3624 at coord 13 > 5 ->
raising min micro steps to 68 for sampling`. The budget 68 (not 128) is
the W-102 graduation doing its job: F/threshold = 4.27, 16 x 4.27 = 68.3
-> 68 — proof the merged w86-side graduated variant is the live one.
Script scratch/w114/run_canary_c.sh; outputs scratch/w114/canary_c/w200/.

(d) DEVIATION SANITY: PASS. Tree-wide v1 -> v2 = examples/stan_cli.cpp
ONLY, +110/-1 (nothing else in the repo changed; all guard headers are
byte-identical to v1). The file diff is 5 hunks: 4 inside
run_walnuts_multi (multi-chain-only code, dead for single-chain runs) + 1
hunk = the dispatch insertion, whose throws all require non-default flags.
The single-chain region (from the W-82 micro-guard comment to EOF — the
whole run_chain/fallback/summarize path) is BYTE-IDENTICAL v1 vs v2
(md5 1d99eeea0c3b78828a2f42f5ead319c9).

## Deviations owned

- hier_2pl canary (b) used bs_models/model_hier_2pl.so (the
  model_hier_2pl_alllayers .so named in the plan is absent on disk;
  the plan's own fallback clause).
- The dispatch port's one-line reformat noted above; the W-114 comment
  block above the dispatch (8 lines) is new prose, not code.
- No PR filed anywhere (standing rule); the push is fork-artifact only,
  per the W-96 precedent. GitHub's "create a pull request" remote message
  is boilerplate and was not acted on.

Machine discipline: one build stream, -j2, nice 19, load checked before
the build (2.72) and before the canaries (1.66), env -u LD_LIBRARY_PATH
everywhere, /usr/bin/make for the build. Canaries are short serial runs.

Artifacts: scratch/w114/ (walnutpie_v2 worktree, build_v2/, canary_b/,
canary_c/, run_canary_b.sh, run_canary_c.sh); this file.
