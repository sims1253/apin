# F-23 log — lean WARMUP (extend the lean NUTS driver to iteration 0)

Binding charter: WORKLOG "F-23 pre-registered" (2026-08-28). Read order
honored: logs/fortk-f22.md (complete F-22 record: lean design, frozen-state
handoff, bitwise surprise, Ir tables, ceiling arithmetic ~1.2-1.35x), WORKLOG
"F-22 VERDICT", "F-20 VERDICT" (--cg callgrind instrument pattern).

Setup (boot, 2026-08-28):
- Plan: worktree external/stanli-pr-loop, branch fortk/f23-leanwarm off
  fortk/f22-lean @ 79ec226. deps/stan patches 0001-0003 must be live
  (+222/-35) before any timing.
- Build: extend --lean so the lean traversal runs from iteration 0: init
  phase, windowed warmup schedule (init buffer / window doubling / term
  buffer — stock driver constants), step-size dual-averaging + diag-metric
  Welford — REUSING the vendored stan adaptation objects at the same
  decision points, lean tree/leapfrog underneath. Preserve two-phase mode
  as fallback if cheap; default --lean = lean from iteration 0. Default
  path (--lean absent) untouched.
- Gates: (a) fidelity full-run byte-identical to arm C on esnc/blr/
  hier_2pl (--sample 1000 1000, seed 20260826, chain 1; md5 + adapted-state
  echo); fallback = frozen-state numeric compare + 3-seed statistical +
  first-divergence localization. (b) full-run Ir geomean >= 1.3x over
  esnc/esc/blr/logmesq/kidscore, phase split reported; 1.2-1.3x = honest
  near-miss naming pass-fusion/dot-batching. (c) default byte-identity +
  ctest. (d) ESS/s end-toend interleaved 3 reps, informational.
- Rules: <=4 concurrent sampling procs, CPU only, -j2 builds, no upstream,
  no push, raw bench/fortk_f23/.

(work in progress — appended incrementally below)

## (i) READ + DESIGN (boot)

- Worktree external/stanli-pr-loop: fortk/f23-leanwarm created off fortk/f22-lean
  @ 79ec226 (clean). deps/stan patches live: +222/-35 over base_nuts.hpp +
  diag_e_metric.hpp + expl_leapfrog.hpp. Confirmed.
- F-22 lean lives entirely in tools/fortk/regions.cpp (fortk_f22 namespace):
  LeanNuts (arena driver, frozen eps/inv_m via ctor) + run_lean_nuts
  (two-phase: stock warmup via stanli::adapt_diag_e_nuts_direct with verbatim
  run_nuts prologue, frozen handoff, lean sampling).
- Stock adaptation wiring (vendored, to REUSE not reimplement):
  - adapt_diag_e_nuts::transition (deps/stan adapt_diag_e_nuts.hpp ==
    stanli/direct_nuts.hpp verbatim copy): learn_stepsize(nom_epsilon_,
  accept_stat) EVERY warmup transition; learn_variance(z_.inv_e_metric_,
  z_.q) EVERY transition; on window update: init_stepsize(logger) +
  set_mu(log(10*nom_eps)) + restart().
  - base_hmc::init_stepsize: probe loop, sample_p + hamiltonian_.init (1
    grad eval) + one evolve (1 grad eval) per probe; direction test
    delta_H > log(0.8); eps *=2 or /=2; guards >1e7 / ==0; final restore
    of z_ = z_init (ps_point slice: q,p,g,V — metric NOT restored).
  - stepsize_adaptation (Nesterov DA) + var_adaptation (windowed Welford
    + n/(n+5) regularization) — plain classes, instantiable directly.
    welford sample_variance ASSIGNS into same-size var (no resize) =>
    a raw pointer into an Eigen::VectorXd metric stays valid.
  - window constants: set_window_params(warmup, 75, 50, 25).
  - disengage: complete_adaptation(nom_eps) => exp(x_bar).
- Fidelity-critical mirrors for the lean warmup (all noted):
  1. Metric starts ONES (diag_e_point ctor), W_V=0 + no eval at seed
     (ps_point V{0}); FIRST transition evaluates init (stock carry_valid_
     false) => lean: eval_pot() once after seeding; grad parity exact.
  2. Probes: 2 exec grads per probe, same RNG (n normals per sample_p),
     same arithmetic; error path g=-0.0(stock negated)/+0.0(lean raw)
     equivalent on every p including +-0.
  3. learn_stepsize BEFORE learn_variance; init_stepsize probes with the
     JUST-UPDATED nom_eps (exp(x)) at window updates, 0.1 at t=0.
  4. Welford q: copy W.q into an Eigen buffer per iteration (z_.q analog);
     metric updated in place; learn_variance call COUNT drives the window
     counters — identical schedule by construction.
  5. eps used by transition i = nom_eps output of DA step i-1
     (sample_stepsize: epsilon_=nom_epsilon_, jitter 0).
