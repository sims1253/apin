# Upstream PR / issue filing kit (W-52)

**Date prepared:** 2026-08-23. Everything here is validated against the exact
base commits recorded below; nothing has been pushed. This directory is the
index: per item, the branch (in which local clone, at which commit), the
push + PR-creation commands, and the polished body text.

## Design principle (applies to every PR body in this kit)

Each PR body is written so a maintainer can **re-derive the solution from the
text alone** — complete problem derivation (the actual equations), a
step-by-step solution derivation that can be followed without reading our
diff, and a validation protocol precise enough to re-run. Our patches are
positioned as *reference implementations of the stated derivation, provided
for convenience*, not as the only path to the fix. If a project prefers not
to take LLM-generated code, the text stands on its own.

## Index

| # | item | target repo | branch (local clone) | base commit | body text |
|---|---|---|---|---|---|
| 1 | Cluster-aware eigh adjoint (fix) | stan-dev/math | `eigen-cluster-aware-adjoint` (`external/math_dev`) | `46a31337d1534a1a5d5368311d7f32aef5ecc957` | `pr-1-math-cluster-adjoint.md` |
| 2 | square() pow→mul (perf, bit-identical) | stan-dev/math | `square-pow-to-mul` (`external/math_dev`) | `46a31337…` (same) | `pr-2-math-square.md` |
| 3 | bernoulli_logit partials sign (fix) | stan-dev/math | `bernoulli-logit-partials-sign` (`external/math_dev`) | `46a31337…` (same) | `pr-3-math-bernoulli-sign.md` |
| 4 | eigh pair-fusion codegen (perf) | stan-dev/stanc3 | `fuse-eigendecompose-pair` (`external/stanc3_pr`) | `90c653249048b3aaa04bd488fcf20dceebeeda62` | `pr-4-stanc3-eigh-fusion.md` |
| 5 | fork PR already filed | sims1253/stan | PR sims1253/stan#1 (scratch-hoist) | — | (already on GitHub; see below) |
| 5a | issue: compile_model silent cache | stan-dev/bridgestan | — (no branch) | bridgestan 2.9.0 | `issue-5a-bridgestan-cache.md` |
| 5b | issue: default .so unsafe under threads | stan-dev/bridgestan | — (no branch) | bridgestan 2.9.0 | `issue-5b-bridgestan-threads.md` |
| 6 | issue/proposal: fused packetized log1p kernel | stan-dev/math | — (no branch) | math 5.3.0 measured; develop current | `issue-6-math-fused-log1p.md` |
| 7 | walnutpie robustness trio (notes) | walnutpie (fork/upstream TBD) | fork branches exist | — | `notes-7-walnutpie-robustness.md` |

## Branch states as prepared (2026-08-23)

All three math branches are **single clean commits** on top of
`46a31337` (develop, 2026-08-12, "Merge pull request #3346 …"); the stanc3
branch is a single clean commit on `90c6532` (master tip, re-verified
2026-08-23 — zero drift since W-39/W-44). Working trees are clean
(`git status` shows only untracked build artifacts).

```
external/math_dev  eigen-cluster-aware-adjoint   3f240769 (3 files, +428/−4)
external/math_dev  square-pow-to-mul             3ef423bd (2 files, +14/−9)
external/math_dev  bernoulli-logit-partials-sign 87026fef (2 files, +37/−1)
external/stanc3_pr fuse-eigendecompose-pair      c2c3b0b  (9 files, +2914/−2)
```

Verification done at preparation time (see WORKLOG W-52):
- math #1: new test binary rebuilt and run — 4/4 PASS (compile + run; full
  test suite for the touched functions was run in W-44 at the same commit).
- math #2: `square_test` 2/2, `squared_distance_test` 7/7 (recompiled + run).
- math #3: `bernoulli_logit_test` 6/6 with the fix; the new test case
  verified to FAIL on the unpatched header (discriminating).
- stanc3 #4: golden tests `test/integration/good/compiler-optimizations` +
  `test/integration/cli-args/warn-pedantic` re-run with `--force` on the
  fresh clone — PASS (exit 0). Full `dune runtest` passed at this exact
  commit in W-39.

## Filing commands

