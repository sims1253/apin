# W-84: guarded-MM2 FULL-domain table — GMD on the 15 models not covered by W-82 (24/24 measured models complete)

Pre-registration: WORKLOG "W-84 PRE-REGISTRATION (before any run)". Binary:
`external/walnutpie_mm2guard/build_mg/examples/stan_cli` (branch
`robustness/mm2-guard`, HEAD ef524a5) — the W-82 binary, unchanged. This
campaign completes PR #20's evidence from 9 to all 24 measured models.

## Remaining-model determination (the pre-reg's open CHECK, resolved)

The 24-model measured set = 21 CORE_SET (`scratch/w63/manifest.csv`) +
{election88_full, gpcm_latent_reg_irt, hierarchical_gp} (W-80). W-82
covered 9 = six CORE_SET {hier_2pl, dogs_hierarchical, gp_regr, blr,
eight_schools_centered, lsat_model} + all three W-80 supplementaries.
Remaining = the OTHER **15** CORE_SET models (not "~12"; the pre-reg's
inline guess self-corrected, its title already said 15):
eight_schools_noncentered, kidscore_momiq, logmesquite_logvash,
wells_dist100_model, diamonds, radon_partially_pooled_noncentered,
radon_variable_intercept_slope_noncentered, pilots, kronecker_gp,
accel_gp, bym2_offset_only, garch11, lotka_volterra, low_dim_gauss_mix,
arma11.

## Protocol

15 models x 1 arm (GMD = `--min-micro-steps 2 --min-micro-guard`, guard
defaults probe 50 / min-unique 25) x 3 reps x 4 chains = **180/180 rc=0**
(~47 min at 2 workers under foreign load 10-17; resume-capable driver).
w1000 s1000 `--metric-window 50`, seeds 20260819+1000*rep+chain, pf inits
per the w63 manifest (12/12 rep/chain init files verified present for all
15 BEFORE the run — nothing missing), `env -u LD_LIBRARY_PATH`,
OMP_NUM_THREADS=1, single chain per process.

**A0 grids REUSED** (per pre-reg): `scratch/w63/runs/A0/<model>/w1000_pf/`
— same seeds, same manifest pf inits, same w1000 s1000 metric-window-50
protocol; binary default-path equivalence was proven by W-82's canaries
(36/36 vs W-80b + W-63 gp_regr) and re-proven HERE on a 15th model: a
fresh same-binary A0 canary of kronecker_gp rep0_c0 (the trickiest chain
in the set) is md5-EQUAL to the reused W-63 grid (46be8163…;
`scratch/w84/canary/`). Wall ratios vs A0 are therefore CROSS-SESSION
(W-63 ran idle, W-84 under load 10-17) and are reported as
non-comparable; ESS/grad is load-invariant. Guard cost on silent chains
remains W-82's within-session GMD/MM2 0.99-1.014.

