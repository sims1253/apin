<!-- DRAFT issue body for https://github.com/stan-dev/math/issues/new — local draft only, human reviews and files.
     Pinned evidence: logs/fortk-f2b.md item 5 (hier_2pl residual dissection); all numbers below re-verified 2026-08-26. -->

# bernoulli_logit_lpmf reverse-mode gradient has the wrong sign in the saturated tail for y = 1

## Summary

In `bernoulli_logit_lpmf`, the reverse-mode partial (adjoint) for the saturated
upper branch (`ntheta > cutoff`, i.e. the observation is on the "correct" side of
a large logit) is missing the `signs = (2y − 1)` factor. It returns
`-exp(-ntheta)` unconditionally, which is the correct derivative only for
`y = 0`. For `y = 1` the true derivative is **+**`exp(-ntheta)`, so the returned
adjoint has the opposite sign. The value path (`logp`) is correct in both tails;
only the gradient is wrong.

## Current behavior

`stan/math/prim/prob/bernoulli_logit_lpmf.hpp` (develop, fetched 2026-08-26),
lines 81–90:

```cpp
  if constexpr (is_autodiff_v<T_prob>) {
    edge<0>(ops_partials).partials_
        = (ntheta > cutoff)
              .select(
                  -exp_m_ntheta,                        // <-- missing `signs *`
                  (ntheta >= -cutoff)
                      .select(promote_scalar<T_partials_return>(
                                  signs * exp_m_ntheta / (exp_m_ntheta + 1)),
                              promote_scalar<T_partials_return>(signs)));
  }
```

All three branches of the exact derivative below carry `signs`; the
`ntheta > cutoff` branch alone drops it. The same omission is in the OpenCL
variant, `stan/math/opencl/prim/bernoulli_logit_lpmf.hpp` lines 65–68
(`select(condition1_expr, -exp_m_ntheta_expr, ...)`).

## Expected behavior

With `lp(theta) = y*theta − log1p(exp(theta))`,

```
d lp / d theta = y − sigmoid(theta)
```

In terms of `ntheta = (2y−1)*theta` this is exactly:

```
ntheta >  cutoff:  (2y−1) * exp(−ntheta)
|ntheta| <= cutoff: (2y−1) * exp(−ntheta) / (1 + exp(−ntheta))
ntheta < −cutoff:  (2y−1)
```

so the upper branch should be `signs * exp_m_ntheta`, not `-exp_m_ntheta`.
Two internal consistency checks that make the bug self-evident from the source:

- Differentiating Stan's *own* value approximation for that region,
  `logp = −exp(−ntheta)` with `ntheta = (2y−1)*theta`, gives
  `d/dtheta = (2y−1) * exp(−ntheta)` — the sign factor is present even in the
  derivative of the tail approximation the same function uses.
- The middle and lower branches (lines 87–89) both multiply by `signs`; only the
  upper branch does not.

Empirically the adjoint is also discontinuous at the cutoff for `y = 1`: the
gradient jumps from `+exp(−20)` to `−exp(−20)` as `ntheta` crosses 20
(measured jump `2.0611536e-09 → −2.0590935e-09` around `theta = 20.001`; see
repro below).

## Reproducible example

Minimal model (compiled with BridgeStan 2.9.0 / Stan 2.39.0, stanc3 v2.39.0,
default flags):

```stan
parameters {
  real theta;
}
model {
  target += bernoulli_logit_lpmf(1 | theta);
}
```

`theta = 25` (`ntheta = 25 > cutoff`, `y = 1`):

| quantity | value |
|---|---|
| AD gradient (`log_density_gradient`) | `-1.3887943864964021e-11` |
| central FD of `log_density` (value path, h = 1e-6) | `+1.3887943879676595e-11` |
| true derivative `1/(1+exp(25))` | `+1.3887943864771144e-11` |
| `-exp(-25)` (what the branch returns) | `-1.3887943864964021e-11` |

The AD gradient equals `-exp(-theta)` to the last digit — an exact sign flip
of the true derivative, which the (correct) value path reproduces by finite
differences. For `y = 0` (`bernoulli_logit_lpmf(0 | theta)`, `theta = -25`,
same saturation region) the AD gradient is `-1.3887943864964021e-11` and
matches FD and the analytic value — that branch is correct, which is why
tests that only probe one sign of the tail (or modest theta) miss it.

Python one-liner after compiling the model above (`bridgestan.compile_model`):

```python
import math, numpy as np, bridgestan
m = bridgestan.StanModel("blr_sat_model.so")
for theta in (25.0, 30.0, 40.0):
    lp, g = m.log_density_gradient(np.array([theta]))
    h = 1e-6
    fd = (m.log_density(np.array([theta+h])) - m.log_density(np.array([theta-h]))) / (2*h)
    print(theta, "AD:", g[0], "FD:", fd, "true:", 1/(1+math.exp(theta)))
# theta=25.0 AD: -1.3887943864964021e-11 FD: 1.3887943879676595e-11 true: 1.3887943864771144e-11
# theta=30.0 AD: -9.3576229688401748e-14 FD: 9.3576229786538304e-14  true: 9.3576229688392989e-14
# theta=40.0 AD: -4.2483542552915889e-18 FD: 4.2483542445653948e-18  true: 4.2483542552915889e-18
```

