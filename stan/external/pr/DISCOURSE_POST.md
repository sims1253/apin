# Discourse post — paste-ready sections
# (This header is not part of the post. Copy from below the line.)
# Paste tip: open this file in an editor, select the section, copy, paste
# into the Discourse composer. Everything below is plain Discourse-flavored
# markdown with no wrapping code fences.

---

## The PRs (on my forks)

Stan's [AI Contribution Policy](https://github.com/stan-dev/stan/wiki/AI-Contribution-Policy) asks that upstream submissions be the work of an accountable human contributor. So I keep these on my forks as documented proposals: elaborate issues with working reference implementations, not merge requests. Each PR body states the problem, derives the fix step by step, and lists the validation. The ideas are reviewable and re-implementable independently of my code.

### stan-math — correctness

- **[math #1 — guard eigenvector adjoints against degenerate eigenvalue clusters](https://github.com/sims1253/math/pull/1).** The reverse-mode adjoint divides by eigenvalue gaps. On exactly repeated eigenvalues the gradient is NaN. On rounding-degenerate spectra, such as a jittered GP kernel, it disagrees with finite differences by 30–50% in every build. Any permitted FP reordering, for example a wider SIMD ISA changing GEMM accumulation order, moves gradients by O(1) with sign flips. The fix applies the classical minimal-norm gauge inside numerically degenerate clusters. The well-separated path is untouched and byte-identical. On a kronecker-GP model the fix takes bulk-ESS from **29 to 411**, because the sampler had been adapting to a wrong gradient. JAX merged the same idea for forward mode in April. Cited in the PR.
- **[math #3 — wrong-sign partials in bernoulli_logit_lpmf above the cutoff](https://github.com/sims1253/math/pull/3)** and **[math #4 — the same fix for the GLM variant](https://github.com/sims1253/math/pull/4).** One dropped `signs` factor in the `ntheta > cutoff` branch. For y=1 observations with logit > 20, every downstream adjoint carries the derivative with the wrong sign. The added tests fail on stock by exactly `2·exp(−25)`. The OpenCL variant carries the same bug. Flagged in the PR, not fixed.

### stan-math — performance

- **[math #2 — square() should multiply, not call std::pow(x, 2)](https://github.com/sims1253/math/pull/2).** Under default `-fmath-errno` the compiler cannot remove the call, so it stays a ~105-instruction libm call in hot paths. That is worth −9–15% per gradient on GP models. Bonus finding: glibc's `pow(x,2)` is 1 ulp off the correctly rounded product about 0.08% of the time, so the multiply is the *more accurate* operation.

### stanc3 + docs

- **[stanc3 #1 — fuse eigenvectors_sym + eigenvalues_sym pairs into one eigendecompose_sym call](https://github.com/sims1253/stanc3/pull/1)**, enabled at `--O1` and above, plus a pedantic warning for un-fusable patterns. Models using both functions on the same matrix run 4 full eigendecompositions per gradient where 2 suffice. Measured −15.6% time per gradient on kronecker-GP, output bit-identical. **[docs #1](https://github.com/sims1253/docs/pull/1)** documents the new warning.

### walnutpie — robustness series

- **[walnutpie #7 — init guard](https://github.com/sims1253/walnutpie/pull/7)**: never start a chain at a non-finite-logp position. File inits fail fast: 0.16 s instead of 8.2 s of pinned, zero-ESS draws. Random inits get Stan's rejection protocol as CLI policy.
- **[walnutpie #8 — freeze clamp](https://github.com/sims1253/walnutpie/pull/8)**: an auditable fallback instead of a `macro_time must be in (0, inf)` abort at the warmup freeze when the adapted step degenerates.
- **[walnutpie #9 — find_reasonable_step was broken three ways](https://github.com/sims1253/walnutpie/pull/9)**: momentum scale inverted against the sampler, fresh momentum per probe, asymmetric accept statistic. Fixed, the probe returns the right step on the pinned cell, and the short-warmup blr class goes from bulk-ESS 5–9 (pinned) to **779**.

Together these treat the stuck-chain class reported in the [walnutpie 0.0.1 release thread](https://discourse.mc-stan.org/t/walnutpie-version-0-0-1-release/41487/11). "Fable"'s analysis there identified Stan's step initialization as the decisive difference. The probe implementing it existed but was broken. Each PR is gated on bit-identical default paths. The fork now carries the whole campaign as PRs #1–#9, including the negative results, so each idea has its own reviewable history.

### cmdstan fork

- **[stan #1 — hoist build_tree scratch vectors in base_nuts](https://github.com/sims1253/stan/pull/1)**: −7% wall on the benchmark set, bit-identical sampler output, all pre-registered gates passing.

## Related to ongoing threads

- The stuck-chain report above (Lotka–Volterra, inits landing in the tails, collapsing mass estimates) is the same failure class as the walnutpie robustness series.
- The [soft gradient clipping idea](https://discourse.mc-stan.org/t/models-where-stan-outperforms-nutpie-walnuts/41095/39) from the nutpie/walnuts comparison thread: I tested it scoped to adapter-visible gradients during early warmup. At the thread's own scales (c = 1e8–1e10) it is a numerical identity on this model class. At model scale (1e6) it lifts the frozen metric 4× but cannot reach the step adapter's acceptance engine, so the pin survives. The same holds for the init-buffer idea (hold the metric at identity for the first ~75 iterations): walnutpie's variance-ratio collapse happens at the first observation, not by accumulation, so deferring does not help. Numbers in the repo (results/warmup_shields_w54.md).
- That thread's tree-size quantization question is directly measurable with per-transition gradient accounting. The harness for it is in the repo too (results/grad_accounting_w38.md).

## Where the rest lives

- Everything (experiment ledger W-1…W-56, final report, all measurement writeups): [sims1253/apin](https://github.com/sims1253/apin)
- One worked example, start to finish — the session transcript of the log1p benchmark that turned into issue 3366 and found the partials sign bug along the way (bugs in my own kernels first, then the triple-check before claiming the upstream one): [w46-log1p-ceiling-transcript.md](https://github.com/sims1253/apin/blob/main/stan/results/traces/w46-log1p-ceiling-transcript.md)
