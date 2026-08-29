# W-109: the EVERYTHING-STACK ESS/s benchmark — S vs E vs E+ on all 21 CORE_SET models; first measurement of the composed posture (MM2 per-model × all-layers math) vs the recommended default; the definitive ESS/s table + residual-gap finder

Pre-registration: WORKLOG "W-109 PRE-REGISTRATION (before any run)".
Grid: 21 CORE_SET models × {S, E} × 3 reps × 4 chains (+ E+ on the
W-91-positive subset), 540/540 cells rc=0, ZERO aborts, ZERO retries,
22 min elapsed at 4 workers nice 19 (scratch/w109/driver.log). Machine
time: grid 1.21 h wall-sum (CLI-internal), + ~7 min builds, + ~5 min
spot/analysis ≈ 1.4 core-hours total.

## ARMS as run (and the three honest deviations from the pre-reg text)

- **S** = sampler `external/walnutpie_mm2guard/build_mg/examples/stan_cli`
  at DEFAULT flags × TRUE-STOCK .so (pristine
  `~/.bridgestan/bridgestan-2.9.0` bundle, default flags):
  `scratch/w81/quiet_stock/<m>/` (10, W-53/81 lineage, reused read-only)
  + `scratch/w109/quiet_stock/<m>/` (11, built pristine-default-flag).
- **E** = same binary × per-model MM2 posture × ALL-LAYERS .so (SoA
  math#5 + W-102 gather/index fix + W-103 log1p kernel +
  uniform `-mavx2 -mfma`, the W-106 recipe extended to all 21):
  `scratch/w106/model_<m>_alllayers/` (3, reused read-only) +
  `scratch/w109/model_<m>_alllayers/` (18, built; uniform-flag property
  verified — model .o AND bridgestan.o compiled `-mavx2 -mfma`,
  `build_logs/`).
- **E+** = E + `--max-hamiltonian-error 2.0` (the W-91 4x recorded
  value) on the W-91-positive subset {eight_schools_centered, hier_2pl,
  arma11} (esc +147%, hier_2pl +62%, arma11 +14% @4x in W-91).

Protocol both arms: w1000 s1000, pf inits per `scratch/w63/manifest.csv`
(12/12 rep/chain files verified for all 21 before run), seeds
20260819+1000·rep+chain, `--metric-window 50` (the W-63/82/84 reference
protocol constant — W-107 showed omitting it shifts hier_2pl-class GMD
2.6x; a protocol flag applied to BOTH arms, not a posture knob),
`env -u LD_LIBRARY_PATH`, OMP_NUM_THREADS=1, single chain per process,
arms interleaved per cell (S,E adjacent — load drift cancels inside
each comparison).

DEVIATIONS (all recorded, none silent):
1. **Sampler binary = build_mg, not the prescribed build_main.**
   build_main (built 03:32 today by another session, mid-modification
   worktree, no canary record in WORKLOG) LACKS `--init-file` and
   `--metric-window` — it cannot execute the pre-registered protocol.
   build_mg is the W-84 binary (branch robustness/mm2-guard), the one
   whose default-path stock-equivalence is canary-proven (W-82 36/36 +
   W-84 kronecker canary) and which ran the W-84 domain table this
   benchmark's MM2 list comes from.
