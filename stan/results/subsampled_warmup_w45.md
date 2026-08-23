# W-45 — data-subsampled warmup transplant: NEGATIVE RESULT (REJECT), with the transfer mechanism measured

Date: 2026-08-22/23. Pre-registration: WORKLOG.md W-45 (arms, gates, verdict
rule registered before any build or run). Harness: `harness/w45/`
(`make_subdata.py`, `build_subso.py`, `w45_run.cpp`, `run_w45.py`,
`analyze_w45.py`); raw under `runs/w45/` (local); results JSONs
`results/w45_{fidelity,ess,wall,state,hierblocks}.json`.

**Headline: REJECT — no arm passes the pre-registered quality gate on the
marginal class (hier_2pl/lsat_model/arma11 all fail in ALL FOUR transplant
arms; hier_2pl collapses to bulk-ESS-min 4–97 vs base 625 with up to 5/12
pinned chains). The mechanism is measured and unambiguous: warmup on a
random α fraction of observation rows estimates a DIFFERENT posterior's
geometry, not a noisier estimate of the full posterior's — the transplanted
POSITION sits 1,250–1,900 logp units below the full-data typical set on
hier_2pl (α=0.25/0.1), and the transplanted inv_mass is per-component
mis-scaled by e^1.2–e^3.0 in exactly the data-dominated parameter blocks
(per-person theta, per-item xi2), while the STEP SIZE and min_micro_steps
transfer well. A global step re-tune (V2) cannot repair a per-component
metric mis-scaling and made things worse. The wall savings are real where
the sampler did not collapse (lsat 0.33–0.44x base) but are attached to
failed quality — and on hier_2pl the transplanted sampler needs
1.4–1.9x the gradient calls per sampling phase, eating most of the warmup
saving.**

## 1. Design (as pre-registered)

Run WARMUP against a SUBSAMPLED-DATA .so (same .stan, data JSON with a
deterministic random α fraction of observation ROWS), then SAMPLE with the
full-data .so using the transplanted frozen (inv_mass, step, min_micro_steps)
+ final warmup position. NOT early exit (iterations stay 1000; W-21/W-25/
W-28/W-37 closed that axis four ways) and NOT error loosening (W-38-E2) —
the lever is the DATA the gradient sees during warmup.

Models + subsampling (seed `w45-<model>-<alpha>`, JSONs
`scratch/w45/data/`):

| model | data structure | subsample | unconstrained dims sub vs full |
|---|---|---|---|
| hier_2pl | N=19,200 rows (y, ii, jj); I=32, J=600 | random αN rows; I/J unchanged | 669 = 669 OK |
| blr | N=100 rows (X 100x5, y) | random αN aligned rows | 6 = 6 OK |
| lsat_model | N=1,000 students as pattern counts | student-level subsample; **modified .stan copy** (parameters alpha[T]/theta[N]/beta UNCHANGED; likelihood over M=αN retained students; dropped thetas prior-only) | 1006 = 1006 OK |
| arma11 (control) | T=200 time series | contiguous PREFIX round(αT) (random row drops invalid for a lag model — pre-registered deviation) | 4 = 4 OK |

α ∈ {0.25, 0.1}. Arms: **base** (stan_cli full-data, the reference),
**toolbase** (harness tool in CLI-clone mode + state dump), **v1_aXX**
(pure transplant: frozen state + position, warmup=0), **v2_aXX** (same
shared warmup state + find_reasonable_step re-tune on the full-data model
with the transplanted mass — the library's own `--step-init-heuristic`
code path). All arms: warmup 1000 (on the warmup model), draws 1000 (on
the full-data model), 4 chains as 4 sequential single-chain invocations,
3 reps, seeds 20260819+1000·rep+c, pf inits from inits_w25/ (W-36
assignment), CLI-default configs, full-data .so from bs_models_threads/.

