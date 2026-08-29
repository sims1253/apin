# W-63: low-rank Alg-1 ESS campaign — results (pre-registered close-out)

Date: 2026-08-25. Base: exp/lr-alg1-basis @ d0ca4a7 build_gates stan_cli
(W-62-gated, default-path bit-identical), single-chain binary, 4 sequential
chain processes per cell, seed = 20260819 + 1000*rep + c, --metric-window 50,
1000 warmup + 1000 draws, 3 reps, pf inits. Pre-registration: WORKLOG "W-63
PRE-REGISTRATION ... low-rank Alg-1 ESS campaign" + campaign diary; step-0
threshold record scratch/w63/step0_threshold.md (threshold = 0.5 fallback,
recorded pre-grid). Arms: A0 = no rank flags; A1 = --metric-rank 10
--metric-basis 4; A2 = A1 + --metric-full; A3 = A2 + --metric-auto 0.5.

> **Record status:** sections 1-5 below are the INTERIM analysis, computed at
> 934/1020 (86 aborted cells missing); they stand unchanged as the interim
> record. Section 6 is the FINAL analysis after the W-64 guard rerun
> completed all 1020/1020. No interim verdict flips; the final numbers
> supersede §1's census and all †/‡ (not-adjudicated) marks.

Analysis: scratch/w63/analyze_lowrank.py -> scratch/w63/lowrank_results.json
(+ analyze_lowrank.out). `posterior` is not installed in this venv, so ESS /
rhat use the self-contained Vehtari-2021 implementation reused from
scratch/w61/runs_w63/analyze_w63.py (rank-normalized Geyer initial-monotone
bulk ESS on the COMBINED 4-chain draws; re-validated here on iid: ESS 4033 /
4000, rhat 1.0008, and AR(1) phi=0.9: ESS 253 vs theory 210). rhat is
rank-normalized split-R-hat (posterior::rhat convention). Per-parameter;
columns exactly constant on the pooled draws are excluded explicitly (W-54
L_Omega.1.1 NaN lesson): excluded 4/rep on hier_2pl (Omega diagonals), 30/rep
on dogs, 466/rep on kronecker_gp. Model score = min-over-params bulk ESS;
cell score = median over reps; grads/wall = sum over the 4 chain logs of both
stanzas ("logp_grad calls", "total time"). Chains trimmed to min length
within a rep (no raggedness observed at s1000/s500 fixed budgets).

## Headline verdict

**ALL EFFICACY AND SAFETY GATES FAIL; the campaign is a decisive negative
result, recorded and kept per protocol.** (i) The A3 screen NEVER ENGAGED
anywhere: all 252 completed main-grid A2 csvs and all 48 pin-battery A2 csvs
are md5-BYTE-IDENTICAL to their A3 twins — A3 ≡ A2 exactly, so every A3
number below is the unscreened exact low-rank operator. (ii) G2 efficacy
geomean A3/A0 ESS_min/grad = 0.037 vs bar 1.5 (a ~41x miss; ESS/s geomean
0.028). (iii) G3 no-harm violated by 5 adjudicable models (worst 0.029x) plus
2 degraded. (iv) G4: rank arms INTRODUCE pins at blr w400-pf (A0 1/12 vs A2/A3
6/12, A1 12/12). (v) G5 full-vs-fold geomean 1.35 (vs ~1.2 expected) is the
only number near expectation, but 3 of its 4 models are quality-collapsed, so
it is uninformative. Mechanism read: a rank-10/basis-4 correction destroys
mixing exactly on the high-dimensional correlated-structure models it was
meant to help (lsat 1012 params, hier_2pl 804, radon_pp 775, kronecker 5463,
bym2 9610), while small/well-separated models are neutral-to-up (wells 2,
garch 4, logmesquite 7, low_dim_gauss_mix 5, dogs 752).

## 1. Fail census (driver FINAL: 934/1020 done, 86 failed-not-done)

Disk state re-verified with the driver's own done criterion (csv + "total
time" in log): 934/1020 chain-runs done. All 86 failures are rc=-6 aborts,
the known `macro_time must be in (0, inf)` NaN-adapter-feed class (W-36/
W-59/W-64 lineage); none are new signatures. Dedupe note: naive attempt2-FAIL
grep double-counts job9 (pre-grid shakedown of A2/bym2 rep0_c0, re-run as
job276); disk census is authoritative.

