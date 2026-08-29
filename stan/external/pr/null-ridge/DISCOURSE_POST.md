# walnutpie locks on likelihood-null ridges — reproducible on stock v0.0.2, invisible to log-density diagnostics

We found a failure mode that affects walnutpie on a class of Stan models,
reproduced it on the stock python package, and traced both the mechanism
and the fix. This post gives the model, the one-file repro, the numbers,
and a fix direction that works.

## The model class

`pilots.stan` (posteriordb; centered hierarchy) predicts with
`y_hat[i] = a[group[i]] + b[scenario[i]]` and priors
`a ~ N(10·mu_a, sigma_a)`, `b ~ N(10·mu_b, sigma_b)`, `mu ~ N(0, 1)`.

This posterior has an exact null direction. For any `s`:

```
a += s·1,  b -= s·1,  mu_a += s/10,  mu_b -= s/10
```

leaves `y_hat` and every prior term unchanged. Only the two N(0,1)
hyperpriors constrain it: the marginal sd along the ridge is ≈ 7 in
a-scale (0.7 in mu_a). Any model with an additive group/scenario split
has this direction.

## What stock walnutpie does (v0.0.2, seed 20260819, 4 chains, 1000+1000)

```
per-chain ESS(mu_a):  [3.3, 1.3, 3.0, 1.7]
chain means of mu_a:  [0.084, 0.588, 0.397, -0.279]   (within-chain sd 0.042)
ridgeF:               7.8      (cross-chain dispersion / within-chain sd)
rhat(mu_a):           3.87
a.1+b.1 per chain:    [0.342, 0.332, 0.340, 0.339]    <- identical
```

Each chain freezes at its own ridge point for the whole run. The four
chains report four different posteriors — while the likelihood-invariant
sums agree to three decimals. The fit "looks fine" per-chain; only
cross-chain comparison shows the break.

## Why the usual diagnostics miss it

The log density is exactly invariant along the ridge. Divergences do not
appear. Anything keyed on log-mass (accept stats, energy, cross-chain
log-mass dispersion) is structurally blind. Position statistics are not:
dispersion of chain means vs within-chain sd separates cleanly — in our
21-model benchmark this statistic sits at 2–5 for healthy fits and
8–16,000 for locked ones.

## The binding constraint is trajectory length, not the metric

With one parameter changed — `min_micro_steps=128` in the same stock API:

```
per-chain ESS(mu_a):  [26.7, 25.2, 20.0, 22.3]
chain means of mu_a:  [-0.005, -0.004, 0.015, 0.276]  (within-chain sd 0.761)
ridgeF:               0.2
rhat(mu_a):           1.02
```

The chains traverse and co-locate. We also tested the alternative
hypothesis — that the adapted diagonal metric collapses onto the
within-lock variance and a metric variance floor would fix it — and
refuted it: long trajectories traverse despite the collapsed mass.
(CmdStan reaches the same place the expensive way: 136–170 gradient
evals/draw on this model vs walnutpie's 8–37.)

## Fix direction that works for us

Detect: after warmup, compute per-coordinate cross-chain dispersion of
chain-mean positions against the adapted within-chain scale. Respond:
raise the frozen trajectory budget, scaled to the misfit. On our fork
this guard adds +57% aggregate bulk-ESS on a 10-model benchmark with
zero harmed models and bit-identical output on unaffected runs; locked
models go from rhat 3–4.4 to 1.0–1.5. Out-of-sample on 11 further
models: zero false positives.

Happy to share the detector/graduated-budget patch and the full
benchmark data. The one-file repro (model + script + expected output,
pure upstream API) is here: [reprex attached].

— Maximilian Scholz (sims1253)
