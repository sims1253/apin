# F-15 log — consolidation #2: merge f112-walnuts + f132-eigh into trunk (fortk/t2-coverage)

Started: 2026-08-26. Binding charter: WORKLOG "F-15 pre-registered" +
verdict sections F-10/F-11.2/F-13.2 (what each branch carries). Executed in
worktree external/stanli-f7, branch fortk/t2-coverage @ 1bfcbb5 (9b2bf80 +
F-10: e750504 patch file/fetch hook, 1bfcbb5 endpoint cache + mallopt +
GRAD_COUNTER).

## Merge plan (pre-registered order)

1. fortk/f112-walnuts (316afe2 vendored walnutpie knobs default-off;
   7d7c9da stanli WalnutsConfig wiring + --w-* tool flags; 58ec219
   test_walnuts_adapt).
2. fortk/f132-eigh (53db89a mir reader tuple grammar; 844ad46
   OP_EIGENDECOMPOSE_SYM lowering + kernel + out2_adj_vec; 08db4b6
   test_eigen fused-kernel parity + FORTK_DUMP verify plumbing + dump_ops
   out2 printing).
   Expected conflict zone: tools/fortk/regions.cpp (three-way history —
   F-10's mallopt/GRAD_COUNTER + f112's --w-* flags + f132's dump plumbing
   all in the CLI/driver region). Resolution rule: keep ALL functionality;
   any dropped feature is a gate failure.

## Pre-merge preservation (BEFORE any rebuild)

- bench/fortk_f15/fortk_t1r.premerge = copy of build-f7/fortk_t1r @ trunk
  1bfcbb5 (the F-10 binary, suite 63/63) — gate (c)/(d) control.

## Log

- (boot) read WORKLOG F-10/F-11.2/F-13.2 verdicts + F-15 charter;
  logs/fortk-f10.md, -f112.md, -f132.md, -f12.md (merge procedure +
  verify/sample invocations). F-14 agent confirmed ACTIVE on cores 2-5
  (cmdstan cc1plus builds + run_a.py) -> this task's builds pinned to
  other cores, -j2, serialized.
- (preserve) premerge binary copied (24470744 bytes, md5
  d4cd8fba648138e6f1ec105f5a6d202a); verified newer than every source
  (newest source = F-10's regions.cpp edit; binary relinked after it,
  carried F-10's 63/63 suite).

## Conflicts and resolutions

NONE — both merges auto-merged clean (merge 1 = ae505df, merge 2 =
f47f001), despite the charter's conservative three-way-regions.cpp prior.
Actual divergence anatomy (mirrors F-12's finding):

- F-10's regions.cpp zones: main() entry (mallopt + MALLOPT line, before
  the argc check) and the NUTS sample path (GRAD_COUNTER around
  run_nuts). Base ~2856-2870 and ~3734-3768.
- f112's zones: usage string + arg-parse loop (~2860-2945) and the
  WALNUTS driver (cfgw knobs + SAMPLE_W_ADAPT + f112() CSV tag,
  ~3659-3740). Adjacent to F-10's entry hunk (usage string sits a few
  lines below the inserted mallopt block) but the changed line sets are
  disjoint -> git 3-way resolved without conflict.
- f132's zones: the VERIFY 64-point loop only (FORTK_DUMP open/write/
  close, ~3409-3440) — untouched by both F-10 and f112.
- graph.hpp: F-10's Executor counters (~198-263) vs f132's KernelCtx
  out2_adj_vec (~111-118) — different structs, clean.

Because "no textual conflict" does not prove coexistence (F-12
doctrine), marker checks were run after EACH merge and again after both:

- After merge 1 (f112): MALLOPT + GRAD_COUNTER + all eight --w-* flags +
  WalnutsConfig wiring + SAMPLE_W_ADAPT + f112() CSV tag all present.
- After merge 2 (f132): FORTK_DUMP dumps (regions.cpp:3409+), KernelCtx
  out2_adj_vec (graph.hpp:118) alongside Executor n_endpoint_cache_hits
  (graph.hpp:212/263), dump_ops out2 printing, mir tuple grammar (6
  refs), lower.cpp eigendecompose_sym (3 refs), optable + kernel
  OP_EIGENDECOMPOSE_SYM, test_eigen + test_walnuts_adapt both registered
  in CMakeLists (579, 601). All F-10/f112 markers still present.
- git diff HEAD --stat after merge 2 = exactly f132's 10-file/372-line
  diffstat (nothing from f112 disturbed).

Nothing dropped; no resolution trade-offs were needed (the charter's
"keep ALL functionality" rule was satisfiable by the clean auto-merge;
the gates below are the semantic proof).

## Build (heavy moment serialized)

- F-14 agent active on cores 2-5 (cmdstan cc1plus + run_a.py; load
  spiked to 16-22 from their side during my window). This build pinned
  taskset -c 8,9, -j2, load watched (free ~16-22G available throughout;
  no earlyoom event). `cmake --build build-f7 -j2` exit 0, 100%, zero
  errors; fortk_t1r relinked 21:57 (24494656 bytes), dump_ops relinked,
  test_walnuts_adapt + test_pathfinder + all tests built.

## GATES (all PASS, none loosened)

### (a) Suite — PASS: ctest 64/64, 0 failures (2.11 s)

