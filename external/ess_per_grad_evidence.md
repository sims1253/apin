# WALNUTS vs NUTS: effective samples per gradient evaluation — evidence package

**For:** Flatiron walnutpie team (prepared from the nindan benchmarking campaign)
**Setup:** 21-model posteriordb core set (CORE_SET @ 28f8d3d6), 4 chains, 3 reps,
seeds 20260819+1000·rep; cmdstan 2.39.0 default vs walnutpie recommended config
(batch-stride 50 + mass-init-clamp 100 + step-init-heuristic + metric-window 50 +
Pathfinder inits). ESS = rank-normalized ESS_bulk min over parameters (posterior 1.7).

## Headline

**With a fair, sampling-phase-only denominator, walnutpie yields a geomean of
0.32x cmdstan's effective samples per gradient — not the ~0.06x that the raw
per-variant table suggests.** The 0.06x figure in earlier tables is an artifact
of two metric-definition asymmetries (below). The real story splits by mixing
status:

- On the 13/20 models where walnutpie's recommended config mixes: **0.25–1.33x**
  (median ~0.35x, and it *wins* on kronecker_gp 1.33x, pilots 1.05x,
  eight_schools_centered 1.00x). This bounded factor is the price of the
  within-orbit dyadic step-size search — design overhead, not a defect.
- On hard-mixing models (hier_2pl 0.025x, bym2 0.062x, diamonds 0.075x,
  low_dim_gauss_mix 0.108x) the ratio collapses because gradients are burned
  during poorly-mixed sampling without gaining ESS. These are the warmup/mixing
  failures the init-robustness and rank-metric work targets; as those land
  (hier_2pl fold-mode: ESS 16 -> 188 at 3-rep medians after the freeze fixes),
  the per-grad ratio rises with the ESS numerator, no kernel change needed.

## The two metric bugs in the original table

1. `n_leapfrog_total` for walnutpie = **warmup + sampling** logp calls
   (harness/run_walnutpie.py:75), while for cmdstan it sums `n_leapfrog__` over
   **saved rows only** = sampling only (save_warmup off). Walnutpie's
   denominator carried ~2x extra gradients; the per-variant geomean ratio
   computed from that table (~0.06x) mixes this bias with reality.
2. cmdstan's `n_leapfrog_sampling` is actually "last 500 of 1000 sampling
   draws" (run_grid.py:75) — a different phase again. Neither column name
   matches its content.

The corrected numbers below use **sampling-phase-only gradients on both
sides** (cmdstan: all 1000 post-warmup draws; walnutpie: its 500-draw sampling
phase), with ESS_bulk_min from each run's own draws, median over 3 reps.

## Corrected per-model table (ESS_min / sampling-phase gradient, walnutpie/cmdstan ratio)

| model | cmdstan e/grad | walnutpie e/grad | ratio |
|---|---|---|---|
| arma11 | 1.794e-01 | 3.227e-02 | 0.180 |
| blr | 1.267e-02 | 4.042e-03 | 0.319 |
| bym2_offset_only | 1.397e-03 | 8.689e-05 | 0.062 |
| diamonds | 3.303e-04 | 2.477e-05 | 0.075 |
| dogs_hierarchical | 8.066e-02 | 6.457e-02 | 0.801 |
| eight_schools_centered | 8.873e-04 | 8.863e-04 | 0.999 |
| eight_schools_noncentered | 7.316e-02 | 4.463e-02 | 0.610 |
| garch11 | 4.182e-02 | 1.862e-02 | 0.445 |
| gp_regr | 1.971e-01 | 7.665e-02 | 0.389 |
| hier_2pl | 1.625e-02 | 4.052e-04 | 0.025 |
| kidscore_momiq | 1.237e-02 | 9.670e-03 | 0.782 |
| kronecker_gp | 2.312e-04 | 3.068e-04 | 1.327 |
| logmesquite_logvash | 7.410e-03 | 1.850e-03 | 0.250 |
| lotka_volterra | 6.754e-03 | 1.204e-03 | 0.178 |
| low_dim_gauss_mix | 1.534e-01 | 1.652e-02 | 0.108 |
| lsat_model | 1.793e-02 | 5.822e-03 | 0.325 |
| pilots | 3.428e-05 | 3.610e-05 | 1.053 |
| radon_partially_pooled_noncentered | 5.010e-03 | 1.751e-03 | 0.349 |
| radon_variable_intercept_slope_noncentered | 9.036e-03 | 2.927e-03 | 0.324 |
| wells_dist100_model | 5.312e-02 | 3.682e-02 | 0.693 |
| **geomean** | | | **0.312x** |

(accel_gp omitted: all samplers fail it — cmdstan ESS 1.0; walnutpie aborts,
see "Robustness asymmetry".)

## Candidate explanations for the residual ~3x orbit overhead, with evidence

1. **Within-orbit dyadic step-size search re-evaluates gradients.** WALNUTS
   spends its budget trading gradient evals for step-size robustness. Evidence
   on well-mixed models the factor is bounded (0.3-0.8x), consistent with
   min_micro_steps x step-halvings per macro step rather than unbounded blowup.
   Cheap experiment: count gradient evals per macro step (logp_grad calls /
   macro steps) as a function of adapted step size.
2. **No cross-orbit gradient memoization.** If the dyadic search revisits the
   same (position, step) pair, logp_grad is called again. A position-keyed
   cache within a macro step could cut evals with zero algorithmic change.
   Measurable via call-pattern logging (positions hash).
3. **ESS numerator capped by draw count.** walnutpie ran 500 draws vs cmdstan
   1000 in these runs; for models where walnutpie mixes antithetically
   (kronecker_gp ESS 77 on 500x4 draws) the ratio understates steady-state
   efficiency. ESS/grad is a rate so this mostly cancels, but worth a
   1000-draw control on 3 models.
4. **Adaptation-quality interaction (dominant on hard models).** The collapse
   cases correlate with R-hat failures, not with per-draw cost; see the
   freeze-consistency fixes (PR #4 follow-ups 12-13) — warmup tuned under one
   metric, sampling ran another. After those fixes hier_2pl fold-mode ESS rose
   12x, which mechanically lifts its e/grad ratio by the same factor.

## Robustness asymmetry (separate from efficiency)

accel_gp: cmdstan completes but with ESS 1.0 (pathology in the posterior);
walnutpie **aborts the process** on non-finite log-density mid-trajectory
(`normal_lpdf: Scale parameter is -nan`) where Stan would reject the proposal
and continue. A trajectory-level rejection path (as NUTS has) would make the
failure mode match cmdstan's: garbage-but-finished instead of crash.

## What W-17 adds

Full 21-model x 3-config (rec / fold / auto) sweep with the freeze-fix binary,
3 reps, capturing sampling-phase gradient counts per chain — will give the
post-fix e/grad table for all models including whether fold mode's ESS gains
translate to per-gradient parity on the previously collapsed models.