**Correction to the diary's expectation**: "the A0 arm never aborts" is
FALSE at chain-run granularity — A0 lost 3/588 runs (0.5%), all rc=-6:
kronecker_gp rep0_c0 (the known dead-init cell, LKJ diag=0), accel_gp rep1_c1,
lotka_volterra rep1_c0. Crucially these SAME seed/init cells also abort under
A2/A3, i.e. a seed/init-driven base class, not rank-driven; and no A0 CELL
was lost (every A0 cell >= 11/12 chains; all 49 A0 cells scored).

Failed chain-runs by arm x model x cell-type (main grid w1000_pf unless
noted; aborting chains in parentheses where informative):

| arm | model | n/12 failed | which |
|---|---|---|---|
| A0 | accel_gp | 1 | r1c1 |
| A0 | kronecker_gp | 1 | r0c0 (dead-init) |
| A0 | lotka_volterra | 1 | r1c0 |
| A1 | bym2_offset_only | 5 | r0{c0,c1,c3}, r2{c1,c2} |
| A1 | kronecker_gp | 4 | r0c0, r1{c2,c3}, r2c1 |
| A2 | accel_gp | 5 | r0{c0,c1}, r1{c1,c2}, r2c2 |
| A2 | arma11 | 12 | ALL (cell lost) |
| A2 | blr | 1 | r0c2 |
| A2 | bym2_offset_only | 6 | r0{all}, r2{c0,c2} |
| A2 | kronecker_gp | 5 | r0{c0,c2,c3}, r1c3, r2c3 |
| A2 | lotka_volterra | 1 | r1c0 (same as A0) |
| A2 | pilots | 2 | r1c0, r2c3 |
| A2 | radon_pp_noncentered | 3 | r0c2, r1c2, r2c1 |
| A2 | blr w100_pf (battery) | 1 | r0c2 |
| A2 | blr w400_pf (battery) | 1 | r0c2 |
| A3 | (identical to A2 in every entry) | 37 | same seeds |

Arm totals: A0 3/588 (0.5%), A1 9/72 (12.5%), A2 37/180 (20.6%), A3 37/180
(20.6%). A2 and A3 abort on EXACTLY the same chain-runs (consistent with
A3 ≡ A2). blr r0c2 is pf-init-driven (def battery cells unaffected).

**Adjudicability rule (applied to all gates, documented post-hoc but
mechanical):** a model x arm is gate-adjudicable iff all 12 chain-runs
completed. Cells missing only 1-2 chains are scored on their full 4-chain
reps and reported as DEGRADED (dagger); cells with no full rep are
NOT-ADJUDICATED (their computed all-partial scores are still shown). Not
adjudicated anywhere: bym2 (A1 7/12, A2 6/12, A3 6/12 + A0 itself degenerate,
see Honest Limits), kronecker_gp (A1 8/12, A2 7/12, A3 7/12, A0 11/12),
arma11 (A2/A3 0/12; A0 fine), accel_gp (A0 11/12, A2/A3 7/12).

## 2. Main grid: per model x arm (w1000_pf)

ESS_min = median-of-reps min-over-params bulk ESS; e/g = ESS_min per
logp_grad call; e/s = ESS_min per wall-second (2-worker shared machine —
wall noise, see Honest Limits 6); rhat>1.02 = median count over reps.
† = degraded (scored on full 4-chain reps only, 1-2 chains missing),
‡ = no full rep (all-partial score, not gate-adjudicable). npar = csv columns.

Cross-structure subset (A1 = fold, A2 = full, A3 = screened full):

| model (npar) | arm | ESS_min | e/g | e/s | rhat>1.02 |
|---|---|---:|---:|---:|---:|
| hier_2pl (804) | A0 | 493.4 | 0.003094 | 1.900 | 0 |
| | A1 | 115.7 | 0.000538 | 0.555 | 14 |
| | A2 | 196.1 | 0.000282 | 0.274 | 6 |
| | A3 | 196.1 | 0.000282 | 0.281 | 6 |
| radon_var_int_slope (345) | A0 | 267.0 | 0.001769 | 30.106 | 0 |
| | A1 | 3.3 | 0.000008 | 0.162 | 341 |
| | A2 | 7.7 | 0.000026 | 0.435 | 328 |
| | A3 | 7.7 | 0.000026 | 0.175 | 328 |
| lsat_model (1012) | A0 | 940.8 | 0.005830 | 27.277 | 0 |
| | A1 | 9.4 | 0.000045 | 0.242 | 814 |
| | A2 | 5.9 | 0.000018 | 0.086 | 747 |
| | A3 | 5.9 | 0.000018 | 0.042 | 747 |
| garch11 (4) | A0 | 747.1 | 0.008251 | 304.753 | 0 |
| | A1 | 110.6 | 0.000721 | 29.756 | 2 |
| | A2 | 378.6 | 0.003734 | 123.183 | 0 |
| | A3 | 378.6 | 0.003734 | 139.375 | 0 |
| bym2 (9610) | A0 | 2.3 | 0.000009 | 0.039 | 9598 (rhat_max 3.6e15) |
| | A1 ‡ | 2.0 | 0.000008 | 0.039 | 9610 |
| | A2 † | 2.0 | 0.000008 | 0.036 | 9610 |
| | A3 † | 2.0 | 0.000008 | 0.028 | 9610 |
| kronecker_gp (5463) | A0 † | 29.0 | 0.000191 | 0.366 | 1973 |
| | A1 ‡ | 1.8 | 0.000010 | 0.021 | 3718 |
| | A2 ‡ | 2.3 | 0.000012 | 0.023 | 2878 |
| | A3 ‡ | 2.3 | 0.000012 | 0.021 | 2878 |

