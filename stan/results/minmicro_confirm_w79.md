# W-79: min-micro-2 selector CONFIRMATORY batch — CLOSE-OUT: gate CONFIRMED (3/4 models ESS/grad > 1) but the selector does NOT cleanly extrapolate — lsat (predicted benefit at calls/draw 16.66) is a DECISIVE harm (0.648, per-rep nnn), breaking the W-76 addendum's perfect 5/5 separation; rule status 8/9 at n=9 with the miss unfixable by any threshold (lsat's feature ≈ hier_2pl's, labels opposite)

Pre-registration: WORKLOG "W-79 PRE-REGISTRATION" (2026-08-26, before any
run). Protocol: the "Protocol to close it" section of the W-76 selector
mining addendum (results/depthcap_w76.md). Binary:
`external/walnutpie_lowrank/build_gates/examples/stan_cli` (the W-63 A0 /
W-76 binary; unchanged — arm-consistency with W-76's C5MM2 arm, which also
pinned `--max-trajectory-doublings 5` = the default).

## Design (as pre-registered)

- Arm: **C5MM2** = `--min-micro-steps 2`, everything else default. Models:
  lsat_model, radon_variable_intercept_slope_noncentered (radon_var),
  dogs_hierarchical (dogs), gp_regr — the addendum's minimal confirm batch
  (boundary-adjacent spendy + low-spend extremes), ALL predicted benefit.
- Grid: 1 arm x 4 models x 3 reps x 4 chains = 48 single-chain runs, pf
  inits (scratch/w63/manifest.csv), w1000 s1000, seeds
  20260819+1000*rep+chain, `--metric-window 50`, `env -u LD_LIBRARY_PATH`,
  `OMP_NUM_THREADS=1`, 4 workers, resume-capable driver.
- Baseline: REUSED W-63 A0 grid `scratch/w63/runs/A0/<model>/w1000_pf/`
  (same binary; identical seeds/args otherwise — canary-proven reusable in
  W-76).
- Completion: 48/48, 0 failures, ~80 s wall (01:32:22-01:33:32) on the
  idle machine (load ~1.4). 0 pinned runs, 0 chains with rhat > 1.02, in
  BOTH arms; the known pf-init error-spam (radon_var 88->932, gp_regr
  18->290, dogs 0->34 "Error in logp_grad" lines) scales with eval count
  and affects no outcome — all runs completed both stanzas.

## Conventions (reused from w63/w74/w76)

ESS_min = min over parameters of rank-normalized Geyer ess_bulk on the
combined 4 chains per rep; rep medians reported. grads/draw = total
`logp_grad calls:` (BOTH stanzas, warmup+sampling) summed over the 4
chains / 1000 draws. **Label = ESS/grad ratio** (ESS ratio / grads/draw
ratio — load-invariant). Selector feature = per-chain SAMPLING calls/draw,
median over the 12 chain-runs (the W-73 convention, results/
p3_logparse_w73.md; verified on-grid: this parse reproduces the
pre-registered predictions exactly — 16.66/16.58/5.68/6.63 vs
16.7/16.6/5.7/6.6).

## Headline table (rep medians; ratios vs reused A0)

| model | calls/draw obs (pred) | ESS_min A0 -> MM2 | ESS ratio | grads/draw ratio | samp-grads ratio | **ESS/grad** | per-rep ESS/grad | side |
|---|---|---|---|---|---|---|---|---|
| lsat_model | 16.66 (16.7) | 940.8 -> 1196.5 | 1.272 | 1.964 | 2.265 | **0.648** | 0.77 / 0.45 / 0.59 (nnn) | harm |
| radon_var | 16.58 (16.6) | 267.0 -> 428.0 | 1.603 | 1.436 | 1.440 | **1.116** | 1.68 / 1.09 / 0.87 (YYn) | benefit |
| dogs | 5.68 (5.7) | 1592.1 -> 2637.7 | 1.657 | 1.141 | 1.023 | **1.452** | 1.42 / 1.39 / 1.52 (YYY) | benefit |
| gp_regr | 6.63 (6.6) | 2261.6 -> 3909.3 | 1.729 | 1.179 | 1.128 | **1.466** | 1.67 / 1.23 / 1.60 (YYY) | benefit |

Secondary, wall (idle machine; no co-load canary this session): ESS/s
ratios radon_var 1.33, dogs 1.35, gp_regr 1.46, lsat 0.77 — corroborate
the grads-based labels.

## Gate adjudication (pre-registered, BINDING)

- **CONFIRMED iff >= 3/4 models ESS/grad > 1** — observed 3/4 (dogs, gp_regr,
  radon_var). **VERDICT: CONFIRMED.**
- STRONG if all 4 > 1.05 — NOT MET (lsat 0.648).
- REFUTED if >= 2 models <= 0.95 — NOT MET (only lsat <= 0.95).

The selector's directional claim (low-spend models net-benefit from
`--min-micro-steps 2`) holds at the model level on this batch; the two
low-spend extremes (dogs 5.7, gp_regr 6.6 calls/draw) are the cleanest
wins — sampling-grads ~parity (1.02-1.13x) for +46-47% ESS/grad, i.e.
nearly free quality.

