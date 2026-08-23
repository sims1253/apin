# Fuse adjacent eigenvectors_sym/eigenvalues_sym pairs into one eigendecompose_sym call (--O1+), pedantic warning

## Problem

### What the compiler emits today

A Stan program that needs both the eigenvectors and the eigenvalues of a
symmetric matrix — the natural two-call idiom, and what essentially all
pre-2.34 GP / latent-factor code looks like:

```stan
matrix[N, N] Q = eigenvectors_sym(A);
vector[N] w = eigenvalues_sym(A);
```

is compiled to two independent calls. Each stan-math primitive internally
constructs and runs a **full `SelfAdjointEigenSolver` in
`ComputeEigenvectors` mode**: `eigenvectors_sym` because its output is V,
and `eigenvalues_sym` because its *reverse-mode adjoint needs V* (the
operand adjoint `V diag(ḡ_w) Vᵀ` requires the vectors), so it cannot take
the cheaper `EigenvaluesOnly` path. Consequences per gradient evaluation,
for every symmetric matrix treated this way:

- **2 full decompositions where 1 suffices**, both computing values *and*
  vectors and each discarding half the result;
- 2 separate reverse-pass callbacks instead of 1.

On a Kronecker-GP-class model (two symmetric eigendecompositions of 30×30
and one 2×2 per gradient), eigh is 39.3% of total program instructions,
and the model runs **4 full decompositions per gradient where 2 would
suffice**.

### The combined primitive already exists

`eigendecompose_sym` — one solver run, one callback, both adjoints —
landed Aug 2023 (math PR #2931, stanc3 PR #1346; language support since
**CmdStan 2.34**, Jan 2024). Models can be rewritten by hand:

```stan
tuple(matrix, vector) eigh_A = eigendecompose_sym(A);
matrix[N, N] Q = eigh_A.1;
vector[N] w = eigh_A.2;
```

and we verified this rewrite is **bit-identical** at the model level (the
two-callback adjoints and the combined callback accumulate into the same
zero-initialized operand adjoint, and the values come from the same Eigen
solver either way — structural, not luck). But the compiler never
generates it from the two-call idiom, so the entire corpus of existing
models keeps paying double. This PR teaches stanc3 to do the rewrite.

## Evidence

Kronecker-GP-class model; matched binaries, identical inputs; medians of
3 interleaved reps; callgrind on a fixed seeded run; gcc 16.2.1, Zen 3.

**Language-level rewrite (stan-math 5.3.0 toolchain)** — establishes the
ceiling and the bit-identity:

| arm | Ir / gradient | µs / call | draws |
|---|---|---|---|
| stock (two-call codegen) | 5.254M | 393.0 | — |
| hand rewrite via `eigendecompose_sym` | **4.238M (−19.4%)** | **337.0 (−14.3%)** | **bit-identical** (draws md5, same 5094 gradient calls) |

**Compiler-generated fusion (stanc3 develop @ 90c6532 with this patch,
`--O1`)** — the PR's own effect:

| arm | µs / call (3 reps) | median | ratio |
|---|---|---|---|
| vanilla develop stanc, `--O1` | 409.0 / 406.8 / 405.5 | 406.8 | 1 |
| patched stanc, `--O1` (fusion) | 367.7 / 341.4 / 343.4 | 343.4 | **0.844 (−15.6%)** |

with the fused `.so` **bit-identical** to the vanilla-develop `.so` on 50
random N(0,1) unconstrained points: max rel logp 0.00e+00, worst gradient
rel-L2 0.00e+00, constrained outputs bit-identical. The compiler fusion
realizes the language-level ceiling within noise, with no model rewrite.

## Solution (the rewrite rule, re-derivable from this text)

### Exact rule

Scan statement lists in every program block and user function. When **two
adjacent statements** are full assignments

```
<target1> = eigenvectors_sym(<ARG>);
<target2> = eigenvalues_sym(<ARG>);
```

(in either order, at any nesting depth), and all gates below hold, replace
the pair with

```
tuple(<type1>, <type2>) eigh_fusedsym<N>__ = eigendecompose_sym(<ARG>);
<target1> = eigh_fusedsym<N>__.1;
<target2> = eigh_fusedsym<N>__.2;
```

preserving the original target names and their order, where `<type1>` /
`<type2>` reuse the sized-declaration dimensions of the two targets when
both are found (else an unsized tuple decl — identical generated C++,
dynamic Eigen types).