No-harm subset (A0/A2/A3):

| model (npar) | A0 ESS_min / e/g / e/s / rhat02 | A2 (=A3 draws) | A3 e/s | A3 rhat02 | note |
|---|---|---|---|---|---|
| eight_schools_nc (18) | 1470.2 / 0.020032 / 16788.7 / 0 | 587.9 / 0.007039 | 2652.5 | 0 | |
| blr (6) | 346.6 / 0.001600 / 494.1 / 0 | 4.7 / 0.000025 | 2.308 | 6 | A2/A3 † (r0c2 abort) |
| kidscore_momiq (3) | 283.4 / 0.002614 / 385.5 / 1 | 262.7 / 0.002254 | 283.5 | 0 | |
| logmesquite (7) | 102.4 / 0.000711 / 267.2 / 4 | 176.8 / 0.001463 | 476.9 | 1 | |
| wells_dist100 (2) | 749.2 / 0.012637 / 211.7 / 0 | 1178.7 / 0.013495 | 241.4 | 0 | |
| diamonds (27) | 2.5 / 0.000009 / 0.175 / 17 | 2.3 / 0.000010 | 0.203 | 26 | A0 itself rhat 3.49 |
| radon_pp_nc (775) | 216.7 / 0.001375 / 3.166 / 1 | 2.1 / 0.000013 | 0.026 | 652 | A2/A3 ‡ |
| dogs_hierarchical (752) | 1592.1 / 0.032944 / 588.4 / 0 | 1713.3 / 0.032687 | 471.3 | 0 | |
| pilots (58) | 2.3 / 0.000007 / 4.444 / 16 | 3.0 / 0.000013 | 1.926 | 16 | † both arms; A0 rhat 3.06 |
| gp_regr (3) | 2261.6 / 0.041894 / 6892.4 / 0 | 1914.5 / 0.034444 | 4016.8 | 0 | |
| eight_schools_c (10) | 103.5 / 0.000711 / 983.6 / 1 | 3.8 / 0.000020 | 9.967 | 10 | funnel class |
| lotka_volterra (90) | 49.4 / 0.000352 / 4.454 / 45 | 66.6 / 0.000260 | 0.957 | 49 | † both arms |
| low_dim_gauss_mix (5) | 778.6 / 0.008371 / 41.137 / 0 | 2626.6 / 0.022983 | 139.8 | 0 | |
| accel_gp (72) | 2.2 / 0.000008 / 0.556 / 68 | 1.2 / 0.000008 | 0.287 | 58 | ‡ both arms; A0 rhat 3.50 |
| arma11 (4) | 1022.3 / 0.016701 / 2002.5 / 0 | — | — | — | A2/A3 0/12, not run |

## 3. Gate adjudication

**G1 canary (default-path bit-identity): CITED** — W-62 increment-1 gate (i);
no new binary introduced this campaign.

**G2 efficacy — FAIL (catastrophic).** Geomean over adjudicable
cross-structure models of A3/A0 ESS_min/grad (rep medians):
hier_2pl 0.0913, radon_var_int_slope 0.0147, lsat_model 0.0030, garch11
0.4525 → **geomean 0.0368** vs bar >= 1.5 (paper ceiling 4x). By ESS/s the
geomean is 0.0278. Sensitivity: including degraded bym2 (0.878) and
kronecker (0.062) gives 0.0680 — still a ~22x miss. bym2 and kronecker_gp
are NOT adjudicated (aborted rank arms; bym2's A0 baseline is itself
degenerate — see Honest Limits 2). lsat_model is the single worst cell:
A0 min-ESS 940.8 with 0 params rhat>1.02 vs A3 5.9 with 747/1012.