Estimators: `scratch/w82/analyze_w82.py` conventions verbatim
(rank-normalized Geyer ess_bulk min over params on combined 4-chain draws
per rep; rank-normalized split-R-hat > 1.02 counts; constant columns
excluded; grads/draw = sampling-stanza `logp_grad calls`, last stanza per
log — for firing chains the MM1 fallback's). ESS/grad = ESS ratio /
sampling-grads ratio vs A0, population level (rep medians), per-rep
spread recorded.

## The 15 new models: GMD vs reused A0 (rep medians)

| model | A0 ESS_min | GMD ESS_min | ESSr | ESS/grad | ESS/grad_total | fires | guard class |
|---|---|---|---|---|---|---|---|
| lotka_volterra | 10.3 | 165.0 | 16.00 | **15.78** | 14.25 | 0 | benefit (degenerate-baseline caveat) |
| wells_dist100_model | 749.2 | 1599.4 | 2.14 | **2.26** | 1.88 | 0 | benefit |
| low_dim_gauss_mix | 778.6 | 1388.8 | 1.78 | **1.83** | 1.50 | 0 | benefit |
| kidscore_momiq | 283.4 | 531.4 | 1.88 | **1.61** | 1.30 | 0 | benefit |
| garch11 | 747.1 | 1078.6 | 1.44 | **1.32** | 1.18 | 0 | benefit |
| eight_schools_noncentered | 1470.2 | 2137.1 | 1.45 | **1.29** | 1.23 | 0 | benefit |
| logmesquite_logvash | 102.4 | 158.7 | 1.55 | **1.24** | 1.15 | 0 | benefit |
| radon_partially_pooled_noncentered | 216.7 | 384.3 | 1.77 | **1.23** | 1.13 | 0 | benefit |
| radon_variable_intercept_slope_noncentered | 267.0 | 428.0 | 1.60 | **1.11** | 1.12 | 0 | benefit |
| arma11 | 1022.3 | 1391.4 | 1.36 | **1.15** | 1.08 | 0 | benefit |
| diamonds | 2.5 | 3.1 | 1.23 | **0.69** | 0.62 | 0 | economic-harm |
| pilots | 2.3 | 2.4 | 1.04 | **0.98** | 0.73 | 2 | fired (MM2-caused, recovered) |
| bym2_offset_only | 2.3 | 2.8 | 1.25 | **1.00** | 0.67 | 8 | fired (mixed) |
| kronecker_gp | 8.1 | 27.0 | 3.32 | **1.97** | 1.84 | 1 | fired (A0-inherent) |
| accel_gp | 2.3 | 2.4 | 1.04 | **0.53** | 0.53 | 3 | fired (mixed) + economic-harm |

(grad_total includes the discarded guarded attempts — the honest
wasted-probe price on firing models. Per-rep ESS/grad votes in
`scratch/w84/analyze.out`: all 10 benefit models have median-consistent
spreads except lotka 1.63Y/0.68n/22.51Y and radon_var 1.68Y/1.07Y/0.91n —
the known boundary cluster.)

## Guard-fire census — 14 fires, a clean 6+8 mechanism split

Fires: kronecker r0c0; bym2 r0c2, r0c3, r1c0-c3, r2c0, r2c3 (8);
accel r0c2, r1c3, r2c1 (3); pilots r0c0, r2c3 (2). Every fire line reads
"1/50 unique parameter rows (< 25)". **Zero guard misses** (no silent
chain anywhere has nu50 < 25; min nu50 on silent chains = 38 diamonds,
median ~46-50) and **zero false fires** (all 14 firing chains nu50 = 1).
The reused A0 grids themselves contain 8 pinned chains — kronecker r0c0,
bym2 r1c0-c3 + r2c3, accel r0c2 + r1c3 (1 unique row over all 1000 draws
at MM1) — which splits the fires exactly:

- **MM2-caused pins (gpcm-class), 6/6 restart md5-EXACT to the healthy
  A0 chain**: pilots r0c0, r2c3; bym2 r0c2, r0c3, r2c0; accel r2c1. The
  in-process MM1 restart is byte-identical to the reused-grid MM1 run —
  the W-82 gpcm mechanism, now on 3 further models.
- **A0-inherent pins (init pathology), 8/8 restart to the pin**: on
  chains where A0/MM1 itself is pinned, the guard fires (the MM2 attempt
  pins too) and the restart returns the pinned MM1 trajectory up to ONE
  marginal acceptance among 1000 draws (2 unique rows vs A0's 1; md5
  differs, first rows identical, outputs equally frozen). The guard
  cannot and does not claim to fix these — it converts MM2's pin to
  MM1's pin, i.e. arm-neutral pathology, detected honestly.

## The COMPLETE 24-model domain table (W-82's 9 + W-84's 15)

ESS/grad = GMD vs A0 (W-82 rows: fresh same-binary A0, results/
mm2_guard_w82.md; W-84 rows: reused W-63 A0 grids as above).

| model | ESS/grad | fires | class | source |
|---|---|---|---|---|
| hierarchical_gp | 3.94 | 0 | benefit | W-82 |
| hier_2pl | 1.63 | 0 | benefit | W-82 |
| dogs_hierarchical | 1.62 | 0 | benefit | W-82 |
| election88_full | 1.54 | 0 | benefit (init-fragile caveat) | W-82 |
| gp_regr | 1.53 | 0 | benefit | W-82 |
| lotka_volterra | 15.78 | 0 | benefit (sick-median caveat) | W-84 |
| wells_dist100_model | 2.26 | 0 | benefit | W-84 |
| low_dim_gauss_mix | 1.83 | 0 | benefit | W-84 |
| kidscore_momiq | 1.61 | 0 | benefit | W-84 |
| garch11 | 1.32 | 0 | benefit | W-84 |
| eight_schools_noncentered | 1.29 | 0 | benefit | W-84 |
| logmesquite_logvash | 1.24 | 0 | benefit | W-84 |
| radon_partially_pooled_noncentered | 1.23 | 0 | benefit | W-84 |
| radon_variable_intercept_slope_noncentered | 1.11 | 0 | benefit | W-82-79 label 1.12 reproduced | W-84 |
| arma11 | 1.15 | 0 | benefit | W-84 |
| blr | 0.84 | 0 | economic-harm | W-82 |
| diamonds | 0.69 | 0 | economic-harm | W-84 |
| lsat_model | 0.56 | 0 | economic-harm | W-82 |
| eight_schools_centered | 0.56 | 0 | economic-harm | W-82 |
| gpcm_latent_reg_irt | 0.90 | 7 | fired: MM2-caused, md5-exact recovery (ESS 2.1→659 vs A0 537) | W-82 |
| pilots | 0.98 | 2 | fired: MM2-caused, md5-exact recovery | W-84 |
| bym2_offset_only | 1.00 | 8 | fired: 3 MM2-caused (md5-exact) + 5 A0-inherent | W-84 |
| accel_gp | 0.53 | 3 | fired: 1 MM2-caused + 2 A0-inherent; economic harm on the silent chains | W-84 |
| kronecker_gp | 1.97 | 1 | fired: A0-inherent; degenerate baseline, ratio not economic evidence | W-84 |

**Headline across 24: 15 benefit / 4 economic-harm / 5 fired** (21
chain-fires total = 13 MM2-caused, all restarted md5-exact to healthy
MM1, + 8 A0-inherent init-pathology pins, all detected and made
arm-neutral). No model is made worse than its own A0 baseline by more
than the known economic-harm band (worst new: accel 0.53 — guard silent
on 9/12 chains there; the guard converts pins, not economic harm, per
W-82).

## Per-class summary (the domain map)

- **Benefit (15/24)**: the class W-76/W-79 predicted and W-82 locked in
  — hierarchials (hier_2pl, hier_gp, radon_pp, radon_var, dogs,
  election88), low-spend GLMs/regressions (wells, kidscore, logmesquite,
  garch11, arma11, gp_regr), the noncentered funnel (8sch_nc 1.29 vs
  centered 8sch_c 0.56 — a clean parameterization axis), a Gaussian
  mixture (low_dim_gauss_mix), and the stiff ODE lotka (15.8, largest in
  the domain — MM2 heals 2 of its 3 sick baseline reps). Guard silent
  everywhere (nu50 min 38 vs threshold 25).
- **Economic harm (4/24)**: lsat 0.56, 8sch_c 0.56, blr 0.84 (W-82),
  diamonds 0.69 (new) — spendy/cap-saturated baselines paying MM2's
  extra grads without trajectory length; guard silent by design (W-82's
  "the guard converts pins, not economic harm").
- **Pin/fire (5/24)**: gpcm (7 chains) + pilots (2) + bym2 (3 of 8) +
  accel (1 of 3) are the gpcm-class — MM2 pins a chain the baseline runs
  healthily, the guard fires at 1/50 and restarts byte-exact to MM1
  (13/13 verified md5). kronecker (1), bym2 (5), accel (2) add a NEW
  subclass the domain table exposes: A0-inherent init-pathology pins
  (8/8) — chains pinned at MM1 in the baseline grids themselves; the
  guard detects them (MM2 pins them too), restarts, and returns exactly
  the baseline's pin up to one marginal acceptance. Detection is honest
  either way; recovery is only possible where the baseline is healthy.

## Updated domain-map paragraph for PR #20's narrative

> Guarded min-micro-2 was evaluated on the full 24-model measured suite
> (3 reps x 4 chains each, Pathfinder inits, fixed seeds). The domain
> splits three ways. (1) A majority benefit class — 15 of 24 models,
> ESS-per-gradient 1.1x-3.9x (plus lotka_volterra at ~16x on a
> slow-median baseline) — spanning hierarchical regressions, IRT with
> hyperpriors, low-spend GLMs, the noncentered eight-schools funnel, a
> Gaussian mixture, and a stiff ODE; on these the guard stays silent
> (probe-uniqueness margin >= 38/50 vs the 25 threshold across every
> silent chain) and GMD is byte-identical to plain min-micro-2. (2) A
> minority economic-harm class — 4 of 24 (lsat, eight_schools_centered,
> blr, diamonds; 0.53-0.84x) — where the extra micro-steps buy no
> trajectory length; the guard is silent by design, so the feature
> remains default-off and per-model. (3) A pin class — 5 of 24 models,
> 21 chains — where min-micro-2 collapses a chain to a frozen point; the
> guard fires at exactly 1/50 unique draws on every one (zero misses in
> 288 guarded chains, zero false fires) and restarts in-process to
> min-micro 1: byte-identical to the unguarded baseline on all 13
> chains whose baseline was healthy (gpcm, pilots, bym2, accel), and
> arm-neutral on the 8 chains whose baseline init pins anyway
> (kronecker_gp, bym2, accel_gp) — a pre-existing init pathology the
> guard surfaces but cannot repair.

## Honest outliers and caveats

- **Degenerate baselines**: kronecker (A0 ESS 3-50, rhat>1.02 on
  ~2000-4400 cols), bym2 (~2.3, ~9600 cols), accel/pilots/diamonds
  (~2.3-2.5, 16-71 cols) — ESS_min is a slow/frozen coordinate in BOTH
  arms; their ESS/grad ratios are population statements about that
  coordinate, not whole-posterior health. kronecker's 1.97 has per-rep
  votes 0.56n/5.40Y/0.31n — ratio-of-medians artifacts on degenerate
  ESS; it is reported in the fire class, not claimed as benefit.
- **lotka 15.78**: median-of-reps lands on A0's sick rep (10.3); per-rep
  1.63Y/0.68n/22.51Y — MM2 heals reps 0/2 (rhat>1.02: 12→0, 78→0) but
  not rep1 (90 cols sick in both arms). Benefit is real (2/3 reps
  healed, grads ~parity 1.015x) but the 15.8 magnitude is a
  sick-median artifact; 1.63 (median of per-rep ratios) is the
  conservative read.
- **bym2 rep1 vote 314.97Y**: ratio of degenerate tiny ESS values
  (31.5 vs ~2.0 after the guard un-pins rep1's chains into a
  slightly-less-frozen state) — recorded, not meaningful as magnitude.
- **Wall**: GMD/A0 wall ratios 1.9-4.6 here are CROSS-SESSION (W-63
  idle vs W-84 under foreign load 10-17) — not evidence of anything;
  the reference guard-cost numbers stay W-82's within-session
  GMD/MM2 = 0.99-1.014 (silent) and 0.874 (gpcm, abort-after-probe).
- **Restart exactness**: on healthy-baseline pins the restart is
  md5-exact (6/6 here + 7/7 gpcm in W-82); on baseline-pinned chains it
  is exact to within one marginal Metropolis acceptance per 1000 draws
  (frozen chains amplify ULP differences; first rows identical). The
  guard's claims (detect + convert to MM1 behavior) hold in both cases.
- **election88** (W-82 caveat, unchanged): marginal, init-fragile
  baseline (A0 rhat>1.02 on 102 cols; per-rep 0.28/1.72/1.44).

## Paths

- Runs: `scratch/w84/runs/GMD/<model>/rep<r>_c<chain>.{csv,log}`
- Driver / analyzer / JSON / log: `scratch/w84/{driver.py,WORKERS}`,
  `scratch/w84/analyze_w84.py`, `scratch/w84/w84_results.json`,
  `scratch/w84/analyze.out`, `scratch/w84/driver.log`
- Binary-equivalence canary: `scratch/w84/canary/kronecker_rep0_c0_A0samebin.{csv,log}`
- Reused A0 grids: `scratch/w63/runs/A0/<model>/w1000_pf/`
- W-82 table being completed: `results/mm2_guard_w82.md`