Mechanism note (why a harness tool): stan_cli exports neither the frozen
mass vector (its WALNUTPIE_DEBUG_WARMUP prints only invm[0]) nor accepts
mass injection. `harness/w45/w45_run.cpp` is a standalone consumer of the
walnutpie HEADERS (header-only library; same include set as
build_w36exp's stan_cli compile; the prebuilt exp-tip binary used
read-only for the base arm; no walnutpie edit, no submodule rebuild).
FULL mode replicates stan_cli's single-chain path exactly; SAMPLE mode
constructs `WalnutsSampler` directly from the transplanted state (the
library's own frozen-sampler constructor), seeds the endpoint cache with
one explicit full-data evaluation (W-42 finite-logp guard; never
triggered — all transplanted positions had finite full-data logp).

## 2. Gate 0 — tool fidelity: PASS 48/48

Every toolbase CSV is md5-identical to the stan_cli base CSV (4 models x
3 reps x 4 chains). The transplant mechanism therefore runs on a
bit-exact replica of the reference sampler path; failures below are the
transplant's, not the tool's. (toolbase ESS/R-hat are consequently 1.00x
base everywhere.)

## 3. Gate (a) QUALITY: FAIL on the marginal class — the verdict arm

arviz rank-normalized ESS-min (bulk/tail) + max R-hat, medians of 3 reps;
base band = per-rep extremes of THIS grid's base arm (formula as
W-25/W-28/W-38-E2). Pinned = chains with all draws identical.

| model | arm | bulk-min (x base) | tail-min (x base) | rhat max | pinned/12 | PASS |
|---|---|---|---|---|---|---|
| hier_2pl (base 625 / 708) | v1_a25 | 97 (0.15) | 115 (0.16) | 1.036 | 0 | NO |
| | v2_a25 | 5 (0.01) | 4 (0.01) | 2.886 | 5 | NO |
| | v1_a10 | 4 (0.01) | 4 (0.01) | 3.424 | 5 | NO |
| | v2_a10 | 7 (0.01) | 4 (0.01) | 1.632 | 3 | NO |
| lsat_model (base 730 / 1210) | v1_a25 | 364 (0.50) | 520 (0.43) | 1.017 | 0 | NO |
| | v2_a25 | 97 (0.13) | 38 (0.03) | 1.031 | 0 | NO |
| | v1_a10 | 21 (0.03) | 12 (0.01) | 1.136 | 1 | NO |
| | v2_a10 | 60 (0.08) | 26 (0.02) | 1.042 | 0 | NO |
| arma11 (base 2939 / 2529) | v1_a25 | 2705 (0.92) | 2273 (0.90) | 1.002 | 0 | NO |
| | v2_a25 | 1258 (0.43) | 1172 (0.46) | 1.006 | 0 | NO |
| | v1_a10 | 3904 (1.33) | 1330 (0.53) | 1.003 | 0 | NO |
| | v2_a10 | 2266 (0.77) | 1086 (0.43) | 1.008 | 0 | NO |
| blr (base 510 / 704) | v1_a25 | 455 (0.89) | 729 (1.04) | 1.007 | 0 | **YES** |
| | v2_a25 | 267 (0.52) | 382 (0.54) | 1.012 | 0 | NO |
| | v1_a10 | 5 (0.01) | 4 (0.01) | 2.297 | 4 | NO |
| | v2_a10 | 19 (0.04) | 7 (0.01) | 1.184 | 1 | NO |