**G3 no-harm — FAIL.** Adjudicable violators (rule: A3/A0 e/g >= 0.9 AND
rhat>1.02 count <= A0's): eight_schools_centered 0.029x (rhat 10 > 1),
eight_schools_noncentered 0.351x, gp_regr 0.822x, kidscore_momiq 0.862x,
diamonds 1.06x but rhat 26 > 17 (both arms broken — A0 rhat_max 3.49 —
garbage-vs-garbage). Degraded violators (computed, excluded from the formal
count): blr 0.015x (rhat 6 > 0), lotka_volterra 0.739x (rhat 49 > 45). Not
adjudicated but reported: radon_pp 0.0097x with rhat 652 vs 1 (plainly
harmful; every rep lost exactly one chain), accel_gp 0.979x (rhat 58 < 68;
both arms collapsed), arma11 — A3 cell entirely aborted (a completion
regression vs A0 12/12 even though unmeasurable for ESS). Adjudicable PASS:
low_dim_gauss_mix 2.75x, logmesquite 2.06x, wells 1.068x, dogs 0.992x;
degraded PASS: pilots 1.94x (rhat 16 = 16; both arms garbage-quality).
Aggregate over the 9 adjudicable no-harm models: geomean 0.708x. The W-9
forced-rank precedent anticipated 0.66-0.79x aggregates; the observed
per-model collapses (0.003-0.06x on the correlated-structure class) are an
order of magnitude worse than that band, and the screen (the pre-registered
mitigation) never fired.

**G4 pin battery — the pre-registered 0/12 bar is VACUOUS-for-comparison
(A0 pins on this base), and the fallback claim "no pins introduced by
rank-on arms" FAILS.** Pinned chains /12 per arm x warmup x init (pin =
all 500 sampling rows identical, the W-43 stuck-at-init/zero-ESS criterion;
pinned chains burn 32 evals/draw, the W-43 31-eval signature; A0's escaped
w400-pf chains settle at 21.3 evals/draw median):

| arm | w100_pf | w100_def | w400_pf | w400_def |
|---|---:|---:|---:|---:|
| A0 (base) | 8/12 | 12/12 | 1/12 | 12/12 |
| A1 | 11/12 | 12/12 | 12/12 | 12/12 |
| A2 | 10/12 | 12/12 | 6/12 | 12/12 |
| A3 | 10/12 | 12/12 | 6/12 | 12/12 |

As pre-registered, this dev/init-robustness base (no W-43 step-init
heuristic, exp-stack fix not ported) pins under A0 (w100-pf 8/12, both def
cells 12/12), so "0/12" cannot adjudicate elimination. But the honest
directional claim also fails: at w400-pf, where A0 escapes almost
everywhere (1/12 pinned, 445 unique rows median, up to 487/500), the rank
arms RE-PIN 6/12 (A2/A3; identical sets r0c0,r1c0,r1c1,r1c2,r2c0,r2c2) and
12/12 (A1). At w100-pf rank arms add +2 (A2/A3) to +3 (A1) pins over A0's
8. A2/A3 battery csvs are byte-identical (48/48). blr r0c2 (pf init) aborts
under A2/A3 at w400/w1000 but completes (pinned or escaped) under A0 — the
same init file drives both the battery abort and the grid blr degradation.
Escape behavior where visible: A0 w400-pf escaped chains mix normally
(445-487 unique rows); no partial-escape cells appear under rank arms
(w400-pf A2/A3 is bimodal: 6 fully pinned, 5 fully escaped).

**G5 full-vs-fold — geomean near expectation, verdict UNINFORMATIVE.**
Adjudicable A2/A1 e/g ratios: hier_2pl 0.525, radon_var 3.10, lsat 0.389,
garch11 5.18 → geomean 1.345 vs the ~1.2x W-9 expectation. But the spread
(0.39-5.18) is far wider than the precedent's tight band, and on 3 of 4
models both operators sit on collapsed chains (hier_2pl A2 196 vs A0 493;
radon 7.7 vs 267; lsat 5.9 vs 941), so the ratio measures which way a
broken chain broke, not an operator-quality difference. Recorded as
expectation-met-on-geomean-only.

## 4. Top wins / losses (A3/A0 ESS_min/grad; A3 ≡ A2)

