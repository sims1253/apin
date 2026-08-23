# W-39 — stanc3 built from develop + eigh pair-fusion implemented and validated; fresh vectorize_loops verdict

Date: 2026-08-23. Pre-registration: WORKLOG.md W-39. Mission: Kit 2 of
`external/upstream_pr_kits.md` — make stanc3 fuse the
`eigenvectors_sym(A)` + `eigenvalues_sym(A)` pair (evidence:
`results/eigh_reuse_w32.md`; novelty: `results/upstream_scan_2026-08.md` §1).

**Headline: BOTH deliverables implemented on stanc3 develop @ 90c6532 —
(1) a `fuse_eigendecompose` optimization pass (enabled at `--O1`/`--Oexperimental`)
that rewrites the adjacent pair into one `eigendecompose_sym` call, and (2) a
pedantic-mode warning recommending the primitive. On kronecker_gp the fused
build is BIT-IDENTICAL to the vanilla-develop two-call build (logp, full
gradient, constrained outputs — worst rel-L2 exactly 0.0) and 15.6% faster
per gradient call (406.8 → 343.4 µs, median of 3), matching W-32's
language-level rewrite within noise. Full stanc3 test suite passes.**

## 1. Toolchain (userspace, no root)

- opam 2.5.2 standalone (`~/.local/bin/opam`); **OCaml 5.5.0 SOURCE-BUILT
  switch `w39`** (`ocaml-base-compiler.5.5.0`, ~25 min at -j2). The distro's
  ocaml-system 5.5.0 package splits `compiler-libs` into an uninstalled pacman
  package, which breaks ocamlfind 1.9.9~preview (`Unbound module Topdirs`) and
  everything downstream (base → ppx_compare/ppx_sexp_conv). Building the
  compiler from source via opam resolves the whole graph; `stanc.opam` pins
  `ocaml {= 5.5.0}` exactly — satisfied either way.
