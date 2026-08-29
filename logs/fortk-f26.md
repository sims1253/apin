# F-26 incremental log — INTEGRATION CAPSTONE (the session's closing number)

Binding charter: WORKLOG "F-26 pre-registered" (2026-08-28). Read order
honored: WORKLOG F-25 VERDICT + F-26 charter, F-24 VERDICT (loop stack +
branch topology), F-18/F-19 VERDICTs (ESS conventions + wall-drift
discipline: interleaved same-day only), F-14 VERDICT (--fits batch
protocol); logs/fortk-f24.md + logs/fortk-f25.md in full.

Setup (boot, 2026-08-29):
- Merge the two arcs: base fortk/f24-loopfusion @ 4dbbbdd (carries the
  full loop arc f22-lean/f23-leanwarm/f24-loopfusion on the PR stack,
  incl. deps/stan patches 0001-0003 as carried files + the fetch.sh
  apply-hook) + merge fortk/f25-kernelfloor @ db60cf0 (kernel arc off
  fortk-pr/jit-tier @ 68c0495; region emitter v6). Merge base of the two
  = 68c0495. Expected conflict surface: tools/fortk/regions.cpp only;
  resolution keeps BOTH (lean loop AND multi-pass v6 emission); region
  cache version = kernel arc's v6 or higher (bumped if muddled).