Wins: low_dim_gauss_mix 2.75x (778.6 -> 2626.6 ESS_min), logmesquite 2.06x
(102.4 -> 176.8), pilots 1.94x (2.3 -> 3.0; both arms garbage-quality —
not a meaningful win); next: wells 1.068x, diamonds 1.06x.
Losses: lsat_model 0.0030x (940.8 -> 5.9; 747 params rhat>1.02),
radon_pp_noncentered 0.0097x (216.7 -> 2.1; not-adjudicated-degraded),
radon_var_int_slope 0.0147x (267.0 -> 7.7); then blr 0.0154x, eight_schools_
centered 0.0285x, kronecker 0.062x, hier_2pl 0.091x. Aggregate over all 20
models with both arms: 0.250x.

## 5. Honest limits

1. **The screen never engaged — anywhere.** Step-0 was vacuous (bym2 pinned
   under all arms at w400), the 0.5 fallback was recorded pre-grid, and the
   grid itself shows 252/252 main-grid + 48/48 battery A2≡A3 md5 identity.
   G2/G3 therefore measure the UNSCREENED exact operator; whether a lower
   threshold would have engaged (and helped) on any model is untested —
   step-0's 0.3 also did not engage on its two probe models.
2. **bym2 double-compromise, now triple**: pins at w400 under every arm
   (step-0), rank arms abort at w1000, AND its A0 w1000 "completions" are
   degenerate (rhat_max 3.6e15 on beta0, 9598/9610 params rhat>1.02) — there
   is no usable bym2 baseline at any arm on this base.
3. **The 86 aborted cells are unmeasured, not measured-and-bad.** All are
   the known macro_time NaN-feed class; the queued fix (cherry-pick
   rob/nan-alpha-guard onto exp/lr-alg1-basis, re-run the W-62 bit-identity
   canary, rerun only aborted cells) was deliberately NOT done inside this
   analysis (no mid-campaign code change; no post-hoc scope creep). arma11
   A2/A3 and parts of bym2/kronecker/accel/radon_pp/pilots/blr could in
   principle recover; the completed-and-collapsed cells (lsat, radon_var,
   blr, eight_schools_c, ...) cannot — their failure is draw-quality, not
   abort-class.
