# F-27 incremental log — WARMUP EARLY-EXIT (the W-21/W-22 port, --wexit)

Binding charter: WORKLOG "F-27 pre-registered" (2026-08-29). Read order
honored: WORKLOG F-26 VERDICT (arm-L baseline 7.53x geomean, the
integration-branch topology) + F-27 charter; F-18/F-19 VERDICTs (ESS
conventions, interleaved-wall discipline); W-21/W-22 sections (the
1.3-2.4x wins, the marginal-class victims arma11 -33% / lsat -40% /
hier_2pl -58%, the step-drift diagnosis, W-21 shipped criterion +
library semantics); HANDOFF item C + NEXT_IDEAS B (pilot-burst design);
logs/fortk-f26.md + logs/fortk-f23.md (the driver structure: where the
warmup windows and the lean loop live in tools/fortk/regions.cpp).

## Setup (boot, 2026-08-29)

- Worktree external/stanli-f26, branch fortk/f27-earlyexit off
  fortk/f26-capstone @ 70fd71a. deps/stan patches 0001-0003 verified
  live (+222/-35 over base_nuts/diag_e_metric/expl_leapfrog). stanc
  5b824ee + stanc.src provenance present.
- Raw dir bench/fortk_f27/ (created below).

## DESIGN (pre-stated, before any code)

Driver placement — LEAN PATH ONLY, stated: the charter allows lean-only
if the stock loop is harder first; it is. --wexit requires --lean (the
lean-from-0 driver run_lean_nuts_full is the flagship arm-L path; the
stock loop lives in the library behind deps patches and a second
implementation would double the risk surface for zero campaign value —
arm L is the only baseline). --wexit WITHOUT --lean is rejected.

Where the true window boundaries are (CORRECTED after a trace
verification — my first reading had term/base swapped; stan's
set_window_params(num_warmup, init=75, TERM=50, BASE=25)): for
warmup=1000 the var_adaptation updates fire at 0-indexed i = 99, 149,
249, 449, 949 (completed 100/150/250/450/950; 5 updates = F-23's
recorded count; probe signatures in the eps trace confirm). Eligible
--wexit sites (completed >= 150 AND remaining > 50 pilot draws):
completed 150, 250, 450 (950 leaves exactly 50 = pilot cost, net zero,
skipped).

GATE 1 (step stability, the W-22 gate; ZERO extra RNG — pure reads of
state the stock path already computes):
- eps_exit_j = exp(x_bar) at the END of window j, obtained by COPYING
  stepsize_adaptation (plain-double class, copyable) and calling
  complete_adaptation on the copy — the decision-relevant quantity:
  "the eps this run would freeze if warmup ended at boundary j".
  Snapshot taken at the top of if(update), BEFORE the stock probe +
  DA restart (x_bar is window-local since the last restart; the probe
  does not touch x_bar).
