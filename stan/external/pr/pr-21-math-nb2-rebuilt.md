On the released interior, `neg_binomial_2_lpmf` runs three lazy passes over the data. Each element recomputes mu and phi four times and calls `log(mu + phi)` twice. An Eigen select evaluates both branch operands, so one `log1p` call per element is discarded unused. The function measures near 942 instructions per element at N = 12,573.

This replaces the three passes with one scalar-sequential pass. Each element calls the same functions in the same order, the fold keeps Eigen's exact shape, and one fused multiply-add is pinned to the form stock's compilation happens to make. The lgamma calls do not change: same count, same arguments.

On the released interior the rebuild saves about 153 instructions per element. On this branch's base the stock interior is already leaner and the saving is 14 to 25. The two vintages differ; both numbers are measured.

Gates: 71 bitwise cases clean at `-O2`; at `-O3` with FMA the remaining one-ulp log-density differences trace to stock's own compile-to-compile instability on those flags, which the pin removes; sampler draws on a neg-binomial model match stock exactly; 100-point parity exact; 31 tests pass.