4. **Base/protocol differences**: single-chain binary run as 4 sequential
   processes (vs the exp stack's in-process multi-chain); this base predates
   the NaN guard and the W-43 heuristic; def-init battery cells are the
   known drift-limited class (W-43 gate (b)) and only inform G4 pin counts.
5. **Degraded cells**: scored on full 4-chain reps only (see rule, §1);
   medians over 1-2 reps where marked †/‡ — blr, lotka, pilots, radon_pp,
   accel, kronecker carry reduced replication.
6. **Wall-time (e/s) noise**: the grid ran 2 workers on a shared machine;
   A2 vs A3 wall differs by up to 2x (lsat 68.7s vs 141.4s) DESPITE
   bit-identical draws and grads — e/s between arms is load noise at this
   granularity; e/g is the reliable comparator. Machine load also explains
   why per-call cost varies across the night.
7. **Broken baselines**: diamonds, pilots, bym2, kronecker A0 baselines are
   themselves unhealthy (A0 rhat_max 3.06-3.6e15); ratios and "wins" there
   are garbage-vs-garbage and were not used as evidence of rank-arm benefit.
8. Constant columns excluded per the W-54 NaN lesson (466/rep kronecker,
   30/rep dogs, 4/rep hier_2pl — LKJ-Cholesky diagonals pinned at 1 by
   construction); they are excluded from min-ESS and rhat counts alike.

## Verdict

Per pre-registration ("negative results recorded and kept, same as wins"):
**low-rank Alg-1 at rank 10 / basis 4 with --metric-full is REJECTED at
CORE_SET scale on this base.** G2 fails by ~41x in the wrong direction, G3
fails on 5 adjudicable + 2 degraded models with the funnel class hit exactly
as W-9 warned, G4 shows the rank machinery re-pins short-warmup chains that
the base escapes, and the A3 screen engaged zero times in 300 opportunities.
Next decision (queued, one item, not batched): the NaN-guard cherry-pick +
aborted-cell rerun is only worth doing if a future arm design changes the
operator; the completed-cell evidence against rank-10/basis-4 stands on its
own.

## Artifacts (interim)

scratch/w63/{driver.log, driver.py, manifest.csv, THRESHOLD, step0/,
step0_threshold.md, runs/ (9.5 GB at interim; 13 GB final), analyze_lowrank.py,
lowrank_results.json (overwritten by the final rerun), analyze_lowrank.out
(likewise)}; results/lowrank_ess_w63.md (this file); WORKLOG.md close-out
entry. Interim JSON/out contents are preserved as the numbers printed in
sections 1-5 above.

## 6. FINAL (post-guard-rerun, 2026-08-25)

Recompute after the W-64 guard rerun (same script
scratch/w63/analyze_lowrank.py, single process):
`CENSUS: 1020/1020 chain-runs done`, grid_missing = 0, pin_missing = 0,
driver FINAL `done=1020/1020 ... failed-not-done=0` (P1 192/192, P2 216/216,
P3 540/540, P4 72/72). EVERY model x arm cell now has 12/12 chains and 3
full reps ("3F+0P" everywhere) — the §1 adjudicability rule is moot: all
cells are adjudicable, all †/‡ marks below are superseded.

**Mixed-binary soundness (why folding guard-era cells into a pre-guard grid
is valid).** The 934 pre-guard chain-runs and the 86 guard-era reruns come
from two binaries that the W-64 canary proved byte-identical on finite paths
(both md5s reproduce W-62 exactly). The guard (commit 6ba0798,
"Guard step adapter against NaN acceptance statistics") only alters behavior
when acceptance statistics go non-finite, so: (a) the 934 finite-path cells
are bit-exactly what the guarded binary would have produced — mixing them in
is not an approximation at all; (b) for the 86 cells the guard-era adaptation
(survive-and-clamp on NaN feeds) does differ from what an UNGUARDED run
would have done — but no unguarded abort-free counterpart exists for any of
them: pre-guard, every one aborted rc=-6. The final grid therefore measures
"arms + guard" semantics for exactly those 86 cells, and this is the only
completions that exist for them. Three of the 86 are A0 cells (kronecker
r0c0, accel r1c1, lotka r1c0), so those A0 baselines are also guard-era.

**The screen STILL never engaged: A3 ≡ A2 on all 300 csv pairs (252 main
grid + 48 battery), including all 37 guard-rescued A3 twins.** md5-identical
across the board; the guard-era A2/A3 pairs even log IDENTICAL per-chain
guard-trigger counts. --metric-auto 0.5 engaged 0/300 opportunities even on
chains throwing 10^4-10^5 NaN feeds — final, and stronger than the interim
claim (the screen is inert on Alg-1 spectra even in NaN-storm conditions).

### 6.1 Guard-trigger accounting (the 86 rerun cells)

"Error in logp_grad" lines per cell (guard catch-and-continue events),
split warmup-phase vs sampling-phase (first "total time" stanza boundary):

| cell | warmup | sampling | reading |
|---|---:|---:|---|
| A2/A3 arma11 (12 ch each) | 121,113 | **0** | NaN storm confined to warmup; sampling clean |
| A2/A3 pilots | 11,854 | 0 | warmup-only |
| A2/A3 radon_pp | 11,971 | 4,175 | mostly warmup; sampling still collapses |
| A2/A3, A1 bym2 | 4,657 / 8,255 | 15,634 / 6,791 | zombie sampling: NaN feeds DURING draws |
| A2/A3 kronecker (+A0 r0c0, A1) | ~32,000 | ~32,000 | NaN on essentially every eval, both phases (dead-init) |
| A0/A2/A3 lotka r1c0 | 31,674 | 31,665-8 | zombie both phases |
| A2/A3 blr r0c2 (w1000 / w400 / w100) | 11,298 / 4,698 / 1,314 | 22,000 / 11,000 / 12,241 | zombie sampling at all warmups |
| A0 kronecker r0c0 / lotka r1c0 / accel r1c1 | 32,001 / 31,674 / 248 | 32,000 / 31,665 / 0 | two of three A0 rescues are zombies |
| **total (86 cells)** | **586,097** | **359,962** | 946,059 events |

Mechanism: the guard converts aborts into completions, but completion is not
quality. Cells whose NaN feeding persists into SAMPLING (bym2, kronecker,
lotka, blr r0c2) are zombie chains — they log a failed gradient roughly every
other leapfrog step while emitting draws; their rhats are 1e0-1e15-scale
garbage. Cells whose storm is warmup-transient (arma11, pilots, accel,
mostly radon_pp) sample cleanly afterwards. This split predicts every
recovered cell's draw quality below.

### 6.2 Recovered cells — final numbers (changes vs interim in brackets)

| model (d) | arm | ESS_min | e/g | rhat>1.02 | rhat_max | final vs interim |
|---|---|---:|---:|---:|---:|---|
| arma11 (4) | A0 | 1022.3 | 1.67e-2 | 0 | 1.003 | unchanged |
| | A2/A3 | **2541.0** | **2.45e-2** | **0** | **1.001** | was 0/12 not run; now 12/12, healthy |
| bym2 (9610) | A0 | 2.3 | 8.9e-6 | 9598 | 3.6e15 | unchanged (degenerate baseline) |
| | A1 | 2.0 | 2.6e-6 | 9610 | 3.6e15 | was ‡ 7/12; now 3F — still degenerate |
| | A2/A3 | 2.0 | 7.3e-6 | 9610 | 3.6e15 | was † 6/12; now 3F — still degenerate |
| kronecker (5463) | A0 | **8.1** | 5.3e-5 | 1992 | 1.75 | was † 29.0 — dropped: rescued dead-init r0c0 is a zombie |
| | A1 | 2.3 | 8.8e-6 | 3771 | 3.66 | was ‡ 1.8; now 3F — collapsed |
| | A2/A3 | 2.5 | 9.1e-6 | 4378 | 3.55 | was ‡ 2.3; now 3F — collapsed |
| radon_pp (775) | A0 | 216.7 | 1.37e-3 | 1 | 1.03 | unchanged |
| | A2/A3 | 2.8 | 1.20e-5 | 762 | 2.38 | was ‡ 2.1; now 3F — catastrophic confirmed |
| accel_gp (72) | A0 | 2.3 | 7.5e-6 | 69 | 3.50 | was ‡ 2.2 (2 reps) |
| | A2/A3 | 2.2 | 8.1e-6 | 66 | 4.10 | was ‡ 1.2; both arms collapsed |
| pilots (58) | A0 | 2.3 | 6.8e-6 | 16 | 3.06 | unchanged |
| | A2/A3 | 2.3 | 1.2e-5 | 16 | 3.38 | was † 3.0 — both arms garbage |
| lotka (90) | A0 | **10.3** | 6.4e-5 | 78 | 1.63 | was † 49.4 — dropped: rescued r1c0 is a zombie |
| | A2/A3 | 3.3 | 1.4e-5 | 87 | 1.95 | was † 66.6 — now garbage-vs-garbage |
| blr (6) | A0 | 346.6 | 1.60e-3 | 0 | 1.02 | unchanged |
| | A2/A3 | 6.4 | 3.5e-5 | 6 | 2.00 | was † 4.7 (2F); now 3F incl. zombie r0c2 |

Headline recoveries:

- **arma11 is a GENUINE WIN and the interim completion regression is
  RESOLVED**: A2/A3 now complete 12/12, survive a 121,113-event NaN storm
  entirely inside warmup (0 sampling-phase events), and then draw CLEANLY —
  ESS_min 2541.0 (per-rep 2428/2541/2928) vs A0 1022.3, rhat_max 1.001,
  0/4 params above 1.02, e/g 1.468x A0 despite burning 1.78x the gradients
  (103,512 vs 58,144 median). A d=4 model: exactly the low-dim-structure
  class that wins everywhere in this campaign.
- **radon_pp is now formally adjudicated: catastrophic** (0.0087x e/g,
  ESS_min 2.8 vs 216.7, 762/775 params rhat>1.02). The interim
  "plainly harmful" note is now a gate-counted violation.
- **bym2 has NO usable baseline at ANY arm, final.** All four arms complete
  (3F each) and all four are degenerate: 9598-9610/9610 params rhat>1.02,
  rhat_max 3.6e15 at every arm; rank arms additionally zombie-sample
  (15,634 sampling-phase NaN feeds for A2). The apparent 0.821x A3/A0 ratio
  is garbage-vs-garbage and is not evidence of anything.
- **kronecker rank arms are confirmed collapsed** (A1 2.3 / A2/A3 2.5 ESS_min;
  3771-4378 of 4997 scored params rhat>1.02) — but the A0 baseline ALSO fell
  to 8.1 once its guard-rescued dead-init chain (NaN on ~every eval of both
  phases) folded in, so kronecker joins the garbage-vs-garbage class; its
  0.173x ratio is an upper bound on harm, not a calibrated number.
- **lotka inverts to garbage-vs-garbage**: the rescued A0 r1c0 chain is a
  zombie, dropping the A0 baseline 49.4 -> 10.3 (rhat>1.02 on 78/90 params);
  A2/A3 sit at 3.3 with 87/90.
- **blr's recovered r0c2 chain is a zombie** (22,000 sampling-phase NaN feeds
  at w1000): blr A2/A3 now have 3 full reps, ESS_min 6.4, 6/6 params
  rhat>1.02 — the interim degraded violator (0.015x) is now an adjudicable
  violator at 0.0217x (the zombie rep actually raised ESS_min 4.7 -> 6.4).