GitHub account: `sims1253` (gh is authenticated; git protocol ssh).
You do NOT have push rights to stan-dev/*, so file via fork.

### 0. One-time per target repo (skip if the fork already exists)

```bash
gh repo fork stan-dev/math    --clone=false    # creates/uses sims1253/math
gh repo fork stan-dev/stanc3  --clone=false    # creates/uses sims1253/stanc3
```

### 1. math — cluster-aware eigh adjoint

```bash
cd /home/m0hawk/Documents/apin/stan/external/math_dev
git remote add fork git@github.com:sims1253/math.git   # once
git checkout eigen-cluster-aware-adjoint
git push -u fork eigen-cluster-aware-adjoint

gh pr create --repo stan-dev/math \
  --head sims1253:eigen-cluster-aware-adjoint \
  --base develop \
  --title 'Guard reverse-mode eigenvector adjoints against numerically degenerate eigenvalue clusters (minimal-norm gauge)' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/pr-1-math-cluster-adjoint.md
```

Consider filing the companion ISSUE first (bottom section of the PR body
contains a ready issue summary) and linking it — the ESS/R-hat evidence
stands on its own even if the fix design gets discussed.

### 2. math — square() pow→mul

```bash
cd /home/m0hawk/Documents/apin/stan/external/math_dev
git checkout square-pow-to-mul
git push -u fork square-pow-to-mul

gh pr create --repo stan-dev/math \
  --head sims1253:square-pow-to-mul \
  --base develop \
  --title 'square() for arithmetic types: multiply instead of calling std::pow(x, 2)' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/pr-2-math-square.md
```

### 3. math — bernoulli_logit partials sign

```bash
cd /home/m0hawk/Documents/apin/stan/external/math_dev
git checkout bernoulli-logit-partials-sign
git push -u fork bernoulli-logit-partials-sign

gh pr create --repo stan-dev/math \
  --head sims1253:bernoulli-logit-partials-sign \
  --base develop \
  --title 'Fix missing signs factor in bernoulli_logit_lpmf partials above the cutoff' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/pr-3-math-bernoulli-sign.md
```

### 4. stanc3 — eigh pair fusion

```bash
cd /home/m0hawk/Documents/apin/stan/external/stanc3_pr
git remote add fork git@github.com:sims1253/stanc3.git   # once
git checkout fuse-eigendecompose-pair
git push -u fork fuse-eigendecompose-pair

gh pr create --repo stan-dev/stanc3 \
  --head sims1253:fuse-eigendecompose-pair \
  --base master \
  --title 'Fuse adjacent eigenvectors_sym/eigenvalues_sym pairs into one eigendecompose_sym call (--O1+), pedantic warning' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/pr-4-stanc3-eigh-fusion.md
```

### 5a/5b. bridgestan issues

```bash
gh issue create --repo stan-dev/bridgestan \
  --title 'compile_model returns a cached <stem>_model.so even when make_args differ' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/issue-5a-bridgestan-cache.md

gh issue create --repo stan-dev/bridgestan \
  --title 'Default (non-STAN_THREADS) model .so silently corrupts memory when used from multiple threads' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/issue-5b-bridgestan-threads.md
```

### 6. math — fused log1p kernel proposal (issue; PR optional later)

```bash
gh issue create --repo stan-dev/math \
  --title 'Proposal: fused, packetized value+partials kernel for bernoulli_logit_lpmf (measured −22.8% Ir/gradient, −15.3% wall)' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/issue-6-math-fused-log1p.md
```

### 5. already filed — fork PR sims1253/stan#1

The cmdstan scratch-hoist (W-24): wall geomean ×0.931 across the 10-model
grid, memcpy/alloc Ir share 9.9% → 6.7%, draws bit-identical 24/24. Nothing
to do; listed for completeness.

## Before filing — drift check (recommended, takes a minute)

The math branches sit on develop@46a3133 (2026-08-12). If develop has moved
since, GitHub will still let you open the PR; check the touched files for
conflicts first:

```bash
git -C /home/m0hawk/Documents/apin/stan/external/math_dev fetch origin develop
git -C /home/m0hawk/Documents/apin/stan/external/math_dev diff --stat \
  origin/develop 46a31337d1534a1a5d5368311d7f32aef5ecc957 -- \
  stan/math/rev/fun/eigenvectors_sym.hpp stan/math/rev/fun/eigendecompose_sym.hpp \
  stan/math/prim/fun/square.hpp stan/math/rev/fun/squared_distance.hpp \
  stan/math/prim/prob/bernoulli_logit_lpmf.hpp
# empty => zero drift in the touched files; anything else => rebase first
```

stanc3 master was re-verified at 90c6532 on 2026-08-23 (tip == base).

## What could NOT be verified locally (be ready for these in review)

- math develop moved past 46a3133 since 2026-08-23 morning — run the drift
  check above; the patches are small and confined.
- CI on other platforms/compilers (macOS clang, MSVC): the cluster-adjoint
  patch uses only Eigen + std headers; the new tests use only gtest + Eigen
  and integer-only LCG data (platform-deterministic). The bernoulli test
  uses exact analytic + FD references (no platform-sensitive tolerances).
- Eigen-5 numerical behavior of the masked path at κ other than 1e3 was not
  re-swept on develop (the κ sweep in the evidence table was measured on the
  cmdstan-2.39/Eigen-3.4.0 toolchain; the guard math is Eigen-independent).