- step gate (primary): |log(eps_exit_j / eps_exit_{j-1})| <
  log(1.05) (5% in log terms, W-22's <5%-drift encoding) — per chain,
  ALL chains must pass.
- mass gate (secondary, loose by W-22 evidence — mass drift was benign
  at 2-13% while step drifted +170% on the victims): L2 rel drift of
  inv_m between the last two window ends < 0.25 (W-21's own library
  mass tol) — per chain, all chains.

GATE 2 (pilot burst, 50 draws, adaptation frozen; RNG discipline =
CLONED STATE): only if gate 1 passes on ALL chains. Each chain
constructs a PILOT LeanNuts over a COPY of the rng (boost mixmax is
copyable), a COPY of inv_m, and eps frozen at eps_exit_j, seeded at
the main driver's current q (seed_partial + eval_pot), and runs 50
transitions collecting lp__. The main stream, main LeanNuts state,
and main inv_m are NEVER touched by the pilot — so BOTH the
gate-2-fail path (continue warmup) and the no-exit path consume ZERO
extra draws from the main stream, and held-warmup runs stay
byte-identical to arm L (gate (a) md5). Cross-chain aggregation via a
file rendezvous (below). Diagnostics per chain: n, mean, var (ddof=1),
lag-1 autocorr of the 50 lp values
(r1 = sum (x_t-xbar)(x_{t+1}-xbar) / sum (x_t-xbar)^2).
- R-hat proxy (charter, < 1.01): classic m-chain R-hat on lp__ across
  the 4 pilot series: W = mean chain var, B = n * var-of-means,
  var_plus = ((n-1) W + B) / n, Rhat = sqrt(var_plus / W).
- lag-1 gate: mean over chains of r1 < LAG1_TOL (calibrated below,
  value stated before the campaign).
Both pass => EXIT: nom_eps = eps_exit_j, warmup loop breaks, sampling
starts from the main state (documented stream change vs arm L: arm L
consumes iterations j+1..999 of warmup draws before sampling; arm X
starts sampling draws immediately after iteration j — behavioral arm,
statistical-gated). Any fail => pilots discarded, warmup continues —
the full-warmup path is unchanged and reachable on every model.

CROSS-CHAIN MECHANICS: the campaign runs 4 chains as 4 separate
PROCESSES (seed = base+1000*rep+c, chain_id=1 — identical topology to
arm L, so walls are comparable: max-chain wall over 4 concurrent
procs). Cross-chain gating therefore uses a file rendezvous:
--wexit-rz DIR (created fresh per run by the campaign driver; the 4
chain processes share it). Protocol per eligible boundary: (1) each
chain writes b{i}.{seed} with its gate-1 numbers; (2) poll until all
--wexit-chains (default 4) files for b{i} exist (timeout 300 s =>
fail-safe HOLD, logged); (3) if all gate-1 pass: each chain runs its
own pilot, writes pilot stats, polls for all; (4) every chain computes
the same aggregate decision deterministically from the same files.
Single-chain mode (--wexit-chains 1) uses a split-half R-hat proxy
(2 x 25) for dev smoke only; the campaign uses 4.

FLAGS: --wexit (default OFF; absent => byte-identical, gate (c));
--wexit-rz DIR (default <outdir>/wexit_rz); --wexit-chains N (4);
--wexit-lag1 T (diagnostic override of LAG1_TOL; the DEFAULT is the
calibrated constant below); --wexit-force-iter B (calibration/
diagnostic: force exit at boundary B skipping both gates; NEVER used
in campaign cells). Tool lines: WEXIT_BOUNDARY (per site: eps_exit,
step drift, mass drift, gate1), WEXIT_PILOT (per site: per-chain
lag1/mean/var, aggregate Rhat, mean lag1, decision), WEXIT_EXIT /
WEXIT_HELD (exit iter + saved iters / never exited), all in tool.log.

## CALIBRATION RESULT (wells_dist100_model, BEFORE the campaign; raw bench/fortk_f27/calib/)

Step 1 (where is warmup enough? forced exits, 3 seeds x 4 chains,
ESS_bulk min over params of 4000 draws / rhat max):

| config | s+101 | s+103 | s+107 | verdict |
|---|---|---|---|---|
| full 1000 | 1072 / 1.0018 | 1110 / 1.0023 | 1496 / 0.9998 | reference |
| force 150 | 763 / 1.0015 | 654 / 1.0014 | 1240 / 1.0180 | HURTS (ESS -30..-40%, rhat 1.018 > 1.01) |
| force 250 | 1221 / 1.0010 | 1189 / 1.0065 | 1117 / 1.0053 | equivalent (within the full-arm's own seed spread 1072-1496) |
| force 450 | 1251 / 1.0056 | 1212 / 1.0007 | 1461 / 1.0004 | equivalent |

Earliest quality-equivalent boundary B* = 250.

Step 2 (pilot stats at every boundary, 3 seeds x 4 chains = 12 cells
each; forced mode runs+logs the pilot without gating):

| boundary | lag1 min/med/max (mean) | split-rhat max |
|---|---|---|
| 150 (hurts) | 0.251 / 0.322 / 0.522 (0.365) | 1.0043 |
| 250 (equiv) | 0.061 / 0.390 / 0.442 (0.298) | 1.0307 |
| 450 (equiv) | 0.066 / 0.439 / 0.500 (0.335) | 1.0354 |

LAG1_TOL by the pre-stated rule: worst equivalent-boundary lag1 0.500
(450) vs best non-equivalent 0.251 (150) -> geometric midpoint 0.354 ->
rounded toward rejection: **0.35**.

HONEST CAVEAT (required by the rule's own wording — the gap is not
narrow, it is INVERTED): the pilot lag1 on lp__ does NOT separate the
classes on the dev model (equivalent-boundary range 0.061-0.500
overlaps the harmful boundary's 0.251-0.522; the split-rhat is even
counter-sorted, 1.03-1.04 at the equivalent boundaries). At 50 draws
the statistic is noise-dominated on this model. The threshold 0.35 is
the mechanical application of the pre-stated rule and lands
mid-distribution; as an instrument the lag1 gate is WEAK — the
protective power lives in gate 1 (step 5% + mass 0.25) and the
cross-chain R-hat, which DID reject arma11's marginal candidate exit
(rhat 1.0513 >= 1.01, see recon below). Reported as found.

Also from the pre-campaign recon (1 seed, single chain, informational):
at the charter's 5% step + 0.25 mass gates EVERY model tested (phase-1
6, sentinels 3, dev) HOLDS at all three sites (150/250/450); the only
gate-1 pass anywhere is arma11@450 — which the pilot then rejects.
The exit-eps-vs-final-frozen table (why holding is correct):
eps_exit@450 vs full-warmup frozen eps: esc 1.27x, blr 0.53x,
kidscore 0.82x, logmesq 1.14x, pilots 2.08x, arma11 1.27x, hier_2pl
1.15x, lsat 1.25x, wells 1.02x — a 450-exit freezes a 15-110%-off
step; full warmup does real work on this stack. Closest near-miss
phase-1 cell: logmesq@450 passes the step gate (0.020) and misses the
mass gate by 0.0085 (0.2585 vs 0.25).

## CALIBRATION PROTOCOL (pre-stated BEFORE the campaign)

- Dev model: wells_dist100_model (OUTSIDE phase-1; the F-25/F-26
  verify-spot model, infrastructure known-good; easy class).
- Seeds 20260826+101, +103, +107 x 4 chains, warmup 1000 + draws 1000.
- Step 1 (where is warmup enough?): --wexit-force-iter at each
  eligible boundary (224 / 424 / 824) vs full-warmup arm L: ESS_bulk
  (geomean + min), R-hat max, divergences. Defines the earliest
  QUALITY-EQUIVALENT exit boundary B*.
- Step 2 (pilot stats at each boundary): --wexit with
  --wexit-lag1 1.0 (lag1 gate disabled; R-hat gate live) logs the
  pilot burst's mean-lag1 + Rhat at every site the gates reach.
- Threshold rule (fixed now): LAG1_TOL = midpoint (geometric) of the
  worst Step-1-equivalent-boundary lag1 and the best non-equivalent
  boundary lag1, rounded to 2 significant digits toward REJECTION
  (fewer exits) if the gap is narrow; if all three boundaries are
  quality-equivalent, set LAG1_TOL just above the boundary-224 pilot
  lag1 (take the early exit) and say so. The chosen value + the two
  numbers it sits between go HERE before any campaign cell runs.

## GATES (from the charter, never loosened)

(a) QUALITY: for each phase-1 model where exit fires: post-warmup
ESS_bulk/draw within noise of arm L full-warmup (3 seeds 20260826+7,
+13, +29), all-chain R-hat < 1.01, divergences not worse (stated rule:
div_X <= max(2, 1.1 * div_L); 0-div models must stay 0). Where the
gate holds warmup (no exit): draws byte-identical to arm L (md5 per
chain). RNG-discipline sub-check: one held-warmup cell WITH failed
pilots exercised (--wexit-lag1 ~0) must still md5-match arm L.
(b) SPEED: ESS/s geomean (phase-1 6) >= 1.2x vs arm L, same-day
interleaved, both arms driven by the F-27 binary (--wexit off = L',
on = X), 3 reps medians, seeds 20260826+1000*rep+c. Report per model:
exit iteration, warmup iterations saved, ESS/s ratio. Exit-iteration
table is first-class.
(c) DEFAULT-OFF: --wexit absent => byte-identical to the f26 binary
(esnc + blr md5 200+200 vs recorded 5253067ddd95ee9b8dbddf09414aa7ed
/ b6e8df4bde54722d36ec328cb9fb58b8); ctest 69/69.
(d) SENTINELS: arma11, hier_2pl, lsat_model (W-21 victims) --wexit vs
full: ESS/draw within noise, R-hat < 1.01; if an exit fires and hurts,
report it as a REAL finding.

Rules: <=4 concurrent sampling procs; CPU only; -j2 builds; no
upstream; no push; explicit staging; do not touch /tmp/review/stanli,
other worktrees' sources, WORKLOG.md, other logs; raw bench/fortk_f27/.

## GATE (c) — PASS (raw byteid/, ctest_f27.log)

- LIVE A/B (f27 binary vs f26 rebuilt from 70fd71a in-place, default
  path 200+200 seed 20260826 chain 1): esnc md5
  5253067ddd95ee9b8dbddf09414aa7ed BOTH (= the recorded F-22..F-26
  value); blr b6e8df4bde54722d36ec328cb9fb58b8 BOTH (recorded).
- The --wexit HOST PATH with the flag absent (--lean 1000+1000 esnc):
  f27 == f26ref (7b6c3c976582d16285eb58e030f50851).
- ctest: **69/69 PASS**.
- --wexit without --lean rejects at parse time (verified).

## GATE (a)+(d) — PASS, with the headline finding: THE GATES HOLD
EVERYTHING (raw gate_a/ + results.json)

Battery: 9 models (phase-1 6 + sentinels arma11/hier_2pl/lsat) x 3
seeds (20260826+7/+13/+29) x 4 chains, L (--lean) vs X (--lean
--wexit, 4-chain rendezvous, calibrated defaults), same binary.

- **27/27 cells: X HELD full warmup (exit_iter -1 on every chain, 3
  sites each). ZERO exits anywhere in the battery.**
- **108/108 chain CSVs md5-MATCH arm L** — where the gate holds warmup,
  X is draw-bit-identical to L (the RNG-discipline claim verified at
  battery scale; includes the failed-pilot discipline check on arma11
  seed 20260826 where the pilot ran and was rejected, md5 still equal).
- Quality columns (ESS/rhat/div) identical L==X BY CONSTRUCTION
  (identical draws). Sentinel rhats: arma11 1.0014-1.0028, hier_2pl
  1.0064-1.0082, lsat 1.0067-1.0091 — all < 1.01. (esc 1.02-1.06 and
  pilots 1.08-1.12 are the documented pathological cells, IDENTICAL in
  L.) Gate (d): PASS — and on arma11 the pilot burst actively REJECTED
  the one gate-1-passing candidate exit it saw (recon seed: rhat 1.0513
  >= 1.01) — the W-21 victim protection works.
- INFORMATIONAL forced cells on logmesquite (the nearest-miss model —
  step gate PASSES at 450 (drift 0.020), mass gate misses by 0.0085
  (0.2585 vs 0.25)): forced exit@250: ESS_min 1203/1303 vs L
  1487/1325 (-19%/-2%), div 7 vs 0 on one seed; forced@450: ESS_min
  1196/1200 vs 1487/1325 (**-19.5%/-9.4%**). The 0.0085 near-miss was
  GENUINELY PROTECTIVE — even the closest call in the battery, forced
  open, costs ~10-20% min-ESS. The gates are not merely conservative;
  they are right.

(work in progress — campaign (b) appended below when done)

## IMPLEMENTATION INCIDENTS (all found by running; fixed in 91fe4ce)

1. RENDEZVOUS TIMEOUTS (campaign v1): the phase-1 publish sat inside
   `if (g1 passes locally)` — a locally-passing chain then waited the
   full 300 s for locally-failing peers that never wrote (rep0/rep2 X
   walls 300-600 s on 4 cells; draws unaffected — every timeout cell
   still md5-matched L). FIX: publish-and-continue — every ELIGIBLE
   chain publishes pass-or-fail; a local fail decides the global hold
   so it continues immediately; only a local passer waits.
2. UNCONDITIONAL-WAIT overshoot (intermediate fix): waiting on every
   cell paid the peer-startup skew (~0.3-0.5 s) even where gates hold
   everywhere. FIX: same publish-and-continue (failing chains never
   wait). Verified: 4-chain esnc exec1 back to L level (0.0031-0.0046
   vs L 0.0038).
3. RZ PARSER (found by the 3-chain machinery test): the pilot-field
   sscanf anchored at position 0 — sscanf literals are not a search —
   so phase-2 aggregates read zeros (rhat=inf, lag1=0) before the fix.
   FIX: anchor at the located " pn=".
4. Spurious b100/b950 publishes (ineligible sites) — gated on
   wx_eligible.
5. MACHINERY TESTS beyond the battery: 4 distinct-seed arma11 chains
   with one g1-passer (publish-and-continue: passer waits <1 s, holds
   on the read fail-file, md5 == L); 3-chain ALL-PASS cell (seeds
   20260826/39/47, all pass g1@450): phase-2 pilots rendezvous,
   aggregate rhat=1.0079 / mean lag1=0.301, UNANIMOUS exit at 450
   (saved 550, per-chain frozen eps) — the full exit path works.
   NOTE from that test: the pilot's cross-chain R-hat is KNIFE-EDGE on
   arma11 (1.0079 just under 1.01 here; the single-chain split-half
   gave 1.0513) — had gate 1 passed all 4 chains on a victim model,
   gate 2 might NOT have caught it. In the real battery arma11's
   protection came from GATE 1 (the step/mass conjunction), not the
   pilot.
6. Binary provenance note: the calibration battery ran on the
   09ab4eb-era binary plus two then-uncommitted diagnostics
   (probe_eps in the boundary line; forced-mode pilot logging); a
   `git checkout 70fd71a -- regions.cpp` A/B build for gate (c) wiped
   them; both were re-added in 91fe4ce (log-only output, no gate
   logic change). All gate batteries above were RE-RUN end-to-end on
   the final binary 91fe4ce and reproduce the earlier results exactly
   (27/27 held, 108/108 md5, forced cells 1202.76/1196.04/1303.11/
   1200.23 ESS_min).

## GATE (a)+(d) on the FINAL binary — PASS (re-run; raw gate_a/)

27/27 cells held (exit_iter -1, 3 sites each), 108/108 chain CSVs
md5-MATCH arm L, quality identical by construction. Sentinel rhats
arma11 1.0014-1.0028 / hier_2pl 1.0064-1.0082 / lsat 1.0067-1.0091,
all < 1.01. Superseded identical first run kept at gate_a.v1-pre-fix.

## GATE (b) — FAIL at the 1.2x bar: 0.92x, ZERO exits (raw campaign/,
campaign.v2-loadspike/, campaign.v1-timeouts/)