- **Pin battery final**: the recovered r0c2 battery chains are PINNED, so
  A2/A3 w100_pf rises 10/12 -> 11/12 and w400_pf 6/12 -> 7/12 (sets: w400-pf
  A2/A3 = r0c0,r0c2,r1c0,r1c1,r1c2,r2c0,r2c2; A0 w400-pf stays 1/12 at 446
  unique rows / 21.3 evals-per-draw escaped median).

### 6.3 FINAL gate verdicts (complete grid; no interim verdict flips)

- **G1 canary: CITED** (W-62 gate (i); W-64 re-canary byte-identical).
- **G2 efficacy — FAIL (unchanged).** All six cross-structure models now
  adjudicable: hier_2pl 0.0913, radon_var_int_slope 0.0147, lsat_model
  0.0030, garch11 0.4525, bym2 0.8209, kronecker_gp 0.1725 -> geomean
  **0.0798** vs bar >= 1.5 (~19x miss). The interim 4-model geomean 0.0368
  is unchanged (those cells were complete then and now); the two added
  models are garbage-vs-garbage baselines, so 0.0368 remains the honest
  point estimate and 0.0798 the all-adjudicable sensitivity — both fail by
  more than an order of magnitude.
- **G3 no-harm — FAIL (stronger).** 8 adjudicable violators of 15: blr
  0.0217x (rhat 6>0; promoted from degraded), diamonds 1.06x (rhat 26>17;
  garbage-vs-garbage), eight_schools_centered 0.0285x (10>1),
  eight_schools_noncentered 0.3514x, gp_regr 0.8222x, kidscore_momiq 0.8622x,
  lotka_volterra 0.2272x (87>78; garbage-vs-garbage after the A0 zombie fold-
  in), radon_pp 0.0087x (762>1; promoted from not-adjudicated). PASS: arma11
  1.4676x (0=0 — genuine), accel_gp 1.0856x (66<69 but both arms collapsed),
  pilots 1.796x (garbage-vs-garbage), dogs 0.9922x, logmesquite 2.0565x,
  low_dim_gauss_mix 2.7455x, wells 1.0679x. Aggregate geomean over the 15
  adjudicable: **0.446** (interim 0.708 over 9 — the aggregate fell because
  the three recovered collapses entered; the W-9 0.66-0.79 band is now
  BELOW the observed aggregate harm). All-21-model A3/A0 aggregate: 0.273
  (interim 0.250 over 20).
