PR #14 added `bernoulli_logit_lpmf_gathered`. End-to-end validation then found a gap that unit gates compiled without FMA flags cannot see.

At `-O3 -mavx2 -mfma`, stock's reverse chain fuses only the alpha increment into an FMA. Theta and beta get one rounded product and a plain add. The primitive's plain statements let the compiler fuse all three. That drifts about one ulp into half the gradient components, and warmup amplifies the drift until trajectories fork.

This branch inserts volatile-barrier rounded products so each increment matches stock's schedule. The value path does not change. The unit gate now runs at the model's build flags, and the rebuilt binary carries the same `vfmadd` count as the reference build.

Gates: 12,000 bitwise checks clean at both flag levels; a 12-cell sampler grid reproduces the reference draws exactly; the original non-FMA regressions still pass. Supersedes #14; the branch contains its tip.
