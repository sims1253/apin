# W-80b — min-micro-2 HARM-BRANCH test on supplementary non-CORE_SET posteriordb models

**SUPPLEMENTARY, EXPLORATORY, non-CORE_SET.** Pre-registered in WORKLOG
"W-80 PRE-REGISTRATION" part (b) BEFORE any run: source 2-3 SPENDY
HEALTHY models from `external/posteriordb` (@28f8d3d6), screen 4-6
candidates, then A0 vs C5MM2 (`--min-micro-steps 2`) arms; "both
outcomes informative (bounds the lever's domain either way)". The
CORE_SET freeze is untouched (all models below are OUTSIDE the 21-model
frozen set; two are from the same posteriordb but distinct models/data).
Binary: `external/walnutpie_lowrank/build_gates/examples/stan_cli` (same
as all min-micro arms). Seeds 20260819+1000*rep+chain, 1 chain per
process, OMP_NUM_THREADS=1, env -u LD_LIBRARY_PATH, ≤4 workers.

Estimators/conventions reused verbatim from W-79
(`scratch/w79/analyze_w79.py`; rank-normalized Geyer ESS_min on combined
4 chains, split-R-hat, grads = logp_grad calls summed over BOTH stanzas
and 4 chains, label = ESS ratio / grads ratio, medians over 3 reps).

## 1. Candidates (5 sourced; why each was picked)

Heuristics per registration: moderate-to-large D, correlated geometry
(grouped predictors / IRT / GP), no ODE, JSON data available in the
reference clone.

| model | data | D (params block) | family / why picked |
|---|---|---|---|
| election88_full | election88 (N=11566) | 90 | grouped-predictor hierarchical logit (state/age/edu/region REs) — the "large regression/GLM with grouped predictors" class, absent from the labeled set |
| 2pl_latent_reg_irt | fims_Aus_Jpn_irt (I=14, J=500) | 531 | IRT with 500 latent person params + latent regression — correlated IRT geometry at large D |
| gpcm_latent_reg_irt | timssAusTwn_irt (I=11, J=500) | 543 | polytomous (GPCM) IRT, same scale as 2pl — tests whether IRT-family behavior is 2PL-specific |
| hierarchical_gp | state_wide_presidential_votes (50 states x 14 yrs) | 934 | non-centered GP + hierarchical variance decomposition (dirichlet simplex of 17 variances) — "GP-ish" spendy class |
| state_space_stochastic_level_stochastic_seasonal | uk_drivers (n=192) | 389 | random-walk level + seasonal state space — strongly correlated D~400; included as the aggressive pick (known stiff class, NOT an ODE) |

Rejected at sourcing: ODE/PK models (lotka class per registration),
nn_rbm1bJ100 (mnist 183 MB, RBM multimodality), ldaK5 (multimodal),
prophet (fragile), small-D GLMs (wells/kidscore/nes, D<15).

## 2. Screen (A0, w300 s300, rep0 chains 0-3, seeds 20260819+c, DEFAULT init — no --init-file, recorded)

Sampling-stanza calls/draw per chain; "rows" = unique CSV rows of 300
draws; "err" = `Error in logp_grad` lines.

| model | calls/draw (c0..c3) | med | rows | err | verdict |
|---|---|---|---|---|---|
| election88_full | 29.0/16.8/16.9/14.0 | 16.9 | 261-281 | 0 | SELECT (spend ok, clean) |
| 2pl_latent_reg_irt | 19.1/16.2/16.6/15.7 | 16.4 | 245-271 | 0 | not selected (all >15 but lowest spend + family-overlap with gpcm) |
| gpcm_latent_reg_irt | 20.5/18.6/15.5/27.0 | 18.6 | 242-283 | 86/2/0/0 | SELECT (spendy; error spam matches W-79 radon_var precedent) |
| hierarchical_gp | 32.0/25.9/23.6/32.0 | 28.9 | 300/300 | 21/14/0/0 | SELECT (most spendy; note 32.0 = 2^5 = depth-cap in 2 chains) |
| state_space_stoch_level_stoch_seasonal | 32.0x3, 136.7 | 32.0 | **1/1/1**/232 | 0/238/202/122 | REJECT — pinned draws (all rows identical) + `normal_lpdf: Scale parameter is nan` spam |

Screen caveat discovered later (honesty note): the registered health
criterion ("draws produced, no mass errors") is too weak —
hierarchical_gp passed with 300/300 unique rows because its
`y_new_pred` generated quantities draw FRESH RNG noise every iteration,
masking that parameter columns were quasi-frozen; and cross-chain
agreement was not screened at all. Both bite in §3.

## 3. Full arms, DEFAULT-init grid (as instructed: w1000 s1000, 3 reps x 4 chains, default init both arms)

Outputs `scratch/w80/runs/<A0|MM2>/<model>/`. 72/72 runs, rc=0, 31.5 min
at 4 workers.

| model | calls/draw med12 (frac>20) | ESSr | GrDr | samGr | wallr | ESS/grad | per-rep | A0 baseline health |
|---|---|---|---|---|---|---|---|---|
| election88_full | 15.14 (0.08) | 2.199 | 1.743 | 1.772 | 1.660 | 1.262 | 1.77/0.29/1.29 YnY | NON-CONVERGED (rhat>1.02 on 913 cols; chains disagree on beta.1: -1.3/-1.0/-1.6/-1.0) |
| gpcm_latent_reg_irt | 21.45 (0.58) | 0.009 | 1.921 | 1.826 | 1.525 | 0.005 | 0.00/1.71/0.00 nYn | HEALTHY (ess 385, rhat02=0) — MM2 broke it: 2/12 pinned, 142k error lines |
| hierarchical_gp | 29.16 (1.00) | 1.047 | 1.847 | 1.653 | 1.843 | 0.567 | 0.49/0.62/0.55 nnn | FROZEN BASINS (chains stuck at init basins, first-500 == last-500 means; tot_var collapsed 0.001 vs 1.19/1.32 across chains) |

Diagnosis: with DEFAULT inits the A0 baseline premise ("healthy models")
fails for 2/3 selected models at w1000 — election88 chains land in
different intercept modes, hierarchical_gp chains freeze in separate
basins (the screen's row-uniqueness was defeated by GQ noise, §2). The
pre-registration explicitly allowed "random pf-style inits via
pathfinder or model default — record which"; the default-init choice was
made and recorded above, and its failure triggered the pre-registered
ALTERNATIVE (pathfinder) as a recovery grid. Both grids are reported;
nothing else differs (same binary, flags, seeds, counts).

## 4. Recovery grid: PF-INIT arms (W-63 pathfinder convention)

Inits: cmdstan-2.39.0 pathfinder, FIRST PSIS draw per (model, rep,
chain), unconstrained via the W-80 bridgestan .so
(`scratch/w80/inits/<model>/rep<r>/chain_<c>.txt`; one mechanical fix:
hierarchical_gp's simplex `prop_var` renormalized — pf draws sum to
1+1.4e-8 which `param_unconstrain` rejects). Same everything else.
Outputs `scratch/w80/runs_pf/<A0|MM2>/<model>/`. 72/72 runs, rc=0,
35.4 min.

| model | calls/draw med12 (p90, frac>20) | ESSr | GrDr | samGr | wallr | ESS/grad | per-rep | baseline health |
|---|---|---|---|---|---|---|---|---|
| election88_full | 21.76 (25.27, 0.92) | 2.097 | 1.552 | 1.364 | 1.437 | **1.351 benefit** | 0.25/1.57/1.43 nYY | MARGINAL (rhat>1.02 on 102 cols; beta.1 still 2+2 chain split -2.1/-1.5) |
| gpcm_latent_reg_irt | 22.63 (27.40, 0.75) | 0.004 | 2.482 | 2.673 | 1.666 | **0.002 harm** | 0.00/0.00/0.00 nnn | **CLEAN** (ess 537, rhat02=0, rhat_max 1.020) |
| hierarchical_gp | 25.41 (27.42, 1.00) | 8.602 | 2.038 | 2.184 | 1.988 | **4.221 benefit** | 3.45/3.41/6.82 YYY | DEGENERATE-consistent (tot_var soft-collapses to ~0.001 in ALL chains; year_std/GP_region_std soft-funnel rhat up to 1.49; ess_min 4.1) |

Key observations:

- **gpcm is the clean harm-branch point the batch was after**: a
  spendy (22.6 calls/draw) model with a fully healthy A0 baseline
  (pf inits). MM2 kills it — 7/12 chains PINNED (each emits literally
  one unique draw, e.g. `rep0_c0`: alpha.1 = 1.891577 identical in all
  1000 draws), 402k `Error in logp_grad` lines, ESS_min 2.1, ESS/grad
  0.002, per-rep nnn at 0.00/0.00/0.00. The registered harm-side
  prediction (high-spend + healthy => harm) is CONFIRMED on this point.
- **Mechanism is chain death, not cost inflation**: the harm shows up
  as discrete destabilization (pinned chains; one visible mode
  reflection: MM2 chain at alpha~1.9/lambda~1.98 vs the population
  mode alpha~0.8/lambda~0.005 — the classic IRT reflection) on top of
  the expected 2.5-2.7x sampling-grad cost. W-79's lsat harm was
  economic (ESS up, grads 2.3x); gpcm's is qualitative.
- **Spend does NOT decide the branch**: at comparable-or-higher spend,
  election88 benefits (1.35; ESS 2.1x for 1.55x grads) and
  hierarchical_gp benefits hugely (4.22 — MM2's finer micro resolution
  mixes the tot_var-collapsed soft funnel far better: ESS_min 4.1 ->
  35.7, rhat>1.02 count 1143 -> 222), each with a baseline caveat
  (marginal / degenerate-consistent). No 1-D calls/draw feature can
  separate gpcm (22.6, harm) from election88 (21.8, benefit).
- Init protocol moves the FEATURE itself: election88 A0 calls/draw
  med12 is 15.14 under default init vs 21.76 under pf inits (p90 19.07
  vs 25.27) — the feature is a property of (model, init-protocol),
  not of the model alone. All W-63/W-79 selector mining was pf-init,
  so features must be measured under the mining protocol.

## 5. Domain map (the registered deliverable) — supplementary non-CORE_SET labels

Joined with the n=9 CORE_SET table (W-79 writeup), feature = A0
sampling calls/draw med12, all points here under the MINING-comparable
pf-init protocol:

| model | calls/draw | ESS/grad | side | baseline caveat |
|---|---|---|---|---|
| blr | 23.9 | 0.819 | harm | (CORE_SET, W-76) |
| 8sch_c | 20.9 | 0.520 | harm | (CORE_SET, W-76) |
| **gpcm_latent_reg_irt** | **22.63** | **0.002** | **harm (clean)** | none — healthy spendy, chain-death mechanism |
| lsat_model | 16.66 | 0.648 | harm | (CORE_SET, W-79) |
| **election88_full** | **21.76** | **1.351** | **benefit** | marginal (102-col rhat, 2+2 beta.1 split) |
| **hierarchical_gp** | **25.41** | **4.221** | **benefit** | degenerate-consistent (tot_var collapse) |

Conclusion: the min-micro-2 lever's sign is NOT a function of spend
alone anywhere in 21.8-29.2 calls/draw: catastrophic harm (gpcm,
chain death on IRT reflection geometry) and large benefits
(hierarchical_gp soft funnel, election88 deep hierarchy) coexist at
~22-25. What correlates (post-hoc, n=3): harm where the posterior has
discrete multimodality at the trajectory scale (IRT reflection), benefit
where mixing is limited by fine-scale degenerate directions (collapsed
variance scales / deep hierarchies). `--min-micro-steps 2` stays a
per-model lever; the "harm branch = spendy healthy" simplification is
DEAD — the harm branch is real but class-specific, and its worst
failure mode is silent chain pinning (7/12 chains), which a
median-ESS/grad read of a sick batch can mask as a normal label.

## 6. Out-of-sample check vs W-80a's v2 selector (p90 <= 21 -> benefit)

W-80a landed after this batch started (WORKLOG "W-80a CLOSE-OUT"): v2 =
p90 of the 12 per-chain A0 sampling calls/draw, rule "p90 <= 21 ->
benefit", separated 9/9 in-sample, registered to be scored one-shot on
W-80b's labels. One-shot score on this batch:

| grid | model | p90 | v2 predicts | observed | verdict |
|---|---|---|---|---|---|
| pf (mining-comparable) | gpcm_latent_reg_irt | 27.40 | harm | harm 0.002 | OK (clean point) |
| pf | election88_full | 25.27 | harm | benefit 1.351 | MISS (marginal baseline) |
| pf | hierarchical_gp | 27.42 | harm | benefit 4.221 | MISS (degenerate baseline) |
| def | election88_full | 19.07 | benefit | benefit 1.262 | OK* (artifact label) |
| def | gpcm_latent_reg_irt | 25.04 | harm | harm 0.005 | OK |
| def | hierarchical_gp | 49.18 | harm | harm 0.567 | OK* (frozen-baseline artifact) |

Honest read: on the mining-comparable (pf) protocol the rule scores
**1/3 out-of-sample** — it holds on the single clean point (gpcm) and
misses both caveated-baseline points; the def-grid "3/3" is worthless
(2 of its 3 labels are artifacts of non-converged baselines, §3). With
W-79's lsat in-sample miss standing, v2 is **not confirmed and not
adopted**: the extrapolation to p90 ~25-27 (beyond every CORE_SET point
except blr) is where it breaks. Additional structural problem found:
the feature is init-protocol-dependent (§4), so any future selector
must pin the init protocol to the mining protocol.

## 7. Protocol lessons (recorded for future waves)

1. Default init is NOT viable for spendy posteriordb models at w1000
   under this sampler (2/3 non-converged/frozen baselines); pf-first-draw
   inits are the minimum protocol, and even they leave marginal
   baselines on multimodal hierarchies (election88).
2. Screen health checks must use PARAM-BLOCK columns only (GQ RNG noise
   defeats row-uniqueness checks) and must include a cross-chain rhat.
3. The pin census (`np.unique(rows) == 1`) catches gpcm-style MM2 chain
   death; ESS_min ~2-8 + rhat counts >~100 are the signature of broken
   baselines. Batch reports should show rhat02 next to every label.

## 8. Files

- Models/data: `scratch/w80/model_<name>/{<name>.stan, data.json,
  <name>_model.so}` (bridgestan 2.9.0, -j2); cmdstan exes
  `build/<name>__default/model`
- Screen: `scratch/w80/screen.py`, `screen.log`, `screen/<model>/c{0-3}.*`
- Drivers: `scratch/w80/driver.py` (`--grid def|pf`, resume-capable,
  rc's in `driver.log`), init gen `scratch/w80/gen_inits.py`
- Runs: `scratch/w80/runs/<A0|MM2>/<model>/rep<r>_c<c>.{csv,log}`
  (default init), `scratch/w80/runs_pf/...` (pf init); inits
  `scratch/w80/inits/`, raw pf draws `scratch/w80/pf/`
- Analyzer: `scratch/w80/analyze_w80.py` (`def|pf` arg), outputs
  `scratch/w80/analyze.out`, `analyze_pf.out`, `w80b_results_def.json`,
  `w80b_results_pf.json`

Machine time (idle machine, ≤4 cores): builds ~10 min (5 bridgestan +
3 cmdstan), screen ~3 min, default-init grid 31.5 min, pf generation
~18 min (36 pathfinder runs, 2 workers), pf grid 35.4 min, analysis
~8 min — **~1h45m total**.