- Fresh worktree external/stanli-f26, branch fortk/f26-capstone.
- GATES (never loosened): build -j2; ctest 69/69; verify spots kidscore
  (F-25's 1.4e-15 class) / blr / esnc (bitwise) / hier_2pl / wells;
  --lean smoke on esnc (draws may be the F-24 statistical class —
  expected, stated).
- CAMPAIGN (F-8/F-18 conventions): phase-1 6 models; arms A (CmdStan
  nuts, cmdstanpy ~/.cmdstan/cmdstan-2.39.0), C (PR-stack fused nuts,
  STOCK loop — external/stanli-pr-loop/build-pr/fortk_t1r default arm),
  L (integration branch, --lean from iteration 0); 4 chains x 1000+1000,
  seeds 20260826+1000*rep+c, 3 reps medians, arms interleaved within rep
  (model-major), load recorded, ESS via harness/ess.R, ESS_bulk/s geomean
  + ESS/draw sanity + divergences + td-hits + max-chain wall.
- ALSO: full-run Ir ratios A-arm-excluded (C vs L, ONE binary = the
  integration branch via --lean toggle — C' = default arm, L = --lean;
  labeled clearly); batch spot --fits 200 blr+esnc on the integration
  branch (F-14 arm-d protocol) vs F-14's 508,260 / 1,156,832.
- REPORT: per-model + geomean ESS/s vs A for C and L; L-vs-C Ir table;
  ESS/draw sanity for L (equivalence class since F-24/F-25 — gate is
  equivalence not identity); divergences; batch numbers; the honest
  3-paragraph read vs F-8's 3.15x C-arm geomean where the session started.
- Rules: <=4 concurrent sampling procs, CPU only, -j2 builds, no
  upstream, no push, explicit staging, do not touch /tmp/review/stanli
  (user's), other worktrees' sources, WORKLOG.md, other logs; raw
  bench/fortk_f26/.

(work in progress — appended incrementally below)

## Setup (i) — merge + deps

- Worktree external/stanli-f26 created (branch fortk/f26-capstone @
  4dbbbdd); merge of fortk/f25-kernelfloor @ db60cf0 committed as
  70fd71a. CONFLICT SURFACE: NONE textual — regions.cpp auto-merged
  (the arcs touched disjoint zones). Semantic audit instead of trust:
  merged-vs-db60cf0 diff = ONLY loop-arc code (LeanNuts driver, --lean
  flags, includes; 9 hunks, none in the Emitter); merged-vs-4dbbbdd
  diff = ONLY kernel-arc code (F-25 la zero-init + v6 multi-pass). All
  other differing files (patches/deps-stan/*, direct_nuts.hpp,
  graph.hpp, model_adapter.hpp, nuts.cpp) are loop-side-only vs the
  68c0495 base. Emitter version = "fortk-t2r-v6" (kernel arc's), emitter
  code byte-equal to db60cf0's => v6 cache key TRUTHFUL, no bump needed.
- deps: symlinked math/stan/stanc3 to the shared external/stanli/deps
  (the established pattern), ran the loop side's fetch.sh hook: patches
  0001-0003 applied, verified `git -C external/stanli/deps/stan diff`
  = +222/-35 over the 3 recorded files, stan @ c96d0411. (Hook re-run
  fails on the reverse-check ordering quirk — atomic apply, harmless.)
- INCIDENT (caught + recovered): the fetch.sh hook DISCARDED the shared
  deps/stanc3/stanc binary ("without 5b824ee provenance" — it predated
  the provenance-file convention; all worktrees share the one file).
  RECOVERY: rebuilt the pinned compiler from source — local clone of
  external/stanc3 (checkout state untouched), checkout 5b824ee ("Merge
  PR #1679 expose-typed-mir-entry"), dune build on the existing f13
  opam switch (deps already installed; build ~1 min), installed as
  deps/stanc3/stanc + stanc.src provenance (now hook-stable).
  EQUIVALENCE PROOF: --O1 --debug-optimized-mir output on 5 recorded
  corpus artifacts (blr/esnc/hier_2pl/diamonds/radon_pp tmir.sexp,
  Aug-26 vintage) = BYTE-IDENTICAL under identical invocation; earlier
  diffs were the prog_path line only (the F-19-documented cosmetic).

## Gates — ALL PASS

- BUILD: cmake Release + build -j2, rc=0, zero warnings.
- CTEST: **69/69 PASS** (raw ctest_f26.log).
- VERIFY SPOTS (64 pts, seed 20260826, vs unmodified executor) — every
  value DIGIT-IDENTICAL to the F-25/F-19 records: kidscore 1.390e-15 /
  4.084e-16 (the F-25 1.4e-15 class); blr 3.249e-16 / 2.423e-16; esnc
  0.0 / 2.485e-16 (bitwise); hier_2pl 1.042e-15 / 1.221e-14; wells
  1.631e-15 / 4.757e-15. The v6 emitter carried through the merge
  exactly (raw verify/).
- DEFAULT-PATH BYTE-IDENTITY (200+200, .stan path = recovered stanc
  exercised): esnc md5 5253067ddd95ee9b8dbddf09414aa7ed grads exec1=
  3741; blr md5 b6e8df4bde54722d36ec328cb9fb58b8 grads exec1=11081 —
  BOTH exactly the recorded F-22..F-25 values (raw byteid/).
- --LEAN SMOKE esnc 200+200 seed 20260826 c1: runs; accept_mean=
  0.8935, grads exec1=3785, LEAN divergent=0 — EXACTLY F-24's recorded
  smoke cell (draws md5 e4d9e8ad... != stock 5253067d... = the F-24
  statistical class, expected and stated; esnc's v6 emitter arithmetic
  is unchanged so the lean realization reproduces F-24's bit-for-bit).

## Full-run Ir — ONE binary (integration branch), C' stock-loop vs L --lean

F-24 shape exactly (200+200 + 200+1 phase split, seed 20260826 c1,
toggle-collect on *cg_sample_run* / *cg_lean_run*, f19 tmir inputs, raw
ir/ + ir_campaign.out):

| model | C' Ir | L Ir | full-run | warmup-ph | sampling-ph | grads C'/L |
|---|---|---|---|---|---|---|
| esnc | 13,059,107 | 8,417,928 | 1.552 | 1.554 | 1.547 | 3741/3785 |
| esc | 35,026,414 | 23,567,158 | 1.486 | 1.366 | 1.771 | 10749/11193 |
| blr | 43,370,288 | 32,915,865 | 1.318 | 1.238 | 1.400 | 11081/10856 |
| logmesq | 84,003,406 | 52,242,470 | 1.608 | 1.534 | 1.697 | 19955/18137 |
| kidscore | 160,296,464 | 134,822,322 | 1.189 | 1.187 | 1.194 | 21427/21427 |
| GEOMEAN | | | **1.422** | | | |

- The two arcs COMPOSED on the Ir instrument: geomean 1.422x vs F-24's
  1.360x (v4 emitter). Per model vs F-24: logmesq 1.373->1.608 and
  kidscore 1.098->1.189 — exactly the two models whose KERNELS the F-25
  arc sped up (fused Ir/eval -27.8% / -53.8%), raising the loop-side
  share the lean loop can win; esnc/esc/blr ~unchanged (their v6
  emitters are within 0.7% of v4).
- Kidscore C'-vs-L grads EXACT (21427/21427, the F-24 bitwise property);
  logmesq lean did FEWER grads (18137 vs 19955) — realization branch,
  reported.
- The C' arm here (v6 emitter + stock loop + patched deps) is NOT F-24's
  C (v4): its kidscore full-run fell 346.4M -> 160.3M Ir = the kernel
  arc's end-to-end effect visible inside the comparison's denominator.

## CAMPAIGN — closing table (3 reps medians, F-8/F-18 conventions, interleaved same-day; raw campaign dirs + results_raw.json + campaign.out)

| model | A ESS/s | C ESS/s | L ESS/s | C/A | L/A | L/C |
|---|---|---|---|---|---|---|
| esnc | 155,702 | 830,346 | 1,075,043 | 5.33 | 6.90 | 1.29 |
| esc | 4,151 | 52,678 | 57,970 | 12.69 | 13.97 | 1.10 |
| blr | 23,100 | 98,015 | 136,712 | 4.24 | 5.92 | 1.39 |
| pilots | 34 | 213 | 169 | 6.20 | 4.91 | 0.79 |
| kidscore | 3,597 | 16,912 | 33,504 | 4.70 | 9.31 | 1.98 |
| logmesq | 8,830 | 45,625 | 61,743 | 5.17 | 6.99 | 1.35 |
| GEOMEAN | 5,036 | 29,833 | 37,926 | **5.92** | **7.53** | 1.27 |

- VALIDATION (strongest check): arm A reuses F-8's exes+seeds -> ESS rel
  diff 0.0000 vs F-18's A on ALL 6 models; arm C (f24 binary, v4
  emitter, byte-identity lineage) -> ESS rel diff 0.0000 vs F-18's C on
  ALL 6. Both arms' draws are the campaign lineage's exact draws; only
  walls moved. Same-day interleaving held (loads at rep starts 0.2-4.1).
- KIDSCORE IS THE COMPOSITION CELL: campaign wall ratio L/C = 0.0845/
  0.0391 = 2.16x ~= kernel arc 1.796x (v4->v6, F-25's full-run Ir) x
  loop arc 1.19x (the one-binary Ir here) = 2.14x. The two arcs
  composed multiplicatively exactly where both touched the same model.
- pilots L/C 0.79 is REALIZATION CHAOS, not a loop regression: per-rep
  rhat A/C/L = rep0 1.044/1.069/1.458, rep1 1.347/1.555/1.084, rep2
  1.315/1.032/1.552 — every arm takes the catastrophic rep in turn (the
  documented F-22/F-24 shared pathology; min ESS 7/4000 draws). L's
  pilots WALL is below C's in 2/3 reps (mean ~1.11x faster). Reported
  as measured.
- ESS/draw sanity (L vs C, equivalence class since F-24/F-25): esnc
  1.104, esc 1.088, blr 0.971, logmesq 0.839, kidscore 1.028, pilots
  0.550 (chaos cell). Divergences A/C/L: esnc 0/1/5, esc 471/208/272,
  blr 0/0/0, pilots 1996/2072/2545 (all arms pathological), kidscore
  0/0/0, logmesq 0/0/0. td-hits: 0 everywhere except pilots (A 653-ish
  scale; C 1340 L 1514 summed over 3 reps — same pathology cell).
- A-arm day note: A's walls ran FAST today (esnc A 155.7k ESS/s vs
  F-18's A-day 89.2k; draws identical) — today's C/A 5.92 vs F-18's
  6.24 and F-19's 5.98 is the documented day-drift pattern, not code.

## BATCH SPOT — --fits 200 on the integration branch (F-14 arm-d protocol; raw fits/)

| model | F-26 median fits/h incl-compile | F-14 d arm | ratio | per-fit wall |
|---|---|---|---|---|
| blr | 956,014 | 508,260 | **1.88x** | 3.63 ms (was 7.08) |
| esnc | 2,615,123 | 1,156,832 | **2.26x** | 1.23 ms (was 3.11) |

- 3 reps medians, warm cache, taskset 2-5, FORTK_CC=clang, quiet (load
  0.14-0.26). Rep0 of each carried the cold clang (0.16-0.32 s) and is
  the low outlier; medians are warm-cache cells, matching F-14's
  convention. Sampling-only: blr 988k, esnc 2.93M fits/h.
- Composition note (honest): --fits routes through stanli::
  run_nuts_chains = the STOCK library loop — it does NOT compose with
  --lean (the lean driver lives in the tool's --sample path). So the
  batch numbers carry the F-17-era loop package + v6 emitter + today's
  stack, NOT the lean loop. Extending --fits to the lean driver is a
  code change, out of a measurement session's scope (noted as future
  item). vs F-14's d (pre-loop-package base 9b2bf80): the 1.88-2.26x =
  loop package + emitter + day, same instrument.

## VERDICT (for WORKLOG, via parent)

fortk/f26-capstone @ 70fd71a (= merge of fortk/f24-loopfusion @ 4dbbbdd
+ fortk/f25-kernelfloor @ db60cf0), NOT pushed. Merge: NO textual
conflict (regions.cpp auto-merged; arcs touched disjoint zones — hunk
audit: merged-vs-each-parent contains only the other arc's code);
emitter version v6 retained (emitter code byte-equal db60cf0's; cache
key truthful, no bump); lean loop AND multi-pass emission both carried
and gated. deps/stan patches 0001-0003 live (+222/-35) via the loop
side's fetch.sh hook. INCIDENT: the hook discarded the shared
provenance-less deps/stanc3/stanc; recovered by rebuilding the pinned
5b824ee from source (f13 switch) — MIR byte-identical to 5 recorded
artifacts, and the campaign's esnc/blr byte-identity md5s reproduce
the recorded values exactly.

GATES: build -j2 zero warnings; ctest 69/69; verify spots ALL
digit-identical to F-25/F-19 records (kidscore 1.390e-15 the 1.4e-15
class; blr 3.249e-16; esnc bitwise 0.0; hier_2pl 1.042e-15; wells
1.631e-15); default-path byte-identity esnc 5253067ddd95/blr
b6e8df4bde54 + grads 3741/11081 = the recorded values; --lean smoke
reproduces F-24's exact cell (accept 0.8935, grads 3785, div 0 — the
F-24 statistical class, expected and stated).

NUMBERS: closing table above — L/A geomean **7.53x** (C/A 5.92x);
one-binary full-run Ir L/C' geomean **1.422x** (F-24 1.360x with v4);
batch --fits 200: blr 956,014 / esnc 2,615,123 fits/h = 1.88x/2.26x
F-14's d arm; kidscore L/C wall 2.16x ~= 1.796 (kernel) x 1.19 (loop).

THE HONEST READ (3 paragraphs):
(1) WHAT COMPOSED: everything that could. The merge carried both arcs
with zero semantic loss — every recorded oracle (verify spots,
byte-identity md5s, grads counters, F-24's lean smoke cell) reproduced
digit-for-digit. The two speed arcs are RESOURCE-DISJOINT by
construction (emitted-kernel Ir vs host-loop Ir) and the capstone
shows the composition is multiplicative where they overlap: kidscore's
campaign wall ratio 2.16x equals kernel 1.796x x loop 1.19x = 2.14x
within noise, and its end-to-end ESS/s vs CmdStan went 4.70x (C) ->
9.31x (L). Even the one-binary loop ratio ROSE 1.360 -> 1.422 because
the kernel arc shrank the kernel share of exactly the two models
(logmesq, kidscore) that had been flooring it.
(2) WHAT DIDN'T: three things, all structural not accidental. (a) The
batch lane doesn't ride the lean loop — --fits drives stanli's stock
run_nuts_chains, so 956k-2.6M fits/h carries the F-17 loop package but
not F-24's lean fusion (extending it is a code change, recorded as the
next item). (b) blr is at its attributed kernel floor (priors/logs/
memcpy, nothing vectorizable — F-25's honest verdict) so its L gain is
loop-only: 1.39 ESS/s, 1.318 Ir. (c) pilots' ESS realization chaos
(min ESS 7/4000, every arm takes the catastrophic rep in turn) makes
its 0.79 L/C a coin flip, not a measurement — its WALL composed fine
(~1.11x faster). And the registered 8-10x expectation: the 6-model
geomean landed 7.53x; excluding only the pilots chaos cell the 5-model
geomean is 8.20x — inside the band; the honest closing number is the
6-model 7.53x, with A's atypically fast day (C/A 5.92 vs F-18's 6.24
on IDENTICAL draws) noted as environment.
(3) THE SESSION'S ARC: day one F-8 measured the fused stack at 3.15x
CmdStan ESS/s geomean; the closing L arm measures 7.53x = a 2.39x
geomean gain stacked from individually-gated layers (T2 kernels +
coverage, F-17 loop package, F-22..F-24 lean loop, F-25 kernel floor),
each of which validated multiplicatively at its own gate and again
here at the capstone; plus the batch lane at 956k-2.6M fits/h
(1.88-2.26x its own F-14 measurement after the loop package). Bit-
identity held through every consolidation (today's gates reproduce
every recorded md5), and the one instrumentation loss — --lean's
statistical class — is bounded, documented, and reproduced F-24's
exact realization on the unchanged-emitter model.

Rules held: <=4 concurrent sampling procs (4-chain cells; Ir + fits
serialized), CPU only, -j2 builds, no upstream, no push, explicit
staging (one merge commit, tool + benches only), /tmp/review/stanli
never accessed, other worktrees' sources untouched (stanc3 rebuilt in a
scratch clone), WORKLOG/other logs untouched, raw under
bench/fortk_f26/.
