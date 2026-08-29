<!-- ======================================================================
     CORRECTION — DO NOT FILE ANY ISSUE FROM THIS FILE.
     The F-2b "upstream-issue candidate 2" (diamonds missing the student_t
     sigma jacobian on the unconstrained scale) is REFUTED by direct
     measurement on our compiled model_diamonds.so (Stan 2.39.0 /
     bridgestan 2.9.0) and by reading the actual stan-math source. The
     compiled model, stanc3 codegen, and the posteriordb model are all
     CORRECT. The F-2b agent (me, earlier today) mis-derived: the "+1
     gradient offset" WAS the transform jacobian (present in the .so,
     missing from my hand formula), and the "-log(sigma)" term I expected
     from student_t_lpdf does not exist for this model because sigma is
     the RESPONSE argument of the prior, not the scale.
     Kept as the evidence trail for why WORKLOG "upstream-issue candidates"
     item 2 must NOT be filed. WORKLOG correction is the only follow-up.
     ====================================================================== -->

# [DO NOT FILE] diamonds "missing sigma jacobian" — investigated and REFUTED

## The claim under test

WORKLOG.md "F-2b VERDICT" upstream-issue candidate 2:

> diamonds (posteriordb reference model) appears to omit the student_t
> -log(sigma) term on the unconstrained scale (measured exactly +1 gradient
> offset; source suggests it should be present).

Two separable assertions had to be checked:

1. The compiled model's unconstrained logp is missing the `<lower=0>` transform
   jacobian `+log(sigma)` (d/d sigma_unc = +1).
2. The compiled model's unconstrained logp is missing a `-log(sigma)` term that
   `student_t_lpdf` allegedly contributes ("source says it should").