Only blr/v1_a25 passes, and only at α=0.25 on a 6-parameter model whose
"dataset" is N=100 (the task's "data-heavy class" label does not fit this
blr instance — its warmup is overhead-dominated, see gate b). The
pre-registered VERDICT RULE ("REJECT if no arm passes (a) on the marginal
class") fires: **REJECT**. The v1_a10 blr failure is the W-43 pin
signature at the transplanted position (4/12 chains zero-movement).

## 4. Gate (b) WALL: savings real where quality failed; inflated sampling cost

Medians of 12 cells, external per-process clock; transplant total =
subsample-warmup process + full-data sampling process (v2 shares v1's
warmup run — attributed per cell). warm share from this grid's base
stanzas: arma11 0.53, lsat 0.52, hier_2pl 0.56, blr 0.69.

| model | arm | total s (= base) | saved (theor) | sampling grad calls vs base |
|---|---|---|---|---|
| hier_2pl (base 44.0s) | v1_a25 | 27.4 (0.62x) | 38% (42%) | 1.36x |
| | v2_a25 | 39.0 (0.89x) | 11% (42%) | 1.94x |
| | v1_a10 | 33.2 (0.76x) | 24% (50%) | 1.90x |
| | v2_a10 | 34.7 (0.79x) | 21% (50%) | 1.78x |
| lsat_model (base 9.5s) | v1_a25 | 3.3 (0.35x) | 65% (39%) | 0.87x |
| | v2_a25 | 4.2 (0.44x) | 56% (39%) | 1.20x |
| | v1_a10 | 3.1 (0.33x) | 67% (47%) | 0.95x |
| | v2_a10 | 4.5 (0.47x) | 52% (47%) | 1.51x |
| arma11 (base 0.1s) | v1_a25 | 0.78x | 22% (40%) | 1.96x |
| | v1_a10 | 1.13x | -13% (48%) | 3.20x |
| blr (base 0.2s) | v1_a25 | 0.42x | 58% (52%) | 1.46x |
| | v2_a10 | 0.55x | 45% (62%) | 0.65x (pinned) |

Readings:

- The subsample warmup itself delivers ~α pricing AND slightly FEWER
  gradient calls (hier a25 17.6k vs base 20.5k; the flatter subsample
  posterior needs shallower ladders) — the warmup phase is not the
  problem.
- The transplanted SAMPLER pays 1.2–1.9x base gradient calls per sampling
  phase on hier_2pl/arma11 (wrong metric -> deeper halving ladders), which
  consumes most of the warmup saving exactly on the model the hypothesis
  targeted (hier v1_a25 gross saving 38% net of a 1.36x costlier sampling
  phase; at α=0.1 only 24%).
- blr's v2 "90% saved" cells are PINNED chains (0.65x calls = no
  movement) — fast garbage; excluded from any win claim.
- Control arma11: as pre-registered, no reliable win (warmup is not
  data-dominated; ratios at 0.1s scale are process-startup noise).

## 5. Gate (c) STATE TRANSFER — why it fails (the mechanism evidence)

Transplanted frozen state vs toolbase's full-data adapted state, medians
of 12 cells (per-cell tables in `results/w45_state.json`):

| model/α | step log-ratio (med) | inv_mass l2 rel | inv_mass med \|log-ratio\| | min_micro base→sub |
|---|---|---|---|---|
| hier_2pl a25 | +0.07 | 2.15 | 1.18 | 1→1 |
| hier_2pl a10 | +0.03 | 4.01 | 1.70 | 1→1 |
| lsat_model a25 | +0.03 | 0.36 | 0.34 (retained 0.07 / prior-only 0.35) | 1→1 |
| lsat_model a10 | +0.03 | 0.40 | 0.35 (retained 0.19 / prior-only 0.35) | 1→1 |
| arma11 a25 | -0.03 | 2.72 | 1.40 | 1→1 |
| arma11 a10 | -0.13 | 9.13 | 2.74 | 1→1 |
| blr a25 | +0.26 | 3.61 | 1.00 | 1→1 |
| blr a10 | +0.24 | 16.36 | 1.29 | 1→1 |

hier_2pl per-block split (median |log inv_mass ratio|; the smoking gun):

| α | theta (600 persons) | xi1 (32 items) | xi2 (32 items) | mu | tau | L_Omega |
|---|---|---|---|---|---|---|
| 0.25 | **1.19** | 1.05 | **1.49** | 0.39 | 0.51 | 0.33 |
| 0.10 | **1.70** | 1.05 | **3.01** | 0.94 | 1.07 | 0.53 |

Position transfer (full-data logp at the transplanted position minus at
base's final warmup position, median over 12 cells): hier_2pl −1,247
(a25) / −1,896 (a10); lsat_model −272 / −448.

Mechanism, stated plainly:

1. **The step size and min_micro_steps DO transfer** (median log-ratios
   0.03–0.26; min_micro 1→1 everywhere). The pre-registered worry that
   the step is the fragile piece was wrong — and consistent with that,
   V2's step re-tune does not rescue anything (retuned-step log-ratio vs
   base scatters −0.72..+0.82 across models — the heuristic, run at a
   bad position with the wrong mass, is no closer to base than the
   transplanted step; on hier/lsat v2 is WORSE than v1).