- **G4 pin battery — FAIL (unchanged direction, +1 pin each).** w400-pf:
  A0 1/12 vs A1 12/12, A2/A3 7/12 (recovered r0c2 pinned). w100-pf: A0 8/12
  vs rank arms 11/12. Rank arms still re-pin the class A0 escapes.
- **G5 full-vs-fold — geomean 1.458 on all six cross models (hier_2pl 0.525,
  radon_var 3.10, lsat 0.389, garch11 5.18, bym2 2.85, kronecker 1.03) vs
  ~1.2x expectation — still UNINFORMATIVE:** 4 of 6 models sit on collapsed
  or degenerate chains under both operators.

### 6.4 Final verdict

The interim verdict stands with the complete grid: **low-rank Alg-1 at rank
10 / basis 4 with --metric-full is REJECTED at CORE_SET scale on this base —
G2, G3, G4 all FAIL, G5 uninformative, and the A3 screen engaged 0/300 times
even under 946k NaN-feed events.** The rerun adjudicated every previously-
open cell and introduced exactly one new fact: a clean win on arma11
(1.47x e/g, 2.49x ESS_min, rhat 1.001) after the guard carried its
warmup-only NaN storm — reinforcing, not weakening, the mechanism reading:
the operator HELPS models that genuinely have a low-rank posterior
(arma11 d=4, low_dim_gauss_mix, logmesquite, wells) and destroys everything
high-dimensional without that structure (lsat, radon both, hier_2pl,
kronecker, bym2), with the screen that should have told them apart never
firing. W-63 is closed as a decisive negative on FORCED rank; the residual
direction is unchanged and narrowed: fix the screen for Alg-1 spectra first,
or restrict rank to screened/structured targets. No further forced-rank
grids.