- Plan: --lean = lean from iteration 0 (new default); --lean-stock-warmup
  = F-22 two-phase fallback; STANLI_DEBUG_LEAN_TRACE=1 dumps per-iter
  (eps/accept/nlf/depth/div/qhash/mhash) for BOTH lean-warmup and the
  two-phase stock warmup => first-divergence localization if bitwise
  fails. LeanResult gains frozen metric echo + phase-split counters.

## (ii) IMPLEMENTATION + FIRST SMOKE (the ulp hunt)

- Implemented: LeanNuts gains z_init probe block, seed_partial,
  sample_p_lean, init_stepsize (base_hmc probe-loop mirror);
  run_lean_nuts_full drives vendored stepsize_adaptation +
  var_adaptation at stock's decision points; --lean = full mode,
  --lean-stock-warmup = F-22 fallback; STANLI_DEBUG_LEAN_TRACE=1
  per-iteration trace on BOTH lean warmup and the two-phase stock
  warmup; LEAN_WARM echo (eps_frozen %.17g + metric FNV + phase
  counters). Build green (-j2).
- FIRST SMOKE (esnc 200+200): FAIL — +20 exec grads, warm divergences
  5 vs 0. TRACE DIFF localized it to iteration 0 accept_stat: lean
  9.8489582015738567e-06 vs stock ...738211e-06 (last-ulp). qhash/
  mhash/eps identical for several iterations; the DA amplifies the
  ulp into visible eps drift by i=4.
- ROOT CAUSE: LeanNuts's hand-loop reductions vs Eigen's. Eigen 5.0.1
  (deps/math/lib/eigen_5.0.1 src/Core/InnerProduct.h) inner_product_
  impl accumulates 4-way PACKET LANES + predux + scalar tail — no
  sequential loop matches it. F-22's sampling phase hid this: the ulp
  only perturbed sum_metro_prob => accept_stat__, printed at 6
  significant digits in the CSV (rounded away), and never flipped a
  draw branch in any F-22 cell. The DA consumes accept_stat EVERY
  warmup iteration — the ulp became fatal exactly at the seam F-23
  opens. (This also retroactively explains F-22's esnc 3765(ex0)/
  3741(ex1) grad-count asymmetry: an executor artifact, see below.)
- FIX: H_working, crit, energy now use Eigen Map-based
  dot/cwiseProduct — stock's exact expression shapes. Alignment
  selects load modes only (never summation order) => lane-identical
  to stock's VectorXd.dot.
- SECOND SMOKE: warmup trace (eps/acc/nlf/depth/div/qhash/mhash,
  200 iters) IDENTICAL lean-vs-stock to the last digit. In-tool
  bitwise= line still NO — diagnosed as the ex0-vs-ex1 (unfused vs
  fused executor) artifact: even stock-vs-stock on ex0/ex1 shows
  exec-count deltas (+8 at 200+50) and draw divergence; F-22's
  protocol (campaign + smokes) compared SAME-EXECUTOR CSVs via
  --sample-arm 1, which is the valid instrument.