2. **The inv_mass does NOT transfer, per-component, in the data-dominated
   blocks.** walnutpie's mass is sqrt(var_draw/var_score) per dimension:
   each per-person theta_j carries α·I rows instead of I, each per-item
   parameter α·J instead of J — the subsample warmup correctly estimates
   a posterior that is ~1/α WIDER in those dimensions (theta med
   |log-ratio| 1.70 at α=0.1 ≈ log 5.5, between the pure-data log(10)
   and the prior-dominated limit; population blocks mu/tau/L stay
   closest, 0.33–1.07). This is the pre-registered risk (a) confirmed as
   the DOMINANT effect, not a minority-component nuisance: on hier_2pl
   632 of 669 components are per-person/per-item.
3. **The position does not transfer either**: the subsample typical set
   is ~1.2–1.9k logp below the full-data one on hier_2pl. With warmup=0
   the frozen sampler starts in a deep, metric-mismatched valley — hence
   pins (hier v1_a10: 5/12 chains never move) and R-hat 3.4.
4. lsat_model is the cleanest controlled demonstration: the modified
   subsample .stan keeps retained thetas on the likelihood and drops the
   rest to prior-only — and the retained components' mass transfers at
   |log-ratio| 0.07–0.19 while the prior-only ones sit at 0.35, exactly
   the constructed split. Per-component information content, not noise,
   is what the mass carries.

The hypothesis's optimistic premise ("mass on αN rows is a noisier but
near-sufficient estimate of the same curvature") is refuted: for iid-row
models the TOTAL information is α-scaled, but the MASS MATRIX and the
typical-set POSITION are per-component quantities that scale with each
component's retained-row count. Naive subsample-warmup = warmup toward a
different target. (This is why the subsampling-MCMC literature uses
importance-weighted/pseudo-marginal corrections rather than transplanting
adaptation state.)

## 6. Verdict + what would be worth proposing

**REJECT the pure transplant (V1) and the step-retune transplant (V2) as
implemented.** All quality gates fail on the marginal class; the wall
wins are inseparable from quality collapse or (blr v2) pinned chains.

Is a LIBRARY-LEVEL in-warmup .so swap worth proposing? **Not in this
form.** The failure is statistical (wrong target geometry), not I/O —
a library swap removes only the second process start (~0.1–0.3s), which
is not the binding constraint. The measured transfer table does motivate
a different, schedule-level follow-up (new pre-registration required,
e.g. W-46 "V3"): subsample-data warmup for the EARLY exploration phase +
a TRUNCATED full-data warmup phase (K iters) that re-estimates mass/step
from the transplanted position — the mechanism data predict the full-data
phase must be long enough for the OnlineMoments discount schedule to
forget the imported state, and the win shrinks to (1−α)·(warmup_share −
K/1000) minus the measured 1.2–1.9x sampling-phase inflation risk. Given
warmup share ≈ 0.52–0.56 and the observed re-adaptation need, the
plausible ceiling is modest; the honest summary is that the
data-subsampled axis, like the four early-exit gates before it, does not
give a free warmup reduction on this model class.

## 7. Reproduction

```
# subsample data + .so (serialized; env -u LD_LIBRARY_PATH; /usr/bin/make -j2)
env -u LD_LIBRARY_PATH .venv/bin/python harness/w45/make_subdata.py
env -u LD_LIBRARY_PATH .venv/bin/python harness/w45/build_subso.py
# tool (walnutpie headers read-only; same includes as build_w36exp stan_cli)
env -u LD_LIBRARY_PATH /usr/sbin/c++ -O3 -w \
  -I external/walnutpie/include \
  -I external/walnutpie/build_w36exp/_deps/eigen-src \
  -isystem external/walnutpie/thirdparty/bridgestan \
  -std=c++20 -o scratch/w45/bin/w45_run harness/w45/w45_run.cpp
# grid + analysis
env -u LD_LIBRARY_PATH .venv/bin/python harness/w45/run_w45.py
env -u LD_LIBRARY_PATH .venv/bin/python harness/w45/analyze_w45.py
```

Raw: `runs/w45/{base,toolbase,v1_a25,v1_a10,v2_a25,v2_a10}/<model>/rep<r>/`,
frozen states `runs/w45/state/{base,a25,a10}/...`. Base arm binary:
external/walnutpie/build_w36exp/examples/stan_cli (read-only, @43b6435).
