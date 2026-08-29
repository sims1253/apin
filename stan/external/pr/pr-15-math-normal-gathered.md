Models whose likelihood reads `for (n) target += normal_lpdf(y[n] | alpha[c[n]], sigma)` pay for one scalar call per data row. The generated code evaluates the scale's log, builds autodiff edges, and pushes chain-stack records once per element. On the Minnesota radon dataset (N = 12,573) that loop is 90% of the gradient.

This adds `normal_lpdf_gathered`. It takes the coefficient vector and the index array instead of a gathered matrix. The value path keeps the per-element order of the scalar calls, and the reverse pass is one callback with the same scatter order. The scale's log is computed once and reused; the per-element addition schedule does not change.

The per-element checks stock performs stay: y finite, location finite. They are not optional. On warmup states where the location overflows, stock throws and the sampler rejects the state cleanly. Without the checks, the gradient carries NaN into the next call and the trajectory forks. The unit gate covers the throw set as well as the values.

Gates: 22,380 bitwise checks over randomized shapes and layouts, clean at `-O3 -mavx2 -mfma` and `-O2`; same-seed sampler draws identical to stock on two radon models; 100-point log density and gradient parity exact. The large model's gradient loses 65% of its instructions.
