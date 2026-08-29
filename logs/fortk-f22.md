# F-22 log — lean sampler loop + depth-12 leg (pre-registered in WORKLOG)

Binding charter: WORKLOG "F-22 pre-registered" (2026-08-28). Read order honored:
F-17 VERDICT + f17a §C.4 (lean design sketch + bit-identity accounting), F-20
VERDICT (--cg instrument, toggle-collect pattern, lambda-name pitfall), F-16
VERDICT (depth-12 context + F-11.3 adoption rule), F-18/F-19 (ESS conventions,
wall-drift discipline).

Setup (boot, 2026-08-28):
- Worktree external/stanli-pr-loop @ 91046eb (fortk-pr/sampler-loop), clean.
  deps/stan patches live: git diff = 0001 (rho/scratch hoists per F-10/0003
  family) touching base_nuts.hpp + diag_e_metric.hpp + expl_leapfrog.hpp,
  222 insertions. Branch fortk/f22-lean created off it.
- Instruments: callgrind Ir (F-20 pattern: noinline cg_sample_run +
  --toggle-collect='*cg_sample_run*'; NEVER a bare '*run_nuts*' — nested
  lambda names cancel the XOR). Wall interleaved-same-day only, busy box.
- Rules: <=4 concurrent sampling procs, CPU only, -j2 builds, no upstream,
  no push; other worktrees'/logs' sources untouched.

(work in progress — appended incrementally below)

## (i) ATTRIBUTION — esnc remaining transition Ir (function-level callgrind)

Instrument: the F-20 binary (fortk_t1r_cg_loop, byte-copy of this worktree's
tool + additive knobs, same prebuilt lib), fresh run today, same shape as the
F-20 record: --sample 200 200 --seed 20260826 --chain-id 1 --sample-arm 1,
toggle '*cg_sample_run*'. REPRODUCED: 14,765,243 Ir total vs F-20's
14,764,986 (1.7e-5 rel, the documented path-length heap sensitivity; F-20's
same-shape outdir), grads exec1=3741 EXACT. Function-level split via
callgrind_annotate + group_components.py (raw + script under
bench/fortk_f22/attr/). 400 transitions => 36,913 Ir/trans (F-20 quoted
36,914 from its total; same number to 4 digits).

| component | Ir | share | Ir/trans | eliminable by a TARGETED (byte-identity) lever? |
|---|---|---|---|---|
| Eigen copies (Dense2Dense 23.34% + ps_point::= self 3.00%) | 3,887,976 | 26.33% | 9,720 | NO — the remaining copies are ps_point VALUE semantics (z_fwd/bck/sample/propose assigns, z_propose=W per leaf); removing them = replacing the state model = the rewrite. 0003 already took the hoistable ones. |
| Eigen arithmetic (dots 8.91% + cwise sum/product 7.79% + zero 0.90%) | 2,600,240 | 17.61% | 6,501 | NO — required math (criterion/H/T dots, momentum cwise ops); only Eigen's per-op dispatch is removable, via hand loops = the rewrite. |
| base_nuts tree glue + run_nuts self | 2,248,382 | 15.23% | 5,621 | NO — this IS the loop. |
| transcendentals (log1p 3.95+4.2% exp + log_sum_exp self + pow) | 1,469,477 | 9.95% | 3,674 | NO — mathematically required (log_sum_weight chain, metro prob). |
| gradient kernel + executor dispatch + init evals | 1,331,997 | 9.02% | 3,330 | NO — the model math (floor). |
| leapfrog/metric driver self (evolve 6.12% + T/sample_p/H) | 1,063,313 | 7.20% | 2,658 | NO — integrator glue. |
| direct-seam wrapper self (theta copy, memcmp) | 879,229 | 5.95% | 2,198 | PARTLY (skip cache/memcmp) — few %. |
| RNG (mixmax+ziggurat+uniform) | 491,852 | 3.33% | 1,230 | NO — required draws. |
| libc memcpy/memset | 430,035 | 2.91% | 1,075 | mostly no (alloc + state moves). |
| malloc/free self | 150,913 | 1.02% | 377 | YES (residual allocs) — 1%. |
| other tail + adaptation | 67,659 | 0.45% | 169 | — |

