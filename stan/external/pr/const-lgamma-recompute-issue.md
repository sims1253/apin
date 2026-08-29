# Constant-data terms in `target +=` likelihoods are recomputed on every gradient evaluation

Paste-ready issue text (stan-dev/math or stan-dev/stan — the fix most
naturally lives in stanc3's optimizer; the measurements are math-side).
Filed by the user, never by agents. Evidence: results/family_census_w121.md,
results/poisglm_fused_w122.md; header line refs verified against the
bridgestan 2.9.0 / stan-math 5.3.0 bundle.

---

**Body:**

For count-model likelihoods written with `target +=` (the form brms
generates for every model), terms that depend only on the data are
recomputed from scratch on every call to the log density — which means
every leapfrog step, every adaptation iteration, every gradient
evaluation of the whole run.

The clearest case is `binomial_logit_glm_lpmf`, where
`lgamma(n + 1) + lgamma(N - n + 1)` over constant `n` and `N` accounts
for roughly 45% of the function's forward instructions at N=12,573
(measured with callgrind; 350 of ~798 Ir per element). The same
pattern appears in `poisson_log_glm_lpmf` (`lgamma(y + 1)`, ~44% of
the family interior with the frame) and `neg_binomial_2_log_glm_lpmf`
(~22%). Under a sampling statement (`~`, propto) these terms are
already dropped — the `include_summand<propto>` gating is correct.
The cost is specific to the explicit `target += ..._lpdf/lpmf(...)`
form, which is what brms emits for the model block, so this is the
default posture of the largest user base.

These terms are invariant across the entire run: the arguments are
data, loaded once. Recomputing them per gradient evaluation spends
transcendental-function budget — the most expensive kind, and the kind
SIMD widths don't help — on values that never change.

Two remedies, both compatible with current semantics:

1. **Compute the constant once, re-add it per evaluation (best of both,
   near-free).** The constant is data-only, so it can be hoisted to
   transformed data (one pass over the data at load) and added to the
   accumulated target as a single precomputed term — one addition per
   log-density call instead of a transcendental pass per element per
   gradient evaluation. The likelihood line then runs in its propto
   form internally while `lp__` still reports the full-constant value
   the `target +=` form promises, to the last ulp. Gradients are
   unchanged (constants carry none). The only observable difference
   from the naive full form is last-ulp log-density values from the
   different summation association — the standard "same terms, different
   order" class, behaviorally inert for sampling.
2. **Pure hoisting without the propto form (bit-identical).**
   Restructure the function so the constant subterms are computed once
   per call rather than eliminated — identical values, identical
   gradients, identical draws, but saves less (still per-call work for
   mixed terms).
3. **Let likelihood lines use propto semantics outright (policy call).**
   Drops the constant from `lp__` entirely — harmless to the sampler
   and to LOO as usually computed, but a user-visible semantic change.

Option 1 is the natural recommendation: measured headroom is 22–45% of
the affected family interiors, it preserves the documented meaning of
`target +=`, and it needs no policy decision.

Measurements and attribution: per-element instruction tables for the
glm and plain families, both at baseline x86-64 and `-O3 -mavx2
-mfma`, available on request.