2. **Ridge-guard is NOT in the E arm.** No binary on the box carries
   MM2-guard + ridge together (checked all 40 stan_cli builds: the ridge
   guard lives only in `external_w86` = branch exp/ridge-guard, which
   has no min-micro-guard; the assembly/combined-posture branch is
   orchestrator-#2's artifact and comms carries no reply releasing it).
   Using the w86 binary for E would break the same-binary S/E pairing
   AND drop the MM2 posture — so E runs without ridge, honestly, and
   the W-88/99 decomposition stands in (see Residual gaps: pilots/bym2/
   diamonds are exactly where it would bite).
3. **MM2 ON = the domain-table BENEFIT list ∩ CORE_SET = 13 models**
   (per the operative rule "MM2 iff model ∈ the W-84 benefit list,
   extract the 15" — 2 of the 15 are non-CORE supplementaries). OFF =
   8: the 4 economic-harm (lsat, eight_schools_centered, blr, diamonds)
   + the 4 fired/degenerate class (pilots, bym2_offset_only, accel_gp,
   kronecker_gp). For those 8, E-vs-S isolates the math layer.

## Staging verification (all green before the grid)

- **Determinism spot check 8/8 bit-exact**: the w36exp CLI + the w106
  alllayers .so + same seeds/inits reproduce `scratch/w106/ess_b/*/`
  alllayers csvs md5-EXACT (3 cells each for hier_2pl/kronecker/diamonds
  — `scratch/w109/spotcheck/`). Kronecker rep0_c0 (the known W-105b
  abort cell) ran CLEAN in this session on both arms.
- **S-arm archive consistency**: S ESS_min medians reproduce the W-84
  A0 archive within ruler-level expectations (radon_pp 220.8 vs 216.7,
  ldgm 792 vs 778.6, wells 769 vs 749.2, garch11 751 vs 747.1, arma11
  1028 vs 1022, 8sch_nc 1488 vs 1470, kidscore 276 vs 283; esc 106.6 vs
  W-92 stock 101). E reproduces the W-82/84 GMD values (hier_2pl 1489.5
  vs 1556.6, wells 1648 vs 1599, ldgm 1342 vs 1389, lotka 123.5 vs 165).
- **Zero guard fires** in the E arm (13 MM2 models × 36 chains — the
  W-84 prediction: fires live on the fired-class models, which are OFF).

## THE TABLE (ruler: blessed split `scratch/w88`; wall LOAD-FLAGGED)

ESS = ess_bulk_min rep-median (4 combined chains); wall = per-rep sum of
ALL per-chain 'total time:' stanzas (warmup+sampling), rep-median;
ESS/s = per-rep ESS/wall, rep-median. E/S full-wall is the headline;
sampling-only ratio in parens column. Wall/ESS-s are LOAD-FLAGGED:
foreign desktop + a sibling agent's compile ran throughout (driver
loadavg median 3.98, max 6.67 of 12 cores); arms interleaved per cell.

| model | MM2 | S ESS | E ESS | E+ ESS | ESS r | S wall | E wall | wall r | S ESS/s | E ESS/s | E/S (samp-only) | E+/E |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kronecker_gp | off | 14.9 | 13.2 | — | 0.89 | 74.1 | 61.9 | 0.84 | 0.20 | 0.21 | 1.09 (1.09) | — |
| hier_2pl | ON | 519.5 | 1489.5 | 1868.4 | 2.87 | 234.6 | 304.9 | 1.30 | 2.21 | 4.84 | 2.19 (2.01) | 1.47 |
| radon_partially_pooled_nc | ON | 220.8 | 371.0 | — | 1.68 | 72.5 | 120.1 | 1.66 | 3.05 | 2.76 | 0.90 (1.12) | — |
| bym2_offset_only | off | 4.4 | 4.4 | — | 1.00 | 56.0 | 37.2 | 0.67 | 0.08 | 0.12 | 1.50 (1.51) | — |
| dogs_hierarchical | ON | 1596.3 | 2421.2 | — | 1.52 | 3.3 | 3.9 | 1.18 | 450.70 | 651.04 | 1.44 (1.57) | — |
| gp_regr | ON | 2261.0 | 3807.9 | — | 1.68 | 0.4 | 0.4 | 1.11 | 6060.83 | 9001.49 | 1.49 (1.57) | — |
| lsat_model | off | 944.5 | 974.4 | — | 1.03 | 34.0 | 22.2 | 0.65 | 28.41 | 43.19 | 1.52 (1.47) | — |
| eight_schools_centered | off | 106.6 | 42.2 | 61.0 | 0.40 | 0.1 | 0.1 | 0.94 | 906.59 | 372.38 | 0.41 (0.45) | 1.69 |
| blr | off | 350.5 | 395.5 | — | 1.13 | 0.6 | 0.5 | 0.87 | 512.66 | 621.01 | 1.21 (1.43) | — |
| low_dim_gauss_mix | ON | 792.1 | 1341.8 | — | 1.69 | 21.4 | 26.4 | 1.24 | 38.71 | 48.47 | 1.25 (1.69) | — |
| diamonds | off | 4.5 | 4.3 | — | 0.97 | 14.6 | 10.2 | 0.70 | 0.30 | 0.42 | 1.41 (1.48) | — |
| lotka_volterra | ON | 10.5 | 123.5 | — | 11.78 | 15.8 | 17.9 | 1.13 | 0.66 | 7.39 | 11.16 (16.44) | — |
| radon_variable_slope_nc | ON | 254.3 | 415.0 | — | 1.63 | 7.8 | 10.4 | 1.34 | 30.75 | 35.38 | 1.15 (1.09) | — |
| accel_gp | off | 4.4 | 4.6 | — | 1.03 | 5.2 | 4.4 | 0.84 | 0.89 | 1.05 | 1.18 (1.05) | — |
| wells_dist100_model | ON | 769.1 | 1648.4 | — | 2.14 | 3.2 | 2.7 | 0.85 | 236.69 | 615.40 | 2.60 (3.34) | — |
| garch11 | ON | 751.2 | 1234.3 | — | 1.64 | 2.2 | 2.5 | 1.15 | 366.36 | 532.53 | 1.45 (1.64) | — |
| kidscore_momiq | ON | 276.2 | 407.7 | — | 1.48 | 0.6 | 0.7 | 1.04 | 426.69 | 640.51 | 1.50 (1.90) | — |
| pilots | off | 4.6 | 4.4 | — | 0.96 | 0.5 | 0.4 | 0.73 | 8.43 | 11.14 | 1.32 (1.50) | — |
| arma11 | ON | 1027.8 | 1453.9 | 1485.0 | 1.41 | 0.5 | 0.6 | 1.15 | 1938.90 | 2484.79 | 1.28 (1.31) | 1.20 |
| logmesquite_logvash | ON | 94.8 | 197.2 | — | 2.08 | 0.3 | 0.3 | 0.92 | 279.77 | 635.35 | 2.27 (2.75) | — |
| eight_schools_noncentered | ON | 1487.6 | 1937.4 | — | 1.30 | 0.1 | 0.1 | 0.96 | 17194.64 | 22525.19 | 1.31 (1.37) | — |

## GEOMEANS

- **E/S ESS/s = 1.485x** (full wall) / **1.637x** (sampling-only);
  ESS ratio 1.467x; wall ratio 0.982x. S ESS/s geomean 38.81,
  E 57.61.
- Split by posture: **MM2-ON 13** — ESS ratio 2.00x, wall ratio 1.14x,
  ESS/s 1.75x. **MM2-OFF 8 (math layer only)** — ESS ratio 0.89x, wall
  ratio 0.77x, ESS/s 1.13x.
- **E+ vs S = 1.508x geomean (n=3); E+ vs E = 1.438x** — the third
  family stacks multiplicatively on its subset: hier_2pl E+/E 1.47
  (ESS 1489→1868, ESS/s 4.84→7.11), arma11 1.20 (wall DOWN — cap
  relaxation truncates fewer trajectories), esc 1.69 (372→630 ESS/s,
  recovering most of its math-layer ESS drop).

## THE HEADLINE VERDICT vs the pre-registered expectation

**EXPECTATION MISSED (1.485x measured vs 2.5-6x pre-registered)** — and
the miss is structural, not noise. The expectation's 1.5-3x "posture
quality" factor describes posture-vs-no-posture, but the pre-registered
S arm ALREADY CONTAINS the protocol posture (pf inits + metric-window
50) by construction — S is "the recommended-default sampler state", and
the recommendation includes the init/protocol package. What E/S
actually isolates here is MM2 × math-layer only. Both real levers did
fire (ON-13 ESS ratio 2.0x; math layer −23% wall on the OFF-8), but
(1) MM2 pays its ESS in grads (ON-13 wall +14%), halving the net ESS/s
of its own ESS gain, and (2) the ridge guard — the third sampler-side
lever and the one that fixes the ridge-locked floor models — is not
composable into a single binary yet (deviation 2). With ridge composed
and on its W-88/99 domain, pilots/bym2/diamonds/accel (currently ESS~4-5,
rhat-fails identical S=E) are the models that move; a composed
everything-stack E/S geomean in the 2-3x range is the honest projection,
consistent with W-88's +57% aggregate geoESS on top of this E.

## RESIDUAL GAPS — E/S ESS/s < 2x (17 of 21), each with its recorded WHY

(next-lever finder; sorted by ratio)
- **eight_schools_centered 0.41x** — MM2 OFF (economic-harm 0.56 W-84);
  the E cell's ESS drop is the math layer's last-ulp trajectory change
  hitting esc's fragile tau-ESS (the W-92 stack-sensitivity class:
  esc ESS moved 101↔26 between stacks at identical config); per-rep S
  [110.9/106.6/83.4] vs E [62.7/39.8/42.2] — consistent, not one sick
  rep. E+ recovers 1.69x of it. Next lever: the cap knob (W-90 H-neck).