One binary (91fe4ce), arms L' (--lean) vs X (--lean --wexit), 3 reps
x 4 chains x 1000+1000 interleaved, seeds 20260826+1000*rep+c, shared
prewarmed cache. Quiet-box run (loads 1.8-5.1 at rep starts; the
first run under a user rustc-build spike load 18-25 kept separately
and excluded — environment, not code):

| model | ESS/s L | ESS/s X | X/L | exit iter (all reps x chains) |
|---|---|---|---|---|
| esnc | 904,976 | 656,927 | 0.726 | held (12/12 chains) |
| esc | 86,620 | 52,624 | 0.608 | held (12/12) |
| blr | 109,961 | 123,618 | 1.124 | held (12/12) |
| pilots | 130 | 157 | 1.205 | held (12/12) |
| kidscore | 28,513 | 32,592 | 1.143 | held (12/12) |
| logmesq | 47,924 | 42,576 | 0.888 | held (12/12) |
| GEOMEAN | 33,954 | 31,239 | **0.920** | 0 exits / 72 chains |

- ESS identical L==X in every cell (draws bit-identical — 72/72
  chains across the campaign; the ESS/s ratio IS the wall ratio).
- THE EXIT-ITERATION TABLE (first-class deliverable): every phase-1
  model, every chain, every seed and rep examined — **held at all
  three sites (150/250/450); warmup iterations saved: 0**. Under the
  charter's 5% step gate + 0.25 mass gate the fortk corpus has NO
  exitable warmup: gate-1 drift at the last site (450) is step
  15-110% off the converged eps (recon table above); the closest call
  (logmesq@450, step 0.020 PASS, mass 0.2585 vs 0.25) was proven
  protective (forced exit costs -10..-20% ESS_min).