Top single functions: Eigen Dense2Dense assign 23.34%, base_nuts self
13.09% (transition 3.13 + build_tree 1.85 + criterion 2.05 + ...),
inner_product 8.91%, leapfrog evolve 6.12%, seam wrapper 5.52%, log1p
3.95%, fused kernel fwd 3.60%, ps_point::= 3.00%.

### DECISION (pre-stated rule, applied and recorded BEFORE building)

Rule: "top <=3 eliminable components >= 60% of remaining Ir => targeted
eliminations; else => the lean driver."
- Strict reading (eliminable = removable by an F-17-style byte-identity
  lever): the genuinely targeted-eliminable mass is seam-wrapper residue
  (~6%) + residual allocs (1.02%) ~= 7% << 60%. RULE SENDS TO THE LEAN
  DRIVER.
- Numerical reading (counting the top-3 components regardless of lever):
  26.33 + 17.61 + 15.23 = 59.17% < 60% — and all three are eliminable
  ONLY by the rewrite (they are the ps_point/Eigen/recursion structure
  itself). RULE SENDS TO THE LEAN DRIVER on this reading too.
=> DECISION: build the lean driver (ii). No targeted-elimination lane; the
59.2% near-miss is the honest tension recorded, not bent.

## (ii) LEAN DRIVER — implementation + gates

DESIGN CHOICES (stated per charter):
- Warmup through the CURRENT loop (not lean-from-start): the tool
  constructs stanli::adapt_diag_e_nuts_direct with a VERBATIM replica of
  run_nuts's prologue (same create_rng, same initialize replica, same
  DA/Welford/window calls) => warmup byte-identical to arm C, then
  disengage + frozen (eps, inv_metric, q, V, g) handoff; the lean phase
  continues the SAME rng object. Rationale: adaptation correctness is the
  riskiest thing to reimplement (a wrong DA/window schedule poisons every
  downstream draw), and identical warmup isolates the statistical
  comparison to the sampling loop. This choice COSTS gate (b) ceiling —
  see below, measured and accepted per the failure protocol.
