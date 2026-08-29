`poisson_log_glm_lpmf` evaluates `exp(theta)` twice: once for the derivative, once for the log density term. Both sites compile to scalar libm calls over the same values, so the second pass repeats the first exactly.

This computes the exponential once and folds the derivative store, the term sum, and the constant-data lgamma sum into one loop. The per-element operation order does not change. Every check stays in stock's order with the same messages, including the deferred NaN classes.

Gates: 55 cases bitwise-clean at `-O3 -mavx2 -mfma` and `-O2`, with the throw set covered; a poisson-log regression model reproduces stock's draws exactly; 200-point parity exact; 24 tests pass.

Measured: the second exponential site disappears from the profile, and the function drops 21% of its instructions per element.