- X's wall delta is rendezvous sync, not exits: a chain that passes
  gate 1 before its peers reach the boundary waits out the peer
  STARTUP SKEW (~0.2-0.3 s; e.g. rep0 esnc chain2: g1=1 at 150 and
  450, exec1 0.267 s vs 0.0035 s in the hot-start smoke — identical
  drift values, deterministic). Aggregate over 72 chains: rep1
  X/L = 0.998 (all-fail rep: zero measurable overhead); cells with a
  g1-passer pay the skew; ms-scale cells make it visible (0.61-0.73
  on esnc/esc). At real workload scales (seconds+) the skew is noise;
  at campaign scale it is the measured 0.92 vs 1.0.

## VERDICT (for WORKLOG, via parent)

fortk/f27-earlyexit @ 91fe4ce (off fortk/f26-capstone @ 70fd71a;
commits 09ab4eb implementation -> 6d9f211 calibrated lag1 0.35 ->
91fe4ce rendezvous hardening), NOT pushed. deps/stan patches
0001-0003 live (+222/-35) throughout. --wexit: default OFF, requires
--lean, lean path ONLY (stock library loop not instrumented — stated
above); flag absent = byte-identical (gate (c) live A/B vs f26
rebuilt from 70fd71a: esnc/blr/lean md5 all equal; ctest 69/69).