**Both are false.** What F-2b actually measured ("bs grad[sigma_unc] =
mine + 1.000000 exactly", logs/fortk-f2b.md item 3 of the derivation war log)
was their own prototype omitting the jacobian, not the compiled model omitting
a term.

## What the model actually is

`external/posteriordb/posterior_database/models/stan/diamonds.stan`
(byte-identical to our `models/diamonds.stan`, verified with `diff`;
brms 2.10.0-generated, posteriordb `models/info/diamonds.info.json`):

```stan
parameters {
  vector[Kc] b;
  real Intercept;
  real<lower=0> sigma;   // the ONLY constrained parameter
}
model {
  target += normal_lpdf(b | 0, 1);
  target += student_t_lpdf(Intercept | 3, 8, 10);
  target += student_t_lpdf(sigma | 3, 0, 10)
            - 1 * student_t_lccdf(0 | 3, 0, 10);
  if (!prior_only) {
    target += normal_id_glm_lpdf(Y | Xc, Intercept, b, sigma);
  }
}
```

`sigma` is the **response** (first) argument of `student_t_lpdf`; the **scale**
argument is the data constant 10. The `student_t_lccdf` term is brms's
half-Student-t normalization (constant, makes the prior on the constrained
space proper) — a legitimate modeling choice, nothing to report.

## What the unconstrained logp should be (reference-manual semantics)

For `real<lower=0> sigma` Stan uses `sigma = exp(sigma_unc)` and adds the
change-of-variable term `log|d sigma / d sigma_unc| = sigma_unc = log(sigma)`
(Stan Reference Manual, "Lower Bound Transform" / sampled-density-on-the-
unconstrained-scale definition). So:

```
lp_unc(b, Intercept, s) = normal_lpdf(b|0,1) + student_t_lpdf(Intercept|3,8,10)
  + [student_t_lpdf(exp(s)|3,0,10) - student_t_lccdf(0|3,0,10)]
  + normal_id_glm_lpdf(Y|Xc,Intercept,b,exp(s)) + s
```

`student_t_lpdf(y|nu,mu,scale)` contributes `-log(scale) = -log(10)` — a
constant w.r.t. the parameter — plus `-(nu+1)/2 * log1p(((y-mu)/scale)^2/nu)`.
There is **no** `-log(sigma_param)` anywhere. Source,
`external/stanli/deps/math/stan/math/prim/prob/student_t_lpdf.hpp`:
line 96 `square_y_scaled = square((y_val - mu_val) / sigma_val)` (response
enters here; `sigma_val` = scale = 10), lines 114–116
`if constexpr (include_summand<propto, T_scale>::value) logp -=
sum(log(sigma_val)) * N / math::size(sigma);` — `sigma_val` is the scale
argument, i.e. `-log(10)`, included as a constant since stanc3 emits the full
(non-propto) lpdf. The F-2b misreading was mapping the source's `sigma`
(the scale) onto the model's `sigma` (the response).

## Direct measurement on the compiled model (decisive)

`bs_models/model_diamonds.so` (built by harness/compile_bridgestan.py,
bridgestan 2.9.0 / Stan 2.39.0), data `data/diamonds.json`, 8 seeded points
(seed 20260826), unconstrained layout `[b.1..b.24, Intercept, sigma_unc]`
(dim 26; `sigma_unc` = coordinate 25):

- **Gradient** `jacobian=True` minus `jacobian=False`: exactly
  `+1.000000000000000` in coordinate 25 and `0` (to 1e-13) in all 25 others,
  at every point. That is precisely d/d sigma_unc [+sigma_unc] — **the
  transform jacobian is present**; a present-but-cancelling `-log(sigma)`
  term would have made the difference 0, an absent jacobian 0 as well.
- **Value** `jacobian=True` minus `jacobian=False` equals `sigma_unc` to
  1.1e-17–7.2e-17 *relative* (|lp| ranges 1.8e4–3.1e7 at these points; the
  1e-12–7e-10 absolute deviations are double-precision summation-order
  rounding, since the two arms add `sigma_unc` at different points in the
  reduction).
- The response-side t-prior gradient composes as the source says:
  `d/ds [-2*log1p(sigma^2/300)] = -4*sigma^2/(300+sigma^2)` plus `+1`
  (jacobian) plus the glm part; measured `g[25]` decomposes exactly this way
  (probe below), i.e. there is no unexplained `±1` anywhere.

Corroboration: F-2b's own final hand-fused formula — which *included* the
jacobian (`lp += s`, `g[25] += +1`) and the t-prior response term
`-2*log1p(sigma^2/300)` and the constant `-log(10)` inside `2*C_t` — matched
the compiled model's logp to 1.136e-14 and gradient to 5.4e-15 across 64
seeded points (logs/fortk-f2b.md "FINAL prototype status"). A model missing
its jacobian cannot match that formula.

## Conclusion / follow-up

- **No upstream issue.** Not against stan-dev/math, not against stanc3, not
  against posteriordb. The only artifact is in our own WORKLOG: "F-2b VERDICT"
  upstream-issue candidate 2 should be struck / annotated as refuted, so it is
  not picked up again by a future lane.
- The earlier F-2b sentence "student_t_lpdf ... does NOT contribute -log(sigma)
  on the unconstrained scale" is *correct behavior*, not an anomaly: the `-log`
  term belongs to the scale argument (data 10), not the response.

## Verification (exact repro)

```
cd /home/m0hawk/Documents/apin/stan && uv run python - <<'EOF'
import numpy as np, bridgestan
m = bridgestan.StanModel('bs_models/model_diamonds.so', 'data/diamonds.json')
rng = np.random.default_rng(20260826)
for i in range(8):
    x = rng.standard_normal(26)
    lj, gj = m.log_density_gradient(x, jacobian=True)
    ln, gn = m.log_density_gradient(x, jacobian=False)
    dlp, dg = lj - ln, gj - gn
    nz = np.flatnonzero(np.abs(dg) > 1e-13)
    print(i, "lp diff - sigma_unc:", dlp - x[25], "(rel %.1e)" % (abs(dlp-x[25])/max(abs(lj),abs(ln))),
          "| grad-diff coords:", nz.tolist(), "dg[25]:", dg[25])
EOF
# expect: coords == [25], dg[25] == 1.000000000000000, lp diff == sigma_unc to ~1e-17 rel

diff external/posteriordb/posterior_database/models/stan/diamonds.stan models/diamonds.stan   # no output = identical
grep -n "real<lower=0> sigma" models/diamonds.stan                                          # line 26
grep -n "log(sigma_val)\|square_y_scaled" external/stanli/deps/math/stan/math/prim/prob/student_t_lpdf.hpp  # lines 96, 114-116
```

Re-verified 2026-08-26. Evidence sources: logs/fortk-f2b.md (derivation war
log items 3–4, final prototype status), WORKLOG.md "F-2b VERDICT", live probes
of bs_models/model_diamonds.so, stan-math source at
external/stanli/deps/math @ v5.3.0-117-g8f326d1459.
