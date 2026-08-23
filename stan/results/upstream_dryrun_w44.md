# W-44 — Upstream dry-run: the W-40 cluster-adjoint patch, Kit 1's square() fix, and Kit 2's stanc3 patch validated against TODAY'S real target repos

Date: 2026-08-22 (session: 2026-08-23). Pre-registration: WORKLOG.md
W-44. Mission: dry-run the upstream kits against the real target repos
so the user's PRs land pre-validated. NO PUSHING anywhere — everything
below is local. Clones under external/ are untracked.

**One-line result: all three patch-carrying kits are GREEN against
today's target tips. Kit 4's cluster-adjoint patch ports to math develop
@ 46a3133 with only the predicted `.val_op()`→`.val()` cosmetic hunks
hand-completed; every existing unit test of the touched functions passes
(incl. the mix FD-reference tests), and the ported W-40
degenerate-spectrum test file passes 4/4 with the patch while 2/4 fail
on stock with exactly the NaN the issue describes. Kit 1's square()/
squared_distance fix passes all four prim+mix test binaries and a
bit-identity micro-check (incl. the int-promotion and float
double-rounding corners). Kit 2's stanc3 patch needs NO rebase: stanc3
master's tip is still 90c6532, the exact commit W-39 validated, and the
applied tree still diff-matches the patch byte-for-byte.**

Environment: gcc 16.2.1, `env -u LD_LIBRARY_PATH`, `/usr/bin/make -j2`,
serialized; math clone is self-contained (Eigen 5.0.1, boost 1.87.0,
TBB, googletest all vendored in-tree — no submodules).

---

## Kit 4 — cluster-aware eigenvector adjoint (stan-math)

