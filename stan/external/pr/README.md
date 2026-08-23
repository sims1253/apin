# Upstream PR / issue filing kit (W-52, extended W-55)

**Batch 1 prepared:** 2026-08-23 (W-52). **Batch 2 prepared + pushed:**
2026-08-23 (W-55): the GLM sign sibling, the walnutpie robustness trio,
and the SoA-arena issue text. Batch-1 math/stanc3 branches have since
been pushed to the forks (`fork/*` remotes in the local clones); batch-2
branches are pushed (✓ below). This directory is the index: per item,
the branch (in which local clone, at which commit), the push +
PR-creation commands, and the polished body text. Item numbers are
per-batch; **file names are the unique identifiers** (batch 2 uses
`pr-5..pr-8`, `issue-9`).

## Design principle (applies to every PR body in this kit)

Each PR body is written so a maintainer can **re-derive the solution from the
text alone** — complete problem derivation (the actual equations), a
step-by-step solution derivation that can be followed without reading our
diff, and a validation protocol precise enough to re-run. Our patches are
positioned as *reference implementations of the stated derivation, provided
for convenience*, not as the only path to the fix. If a project prefers not
to take LLM-generated code, the text stands on its own.

## Index

### Batch 2 (W-55) — prepared AND pushed to the forks

| # | item | target repo | branch (local clone) | base commit | body text | pushed |
|---|---|---|---|---|---|---|
| 5 | bernoulli_logit_**glm** partials sign (fix) | stan-dev/math | `bernoulli-logit-glm-partials-sign` (`external/math_dev_glm` worktree) | `46a31337…` (same as batch 1) | `pr-5-math-glm-sign.md` | ✓ fork |
| 6 | walnutpie init-protocol guard | walnutpie (fork or upstream) | `robustness/init-guard` (`external/walnutpie_rob` worktree) | `dev/init-robustness` = `3eddfc4` | `pr-6-walnutpie-init-guard.md` | ✓ fork | **HOLD - Stan AI Contribution Policy (stan wiki, May 2026): open no further PRs; branches stay on the fork as documented history. The policy addresses PRs; issues remain the user's call.** **All items now filed as FORK-INTERNAL PRs (math #1-#4, stanc3 #1, docs #1, walnutpie #7-#9); issues remain the user call.**
| 7 | walnutpie freeze-time step clamp (+ probe-fix port) | walnutpie (fork or upstream) | `robustness/freeze-clamp` (same worktree) | same | `pr-7-walnutpie-freeze-clamp.md` | ✓ fork |
| 8 | walnutpie find_reasonable_step fix | walnutpie (fork or upstream) | `robustness/step-heuristic-fix` (same worktree) | same | `pr-8-walnutpie-step-heuristic.md` | ✓ fork |
| 9 | issue: SoA arena / tape-machinery design conversation | stan-dev/math | — (no branch) | math 5.3.0 + develop 344d7167 measured | `issue-9-math-soa-arena.md` | — |

### Batch 1 (W-52) — historical numbering (file names are authoritative)

| # | item | target repo | branch (local clone) | base commit | body text |
|---|---|---|---|---|---|
| 1 | Cluster-aware eigh adjoint (fix) | stan-dev/math | `eigen-cluster-aware-adjoint` (`external/math_dev`) | `46a31337d1534a1a5d5368311d7f32aef5ecc957` | `pr-1-math-cluster-adjoint.md` |
| 2 | square() pow→mul (perf, bit-identical) | stan-dev/math | `square-pow-to-mul` (`external/math_dev`) | `46a31337…` (same) | `pr-2-math-square.md` |
| 3 | bernoulli_logit partials sign (fix) | stan-dev/math | `bernoulli-logit-partials-sign` (`external/math_dev`) | `46a31337…` (same) | `pr-3-math-bernoulli-sign.md` |
| 4 | eigh pair-fusion codegen (perf) | stan-dev/stanc3 | `fuse-eigendecompose-pair` (`external/stanc3_pr`) | `90c653249048b3aaa04bd488fcf20dceebeeda62` | `pr-4-stanc3-eigh-fusion.md` |
| 5 | fork PR already filed | sims1253/stan | PR sims1253/stan#1 (scratch-hoist) | — | (already on GitHub; see below) |
| 5a | issue: compile_model silent cache | stan-dev/bridgestan | — (no branch) | bridgestan 2.9.0 | `issue-5a-bridgestan-cache.md` |
| 5b | issue: default .so unsafe under threads | stan-dev/bridgestan | — (no branch) | bridgestan 2.9.0 | **FILED as bridgestan #336 — closed as documented** (the docs cover STAN_THREADS; the point-of-misuse-signal ask was not taken). `issue-5b-bridgestan-threads.md` kept for the record |
| 6 | issue/proposal: fused packetized log1p kernel | stan-dev/math | — (no branch) | math 5.3.0 measured; develop current | `issue-6-math-fused-log1p.md` |
| 7 | walnutpie robustness trio (notes) | walnutpie | — | — | `notes-7-walnutpie-robustness.md` (superseded as filing text by batch-2 items 6–8; kept for the evidence summary + community cross-references) |