- GOLD SMOKE (--sample-arm 1, esnc 200+200, seed 20260826 chain 1):
  CSV md5 stock = two-phase-lean = FULL-lean-from-0 =
  5253067ddd95ee9b8dbddf09414aa7ed (F-22's recorded value); GRAD
  exec1=3741 in all three. THE BET HOLDS on esnc 200+200.

## (iii) GATE (a) FIDELITY — **GOLD (bitwise)**

Protocol (--sample-arm 1 => same fused executor both arms, F-22
campaign convention; --sample 1000 1000 --seed 20260826 --chain-id 1;
raw bench/fortk_f23/gate_a/):

| model | stock md5 | lean-full md5 | 2-phase md5 | exec1 stock/full/2ph | hits1 |
|---|---|---|---|---|---|
| esnc | abb6eddd3b1dc0daa8e43c099b304ae9 | SAME | SAME | 17348/17349/17348 | 1/0/1 |
| blr | 7816c45c3fa802c1d370626b6106719d | SAME | SAME | 31921/31921/31921 | 0/0/0 |
| hier_2pl | 0a09744b3a8e7daadaef18415da3beff | SAME | SAME | 59247/59247/59247 | 0/0/0 |

- FULL-RUN draws (warmup-inclusive) BYTE-IDENTICAL to arm C on all
  three gate models. Grad counts: blr/hier_2pl EXACT; esnc +1 exec
  eval in lean-full — pinned to arm C's ONE endpoint-cache hit
  (hits1=1: ExecutorModel served a probe-init from the cache; the
  cached doubles are identical by design — the CSVs prove it). F-22's
  campaign numbers reproduced exactly (17348/31921/59247).
- Adapted-state echo (LEAN_WARM): eps_frozen to 17 digits AND metric
  FNV identical lean-full vs stock-warmup on all three:
  esnc 0.44939869862131288 / 5bc5406fb9b6ca71; blr 0.11739110319980951
  / 3a891af2531f5d13; hier_2pl 0.18295903947368738 / f29fc1231418eb81.
  5 window updates each (1000-warmup stock schedule).
- 200+200 esnc warmup TRACE (all fields x200 iters) identical — the
  localization instrument is in place should anything ever diverge.
- NOTE (instrument hygiene): the tool's in-process `bitwise=` line
  compares ex0-unfused vs ex1-fused draws and shows NO even for
  stock-vs-stock (executor-level last-ulp chaos; F-22's recorded
  3765/3741 asymmetry was the same artifact). The valid gate is the
  same-executor CSV md5 above.
- Committed: fortk/f23-leanwarm @ 2eb3785 (implementation + fixes).

## (iv) GATE (c) — PASS

- Default path byte-identity: pre-F-22 binary (bench/fortk_f22/
  fortk_t1r.pre_f22) vs F-23 binary, esnc+blr 200+200 default (no
  --lean): CSV md5 EQUAL (5253067ddd95ee9b8dbddf09414aa7ed /
  b6e8df4bde54722d36ec328cb9fb58b8 — both equal to F-22's recorded
  values). Raw gate_c/. (Note: pre_f22 binary predates --sample-arm;
  run without it, CSV still written from the ex1 arm.)
- ctest 69/69 PASS (build-pr, -j2). Raw ctest_f23.log.

## (v) GATE (b) SPEED — full-run Ir — 1.228x geomean (NEAR-MISS band)

F-20 pattern, ONE binary both arms (fortk_t1r.f23), 200+200 seed
20260826 chain 1 arm 1; warmup-phase Ir from 200+1 runs; sampling =
difference. Grad parity EXACT in every cell (exec1 identical stock vs
lean — the comparison is iso-grad by construction). Raw ir/ +
ir_campaign.out.

| model | stock Ir/run | lean Ir/run | full-run | warmup-ph | sampling-ph |
|---|---|---|---|---|---|
| esnc | 13,112,752 | 9,830,697 | **1.334x** | 1.322x | 1.353x |
| esc | 35,210,307 | 27,152,209 | 1.297x | 1.292x | 1.306x |
| blr | 43,556,908 | 36,768,491 | 1.185x | 1.185x | 1.185x |
| logmesq | 95,689,078 | 75,161,221 | 1.273x | 1.273x | 1.273x |
| kidscore | 346,350,101 | 323,389,070 | 1.071x | 1.070x | 1.073x |
| GEOMEAN | — | — | **1.228x** | 1.225x | 1.234x |

- VERDICT at the 1.3x bar: **NEAR-MISS** (the pre-declared 1.2-1.3x
  band), exactly where the F-22 ceiling arithmetic (~1.2-1.35x) said
  it would land. Remaining levers, unchanged from F-22: pass-fusion +
  dot-batching INSIDE the lean loop (FP-order changes, statistical
  gates) — the lean loop's residual (loop self ~50% of lean Ir) plus
  the kernel floor.
- HYPOTHESIS CONFIRMED: warmup phases now show the SAME gain the
  sampling phase had in F-22 (esnc warmup 1.322x vs F-22's 1.0x stock
  warmup; sampling-phase ratios essentially unchanged: esnc 1.353 vs
  F-22's 1.36). Full-run esnc moved 1.127x (F-22) -> 1.334x; blr
  1.097 -> 1.185. The dilution is kidscore (1.071x — 13.5k Ir/grad,
  gradient-bound like F-22's hier_2pl 0.995x) and blr (1.185x —
  eval-heavy, 28 gpi).

- Instrument note: first Ir launch failed wholesale (zsh does not
  word-split unquoted vars: `--sample $SHAPE` passed "200 200" as ONE
  arg). Fixed (W_/S_ split), re-run clean; raw cells under ir/.

## (vi) GATE (d) ESS/s END-TO-END — informational; walls now resolve

Interleaved same-day (model-major, C then L within rep), 3 reps x 4
chains, 1000+1000, esnc-class 5 (raw campaign/ + gate_d.out; first
launch hit a region-cache race — 4 chains compiling the same .so into
the shared cache; prewarm added, F-22's pattern). 15/15 cells md5-EQ
(= 60 chains of full-run bitwise C==L beyond the gate-(a) cells).
ESS identical by construction (md5); ESS/s ratio = wall ratio:

| model | ESS_min (reps) | rhat max | C/L wall ratio (reps) |
|---|---|---|---|
| esnc | 2394/2853/2673 | 1.0043 | 1.197/1.477/1.432 |
| esc | 263/45/130 | 1.0706 | 1.166/1.428/1.146 |
| blr | 824/760/950 | 1.0044 | 1.283/1.223/1.434 |
| logmesq | 1574/1449/1677 | 1.0031 | 1.213/1.106/1.103 |
| kidscore | 1169/1257/1247 | 1.0067 | 1.145/1.008/1.060 |

ESS/s geomean (C/L, per-cell max-chain wall, ms-scale — labeled
noisy): **1.220x**, median 1.197x — unlike F-22 (1.123 vs 1.003, wall
resolved nothing) the effect is now large enough that the busy-box
walls BRACKET the Ir answer (1.228x) from below. Ir remains primary.

## (vii) EDGE HARDENING (gold robustness beyond the gate shape)

Warmup-schedule branch coverage, esnc, seed 20260826 chain 1,
--sample-arm 1 md5: w=100 (75+50+25 > 100 => the 15%/75%/10% rescale
branch) EQUAL; w=20 (rescale to 3/15/2) EQUAL; w=1000 s=20 EQUAL
(grads 10060 vs +1 cache-hit). The vendored-objects bet holds across
every window-schedule branch the stock driver can take.

## VERDICT (for WORKLOG, via parent)

F-23 (fortk/f23-leanwarm @ 2eb3785, off fortk/f22-lean @ 79ec226;
deps/stan patches unchanged +222/-35; NOT pushed):

- (a) FIDELITY: **GOLD — bitwise**. Full-run (warmup-inclusive) draws
  BYTE-IDENTICAL to arm C on esnc/blr/hier_2pl 1000+1000 seed 20260826
  chain 1 (CSV md5 equal; grad parity exact — esnc's +-1 is arm C's
  endpoint-cache hit serving identical doubles); PLUS 15/15 campaign
  cells x 4 chains md5-EQ and the window-rescale/sub-20 edge shapes.
  Adapted frozen state identical to 17 digits + FNV. The design bet
  (same vendored adaptation objects, same RNG/arithmetic through the
  seam) held — after one real fix: the F-22 hand-loop reductions
  differed from Eigen's packet-lane inner product in the last ulp,
  which the DA amplifies every warmup iteration (invisible in F-22
  where only 6-sig-digit accept_stat__ consumed it); lean reductions
  now use Eigen Map dots. STANLI_DEBUG_LEAN_TRACE localizes any
  future divergence per iteration (tested: 200-iter trace identical).
- (b) SPEED: **NEAR-MISS at the 1.3x bar** — full-run Ir geomean
  **1.228x** (esnc 1.334 / esc 1.297 / logmesq 1.273 / blr 1.185 /
  kidscore 1.071), in the pre-declared 1.2-1.3x honest band, exactly
  the F-22 ceiling arithmetic. Phase split: WARMUP-phase ratios now
  1.32/1.29/1.27/1.19/1.07 — the hypothesis confirmed (warmup gains
  what sampling gained; sampling-phase ratios unchanged: esnc 1.353
  vs F-22's 1.36). Full-run moved esnc 1.127->1.334, blr 1.097->1.185.
  Residual = the named levers: pass-fusion + dot-batching inside the
  lean loop (FP-order, statistical-gated), then the kernel floor
  (kidscore 13.5k Ir/grad bounds it at 1.07x).
- (c) PASS: default path byte-identical (pre-F-22 binary vs F-23,
  esnc+blr md5 equal to F-22's recorded values); ctest 69/69.
- (d) PASS (informational): ESS/s geomean 1.220x C/L on walls (15/15
  cells md5-EQ; ms-scale walls labeled noisy but now bracket Ir 1.228x).
- PR edits: NONE — the full-run Ir geomean did not cross 1.3x, the
  flag is default-off tool code not in any PR body (F-22's rule
  applied identically).
- Rules held: <=4 concurrent sampling procs (4-chain cells), CPU only,
  -j2 builds, no upstream, no push, other worktrees'/logs' sources
  and WORKLOG untouched, raw under bench/fortk_f23/.
