When a distribution builds a partials array it will fully overwrite, the edge first zeroes the array, then the function fills it. For `normal_id_glm` with a per-observation intercept, that zero pass costs 8 instructions per element, and a full arena copy of the operand adds five more.

This adds an opt-in construction: `internal::operand_with_partials` and an edge specialization that seeds the partials from the caller's expression. `normal_id_glm` uses it for vector alphas. No existing code path changes; the additions are new templates only.

Gates: 173,664 byte-level checks over randomized shapes, clean at both flag levels; sampler draws on a brms-style model identical to stock; 190 tests pass, including the bernoulli and poisson glm suites that share the pattern.

Measured: the memset leaves the profile and the vector-alpha path drops 18% per element. The sibling glm densities can adopt the same seeding.