- **radon_partially_pooled_nc 0.90x** — MM2's grad spend (wall 1.66x)
  exceeds its ESS surplus (1.68x; W-84 ESS/grad only 1.23). Next lever:
  MM2 only where ESS/grad > wall-ratio, i.e. a sharper benefit list.
- **kronecker_gp 1.09x** — W-35 eigenvector-adjoint amplification: the
  O(1) sparse gradient components that set ESS_min are untouchable by
  the math layer (W-105b per-block parity); degenerate ESS 3-50 both
  arms (W-84). Next lever: none at this layer; model-numerics class.
- **radon_variable_slope_nc 1.15x** — MM2 ESS/grad 1.11 (W-84):
  near-neutral posture on this variant.
- **accel_gp 1.18x** — MM2 OFF (fired mixed + 0.53 economic-harm
  W-84); ridge-locked ESS~4.4 with rhat-fails 72 S=E. Ridge lever.
- **blr 1.21x** — MM2 OFF (0.84 W-84); cap-saturated spendy baseline
  (W-92's E+-family lever).
- **low_dim_gauss_mix 1.25x** — slow sigma decorrelation at the true
  mode (W-90): trajectory-budget family, orthogonal to both layers.
- **arma11 1.28x** — near-ceiling ESS (1454 of 4000): ratios compress
  at the ceiling; E+ still buys 1.20x via wall.
- **eight_schools_noncentered 1.31x** — easy model, S already mixes
  (ESS/grad 1.29 W-84): little posture headroom.
- **pilots 1.32x** — MM2 OFF (fired class 0.98 W-84); ridge-locked
  ESS~4.5, rhat-fails 16 S=E. THE ridge-guard exhibit (W-88: ESSmin
  4.6→33).
- **diamonds 1.41x** — MM2 OFF (0.69 W-84); ridge-locked ESS~4.5
  (W-105b both arms); init/mode-separation disease, not math.
- **dogs_hierarchical 1.44x** — MM2 ESS/grad 1.62 (W-84) but grad
  spend ~1.6x eats it.
- **garch11 1.45x** — MM2 surplus small (1.32 W-84); marginal class.
- **gp_regr 1.49x** — MM2 ESS/grad 1.53 (W-84); same spend pattern.
- **kidscore_momiq 1.50x** — small GLM, S already high; modest absolute
  headroom (sampling-only 1.90x).
- **bym2_offset_only 1.50x** — MM2 OFF (fired 1.00 W-84); A0-inherent
  init-pathology pins (W-84); ridge +145% (W-88) is the lever.
- **lsat_model 1.52x** — MM2 OFF (0.56 W-84); cap-saturated baseline
  (W-92 +37% @4x — E+-family lever, out of E scope).
- (Above 2x: hier_2pl 2.19x, logmesquite 2.27x, wells 2.60x,
  lotka 11.16x — the MM2-surplus class with wall headroom.)

## Arm-neutral pathologies (unchanged S→E, as the records predict)

rhat>1.02 rep-medians identical or near-identical on the ridge-locked
floor models — bym2 9610=9610, accel 72=72, pilots 16=16, diamonds
17=17 (ridge-locked in both arms; the guard/ridge levers are the fix,
not the math layer); kronecker ~2017→2150 (degenerate both arms).
MM2 HEALS where predicted: lotka rhat-fails 90→4 (2/3 sick reps healed;
per-rep ESS S [61.1/7.1/10.5] → E [132.3/7.1/123.5]), radon_pp 1→0,
kidscore 1→0, logmesquite 4→2.

## Paths

- Grid: `scratch/w109/runs/{S,E,E+}/<model>/rep{r}_c{c}.{csv,log}`
- Driver/analyzer/results: `scratch/w109/driver_w109.py`,
  `scratch/w109/analyze_w109.py`, `scratch/w109/w109_results.json`
- Builds: `scratch/w109/build_alllayers.sh`, `build_stock.sh`,
  `build_logs/`, `model_*_alllayers/`, `quiet_stock/`
- Spot checks: `scratch/w109/spotcheck/` (8/8 md5 match)
- Comms: grid announce (15:42) + close-out notice
- Machine time: grid 1.21 h wall-sum, 22 min elapsed (4 workers);
  builds ~7 min; total session ≈ 1.4 core-hours