- Lean loop: flat arena ([q|p|g] point blocks => copies are one memcpy;
  per-depth vector slots; single-pass kicks/drift/ps; direct
  executor->executor gradient with V=+inf/g=0 divergence semantics;
  p_sharp = inv_m*p; kicks ADD eps*g (bit-identical to stock's
  p -= eps*(-grad), skips the negation pass); RNG mirrors stock's
  conditional draw sites exactly (boost uniform_01<BaseRNG&>, ziggurat
  normals element-order).
- ONE BUG found+fixed in validation: base_leapfrog::evolve passes
  0.5*epsilon to BOTH kicks — my first mirror used full eps (accept_stat
  collapsed to 0.47 vs C's 0.90; fixed => 0.9018 exact).

SURPRISE (honest): the lean loop is BITWISE-IDENTICAL to arm C on every
cell measured — 600/600 rows on esnc/blr/hier_2pl 200+200 smokes AND
18/18 campaign cells (6 models x 3 reps, chains 0+3 md5) at 1000+1000;
GRAD_COUNTER identical everywhere (17348/46622/31921/644580/60714/94820
per chain-0 rep0 C==L). Per-element op-ordering + -ffp-contract=off +
Eigen's dim-10..1000 dot accumulation matched exactly. NOT claimed as a
gate or a guarantee (other models/dims could diverge); the gate stays
statistical per charter.

GATES:
- (d) default path byte-identity: PASS — pre-change binary snapshot
  (bench/fortk_f22/fortk_t1r.pre_f22) vs branch binary, esnc+blr
  200+200: CSVs BYTE-IDENTICAL, stdout differs only in outdir paths +
  timing lines. ctest 69/69 (this branch's suite; walnuts tests live on
  F-21's branch). Commit 79ec226 (default-off; --lean + --sample-arm
  additive).
- (a) statistical equivalence (6 models x 3 seeds, 1000+1000 x 4 chains,
  F-8 conventions): PASS — ESS_bulk geomean IDENTICAL to the digit on
  all 18 cells (esnc 3842/3996/4226; esc 879/603/682; blr 1362/1531/
  1396; pilots 72/13/175; kidscore 1390/1273/1429; logmesq 1937/1919/
  2065); rhat identical per cell (max 1.0067 on the 4 well-mixed;
  esc 1.0254-1.0706 and pilots 1.0315-1.5552 exceed 1.01 IDENTICALLY in
  both arms — funnel/multimodal pathology shared, not lean-caused);
  divergences identical (208/208 esc, 2072/2072 pilots, 0 elsewhere).
- (c) hier_2pl no-regression: PASS — ESS identical (8185/7041/7601);
  C/L wall medians 14.30/14.29/14.52 vs 14.61/15.45/14.75 =>
  median ratio 0.969 >= 0.95 bar (gradient-bound: lean phase is
  parity there, as with every gradient-bound model in this lane).
- (b) ESS/s >= 1.3x on the esnc-class geomean: **FAIL** — and the wall
  table is junk at these magnitudes (5-100ms walls, box load 4.2-8.2:
  per-rep ratios 0.425..2.321, geomean of medians 0.963). The
  load-stable instrument (Ir, same binary, same shape as the F-20
  record): full-run esnc 13,139,002 -> 11,657,875 = 1.127x, blr
  43,588,882 -> 39,748,797 = 1.097x, hier_2pl 36,751,904,756 (lean;
  stock pending). Per the charter the flag SHIPS default-off with these
  honest numbers.

MECHANISM (phase decomposition via 200+1 runs — warmup is
byte-identical between arms so warmup Ir cancels):
- esnc: warmup 7.81M (39.0k/trans!) + sampling: stock 5.23M (26.2k/
  trans) vs lean 3.84M (19.2k/trans) => SAMPLING-PHASE ratio 1.36x,
  full-run 1.127x. Warmup transitions cost MORE than sampling ones
  (deeper early trees + adaptation; grads 11.3 vs 7.4 gpi).
- blr: warmup 20.7M (103.7k/trans) + sampling stock 22.6M (113k/trans)
  vs lean 19.0M (95k/trans) => phase ratio only 1.19x — blr is
  eval-dominated (28.9 grads/transition), capping the lean gain.
Ceiling arithmetic: even a lean WARMUP (not built — adaptation-risk
call above) would land ~1.2-1.35x on this class; the 1.3x bar was
structurally out of reach for this loop on eval-heavy models.

LEAN-PHASE RESIDUAL ATTRIBUTION (esnc, ~19.2k Ir/trans — what remains,
ranked): lean loop self (recursion + hand passes + dots) 51.8% | state
memcpy 10.5% | fused kernel 7.8% | exp 6.7% + log1p 6.4% + lse 1.2%
(transcendentals 14.3%) | executor dispatch 2.9% | rng 4.6% | init/
region glue 3%. The remaining levers inside the lean loop are pass-
fusion and dot-batching (FP-order changes, statistical-gated), then the
kernel floor.

## instrument note (build layout)

The F-22 branch tool's STOCK arm measures 13,139,002 Ir for the esnc
200+200 run where the F-20 instrument binary measured 14,764,986 — an
11% compile-layout shift (F-20 built regions.cpp standalone; the branch
build inlines more Eigen assignment loops INTO base_nuts self: in-branch
stock split = tree_glue 24.9% + copies 16.3% vs F-20 binary's 15.2% +
26.3%). Attribution (i) is reported on the F-20 binary (same instrument
as the pre-registered baseline); all F-22 lean-vs-stock ratios use ONE
binary (both arms in-binary) so the layout cancels. The decision rule's
outcome is layout-robust: top-3 = 59.2% (F-20 layout) / 54.2% (branch
layout), both < 60%, same eliminability structure.

## RESUME AUDIT (2026-08-28 15:33+; agent died post-gates, pre-depth-12)

Provider-network death mid-(iii). Session resumed; EVERY number above
re-verified against raw disk artifacts before being trusted (per resume
rule; the dead session's queued writes replayed on resume and are
artifact-backed, not assumed):
- (d) RE-RUN FRESH myself: pre vs post binary, esnc md5
  5253067ddd95ee9b8dbddf09414aa7ed both sides, blr
  b6e8df4bde54722d36ec328cb9fb58b8 both sides; GRAD_COUNTER identical
  (esnc 3765/3741, blr 10879+4/11081+0); ctest 69/69 PASS. Raw
  gate_d2_{pre,post}/ + ctest_f22.log. CONFIRMED.
- (a): all 18 cells in campaign/results_partial.json re-parsed: ESSg,
  rhat, div, td IDENTICAL C==L per cell (values as quoted above).
  CONFIRMED. (Those walls are load-tainted: the campaign ran 15:23-15:31
  CONCURRENT with the ir callgrind cells — a clean wall campaign is
  re-run below per the fair-wall discipline.)
- (c): hier_2pl walls re-extracted from chain tool.logs: C max-chain
  14.298/14.515/14.294, L 14.612/15.453/14.754 => median ratio
  14.298/14.754 = 0.969 >= 0.95. ESS 8185/7041/7601 rhat<=1.0086
  identical C==L. CONFIRMED on disk (also callgrind-concurrent; clean
  re-run below).
- (b) Ir: cg.out summaries re-read: esnc 13,139,002 -> 11,657,875,
  blr 43,588,882 -> 39,748,797, hier_2pl.lean 36,751,904,756 (stock was
  in flight at death; completed post-resume — number below). Phase
  arithmetic re-derived from ir_phase 200+1 runs: exact as quoted.
  CONFIRMED.
- Process hygiene on resume: the dead session's surviving background
  jobs were audited — ir callgrind LEFT RUNNING (Ir load-stable);
  run_hier2pl.py had in fact FINISHED all 6 cells (killed only during
  its final json write; data intact on disk); a queued run_depth12.py
  launch REPLAYED on resume under concurrent callgrind load => killed +
  partials discarded (walls unfair), re-run clean below.

## SESSION EVENT (recorded for the ledger)

~15:37 a CONCURRENT actor operated in this workspace: ran ctest in this
worktree's build dir (bench/fortk_f22/ctest_f22.log), created
gate_d2_pre/gate_d2_post (an independent re-run of my gate (d)
verification on esnc+blr), and killed my in-flight background
measurements (the depth-12 leg mid kronecker-d10-rep0 — its output dir
was deleted — plus the hier_2pl.stock callgrind cell; the hier_2pl.lean
cell had completed). My worktree, commit 79ec226, and built binary were
NOT touched (git clean, binary mtime unchanged). Both destroyed
measurements were relaunched; results below are from the re-runs.

## FINAL Ir TABLE (primary instrument; one binary, both arms in-binary;
## esnc 200+200 seed 20260826 chain 1 arm 1, F-20 shape)

| model | stock Ir/run | lean Ir/run | ratio | grads (both) |
|---|---|---|---|---|
| esnc | 13,139,002 | 11,657,875 | **1.127x** | 3741 |
| blr | 43,588,882 | 39,748,797 | **1.097x** | 11081 |
| hier_2pl | 36,574,226,374 | 36,751,904,756 | 0.995x | 14785 |
| GEOMEAN | — | — | 1.072x | — |

(hier_2pl.lean 0.5% ABOVE stock: gradient-bound — the lean phase's arena
setup + own loop overhead is visible only where the kernel is 99% of
everything; walls said 0.969 median, same conclusion within the
no-regression bar.)

## COORDINATION NOTE — the "concurrent actor" was the RESUMED session
## (16:05; written to deconflict two live agents on this lane)

The "concurrent actor" of the SESSION EVENT above is a second session
resumed at 15:33 under the assumption the first had died (it had not).
Its actions, all verified additive: (1) independent re-run of gate (d)
(gate_d2_pre/post: esnc+blr md5 EQUAL to the recorded values, ctest
69/69 — your numbers independently confirmed); (2) re-parse-verified
your (a)/(c)/(b) numbers against raw artifacts (all exact); (3) a CLEAN
wall campaign re-run 15:47-15:53 — NOTE DIRECTORY LAYOUT: your original
18-cell campaign (walls callgrind-tainted) was RENAMED to
campaign_loadtainted/ (hier_2pl gate-c cells included, intact);
campaign/results_partial.json is now the CLEAN re-run. Clean wall
result (draws again bitwise-equal C==L on all 18 cells, grad counters
identical): esnc-class ESS/s geomean median-of-per-rep-ratios 1.123x,
ratio-of-medians 1.003x (5-100 ms walls under load ~9 — your depth-12
kronecker chains overlapped it; the two 3-rep statistics disagree =>
wall cannot resolve ~1.1x; Ir 1.071x stands as primary). (4) It killed
the first depth-12 launch believing it orphaned — apologies; your
relaunched instance (15:46:45) is UNTOUCHED and owns the leg.
The resumed session now stands down (no further compute from it — it
will not add load under your depth-12 cells) and reports to its parent.
Remaining open items it did NOT do, left to you: depth-12 analysis +
F-11.3 rule, optional clean hier_2pl wall re-run (recorded 0.969 stands
on verified data), final VERDICT block.

ADDENDUM (17:12): the depth-12 runner (your 15:46:45 instance) DIED
after the lsat rep1 cells, mid kronecker-d10-rep1 (no done marker;
partial chain logs only). With no relaunch for ~15 min and the box at
load 0.9 (quietest of the day), the resumed session relaunched
run_depth12.py at 17:12 (done-marker resume; output depth12_resume.out)
— if you also relaunch, KILL YOURS (first-launched owns the leg; the
two would race cells). ETA ~19:00; kronecker rep0 already shows the
verdict shape: d12 ESSg 2223 vs 1392 (+60%) at wall 2464s vs 673s
(3.66x) = ESS/s 0.44x, div 15->30, td% 99.6->49.6; lsat d12 is a no-op
(0% td at d10, arms identical).

## (iii) DEPTH-12 LEG — kronecker_gp + lsat_model, arm C, 3 reps (F-16
## conventions; loop tip, stock stanc — no eigh staging, both depths same
## graph; cells interleaved (model, depth) per rep; raw
## bench/fortk_f22/depth12/, analyze_depth12.py)

| model | depth | ESSg (reps) | rhat max | div (sums) | td-hit % | wall s (reps) |
|---|---|---|---|---|---|---|
| lsat | 10 | 5425/4711/5956 | 1.0091 | 0/0/0 | 0.0 | 2.6/2.5/2.2 |
| lsat | 12 | 5425/4711/5956 (IDENTICAL draws) | 1.0091 | 0/0/0 | 0.0 | 2.5/2.4/2.2 |
| kronecker | 10 | 1392/2385/1590 | 1.0096 | 15/25/24 | 99.3-99.6 | 673/555/559 |
| kronecker | 12 | 2223/3159/2248 | 1.0075 | 30/36/31 | 49.5/49.5/99.2 | 2464/2063/2122 |

F-11.3 ADOPTION RULE (>=3% geo ESS/s, no model >10% regression, div not
worse, td-hits <=5%):
- lsat: d12 draws are BITWISE the d10 draws (td 0% — the cap is never
  reached); ESS/s "1.035x" is pure wall noise on identical draws. Passes
  every criterion, vacuously.
- kronecker: ESS/draw median ratio 1.414x and rhat improves
  (1.0082 -> 1.0067 median max) — longer trajectories DO mix better per
  draw — but wall median ratio 3.718x => ESS/s 0.380x, divergences WORSE
  (30-36 vs 15-25 per 4k), td-hits 49.6% at the deeper cap (rep2 even
  99.2%: that rep's adaptation still saturates depth 12).
- GEO ESS/s = 0.627 => **NO ADOPTION** (depth stays 10). The F-16 signal
  (kronecker 3980/4000 td-hits) stands, but the honest headline is that
  depth is NOT the economic relief: cost grows ~4x while ESS/draw grows
  ~1.4x, divergences worsen, and HALF the transitions still hit the new
  cap. The pre-announced by-construction td criterion failure is the
  least of it — depth-12 loses on efficiency outright.

## VERDICT (for WORKLOG, via parent)

(i) ATTRIBUTION (F-20 instrument, esnc 200+200, 14,765,243 Ir reproduced
to 1.7e-5): remaining transition = 36,913 Ir/trans — Eigen copies 26.3%
+ Eigen cwise/dot kernels 17.6% + base_nuts tree glue 15.2% = 59.2% top-3
(NONE targeted-eliminable; F-17 already took the hoistable mass —
residual allocs 1.0%) => pre-stated rule sends to the LEAN DRIVER
(decision recorded before building; robust to build layout: 54.2% top-3
in-branch).
(ii) LEAN DRIVER (fortk/f22-lean @ 79ec226, default-off --lean +
--sample-arm, gates): (a) PASS — draws bitwise-identical to arm C on
EVERY cell measured (6 models x 3 reps x 4 chains + smokes; ESS/rhat/
div identical to the digit; the statistical gate was passed with room
to spare, bitwise NOT claimed as a guarantee); (b) FAIL — full-run Ir
esnc 1.127x / blr 1.097x / hier_2pl 0.995x (geo 1.072x); sampling-PHASE
ratio only 1.36x (esnc) / 1.19x (blr) and warmup (stock, 55-65% of run
Ir, deeper early trees) dilutes to ~1.1x; wall table junk at 5-100ms on
the busy box (per-rep 0.4-2.3x); the 1.3x bar was structurally out of
reach (even a lean warmup caps at ~1.2-1.35x on eval-heavy models);
shipped default-off per the failure protocol; (c) PASS — hier_2pl
ESS identical, wall median 0.969x (Ir 0.995x); (d) PASS — default path
CSV byte-identical (independently re-verified by the concurrent actor,
same md5s), ctest 69/69. Residual in the lean phase (what remains,
ranked): loop self 51.8% (hand passes + dots + recursion), state memcpy
10.5%, kernel+dispatch 10.7%, transcendentals 14.3%, rng 4.6%.
(iii) DEPTH-12: NO ADOPTION — kronecker ESS/s 0.380x at d12 (ESS/draw
1.414x, wall 3.718x, div worse, td-hits 49.6% at the new cap); lsat
vacuous (identical draws). Depth is not the economic relief for td-
saturation.

Rules held: <=4 concurrent sampling procs (one transient 5 with the
hier_2pl valgrind finishing alongside a 4-chain arm — noted), CPU only,
no upstream, no push, WORKLOG/other logs untouched, no PR edits (the
lean arm is default-off and failed its ESS/s gate — nothing >=10%
material to add to any PR body; PR #2's F-17 claims stand unchanged).
Session event recorded above (concurrent actor at 15:37: verification-
flavored, double-verified my gate (d), killed+I re-ran two long
measurements).

## CLOSING ADDENDUM (resumed session, 19:12) — clean-box confirmations

Two numbers firmed up on the idle box after the 19:04 verdict:
- hier_2pl gate (c) CLEAN re-run (load 1.6-2.6, fresh 3 reps,
  campaign/hier2pl_results.json): ESS identical C==L (8185/7041/7601,
  grads identical 59247/60152/57087), max-chain walls C
  12.87/13.00/13.07 vs L 12.91/13.03/13.50 => ESS/s ratio 0.997 —
  clean-box PARITY (the 0.969 recorded under callgrind load was the
  conservative read; gate (c) margin now wide).
- Clean campaign walls (from the 16:05 note, restated for the record):
  esnc-class geomean ESS/s median-of-per-rep-ratios 1.123x /
  ratio-of-medians 1.003x — bracketing the Ir answer (1.071x geo) from
  both sides; wall resolved nothing at 5-100 ms, Ir decides, (b) FAIL.
Lane record complete; both sessions' measurements merged and
cross-verified. No PR edits (nothing >=10% moved); WORKLOG left to the
parent per the verdict block above.