GATES: (c) PASS; (a) PASS — 27/27 cells (phase-1 6 + sentinels 3 x 3
seeds) HELD full warmup with 108/108 chain CSVs md5-identical to arm
L (zero "where exit fires" cells exist; the RNG-discipline design —
gate 1 pure reads, pilots on cloned rng+state — is the reason holds
are bit-identical, and it survived a failed-pilot discipline check);
(d) PASS — sentinels held, rhat < 1.01, and arma11's ONE gate-1 pass
in the corpus was REJECTED by the pilot (single-chain rhat 1.0513);
(b) **FAIL — 0.92x ESS/s geomean vs the 1.2x bar, because ZERO exits
fire anywhere** (72/72 campaign chains + 108 battery chains + recon:
held at all three sites). THE HEADLINE FINDING: the W-22 step-drift
gate (<5% across the last two windows), ported exactly, closes the
warmup-early-exit lever on the fortk corpus — at the last checkable
site (450/1000) the would-freeze eps is still 15-110% off the
converged value (blr 0.53x, pilots 2.08x), and the closest near-miss
(logmesq@450: step 0.020 PASS, mass 0.2585 vs 0.25) was PROVEN
protective: forcing it open costs -10..-20% ESS_min. W-21's 1.3-2.4x
wins lived on walnutpie's own adaptation schedule; on this stack
(with stan's 75/25/50 windowing the big window only STARTS at 450)
the models genuinely need their 1000. Also: the dev-model calibration
(wells) showed the pilot's lag-1 statistic does NOT separate harmful
from equivalent boundaries at 50 draws (inverted gap — threshold 0.35
is the mechanical rule application, stated as weak); the pilot's
cross-chain R-hat is knife-edge on arma11 (1.0079 vs 1.0513 split-
half) — the marginal-class protection in practice came from gate 1.
Positive residue shipped: the exit MACHINERY is complete, default-
off, and validated end-to-end (3-chain all-pass test exits
unanimously at 450, saving 550/1000 warmup iterations with per-chain
frozen state) — the lever opens the moment a model corpus with
genuinely-converged-by-450 adaptation appears. PR addendum: NONE
(the ESS/s headline did not improve; materiality rule not met).

Rules held: <=4 concurrent sampling procs (4-chain cells; batteries
sequential), CPU only, -j2 builds, no upstream, no push, explicit
staging (3 commits, tools/fortk/regions.cpp only), /tmp/review/stanli
never accessed, other worktrees' sources untouched (f26ref binary
built in-place then restored; stanc untouched), WORKLOG/other logs
untouched, raw under bench/fortk_f27/.