**Target repo/commit:** stan-dev/math develop @
`46a31337d1534a1a5d5368311d7f32aef5ecc957` (2026-08-12, "Merge pull
request #3346 from florence-bockting/feat/map-helpers"), shallow clone
at `external/math_dev` (untracked). Eigen 5.0.1 vendored.

**Patch apply status: 3 of 5 hunks clean, 2 hand-ported (trivial,
predicted).** `git apply` of `scratch/w40/cluster_adjoint.patch`:
- `eigenvectors_sym.hpp`: hunk 1 (macro block) + hunk 2 (cluster guard)
  applied cleanly; hunk 3 (the one-line else-branch closing brace)
  rejected — its context contains `eigenvecs.val_op()`, which develop
  renamed to `eigenvecs.val()` (the exact cosmetic W-40 §5 predicted).
- `eigendecompose_sym.hpp`: hunk 1 (macro block) clean; hunk 2 (the
  guard) rejected wholesale for the same `val_op()` → `val()` reason
  (`eigenvals.val_op()` → `eigenvals.val()` etc.).
- Hand-completion recorded: in both rejected hunks every added line was
  rewritten `*.val_op()` → `*.val()` to match develop's API
  (`.adj_op()` was already develop's spelling and is unchanged); no
  logic edits, no moved lines, no other drift. Ported patch saved as
  `scratch/w44/cluster_adjoint_dev_46a3133.patch` (source only) and
  `scratch/w44/cluster_adjoint_dev_with_tests_46a3133.patch` (source +
  the new test below) — the PR should carry the latter against develop.

**Existing repo tests with the patch applied (all PASS):**

| test | result |
|---|---|
| `test/unit/math/rev/fun/eigenvectors_sym_test` | 1/1 PASS |
| `test/unit/math/rev/fun/eigenvalues_sym_test` | 1/1 PASS |
| `test/unit/math/prim/fun/eigendecompose_sym_test` | 1/1 PASS |
| `test/unit/math/mix/fun/eigenvectors_sym_test` | 2/2 PASS |
| `test/unit/math/mix/fun/eigenvalues_sym_test` | 2/2 PASS |
| `test/unit/math/mix/fun/eigendecompose_sym_test` | 2/2 PASS |

The mix tests are the ones that check rev gradients against finite
differences — the patch's well-separated path is untouched by
construction and they confirm it. Build: `make -j2 <target>` (repo's own
make/test structure; first target builds gtest + TBB once), run the
binary directly.

**New degenerate-spectrum test file (the PR's test):
`scratch/w44/eigen_cluster_adjoint_test.cpp`** — 4 gtest cases in the
repo's conventions (`TEST_F(AgradRev, ...)`, rev/util.hpp fixture,
integer-only LCG matrices so the tests are platform-deterministic):
1. `eigenvectors_sym_exact_repeated_eigenvalue` — exactly 4-fold
   repeated eigenvalue: all gradient components finite (stock: NaN in
   every cluster-coupled component) + Richardson-FD consistency ≤1e-8
   on cluster-diagonal {(0,0),(1,1)}, separated-diagonal {(5,5)} and
   cross-cluster {(0,7)} directions + two-call vs `eigendecompose_sym`
   gradients bit-identical.
2. `eigenvectors_sym_total_degeneracy_zero_matrix` — zero matrix
   (n-fold exact degeneracy): all components finite, both primitives.
3. `eigenvectors_sym_jitter_floor_kernel` — 30-pt exp-quad kernel +
   1e-5 jitter (bottom 10 eigenvalues pinned at the floor, 8 adjacent
   gaps below tau → the guard FIRES here; verified by spectrum dump):
   finite + two-call vs combined bit-identical.
4. `eigenvectors_sym_well_separated_matches_textbook_adjoint` — 10 LCG
   matrices with enforced min-gap ≥1e-6·scale: both primitives
   reproduce the textbook adjoint V(F∘(VᵀG_V))Vᵀ + V diag(g_w) Vᵀ to
   ≤1e-12 (measured 4.4e-16; a fired guard would show O(1) drift).

Results: **with patch 4/4 PASS; on stock 2/4 FAIL** — tests 1 and 2
fail with exactly the NaN the issue describes (test 3 also passes on
stock: rounding-level gaps are never exact zeros, so it is a
finiteness/consistency test, not a stock-discriminating one; test 4
passes on stock by design — it guards against the fix overreaching).

**Honest record of test-porting stumbles (all in MY test file, not the
patch; found by the dry run, fixed before saving):** (a) the first
draft asserted bit-exact equality (EXPECT_DOUBLE_EQ) against a
hand-written reference — GEMM blocking differences between the
primitive's `adj_op()` matrix and the test's plain matrix reorder the
sums by ~4e-16; relaxed to 1e-12 with a max-abs debug harness
confirming agreement 4.4e-16 (i.e., the primitive adjoints were right
all along); (b) the first draft read the gradient vector row-major
against Eigen's column-major layout — the operand adjoint is NOT
symmetric (antisymmetric F ∘ generic downstream), so the transposed
read corrupted entries; fixed by returning a MatrixXd; (c) the first
draft FD-checked the within-cluster MIXING directions {(0,1),(2,3)},
where the gauge deliberately returns 0 while FD gives the bounded true
value — W-40 §1.2(3)'s provably-dropped term; the FD-consistency
claim is only made on the cluster-symmetric/diagonal/cross directions
where the masked adjoint IS the exact derivative (all pass ≤1e-8,
measured ~1e-10). These are exactly the distinctions the PR text must
carry — the dry run surfaced them before review could.

**Red flags: none.** No existing test fails with the patch; the port
touches only the predicted cosmetic API renames; behavior under Eigen 5
is now COMPILED and tested (W-40's §8 "not established: behavior under
Eigen 5" is closed).

## Kit 1 — square() should multiply (stan-math)

**Target repo/commit:** same clone, second clean state (`git stash` of
the Kit 4 patch; square.hpp/squared_distance.hpp pristine at 46a3133).

**Apply status:** `scratch/w33/pow_to_mul.patch` still context-matches
develop's square.hpp exactly (the `std::pow(x, 2)` line is unchanged),
but the dry run used the ADAPTED version per the kit's own caveats,
saved as `scratch/w44/square_fix_dev_46a3133.patch`:
- `prim/fun/square.hpp`: `const double x_d = x; return x_d * x_d;` —
  widen-to-double-first covers BOTH kit caveats at once: integral
  arguments keep the promoted semantics (x*x as int could overflow) and
  float arguments avoid the double-rounding drift of a float multiply.
- `rev/fun/squared_distance.hpp`: the two sibling `std::pow(a.val() −
  b(·val()), 2)` sites hoisted to `diff * diff` with the difference
  captured once and reused in the callback (vector paths already use
  squaredNorm/diff*diff — untouched).

**Tests (all PASS):** `test/unit/math/prim/fun/square_test` (2/2),
`test/unit/math/prim/fun/squared_distance_test` (7/7),
`test/unit/math/mix/fun/square_test` (1/1),
`test/unit/math/mix/fun/squared_distance_test` (2/2).

**Bit-identity micro-check (PASS):** edited square() == std::pow(x,2)
exactly on int64 3e9 (promotion), int −46341 (int-overflow corner),
float 1.0000001f (double-rounding corner), and a double sweep
{−3.7e5 … 1e300} incl. the overflow-to-inf case — confirming the
widen-first formulation, not just `x*x`, is the right PR shape.

**Red flags: none.** Tree restored to Kit 4 state after testing.

## Kit 2 — stanc3 eigh pair fusion (stanc3)

**Target repo/commit:** stan-dev/stanc3 default branch is **master**
(no develop branch exists); tip TODAY is still
`90c653249048b3aaa04bd488fcf20dceebeeda62` — **the exact commit W-39
implemented and dune-validated against. Zero drift since 2026-08-22.**

**Apply status: verified by round-trip, not just --check.** The W-39
clone at external/stanc3 still carries the patch applied; `git diff
HEAD` there vs `scratch/w39/stanc3_eigh.patch` is EMPTY after
normalizing `index` lines — the applied tree is byte-identical to the
patch, i.e. the patch applies exactly at the current tip. No rebase
needed; W-39's full `dune runtest` pass at 90c6532 remains the
validation of record (not re-run: the target commit is unchanged, and
re-running the OCaml suite is not "quick").

**Red flags: none.**

## Kit 3 — bridgestan compile_model cache (issue-only, no patch) — SKIPPED per plan.

## Kit 5 — walnutpie upstream (not in this dry-run's scope; local branch exp/safe-adapt-defaults stands).

---

## Verdicts

| kit | target @ commit | apply | tests | red flags | PR-ready? |
|---|---|---|---|---|---|
| 1 square() | math develop @ 46a3133 | adapted patch, clean | 4/4 binaries PASS + micro bit-identity | none | **YES** — carry `scratch/w44/square_fix_dev_46a3133.patch` |
| 2 stanc3 fusion | stanc3 master @ 90c6532 | zero drift, byte-verified | W-39 dune runtest (same commit) stands | none | **YES** — patch as-is |
| 4 cluster adjoint | math develop @ 46a3133 | 3 hunks clean + 2 predicted-cosmetic hand-ports | 6/6 existing + 4/4 new (2 NaN-fails on stock) | none | **YES** — carry `scratch/w44/cluster_adjoint_dev_with_tests_46a3133.patch`; file issue + PR per results/cluster_adjoint_w40.md §6 |

Artifacts: `scratch/w44/{cluster_adjoint_dev_46a3133.patch,
cluster_adjoint_dev_with_tests_46a3133.patch,
eigen_cluster_adjoint_test.cpp, square_fix_dev_46a3133.patch}`;
clone left at external/math_dev (untracked, Kit 4 patch + test applied,
commit 46a3133 recorded above); external/stanc3 index restored to its
W-39 state after inspection.