Generated C++ before (abridged, per matrix):

```cpp
Eigen::Matrix<double, -1, -1> Q = stan::math::eigenvectors_sym(A);
Eigen::Matrix<double, -1, 1>  w = stan::math::eigenvalues_sym(A);
```

after:

```cpp
std::tuple<Eigen::Matrix<double, -1, -1>, Eigen::Matrix<double, -1, 1>>
    eigh_fusedsym0__ = stan::math::eigendecompose_sym(A);
Eigen::Matrix<double, -1, -1> Q = std::get<0>(eigh_fusedsym0__);
Eigen::Matrix<double, -1, 1>  w = std::get<1>(eigh_fusedsym0__);
```

### Gates (all must hold; otherwise the pair is left untouched)

1. **Structurally equal arguments** — the two argument expressions match
   under structural equality (`Expr.Typed.equal`, locations ignored).
2. **Distinct plain-variable targets, no index expressions**, and the
   argument does not reference either target.
3. **The argument is side-effect-free**: no target-incrementing calls, no
   RNG calls, no compiler-internal effectful calls (the same
   `cannot_duplicate_expr` predicate the optimizer already trusts), and no
   user-defined function calls (conservative: they may print/reject).
   This is required because the fused form evaluates the shared argument
   **once** instead of twice — the only semantic difference the rewrite
   introduces, and exactly the difference the gates must license.
4. **Adjacency** — no intervening statement (no dataflow proof available
   that the argument is unchanged in between; decl-initializer pairs and
   non-adjacent pairs are deliberately out of scope).
5. **Complex targets** (`complex_matrix`) keep the real decomposition and
   re-promote the two projections (bit-identity preserved); a genuinely
   complex argument fuses via the complex overload.

Pass placement: after function inlining + constant folding, so the
existing copy-propagation / DCE / unenforce-initialize passes clean up
around the tuple decl. Enabled at `--O1` and `--Oexperimental`, off at
`--O0`.

### Pedantic warning

Under `--warn-pedantic`, fire once per distinct shared (pure) argument when
the same argument feeds both primitives anywhere in log_prob or a function
body — including the non-adjacent pairs the optimizer cannot fuse —
recommending the `tuple(matrix, vector) e = eigendecompose_sym(A);` form
(available since CmdStan 2.34) and noting `--O1`+ fuses adjacent pairs
automatically.

The diff is one concrete implementation of the above (a peephole in
`Optimize.ml` + a pass in `Pedantic_analysis.ml` + golden tests); a
maintainer can re-implement the rule from this section alone.

## Validation

- **Golden tests** (`test/integration/good/compiler-optimizations/eigh-fusion.stan`
  with `cppO0/cppO1/cpp.expected`): fused pair, reversed-order pair,
  different-arguments NOT fused, non-adjacent NOT fused, nested-block
  fusion — at all three optimization levels; plus
  `test/integration/cli-args/warn-pedantic/eigh-pair.stan` for the
  warning and its suppression on distinct arguments. Regenerated expected
  files are purely additive relative to develop.
- **Full `dune runtest` passes** at the base commit (90c6532).
- **End-to-end model parity and timing** (the tables above): fused .so
  bit-identical to vanilla-develop .so on 50 points, −15.6% µs/call
  median; hpp-level token comparison against the known-good language
  rewrite confirms identical eigen regions in all three instantiations.
- **Edge-model sweep** (local): reversed order, non-adjacent,
  different-args, user-fn argument (not fused — gate 3), complex target,
  nested-in-loop, plus O0/no-fusion and Oexperimental/fusion level checks
  — all behave as designed.

## References

- math PR #2931 and stanc3 PR #1346 — `eigendecompose_sym` primitive and
  language support (shipped math 4.8.0 / CmdStan 2.34).
- The bit-identity argument in full: the two-callback adjoints
  (`eigenvectors_sym`: `V(F∘(VᵀḠ_V))Vᵀ`; `eigenvalues_sym`:
  `V diag(ḡ_w)Vᵀ`) accumulate into the same zero-initialized operand
  adjoint that the combined callback builds in one pass; forward values
  come from the same Eigen solver call.
- The ceiling and bit-identity measurements, the pass implementation
  gates, and the zero-drift tip re-verification are available on request
  or via the public benchmark repo (https://github.com/sims1253/apin —
  `stan/results/` and `stan/WORKLOG.md`); happy to attach.
