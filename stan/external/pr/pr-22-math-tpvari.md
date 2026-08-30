Election-style models build their predictor in a transformed-parameters loop: a per-observation sum of indexed coefficient vectors, a few data terms, then `y ~ bernoulli_logit(y_hat)`. The loop's autodiff chain — one vari per element per operator — costs more than the rest of the model together: on a 5-field survey model (N = 1,578-ish per gradient call, 11,566 output columns) the tp complex is 55% of the run.

This adds the missing entry point. `gathered_additive_tp` builds the predictor in one pass and pushes one custom vari per element onto the stack at the transformed-parameters site. Its forward is the value-only computation; its chain replays, per element, the exact edge arithmetic stock performs; the likelihood line stays stock and untouched. Because the varis are created where stock creates its own, the reverse sweep visits them in stock's order — the construction is position-correct by design, not by imitation.

Gates: 440,067 bitwise checks clean at `-O3 -mavx2 -mfma` and `-O2`, with the prior-ordering control exact in both directions; sampler draws identical to stock digit for digit, all output columns included; 100-point log density and gradient parity exact; 11 tests plus the untouched control suites.

Measured: the whole run drops 67.5% of its instructions (54.8B to 17.8B) and runs 4.1x faster in wall time, with every draw bit-identical to stock.