## Per-rep record (the addendum's boundary-flip lesson)

- lsat: 0.77/0.45/0.59 = **nnn** — a DECISIVE harm, not boundary noise;
  the harm is on the economics axis (ESS rose 1.27x but sampling grads
  2.27x), exactly the axis the label measures.
- radon_var: 1.68/1.09/0.87 = **YYn** — the expected boundary-cluster
  behavior; its median 1.116 sits in the same 1.12-1.15 band as the W-76
  boundary benefit models (radon_pp 1.127, logmesquite 1.147), and its
  feature (16.58) sits in the same 16.6-17.4 cluster. Rep noise is the
  addendum's ±30%, unchanged.
- dogs/gp_regr: YYY — stable, far from the boundary.

## Does the selector extrapolate? NO — one decisive miss (the honest answer)

Joined n=9 table (this batch + W-76 C5MM2 labels; feature = W-73
per-chain median calls/draw):

| model | calls/draw | ESS/grad | side | predicted |
|---|---|---|---|---|
| hier_2pl | 16.7 | 1.752 | benefit | benefit ok |
| gp_regr | 6.6 | 1.466 | benefit | benefit ok |
| dogs | 5.7 | 1.452 | benefit | benefit ok |
| logmesquite | 17.4 | 1.147 | benefit | benefit ok |
| radon_pp | 17.1 | 1.127 | benefit | benefit ok |
| radon_var | 16.6 | 1.116 | benefit | benefit ok |
| blr | 23.9 | 0.819 | harm | harm ok |
| 8sch_c | 20.9 | 0.520 | harm | harm ok |
| **lsat_model** | **16.66** | **0.648** | **harm** | **benefit — MISS** |

- The rule scores **8/9**; no threshold on this feature can do better:
  lsat (16.66) and hier_2pl (16.7) have essentially identical features and
  opposite labels (1.752 vs 0.648). The addendum's clean 5/5 separation is
  dead at n=9.