- stanc3 develop cloned to `external/stanc3` (untracked) @
  **90c653249048b3aaa04bd488fcf20dceebeeda62** ("Merge pull request #1672 from
  nhuurre/fix/vectorize-loops-nobase"; tip of develop as of 2026-08-22 —
  includes the vectorize_loops PR #1666 and its #1672 follow-up).
- Vanilla build verified before patching (`stanc --version` runs; the
  `%%VERSION%%` placeholders are unexpanded because `dune subst` only runs for
  opam-release installs — cosmetic, identical in both arms).
- Deps: `opam install --deps-only ./stanc.opam` + `ppx_sexp_value` (with-test).

## 2. Implementation (patch: `scratch/w39/stanc3_eigh.patch`)

### 2a. Fusion pass — `Optimize.fuse_eigendecompose`

`src/analysis_and_optimization/Optimize.ml` (+ `.mli`): a peephole over
statement lists in every program block and user function. When two ADJACENT
statements are full assignments of `eigenvectors_sym(A)` / `eigenvalues_sym(A)`
(in either order, at any nesting depth) to plain variables, they are replaced by

```
tuple(matrix, vector) eigh_fusedsym<N>__ = eigendecompose_sym(A);
V = eigh_fusedsym<N>__.1;   // original variable names and order preserved
w = eigh_fusedsym<N>__.2;
```

Gates (all must hold, otherwise the pair is left untouched):
- the two argument expressions are structurally identical
  (`Expr.Typed.equal`, which ignores locations);
- distinct plain-variable assignment targets (no indices), and the argument
  does not reference either target;
- the argument is free of side effects — no target-incrementing calls, no RNG,
  no compiler-internal effectful calls (`cannot_duplicate_expr`), and no
  user-defined function calls (conservative: they may print/reject) — because
  the fused form evaluates the shared argument once instead of twice;
- complex targets (`complex_matrix V`) are supported by keeping the REAL
  decomposition and re-promoting the two projections (bit-identity preserved);
  a genuinely complex argument fuses via the complex overload.

The synthesized tuple declaration reuses the dimension expressions of the two
targets' sized declarations when both are found (kronecker_gp: `n1`/`n2`), else
falls back to an unsized tuple decl (identical C++ — dynamic Eigen types).
Placement in the suite: right after function inlining + constant folding, so
the later copy-propagation / DCE / unenforce-initialize passes clean up around
it (`Decl(Default)` + adjacent assignment becomes an uninit decl, no dummy
`Constant` init). Enabled at `--O1` and `--Oexperimental`, off at `--O0`.

Deliberately NOT fused: non-adjacent pairs (no dataflow proof that the
argument is unchanged in between), decl-initializer pairs
(`matrix Q = eigenvectors_sym(A);`), compound-index args.

### 2b. Pedantic warning — `eigh_pair_warnings`

`src/analysis_and_optimization/Pedantic_analysis.ml`: under `--warn-pedantic`,
fires once per distinct shared argument when the same (pure) argument
expression feeds both calls anywhere in log_prob or a function body. Message
recommends `tuple(matrix, vector) e = eigendecompose_sym(A);` (available since
CmdStan 2.34) and notes that `--O1`+ fuses adjacent pairs automatically.

### 2c. Tests

- `test/integration/good/compiler-optimizations/eigh-fusion.stan`: fused /
  reversed-order fused / different-args not fused / non-adjacent not fused /
  nested-block fused. Golden files `cpp.expected` (`--Oexperimental`),
  `cppO1.expected`, `cppO0.expected` regenerated — diffs purely additive
  (numstat 949/0, 837/0, 811/0).
- `test/integration/cli-args/warn-pedantic/eigh-pair.stan` + regenerated
  `stanc.expected` (9 lines added).
- **`dune runtest` (full suite): PASS, zero failures.**
- Local edge models in `scratch/w39/`: pair, reversed, non-adjacent,
  different-args, user-fn-arg, complex-target, nested-in-loop, plus
  O0/no-fusion and Oexperimental/fusion level checks — all behave as designed.

## 3. Validation (kronecker_gp; pre-registered gates)

Arms (fresh dirs, bridgestan 2.9.0, default CXXFLAGS, `env -u LD_LIBRARY_PATH`,
make -j2, custom stanc injected via `make_args=['STANC=...']`,
`stanc_args=['--O1']`):
- `so_stock`: `models/kronecker_gp.stan` × **vanilla develop stanc** --O1
  (two-call codegen);
- `so_fused`: same model × **patched stanc** --O1 (fusion).

### (a) Semantics — PASS

hpp level: patched `kronecker_gp` vs the known-good language rewrite
(`harness/w32/kronecker_gp_eigendecompose.stan` × vanilla stanc --O1),
normalized diff (names/locations/wraps stripped): the eigen regions are token-
identical (`std::tuple` + `assign(ED, eigendecompose_sym(Sigma1/Lambda))` +
`std::get<0/1>` projections in all three instantiations). Only differences:
the lang arm emits 3 redundant `validate_non_negative_index("ed", "n1", n1)`
per site (frontend-generated for user-written sized tuple decls; the fused
decl skips them — those dimensions are already validated at Q1/R1's own
decls), temp names, statement numbering/locations array, line wrapping, and
`local_scalar_t__` (= double) vs `double` in write_array.

.so level: **bit-identical** on 50 random N(0,1) unconstrained points —
max rel logp 0.00e+00, worst gradient rel-L2 0.00e+00, worst cos 1.0,
`array_equal` on every gradient, and constrained outputs bit-identical
(10 pts). Pre-registered bar (rel-L2 == 0.0 exactly) met — confirming W-32's
structural bit-identity argument transfers from the language-level rewrite to
compiler-generated code.

### (b) Timing — PASS (matches W-32's lang arm)

| arm | us/call (3 interleaved reps) | median | ratio |
|---|---|---|---|
| stock (vanilla develop, two-call) | 409.0 / 406.8 / 405.5 | 406.8 | 1 |
| fused (patched --O1) | 367.7 / 341.4 / 343.4 | 343.4 | **0.844 (−15.6%)** |

(100 posterior-cloud points, taskset 0-3, serialized. W-32 lang arm reference:
337.0 vs 393.0 µs = −14.3% on the 2.39 toolchain — consistent.)

### (c) Warning coverage — PASS

- `models/kronecker_gp.stan`: fires twice (Sigma1 pair, Lambda pair), correct
  lines.
- Silent on the eigh pattern for: hier_2pl, gp_regr, lotka_volterra, arma11,
  accel_gp (their other, pre-existing pedantic warnings unchanged), and on
  `harness/w32/kronecker_gp_eigendecompose.stan` (no warnings at all).

### (d) Suite — PASS

`dune runtest` clean (see 2c).

## 4. vectorize_loops verdict (secondary; develop stanc, cmdstan-2.39-era math via bridgestan 2.9.0)

- **Compilation: 21/21 models compile with `--Oexperimental`** — same with
  vanilla and with patched stanc (the fusion does not interact). Phase 0's
  old-`--Oexperimental` verdict (3/21 uncompilable + 1 silent miscompile) is
  superseded: the new pass set compiles our whole grid cleanly.
- **Coverage on our model set: 0/21.** No model contains an eligible loop:
  either the likelihood is already vectorized syntax, or the loop argument is
  compound-indexed (`beta*theta - alpha[k]*ones` in lsat_model,
  `log(z_init[k])` in lotka_volterra) — the pass only vectorizes arguments
  that are exactly `x[n]` or loop-invariant (the documented follow-up work,
  stanc3 #1666). So no grid-model .so comparison was possible; instead the
  pass itself was measured on two synthetic eligible models:
  `for (n in 1:N) y[n] ~ normal(mu, sigma)` and
  `for (n in 1:N) y[n] ~ bernoulli_logit(eta[n])`.
- **Correctness when it fires:** N=2000: bit-identical (logp and gradient).
  N=200,000: max rel logp 1.9e-14, worst gradient rel-L2 2.0e-14 —
  rounding-level reordering, statistical parity as expected.
- **Speed when it fires:** N=2000: 57.1 vs 57.8 µs/call (ratio 1.01 — masked
  by per-call fixed overhead). N=200,000: **7710.6 → 285.8 µs/call = 27×
  (ratio 0.037)**, medians of 3 interleaved reps.
- Verdict: the new `--Oexperimental` is compile-clean and, where the pattern
  matches, large-N-correct and very fast; our grid simply has no eligible
  loops. If we ever adopt models with scalar-loop likelihoods, `--Oexperimental`
  is worth it; for the current grid it is a no-op.

## 5. Reproduction

```
# builds (custom stanc into bridgestan via STANC make arg):
env -u LD_LIBRARY_PATH BRIDGESTAN=~/.bridgestan/bridgestan-2.9.0 MAKEFLAGS=-j2 \
  uv run python -c "import bridgestan; \
  bridgestan.compile_model('scratch/w39/<arm>/kronecker_gp.stan', \
    make_args=['STANC=scratch/w39/stanc_<vanilla|patched>.exe'], stanc_args=['--O1'])"
# gates:
env -u LD_LIBRARY_PATH taskset -c 0-3 uv run python scratch/w39/w39_gates.py
env -u LD_LIBRARY_PATH taskset -c 0-3 uv run python scratch/w39/w39_vec_gates.py
env -u LD_LIBRARY_PATH taskset -c 0-3 uv run python scratch/w39/w39_vec_big.py
# patch (against stanc3 develop @ 90c6532):
git -C external/stanc3 apply < scratch/w39/stanc3_eigh.patch
```

Artifacts: `scratch/w39/` (stanc binaries, arms, hpps, gate scripts, patch,
edge models, Oexperimental sweep); `results/stanc3_w39.md` (this file).
`external/stanc3` stays untracked; the pinned commit and patch are recorded
here and in WORKLOG W-39.