## Branch states as prepared (2026-08-23)

All three batch-1 math branches are **single clean commits** on top of
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

Batch-2 branch states (W-55; all **pushed**):

```
external/math_dev_glm   bernoulli-logit-glm-partials-sign 305cc0cb (2 files, +55/−1; base 46a31337)  → fork ✓
external/walnutpie_rob  robustness/init-guard            1f963eb (1 commit, 3 files +317/−18; base dev/init-robustness 3eddfc4)  → origin(sims1253 fork) ✓
external/walnutpie_rob  robustness/freeze-clamp          c5058ff (2 commits: W-41 clamp 0c95436 + W-43 probe-fix port c5058ff)    → origin ✓
external/walnutpie_rob  robustness/step-heuristic-fix    da42cc2 (1 commit: W-43 probe fix; warmup_heuristics.hpp only)          → origin ✓
```

Notes on the walnutpie cherry-picks (branches are off `dev/init-robustness`
= `3eddfc4`, which already exists on the fork == `origin/dev/init-robustness`):
- `robustness/freeze-clamp` and `robustness/step-heuristic-fix` cherry-picked
  CLEANLY (their files don't overlap the W-23..W-31 commits that separate
  the exp/* lineage from dev/init-robustness).
- `robustness/init-guard` needed a documented adaptation: the original
  exp/init-guard commit 5aed078 also (i) seeds the W-23 endpoint cache
  (`cached_grad_`/`cached_logp_` — members that do not exist on this
  lineage) and (ii) plumbs `--init-tries` through the multi-chain path
  (run_walnuts_multi, likewise absent here). Both parts were dropped; the
  guard itself (config.hpp lp recording, CLI file-init fail-fast,
  random-init rejection loop, `--init-tries`) is unchanged. Commit message
  documents this. All gates were run on the original 5aed078 (report:
  results/init_guard_w42.md); the dropped E5 extra was proven draw-neutral
  by those same gates, so removing it cannot move draws.
- No binaries rebuilt for the trio (gates already run on the originals);
  each branch passed a `g++ -fsyntax-only` check of examples/stan_cli.cpp
  against the branch's own headers (the check that caught the W-23
  dependency in the first place).

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

Verification done at batch-2 preparation (W-55):
- math #5 (GLM sign): test target
  `test/unit/math/rev/prob/bernoulli_logit_glm_lpmf_test` rebuilt and run
  in the `external/math_dev_glm` worktree — **23/23 PASS** with the fix
  (new case `AgradRev.bernoulli_glm_cutoff_partials_sign`); verified to
  **FAIL on the unpatched header** via the stash/rebuild/run/pop cycle
  (adjoints come back sign-flipped by exactly `2·exp(−25)`: −1.3888e-11
  vs expected +1.3888e-11) — discriminating. Rev/mix route through the
  same prim template (no overrides exist); the OpenCL variant carries
  the same pattern and is flagged in the body, not changed.
- walnutpie #6/#7/#8: no rebuilds (gates were run on the original
  commits — see results/init_guard_w42.md, freeze_clamp_w41.md,
  blr_pin_w43.md); per-branch `g++ -fsyntax-only` of stan_cli.cpp only.

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

## Batch-2 filing commands (W-55) — branches are ALREADY PUSHED (✓)

### 5. math — bernoulli_logit_glm partials sign (pushed ✓ to sims1253/math)

```bash
gh pr create --repo stan-dev/math \
  --head sims1253:bernoulli-logit-glm-partials-sign \
  --base develop \
  --title 'Fix missing signs factor in bernoulli_logit_glm_lpmf theta_derivative above the cutoff' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/pr-5-math-glm-sign.md
```

Cross-link it with PR #3 (the non-GLM sibling) whichever way review
prefers — the body already references the sibling by title and offers to
fold both into one PR.

### 6/7/8. walnutpie robustness trio (pushed ✓ to sims1253/walnutpie)

`origin` in `external/walnutpie` IS the user's fork
(git@github.com:sims1253/walnutpie.git) — the branches went there. Two
filing variants depending on where you want the review to happen:

(a) **PRs inside your own fork** (branch `robustness/*` → `dev/init-robustness`,
which already exists on the fork):

```bash
gh pr create --repo sims1253/walnutpie --head robustness/init-guard --base dev/init-robustness \
  --title 'Init-protocol guard: never start a chain at a non-finite-logp position (file-init fail-fast + CLI-owned random-init rejection loop, --init-tries)' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/pr-6-walnutpie-init-guard.md
gh pr create --repo sims1253/walnutpie --head robustness/freeze-clamp --base dev/init-robustness \
  --title 'Freeze-time step clamp: auditable fallback instead of a macro_time abort when the adapted step is degenerate' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/pr-7-walnutpie-freeze-clamp.md
gh pr create --repo sims1253/walnutpie --head robustness/step-heuristic-fix --base dev/init-robustness \
  --title 'Fix find_reasonable_step (3 defects) so --step-init-heuristic actually unpins hard inits (blr w100 bulk-ESS 5-9 -> 779)' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/pr-8-walnutpie-step-heuristic.md
```

(b) **PRs to upstream flatironinstitute/walnutpie** (from the fork, via
`sims1253:` head prefixes). NOTE: check the upstream base branch first
(`gh api repos/flatironinstitute/walnutpie/branches --jq '.[].name'`) —
`dev/init-robustness` exists on the fork; if upstream tracks it, use it,
else target upstream's default branch and note the base in the PR:

```bash
gh pr create --repo flatironinstitute/walnutpie \
  --head sims1253:robustness/init-guard --base dev/init-robustness \
  --title '…' --body-file …/pr-6-walnutpie-init-guard.md   # likewise 7, 8
```

Recommended order if filed sequentially: 6 (root cause) → 7 (second line
of defense; depends on 8's probe fix, which it carries) → 8 (standalone).
If 8 is merged first, 7's second commit becomes a cherry-pick no-op.

### 9. math — SoA arena / tape-machinery design conversation (issue; no branch)

```bash
gh issue create --repo stan-dev/math \
  --title 'Design conversation: batch vari allocation + span nochain registration (and typed pools) — measured 10.9% instructions on eltwise models, bit-identical sampler proven' \
  --body-file /home/m0hawk/Documents/apin/stan/external/pr/issue-9-math-soa-arena.md
```

Conversation-starter, not a PR (the vertical-slice patch exists locally
in scratch/w53 and is offered as a reference implementation in the body).

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
  stan/math/prim/prob/bernoulli_logit_lpmf.hpp \
  stan/math/prim/prob/bernoulli_logit_glm_lpmf.hpp
# empty => zero drift in the touched files; anything else => rebase first
```

stanc3 master was re-verified at 90c6532 on 2026-08-23 (tip == base).

## What could NOT be verified locally (be ready for these in review)

- math develop moved past 46a3133 since 2026-08-23 morning — run the drift
  check above; the patches are small and confined.
- CI on other platforms/compilers (macOS clang, MSVC): the cluster-adjoint
  patch uses only Eigen + std headers; the new tests use only gtest + Eigen
  and integer-only LCG data (platform-deterministic). The bernoulli tests
  use exact analytic + FD references (no platform-sensitive tolerances).
- Eigen-5 numerical behavior of the masked path at κ other than 1e3 was not
  re-swept on develop (the κ sweep in the evidence table was measured on the
  cmdstan-2.39/Eigen-3.4.0 toolchain; the guard math is Eigen-independent).

Batch-2 specific (W-55):
- The GLM fix's OpenCL sibling (`opencl/prim/bernoulli_logit_glm_lpmf.hpp`,
  same missing-signs first branch) is flagged in the body but NOT fixed —
  validating it needs a STAN_OPENCL build/GPU environment.
- walnutpie batch-2 gates were run on the ORIGINAL exp/* commits (reports
  in results/), not re-run on the re-based robustness/* branches; the
  init-guard branch additionally drops the W-23-dependent E5 extra
  (proven draw-neutral by the original gates). A syntax check (not a
  rebuild) was done per branch.
- Whether upstream flatironinstitute/walnutpie tracks a
  `dev/init-robustness` base branch is unverified — check before using
  filing variant (b).
