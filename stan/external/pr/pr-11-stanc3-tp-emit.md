This extends the gathered-likelihood registry (#8) with a fourth family and a new emission class: indexed-coefficient predictors built in a transformed-parameters loop.

The pattern is the election-model shape: `y_hat[i] = beta[1] + beta[2]*x[i] + a[age[i]] + b[edu[i]] + ...` in transformed parameters, then `y ~ bernoulli_logit(y_hat)`. When the loop's result feeds only the likelihood, the pass rewrites the loop body to the `gathered_additive_tp` factory call (sims1253/math#22) and leaves everything else stock — the likelihood line, the priors, and the output columns all stay exactly as they were.

The gates run in the strongest class this series has used: the compiler's output is token-identical to a hand edit that was itself gated bit-identical against stock, and the end-to-end sampler draws reproduce stock digit for digit, all output columns included. Ten negative controls stay silent — any other read of the loop variable disqualifies the rewrite. A full-tree census of 2,562 models at `--O1` finds exactly three emitted calls in two models, both intended; everything else compiles byte-identical.

With the math-side primitive this carries the measured win end-to-end: the model runs 3.4 times faster in wall time with every draw bit-identical to stock.

Requires sims1253/math#22.
