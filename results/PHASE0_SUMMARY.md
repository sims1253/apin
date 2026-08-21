# Phase 0 results — baselines on CORE_SET (21 posteriordb models, 3 reps, median)

Protocol: 4 chains x (1000+1000), default NUTS, CmdStan 2.39.0, Ryzen 9 5900X
(4 cores used), seeds 20260819+1000r. ESS = rank-normalized ESS_bulk (posterior 1.7).
Full tables: results/table_per_model.csv, table_per_config.csv.

## Headline table (geomean over models)

| baseline | wall vs default | ESS/s vs default | ESS/grad vs default | quality flags |
|---|---|---|---|---|
| cmdstan default | 1.00 | 1.00 | 1.00 | 4 models rhat>1.01 (pilots 1.10, radon 1.02, kronecker 1.010, bym2 1.013) |
| cmdstan --Oexperimental | 0.94x wall (1.03x faster) | 0.97x | 0.98x | **BROKEN on 4/21**: 3 uncompilable, 1 silent miscompile (Eigen resize assert; would corrupt w/ NDEBUG). Not shippable. |
| nutpie 0.16 (nuts-rs, bridgestan 2.9 = same Stan 2.39 math) | 1.21x faster | 0.98x | 0.38x | 4 models rhat>1.01 (incl bym2 1.60 one rep, pilots 1.38) |
| walnutpie 0.0.1 (WALNUTS defaults) | 1.73x faster | 0.107x | 0.06x | **17/21 models rhat>1.01 (up to 9.45)** — unusable at defaults; kept as attribution probe |

## The nutpie "2x", localized

- Wall speedup geomean 1.21x (range 0.63x-4.8x). NOT 2x on this set.
- **Per-gradient cost: nutpie is 2.6x cheaper (geomean; 3.3x for models >10µs/grad):
  hier_2pl 585->134 µs/grad, radon 480->92, lsat 140->35, diamonds 16->5.**
  Same Stan 2.39.0 model math via bridgestan — so the difference is per-gradient
  implementation overhead in the cmdstan path. This is the Phase 1 target.
- But nutpie converts gradients to ESS less efficiently (ESS/grad 0.38x, ESS 0.82x):
  quality-adjusted wall (ESS/s) is a WASH (0.98x). The "2x" is real only before
  quality adjustment, and only per-gradient.

## Other Phase 0 facts

- Warmup = 52.7% of sampler wall (median, models >1s); radon_partially_pooled 77%.
- kronecker_gp: 99.5% of iterations hit maxdepth=10 (731s median; ESS 944).
- pilots: 11-17% divergences, ESS_bulk_min 40, rhat 1.10 (pathological rep confirmed).
- eight_schools_centered: funnel — cmdstan rhat 1.06 / ESS 55; nutpie 3.5x ESS.
- Run-to-run noise: wall CV ~2-5% (big models), ESS CV up to 99% on pathological
  models (eight_schools_centered), 15-25% typical.
- CmdStan service overhead measured indirectly (walnutpie logp_grad fraction
  0.91-0.99 with bridgestan backend): with a lean driver, gradient math is nearly
  all the wall — so cmdstan's µs/grad gap vs bridgestan sits in the gradient path
  itself (AD arena/allocs/checks/Eigen codegen), to be split by Phase 1.