- Post-hoc observation (NOT a rule, recorded for the next mining pass):
  lsat is the only predicted-benefit model whose A0 per-chain feature is
  BIMODAL — 9/12 chains at 16.4-16.8 but 3/12 at 18.4/23.9/30.9
  (depth-cap-saturation-like values; 23.9 = blr's median). The
  median-based feature hides minority-chain cap saturation, which is the
  addendum's own mechanism for harm ("where the cap binds, min-micro 2
  adds grads without trajectory length"). A per-chain saturation fraction
  (e.g. frac chains > ~20) would have flagged lsat — untested, n=9, treat
  as a hypothesis only.
- Batch-level directional claim CONFIRMED, but the selector-as-deployed
  (median calls/draw <= ~18) is NOT adoption-ready: it has an in-sample
  miss that its feature cannot express, and the harm branch is still
  untested on healthy spendy models (none exist in CORE_SET — the
  addendum's design limit, unchanged: needs 1-2 new spendy healthy models
  from OUTSIDE CORE_SET, user decision whether to source them).

## Status

`--min-micro-steps 2` remains what W-76 concluded: a per-model quality
lever, strong on low-spend models (dogs/gp_regr class: ~parity cost,
+45% ESS/grad) and on some hierarchical models (hier_2pl 1.75x), harmful
on cap-saturated (blr, 8sch_c) and now lsat. No default change; no
selector adopted. The two follow-up leads: (a) outside-CORE_SET spendy
healthy models to occupy the harm branch; (b) a per-chain saturation
feature to replace the median.

## Files

- Driver: `scratch/w79/driver.py` (log: `scratch/w79/driver.log`)
- Runs: `scratch/w79/runs/C5MM2/<model>/rep<r>_c<chain>.{csv,log}`
- Analyzer: `scratch/w79/analyze_w79.py` (stdout: `scratch/w79/analyze.out`;
  JSON: `scratch/w79/w79_results.json`)
- Baseline: `scratch/w63/runs/A0/<model>/w1000_pf/` (reused)

## v2 selector (W-80a, appended 2026-08-26): per-chain saturation feature mining — p90 of the 12 chains separates 9/9 AND is LOO-stable (0/9); the registered frac(chains>20) hypothesis also separates 9/9 but with a ONE-CHAIN margin; frac>18 does NOT separate (lsat ties logmesquite/radon_pp at 3/12, the median's pathology at a new threshold)

Pre-registration: WORKLOG "W-80 PRE-REGISTRATION" (a) V2 MINING. Zero cost:
single-core python over the EXISTING W-63 A0 logs, no sampling, no builds.
Hypothesis under test: the label is predicted by a PER-CHAIN saturation
feature, not the median (falsified in W-79: lsat 16.66 -> harm vs hier_2pl
16.7 -> benefit). Feature parse = the W-73/W-79 convention, validated by
reproducing all 9 known medians exactly (16.74/17.35/17.11/16.58/5.68/
6.63/23.89/20.85/16.66 vs 16.7/17.4/17.1/16.6/5.7/6.6/23.9/20.9/16.66),
and lsat's chains reproduce W-79's bimodality note exactly (9/12 at
16.4-16.8, 3/12 at 18.4/23.9/30.9).

### Per-model 12-chain sampling calls/draw distribution (W-63 A0)

| model | side | min | med | max | frac>20 | frac>18 | p90 |
|---|---|---|---|---|---|---|---|
| hier_2pl | benefit | 16.54 | 16.74 | 17.08 | 0/12 | 0/12 | 17.02 |
| logmesquite | benefit | 11.98 | 17.35 | 18.60 | 0/12 | 3/12 | 18.38 |
| radon_pp | benefit | 15.13 | 17.11 | 23.64 | **1/12** | 3/12 | **19.18** |
| radon_var | benefit | 16.11 | 16.58 | 16.95 | 0/12 | 0/12 | 16.87 |
| dogs | benefit | 5.51 | 5.68 | 6.00 | 0/12 | 0/12 | 5.83 |
| gp_regr | benefit | 5.82 | 6.63 | 6.80 | 0/12 | 0/12 | 6.78 |
| blr | harm | 15.95 | 23.89 | 26.99 | 11/12 | 11/12 | 26.12 |
| 8sch_c | harm | 14.36 | 20.85 | 26.34 | 7/12 | 9/12 | 26.10 |
| lsat | harm | 16.38 | 16.66 | 30.91 | **2/12** | 3/12 | **23.34** |

(bold = the boundary pair that decides each feature). All 6 benefit models
have upper tails at or below ONE saturated chain; all 3 harm models have
>= 2 chains past 20. p90 = numpy linear-interp percentile of the 12 values
(n=12: a soft second-highest-chain value; lsat = 18.4 + 0.9*(23.9-18.4)).

### Candidate features vs the 9 labels (rule: benefit iff feature below t)

| feature | in-sample | class gap | LOO |
|---|---|---|---|
| median (W-76 v1, baseline) | 8/9 (lsat, known) | none possible | 1/9 |
| (i) frac(chains > 20), t = 1/12 | **9/9** | 1/12 (= ONE chain-count step: radon_pp 1/12 vs lsat 2/12) | 1/9 (hold-out-lsat fold: t floats to 1/3, lsat 2/12 -> benefit) |
| (ii) frac(chains > 18) | 8/9 | none possible (lsat TIES logmesquite/radon_pp at 3/12 with opposite labels — the median's pathology at a new threshold) | 3/9 |
| (iii) max chain, t ~ 25 | **9/9** | 2.70 (radon_pp 23.6 vs 8sch_c 26.3) | 1/9 (hold-out-radon_pp fold: its 23.6 max lands above fold-t 22.5) |
| (iv) p90 of chains, t ~ 21.3 | **9/9** | **4.15** (max-benefit 19.18 radon_pp vs min-harm 23.34 lsat) | **0/9** |

### Winner: p90 (benefit iff p90 of the 12 chains <= ~21; any t in (19.18, 23.34) works)

- 9/9 in-sample, LOO 0/9 (all 9 folds correct; fold thresholds span
  20.86-22.64 — the rule does not hinge on one point).
- Largest margin of the four candidates (4.15 calls/draw), and it is NOT a
  knife-edge count: threshold can move a full ~2 calls/draw either way.
- Mechanism-consistent: p90 ~ soft second-highest chain = exactly the
  "minority-chain depth-cap saturation" W-79 post-hoc-observed in lsat;
  the registered form of the hypothesis (i) agrees on all 9 labels.
- Boundary case identified a priori for W-80b: radon_pp (p90 19.18,
  frac>20 = 1/12) is the closest benefit model to the harm line —
  consistent with its boundary-cluster ESS/grad (1.127) in W-76.

### HONEST verdict (post-hoc search on 9 points)

This was a feature SEARCH: 5 features x 2 directions = 10 rules tried on 9
labeled points, pre-registered only at the family level ("a per-chain
saturation feature such as frac > ~20"), not at the p90 level. A 9/9 + LOO
0/9 winner out of 10 candidates carries winner's-curse risk that LOO on
the SAME 9 points cannot fully price (LOO reuses the search's chosen
family). The mechanism claim (minority-chain cap saturation drives harm)
is now supported by THREE agreeing features (frac>20, max, p90 all 9/9),
but the specific v2 rule is EXPLORATORY until confirmed out-of-sample:
the W-80b harm-branch models (and any future labeled models) are the real
test — register "p90 <= 21" as the candidate rule BEFORE W-80b runs and
score it on the new labels, one-shot. If W-80b falsifies it, the valid
fallback finding stands: the lever is real but not predictable from
calls/draw alone.

Files: `scratch/w80/v2_mining.py` (driver, zero cost), `scratch/w80/
v2_mining.out` (full output incl. per-fold LOO), `scratch/w80/v2_results.json`
(machine-readable, for W-80b scoring). Inputs: reused W-63 A0 logs.