## Magnitude and impact

Per-term error is bounded by `exp(−20) ≈ 2.06e-9` (plus the `2*exp(−20)`
discontinuity at the cutoff for `y = 1`), so individual gradients are barely
affected — this is not a numerical-stability emergency. But the error is
*systematic*, not noise: every well-classified `y = 1` observation contributes a
negative pull on its logit instead of a positive one, and the gradient of the
saturated tail is directionally wrong wherever it is not negligible. Real models
hit this routinely:

- IRT / Rasch upper asymptote: items a strong respondent answers correctly
  every iteration (`sat-hier_2pl` from posteriordb: 7,117 saturated terms across
  64 random reference points, i.e. 0.6% of 19,200 observations).
- Well-separated classifiers / separable logistic regression: perfect
  prediction is exactly the `ntheta > 20` regime, and there the tail gradient is
  the *only* signal left in the likelihood.

It also silently breaks any consumer that compares adjoints against
finite-difference references at large logits (we found it as an unexplained
~1e-8-scale residual when validating a hand-fused gradient of `hier_2pl`
against Stan 2.39.0; replicating Stan's branch structure to 7.6e-16 confirmed
the source of the discrepancy).

## Version / history

- Present in `stan-dev/math` develop as of 2026-08-26 (`prim/prob/bernoulli_logit_lpmf.hpp` line 85) and in the OpenCL variant (`opencl/prim/bernoulli_logit_lpmf.hpp` lines 65–68).
- Present in Stan 2.39.0 / math shipped with BridgeStan 2.9.0 (verified in the compiled model above; source at `stan/lib/stan_math/stan/math/prim/prob/bernoulli_logit_lpmf.hpp` lines 82–86).
- Old: the Taylor tail branches with the missing sign factor predate the `_lpmf` file itself — `stan/math/prim/scal/prob/bernoulli_logit_log.hpp` at tag `v2.7.0` (2015-07-08) already reads `operands_and_partials.d_x1[n] -= exp_m_ntheta;` while the other two branches carry `sign`. The logic was copied into `bernoulli_logit_lpmf.hpp` when the `_log` functions were deprecated (Nov 2016), and survived the 2020 vectorized rewrite (PR #1925) into the current Eigen-select form. Verified present in every release tag we sampled: v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.14.0, v2.19.1, v4.6.0, v5.0.0, v5.3.0 — i.e. every Stan/math release since at least mid-2015.

The existing unit tests miss it because the autodiff fixtures probe modest
`|theta|` (mid branch) and use FD-reference tolerances loose relative to 1e-9
absolute on quantities that are themselves ~1e-11 in the tail.

## Suggested fix

One line in each file — multiply the upper branch by `signs`:

```cpp
edge<0>(ops_partials).partials_
    = (ntheta > cutoff)
          .select(signs * exp_m_ntheta,   // was: -exp_m_ntheta
                  ...);
```

(and `select(condition1_expr, elt_multiply(signs_expr, exp_m_ntheta_expr), ...)`
in the OpenCL variant). This restores continuity with the mid branch at
`ntheta = cutoff` for both `y` and matches the exact derivative
`y − sigmoid(theta)` up to the existing `O(exp(−2*ntheta))` tail-approximation
error.

## Verification (for the filer)

All of the above was re-verified on 2026-08-26 on this machine:

1. Math: `d/dtheta [y*theta − log1p(exp(theta))] = y − sigmoid(theta)`;
   tail asymptotics `y=1, theta→+∞ ⇒ +exp(−theta)`, `y=0, theta→−∞ ⇒ −exp(−theta)`
   (confirmed symbolically with SymPy and numerically by FD of the value path).
2. Source (local, pinned):
   - vendored math `v5.3.0-117-g8f326d1459`: `external/stanli/deps/math/stan/math/prim/prob/bernoulli_logit_lpmf.hpp` lines 81–90 (bug at line 85), OpenCL variant lines 65–68;
   - Stan 2.39.0 copy: `~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/stan/math/prim/prob/bernoulli_logit_lpmf.hpp` lines 81–87 (bug at line 83);
   - upstream develop fetched 2026-08-26 to `/tmp/upstream_bernoulli_logit_lpmf.hpp` (bug at line 85) — NOT yet fixed upstream.
3. Empirical: repro models at `/tmp/orwell_repro/blr_sat.stan` and `blr_sat0.stan`
   compiled with the local bridgestan 2.9.0; run:

   ```
   cd /home/m0hawk/Documents/apin/stan && uv run python /tmp/orwell_repro/repro.py
   ```

   (script contents inline in the Reproducible-example section above; prints the
   AD-vs-FD-vs-analytic table for y=1, y=0, and the cutoff discontinuity sweep).
4. History: release-tag sweep over the vendored math clone
   (`git show <tag>:stan/math/prim/scal/prob/bernoulli_logit_log.hpp` for
   pre-2017 tags — the `_log`/`_lpdf` split dates to Nov 2016 — and
   `.../prim/prob/bernoulli_logit_lpmf.hpp` for later ones) shows the
   `-exp_m_ntheta` adjoint at `ntheta > cutoff` in v2.7.0 … v5.3.0 and
   absent only in tags that predate the file; develop fetched 2026-08-26
   still affected.