64 = 63 baseline + test_walnuts_adapt (new); test_eigen is the
pre-existing suite member that f132 EXTENDED with the fused-kernel
bitwise oracles (Test #10 present and passing). The charter's "63 +
test_walnuts_adapt + test_eigen" counts test_eigen as new, but it was
already in the 63 at 9b2bf80; net growth is +1 to 64 — the >= 64 bar
holds. test_walnuts_adapt + test_walnuts + test_eigen re-run together:
3/3.

### (b) Verify spot-checks — PASS (all values match the recorded history)

Run from worktree cwd (stock pinned stanc), outdirs
bench/fortk_f15/<model>/run.log:
- eight_schools_noncentered (esnc): grad_relL2 0.000e+00 (bitwise) +
  VERIFY_DIRECT grad 0.000e+00 bitwise PASS — matches F-12 exactly.
- hier_2pl: 1.042e-15 / 1.221e-14 — 1e-15-class, matches F-12/F-7
  exactly.
- arma11: 7.778e-16 / 3.958e-15 + DIRECT PASS — matches.
- wells_dist100_model: 1.631e-15 / 4.757e-15 + DIRECT PASS — matches.
- kronecker_gp via the F-13 FUSED stanc, staged per charter at
  /tmp/f15-stage (deps/stanc3/stanc -> external/stanc3/_build/default/
  src/stanc/stanc.exe; model+data copies; run from that cwd):
  VERIFY grad_relL2_max = 0.000e+00 AND logp_rel_max = 0.000e+00 —
  FULLY BITWISE (ex0 interpreter vs ex1 regions on the fused graph).
  Fusion confirmed firing through the merged stack: dump_ops shows
  exactly 2 EIGENDECOMPOSE_SYM (out len900 vectors, out2 len30 values,
  idata 30) and 0 stock eigh ops; FORTK line ops=221->94 regions=33.

### (c) Default-path byte-identity vs premerge trunk binary — PASS

--sample 200 200, default init, seed 20260826, chain 1 (gates dirs
bench/fortk_f15/gC/{pre,post}/<model>/), premerge =
fortk_t1r.premerge:
- esnc (eight_schools_noncentered): sample_nuts_seed20260826_chain1.csv
  cmp BYTE-IDENTICAL (202 lines).
- blr: BYTE-IDENTICAL (202 lines).
- F-10 mechanism cross-check on the merged binary: GRAD_COUNTER
  esnc exec1=4079 hits1=61, blr exec1=11418 hits1=62 — F-10's recorded
  numbers EXACTLY (drop == hits arithmetic intact through both merges).

### (d) Walnuts D0 (all knobs off) bitwise vs premerge — PASS

esnc --sample 200 200 --seed 20260826 --chain-id 1 --sampler walnuts,
default flags (gD/): data lines (f112's canonical comparator: the
all-off CSV's line-1 comment carries the designed f112(chop=0,...)
provenance tag, which bench/fortk_f112/bitwise_check.sh strips by
construction — "compare data lines only"):
- init u: grep -v '^#' cmp IDENTICAL (200 draws + column header).
- init pf (+ --pf-seed 20260826): IDENTICAL; pf_draws_seed20260826.csv
  BYTE-IDENTICAL over the WHOLE file including header.
- SAMPLE_W_ADAPT line confirms all-off: chop=0 clip_k=0 var_floor=0
  shrink_kappa=0 smooth=0 batch=1 decay=0.5 accept=0.8.

### (e) kidscore --w-batch 10 (pf-init walnuts, 4 chains, 1 rep) — PASS

F-11.2 rep-0 protocol verbatim (1000+1000, seeds 20260826..29,
chain-id 1, --init pf --pf-seed 20260826, --w-batch 10;
bench/fortk_f15/gE_kidscore/): rank-normalized R-hat (harness/ess.R,
posterior package) across all params, all 4 chains:
  rhat_max = 1.0084 < 1.01  (F-11.2 D_b10 rep medians: 1.008)
  ESS/draw geomean = 533/4000 = 0.133 >= 0.1 (companion metric holds)
PF signature sane (paths_ok=4, khat=0.209). F-11.2's fix survives the
merge.

## Final state

Branch fortk/t2-coverage @ f47f001 (NOT pushed). Trunk-only commits
since 9b2bf80 (first-parent): e750504, 1bfcbb5 (F-10) + merge commits
ae505df (f112) and f47f001 (f132). Full ancestry brings in
316afe2/7d7c9da/58ec219 and 53db89a/844ad46/08db4b6 verbatim.

DROPPED: nothing. Every feature marker from F-10 (mallopt, endpoint
cache + counters, scratch-hoist patch file/fetch hook), F-11.2 (8 --w-*
flags, WalnutsConfig wiring, SAMPLE_W_ADAPT, f112 CSV tag,
test_walnuts_adapt) and F-13.2 (tuple reader, eigh lowering/kernel,
out2_adj_vec, FORTK_DUMP, dump_ops out2, test_eigen oracles) is
present and exercised by the gates above.

Untouched per rules: external/stanli main worktree, external/stanli-f112,
external/stanli-f132, external/stanli-f14, /tmp/stanli-b7a3fd5,
WORKLOG.md, all other logs (verified clean git status in each sibling
worktree at session end). Scratch: bench/fortk_f15/ + /tmp/f15-stage/
only. Builds stayed off F-14's cores 2-5 (-j2, cores 8-9).

F-15 complete; trunk ready for F-16 (grand campaign) once F-14 lands,
per charter.


