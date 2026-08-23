# Upstream ecosystem scan — 2026-08 (SCAN-ONLY)

Date: 2026-08-22/23. Method: read-only web research (GitHub API via `gh`,
web search, arXiv) + reading our own evidence files. No builds, no
benchmarks, no local compute. Companion worklog entry: W-38u. Cross-checks
against `external/upstream_candidates.md`, `external/upstream_pr_kits.md`,
`results/march_native_w35.md`.

Headline table:

| # | Topic | Upstream status | Plan impact |
|---|---|---|---|
| 1 | `eigendecompose_sym` two-call idiom | Primitive is OLD (Aug 2023, math PR #2931) — NOT new in 5.3.0/2.39; no stanc3 fusion work | Kit 2 still novel, but **text must be corrected** |
| 2 | Eigenvector adjoint conditioning | **NOT known, NOT fixed, NOT documented** in stan-dev/math; adjoint-methods literature exists | W-40 proceed — novel; Kit 4 valid as-is |
| 3 | Elementwise var-mode plumbing | stanc3 `vectorize_loops` pass merged 2026-08-19 (`--Oexperimental`); no eltwise-fusion for already-vectorized lines | Candidate 2 reframe as extension of #1666; test `--Oexperimental` |
| 4 | `square()` = `std::pow(x,2)` | Still `std::pow` on develop; no issue/PR exists | Kit 1 valid, unfiled, novel |
| 5 | bridgestan compile cache | v2.9.0 is latest; main = 5 CI commits past it; issue unfiled anywhere | Kit 3 valid; file it |
| 6 | Releases after 2.39/5.3.0 | None yet; **math develop migrated Eigen 3.4.0 → 5.0.1** (PR #3271) | Re-validate W-35 repro under Eigen 5 before filing; stay pinned 2.39 |
| 7 | walnutpie / WALNUTS | Upstream main = 6162d88 (our fork point, current); paper published JMLR 2026; Picard-map parallel transitions paper is the new idea | Unaffected; watch branches `leapfrog-momentum-compose`, PR #77, issue #34 |

---

## 1. `eigendecompose_sym` and the two-call idiom (Kit 2)

**What exists upstream.** The combined primitive is much older than our
records claim. `eigendecompose_sym` was added to stan-math in August 2023:

- math PR #2931 "Add tuple-returning special functions" (merged 2023-08-18),
  closing issue #2845 "Add tuple-returning versions of special functions"
  (opened by WardBrian; the issue text literally motivates it with
  "eigenvalues and eigenvectors are two functions for which a complementary
  function ... would result in only half as much computation" — the same
  argument as our Kit 2).
  https://github.com/stan-dev/math/pull/2931 ,
  https://github.com/stan-dev/math/issues/2845
- Language exposure: stanc3 PR #1346, same title, merged 2023-08-18.
  https://github.com/stan-dev/stanc3/pull/1346
- First release containing it: math 4.8.0 (2024-01-16) / CmdStan 2.34
  (2024-01-16) — the 4.8.0 release notes reference the eigendecompose test
  split (#2953), confirming the function is in that release. Doxygen:
  https://mc-stan.org/math/rev_2fun_2eigendecompose__sym_8hpp.html

**Corrections to our records.** `upstream_candidates.md` item 1, Kit 2, and
the W-32 close-out say the primitive was "added in stan-math 5.3.0 + stanc3
2.39 language support". That is wrong — it shipped in **4.8.0 / CmdStan
2.34 (Jan 2024)**, so it is also present in our pinned 2.37.0 lane, and in
every release users actually run today. The stanc3-side ask (peephole/pedantic
fusion of the natural `eigenvectors_sym(A)` + `eigenvalues_sym(A)` pair)
remains **unclaimed upstream** — searches of stan-dev/stanc3 and stan-dev/math
issues/PRs find no existing ask for the pair fusion.

**Plan impact: complements (with a text correction).** Kit 2's ask is still
novel and the measured win (−19.4% gradient Ir, bit-identical draws) is
untouched by anything upstream. But reframe the pitch: not "5.3.0 added a
combined primitive, stanc3 should use it" — instead "the combined primitive
has existed since 2.34, models still emit the wasteful pair (including
posteriordb's own kronecker_gp), stanc3 should fuse or at least pedantic-
warn". This is a stronger ask (bigger install base affected) and immune to
release-notes pedantry.

## 2. Eigenvector ADJOINT conditioning on degenerate spectra (W-35/W-40) — CRITICAL CHECK

**Verdict: NOT known, NOT fixed, NOT documented in stan-dev/math.** The
issue would be novel. Evidence:

- **No matching issue or PR.** Searched stan-dev/math issues/PRs with:
  degenerate/repeated/clustered eigenvalues + adjoint/derivative;
  eigenvectors_sym + derivative; eigenvalue + finite difference;
  condition-number-of-eigenvalue-derivatives phrasings. Nothing matches.
  The only hits are about unrelated functions (adjoint ODEs, GPU, wiener).
- **The code on develop still has the raw divisor, no guard, no docs
  caveat.** `stan/math/rev/fun/eigenvectors_sym.hpp` computes
  `f = 1/(w_j − w_i)` (via `eigenvals.rowwise().replicate(p) − ...`) with
  diagonal zeroed and `reverse_pass_callback` accumulating
  `V (F ∘ (Vᵀ G_V)) Vᵀ`; the doc comment says only "Return the eigenvectors
  of the specified symmetric matrix."
  https://github.com/stan-dev/math/blob/develop/stan/math/rev/fun/eigenvectors_sym.hpp
- **No degenerate-spectrum test coverage.** `test/unit/math/mix/fun/
  eigendecompose_sym_test.cpp` has no degenerate/repeated/identical-
  eigenvalue cases (grep for degener/repeat/identity patterns: none).
- **Closest known items (all adjacent, none the same):**
  - math issue **#1803** "Wrong derivatives for cholesky and symmetric
    eigen decomposition" (OPEN since 2020-03) — this is the *triangular vs
    symmetric adjoint* convention problem (adjoint of A for symmetric-input
    functions lands lower-triangular), acknowledged by bob-carpenter and
    bbbales2, never resolved. Related to eigen adjoints but NOT about
    conditioning/degeneracy. Worth citing in our issue as a second known
    wart of the same primitives.
    https://github.com/stan-dev/math/issues/1803
  - Stan Discourse "Surprising memory usage with eigendecomposition" (2017,
    maedoc) — the thread that led to the analytic (Giles-formula) gradients.
    Degeneracy is discussed in passing: bbbales2 "I dunno if the derivatives
    fall apart there or what"; betanalpha notes arbitrary-basis gradients
    are "well-defined relative to that basis" and avoids stan-math's
    eigenvalue functions in his Riemannian HMC code (per arXiv:1212.4693).
    The concern was never filed as an issue.
    https://discourse.mc-stan.org/t/surprising-memory-usage-with-eigendecomposition/7616
  - Discourse "Known gradient breaking behaviours?" (9813) does NOT mention
    eigendecomposition (checked). https://discourse.mc-stan.org/t/known-gradient-breaking-behaviours/9813
  - Eigen's tracker (gitlab libeigen/eigen): no issue on eigenvector-
    derivative conditioning; nearest is #2191 (SelfAdjointEigenSolver wrong
    eigenvalues via QL bulge-chasing underflow — a different defect).
    https://gitlab.com/libeigen/eigen/-/issues/2191

**Literature that DOES exist (usable for W-40 design and for citations in
the stan-math issue):**

- He, Scarbourough, Amsallem et al., "Eigenvalue problem derivatives
  computation for a complex matrix using the adjoint method" (J. Sound
  Vib. 2023; also AIAA J. 2022) — adjoint eigenvalue/eigenvector
  derivatives incl. the repeated-eigenvalue pathology.
  https://www.sciencedirect.com/science/article/abs/pii/S0888327022007920 ,
  https://par.nsf.gov/servlets/purl/10629986
- "Adjoint methods for computing derivatives of functions of eigenvectors
  using shift-and-invert preconditioning" (2025) — modifies the adjoint so
  derivatives remain computable when eigenvalues are numerically repeated;
  the closest published analogue of W-40's cluster-aware minimal-norm
  adjoint. https://www.researchgate.net/publication/387337875
- de Leeuw, "Differentiating Generalized Eigenvalues and Eigenvectors"
  (arXiv:2508.09355, 2025). https://arxiv.org/abs/2508.09355
- Classical repeated-eigenvalue derivative theory: Friswell,
  "The derivatives of repeated eigenvalues and their associated
  eigenvectors" (http://michael.friswell.com/PDF_Files/J26.pdf); van der Aa
  et al., ELA 2007
  (https://journals.uwyo.edu/index.php/ela/article/download/463/463).
- The 1/δ conditioning is common knowledge in adjacent AD communities:
  Julia discourse thread on eigenvector AD
  (https://discourse.julialang.org/t/derivative-of-eigenvalues-and-eigenvectors-of-hermitian-matrix-by-automatic-differentiation/11563);
  TF vs PyTorch eigh backward differences
  (https://stackoverflow.com/questions/58856160/).

**Plan impact: unaffected — proceed.** W-40 (cluster-aware minimal-norm
adjoint) and Kit 4 (docs + relative-gap warning ask) are novel upstream.
Recommended additions: (a) cite the adjoint-methods literature above in the
issue and in W-40's design note (especially shift-and-invert and He et al.);
  (b) cite #1803 as the sibling known wart; (c) since math develop just
  migrated to Eigen 5.0.1 (topic 6), state in the issue that the repro was
  validated on Eigen 3.4.0 and re-run it under Eigen 5 before/at filing —
  different GEMM internals could shift the exact rounding trigger, though
  the mathematical point (no guard on min gap) stands in any version.

Also for the record on the context prompt's "2.39 cholesky_decompose
derivative fix mentioned in the release notes": **not found upstream.** The
full release notes of CmdStan 2.38.0, 2.39.0 and math 5.2.0/5.3.0 contain no
cholesky derivative item (2.39.0's notes list exactly two fixes: log_prob
parameter ordering #1337, converged__ column tests #1338; math 5.3.0's notes
have no cholesky item). No stan-math PR for a cheaper symmetric-cholesky
reverse pass exists (searched). Our W-29 measurement (adjoint sweep 1.7×
forward) therefore remains unaddressed upstream — `upstream_candidates.md`
item 3(a) is unaffected.

## 3. Elementwise var-mode plumbing tax (~32% of hier_2pl gradient)

**What exists upstream.**

- **stanc3 PR #1666 "Add vectorize_loops optimization" — merged to master
  2026-08-19** (post-2.39, in nightlies only). Rewrites loops whose body is
  a single scalar density statement into the vectorized density call
  (`for (n in 1:N) y[n] ~ normal(mu[n], sigma)` → `y ~ normal(mu, sigma)`),
  explicitly to "allocate O(1) autodiff nodes instead of O(N)". Measured
  3.54× per-gradient on radon_pooled in their own benchmarks; enabled at
  `--Oexperimental`; follow-up PRs planned for *indirectly indexed
  arguments* (`a[county[n]]`) and elementwise assignment loops. Closes the
  ancient stanc3 #356.
  https://github.com/stan-dev/stanc3/pull/1666 ,
  https://github.com/stan-dev/stanc3/issues/356
- math develop PR #3352 "Always use const view for rev Eigen .val()"
  (merged 2026-07-21/23) + Holder `coeffRef` — a rev-mode Eigen view/access
  refactor across rev/fun (311 lines). Plumbing-adjacent; no perf claims in
  the commit messages. https://github.com/stan-dev/math/pull/3352
- math develop PR #3346 "Add map-like helpers" (`map`, `mapN`, `row_map`,
  `col_map`, ...; merged 2026-08-12, closes #3339, suggested by
  bob-carpenter) — groundwork for user-expressible elementwise fusion at
  the functor level; C++-side for now, language exposure TBD.
  https://github.com/stan-dev/math/pull/3346 ,
  https://github.com/stan-dev/math/issues/3339
- **No** SoA-arena/adjoint-container refactor activity (searches for
  arena/SoA/adjoint-container work return only old closed PRs #1103/#2928
  and unrelated items). The 8–17% tape tax remains unaddressed upstream.
- stanc3 PR #1508 "Stop generating unnecessary omni indexes" (merged
  2025-04) — small codegen cleanup in the same direction as our
  `rvalue<index_multi>` observation.

**Plan impact: complements + one reframe.** Our hier_2pl line
(`y ~ bernoulli_logit(alpha[ii] .* (theta[jj] - beta[ii]))`) is already
vectorized *syntax* — `vectorize_loops` does not touch it; the tax we
measured is in the elementwise var ops feeding the density, which no
upstream pass addresses. So candidate 2's ceiling stands. But the framing
should change: propose it as the natural next member of the #1666 pass
family ("fuse indexed elementwise argument chains into the density call /
keep operands double until the likelihood boundary") and cite #1666's
O(1)-nodes motivation. Also actionable now: re-run our grid models with
nightly stanc `--Oexperimental` (radon_partially_pooled_noncentered is the
likely beneficiary if any model text uses scalar loops — ours don't, so
expect no change, but it is cheap to confirm and W-36's .so protocol needs
no rebuild discipline for a stanc-only flag test).

## 4. `square()` calling `std::pow(x, 2)` (Kit 1)

**What exists upstream: nothing.** develop's `stan/math/prim/fun/square.hpp`
still reads `return std::pow(x, 2);` for arithmetic types directly beneath
the doc comment "The implementation of square(x) is just x * x"
(verified on the develop branch today). No issue or PR proposing the
multiply exists (searched open+closed, multiple phrasings). The sibling
sites in `stan/math/rev/fun/squared_distance.hpp` also still call
`std::pow(a.val() - b.val(), 2)` (verified lines ~24/~38 pattern).
https://github.com/stan-dev/math/blob/develop/stan/math/prim/fun/square.hpp

**Plan impact: unaffected.** Kit 1 is valid, unfiled, and now
double-verified against develop (not just our 5.3.0-era tree). File as-is.

## 5. bridgestan: silent `.so` cache + STAN_THREADS signaling (Kit 3)

**What exists upstream.** Latest release is still **v2.9.0 (2026-07-06)**
— nothing after it. `main` is 5 commits past the tag, all CI/tooling
(dependabot bumps, Windows dll setup move #331, rust path-absolutize #330;
Jul 14–Aug 1). No issue or PR about `compile_model` ignoring `make_args`
against a cached `.so` exists (searched compile/cache/so/stale phrasings).
Adjacent but different: issue #194 (open) "Control over the internal
threading of a model"; issue #289 (closed) "Segmentation fault with
parallel `param_constrain!`" — a misuse-crash cousin of our
non-`STAN_THREADS` double-free, resolved as user error/documentation.
https://github.com/roualdes/bridgestan/releases/tag/v2.9.0 ,
https://github.com/roualdes/bridgestan/issues/194 ,
https://github.com/roualdes/bridgestan/issues/289

**Plan impact: unaffected.** Kit 3 remains valid and unclaimed; no release
fixes it. When filing, referencing #289 (parallel misuse crash precedent)
and #194 (threading-control discussion) will help the maintainers place the
STAN_THREADS-signaling half.

## 6. CmdStan / stan-math releases after 2.39.0 / 5.3.0

**No new releases.** Latest tags: math v5.3.0 (2026-05-19), CmdStan v2.39.0
(2026-05-19), stanc3 v2.39.0 + nightlies (latest 2026-08-21). No 2.40/5.4
exists as of 2026-08-22. But the develop branches are active and carry
perf-relevant material (math develop is 142 commits ahead of v5.3.0):

- **Eigen 3.4.0 → 5.0.1 migration (the big one).** math PR #3271 "Update
  Eigen to 5.0.1" (merged 2026-06-11), plus PR #3338 (backwards-compat
  `Eigen < 5`), issue #3332 and PR #3334 (compile/eager-execution fixes the
  migration surfaced in Holder/`var_value<Matrix>`), "Document Stan changes
  to vendored Eigen". Consequences for us: (a) W-35's characterization was
  done against Eigen 3.4.0 (bridgestan 2.9.0's vendored copy) — the exact
  ISA-trigger (packet-width switch in Eigen's GEMM) may differ under 5.0.1,
  so re-validate `scratch/w35/repro` against a math-develop tree before
  filing the stan-math issue; (b) any 2.40-era re-baseline of our benchmark
  lane will be a different numerics platform (see also walnutpie's own
  Eigen 5.0.1 bump, topic 7).
  https://github.com/stan-dev/math/pull/3271 ,
  https://github.com/stan-dev/math/issues/3332
- stanc3 PR #1666 `vectorize_loops` (topic 3) — likely the headline
  codegen perf feature of 2.40 if it graduates to `--O1`.
- math PR #3352 (rev Eigen const views) and #3346 (map helpers) — topics 3.
- CmdStan develop: mostly submodule bumps; PR #1346 "Use clang pch template
  instantiation when available" (compile-time win, 2026-08-06); GQ RNG seed
  fix (#1347). https://github.com/stan-dev/cmdstan/pull/1346
- Other math develop content: `integrate_1d` gauss-kronrod/double-exp
  variants, `laplace_latent_solve` family (Florence Bockting), softmax
  refactor, `student_t_qf`, `-isystem` include changes (PR #3333),
  `rep_matrix` row-major fix (#3342).

**Plan impact: wait-and-prepare.** Stay pinned on CmdStan 2.39.0 for the
W-36 benchmark session (nothing to adopt from releases). Two prep items:
(1) W-35 repro re-validation under Eigen 5.0.1 (before filing Kit 4);
(2) a post-2.40 re-baseline is already justified by Eigen 5 + vectorize_loops
— add it to the backlog rather than chasing develop mid-session.

## 7. WALNUTS / walnutpie upstream

**Repo identity confirmed:** `github.com/flatironinstitute/walnutpie` —
"Within-orbit Adaptive Leapfrog No-U-Turn Sampler", default branch `main`,
**not a GitHub fork of anything**, no releases/tags, 65 stars, last push
2026-08-14. Our submodule's `origin/main` (6162d88, "Merge PR #93 from
flatironinstitute/update-eigen") IS the current upstream main tip — **our
fork point is current; nothing has landed on upstream main since.**
https://github.com/flatironinstitute/walnutpie

- The paper: Bou-Rabee, Carpenter, Kleppe & Liu, "The Within-Orbit Adaptive
  Leapfrog No-U-Turn Sampler", arXiv:2506.18746 (v1 2025-06-23, single
  version), **published JMLR 27(113):1-64, 2026**. Its companion *research*
  repo is a different, small codebase: `github.com/bob-carpenter/walnuts`
  ("Step size adaptation for the No-U-Turn Sampler", Python/MATLAB, last
  push 2025-11-25). Do not confuse the two: walnutpie is the C++
  implementation we track.
  https://arxiv.org/abs/2506.18746 , https://github.com/bob-carpenter/walnuts
- Upstream branches (tips, none merged to main after 6162d88):
  `leapfrog-momentum-compose` (2026-06-12, "unroll leapfrogs; fixes #30" —
  this is open **PR #77**), `preconditioner` (2026-06-11, includes PR #74
  polish-spsc), `feat/concepts` (2026-01-21), `benchmarks` (2025-12-01,
  "adam for step size adapt"), `python-interface` (2026-08-03, docs),
  `update-eigen` (merged as PR #93: Eigen 5.0.1, matching stan-math).
- Open issues with ideas relevant to our ESS-per-gradient lane: **#34
  "cache gradients across transitions + micro-steps composition"** (directly
  our gradient-cost theme), #31 "conserve Hamiltonian each micro step", #30
  "eliminate double rho updates in leapfrog" (= PR #77), #35 "fourth-order
  leapfrog integrator", #3 "specialize depth 0/1 transitions", #84 "soft
  clamping on gradients", #79 independent disable of stepsize/mass
  adaptation, #89 std::jthread & libc++, #6 posteriordb evaluation.
  https://github.com/flatironinstitute/walnutpie/issues/34
- Recent merged PRs on main: #93 (Eigen 5.0.1), **#90 "Warn when a seed is
  specified but adaptive stopping is still enabled"** (2026-08-11) — note
  the house style: upstream prefers *warnings* over behavior changes; our
  Kit 5 (`allow_early_exit=false` default) is a stronger ask and should
  present the warn-only alternative explicitly. #92 doc fix.

**New WALNUTS-adjacent literature 2025–2026:**

- GIST: Bou-Rabee, Carpenter, Marsden, "Gibbs self-tuning for locally
  adaptive HMC" — arXiv:2404.15253, now published in Statistics Surveys
  vol. 20 pp. 135-179 (2026). The framework paper WALNUTS builds on.
  https://arxiv.org/abs/2404.15253
- **Parallel computations for Metropolis Markov chains with Picard maps**
  (Grazzi et al.), arXiv:2506.09762, published in Biometrika 2026 —
  parallelizes a *single* Metropolis transition via Picard-map fixed-point
  iteration. This is the most relevant new idea for our parallel-execution
  lane (W-30/W-36): it attacks within-transition parallelism, which is
  orthogonal to our cross-chain parallelism and could compose with
  endpoint-grad-threading on WALNUTS's macro/micro-step structure (their
  micro-step sequence is exactly a fixed-point-shaped pipeline).
  https://arxiv.org/abs/2506.09762
- The No-Underrun Sampler (Bou-Rabee, Carpenter, Liu, Oberdörster),
  arXiv:2501.18548 (2025) — locally adaptive, gradient-free cousin.
  https://arxiv.org/abs/2501.18548
- A community JAX port of WALNUTS is being discussed in BlackJAX
  (discussion #935, "WALNUTS: A New Windowed Adaptive Leapfrog NUTS
  Kernel") — evidence of external uptake worth citing in any walnutpie
  upstream conversation. https://github.com/blackjax-devs/blackjax/discussions/935

**Plan impact: unaffected, two watch items + one idea.** (a) Kit 5 still
valid; account for upstream's warn-first style (cite PR #90). (b) Watch PR
#77 (leapfrog unroll) and issue #34 (gradient caching) — both change the
gradient-cost accounting our ESS-per-gradient work depends on if merged.
(c) Park "Picard-map parallel transitions" (arXiv:2506.09762) in the
proposal backlog as the next parallelism axis after W-36 (cross-chain) —
natural fit with WALNUTS micro-steps, but only worth prototyping if the
W-36 session shows per-chain gradient cost still dominating after
cross-chain parallelism.

---

## Action list (deltas to our plan, in priority order)

1. **Correct the eigendecompose_sym provenance** in Kit 2 / upstream_candidates
   item 1 / W-32 record: Aug 2023 (PR #2931/#1346), shipped math 4.8.0 /
   CmdStan 2.34 (Jan 2024) — not 5.3.0/2.39. Reframe Kit 2's ask
   accordingly ("available since 2.34, models still emit the pair").
2. **W-40 + Kit 4: proceed as novel.** Enrich the issue text with the
   adjoint-methods citations (shift-and-invert 2025; He et al. 2023;
   de Leeuw 2025; Friswell/van der Aa classics) and cite #1803 as the
   sibling wart. Re-validate the W-35 repro under Eigen 5.0.1 (math
   develop) before/at filing since 2.40 will ship Eigen 5.
3. **Candidate 2 reframe**: pitch eltwise-argument fusion as an extension
   of stanc3 PR #1666 (`vectorize_loops`); cheap experiment: compile grid
   models with nightly stanc `--Oexperimental` and record (expected: no
   change — our model texts are already vectorized).
4. **Kits 1 and 3: file as-is** (both verified still-valid against
   develop/main today; nothing upstream supersedes them).
5. **Stay pinned CmdStan 2.39.0 for W-36**; backlog a post-2.40 re-baseline
   (Eigen 5.0.1 + possible vectorize_loops graduation).
6. **walnutpie**: keep `allow_early_exit` proposal (Kit 5) but present the
   warn-only alternative given upstream PR #90's style; watch PR #77 and
   issue #34; park Picard-map parallel transitions (arXiv:2506.09762) as a
   future proposal axis.

## Sources

stan-dev/math: PR #2931, issue #2845, issue #1803, PR #3271, PR #3332,
PR #3338, PR #3352, PR #3346, issue #3339, develop `eigenvectors_sym.hpp`,
`square.hpp`, `squared_distance.hpp`, RELEASE-NOTES.txt @ v5.3.0, releases
page. stan-dev/stanc3: PR #1346, PR #1666, issue #356, PR #1508, releases.
stan-dev/cmdstan: releases v2.38.0/v2.39.0, PR #1346 (cmdstan), develop log.
roualdes/bridgestan: release v2.9.0, compare v2.9.0...main, issues #194,
#289. flatironinstitute/walnutpie: repo, branches, PRs #93/#90/#77, issues
#34/#30/#31/#35/#3/#79/#84/#89. arXiv: 2506.18746 (JMLR 27(113) 2026),
2404.15253 (Stat. Surveys 20, 2026), 2501.18548, 2506.09762 (Biometrika
2026), 2508.09355. Discourse mc-stan threads 7616, 9813; Julia discourse
11563; StackOverflow 58856160; Eigen gitlab #2191; ScienceDirect/NSF-PAR He
et al.; ResearchGate 387337875 (shift-and-invert adjoint); Friswell J26;
van der Aa ELA 2007. All URLs inline above.
