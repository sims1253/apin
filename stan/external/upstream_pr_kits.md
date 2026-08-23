# Upstream PR/issue kits — ready-to-paste texts

**Date:** 2026-08-23. Companion to `upstream_candidates.md` (evidence lives
there); this file holds the actual texts to paste when the user pushes.
Patches referenced live under `scratch/` or on walnutpie exp branches —
verify they still apply at push time. Do NOT push from this repo; these are
drafts for the user's own accounts.

---

## Kit 1 — stan-math PR: `square()` should multiply, not call `std::pow`

**Title:** `square()` for arithmetic types calls `std::pow(x, 2)` — use `x * x`

**Body draft:**

`stan/math/prim/fun/square.hpp` implements `square(x)` for arithmetic `x` as
`std::pow(x, 2)`, while its own doc comment says "return the square of the
argument ... just `x * x`". `std::pow` is a function call glibc cannot
constant-fold as well as a multiply, and it shows up in hot paths: on a GP
regression model (`gp_exp_quad_cov`, n=11, 55 kernel pairs), `square` is 57
`pow` calls per gradient and 8.9% of gradient instructions (callgrind, Ir).

Measured (matched binaries, identical inputs, glibc):

| metric | stock | `x * x` | delta |
|---|---|---|---|
| Ir / gradient | 66,950 | 60,864 | −9.1% |
| µs / logp_grad (warmup) | 6.681 | 5.820 | −12.9% |
| µs / logp_grad (sampling) | 6.655 | 5.640 | −15.2% |

Gradients are **bit-identical** on glibc (correctly-rounded `pow` gives
`pow(x,2) == x*x` exactly); on other libms ≤1 ulp drift is possible, which
falls under normal FP non-associativity. Full protocol: WORKLOG W-33 in our
benchmark repo; patch: `scratch/w33/pow_to_mul.patch` (one line).

Caveats to address in the patch (we did not need them for the measured
models, but review should decide):
- keep the `int` overload semantics safe: `x * x` for integral `x` can
  overflow where `std::pow` promotes to `double` — use
  `if constexpr (std::is_integral_v<T>)` to keep the promoted path, or
  static_assert/widen first;
- sibling sites with the same pattern: `stan/math/rev/fun/squared_distance.hpp`
  lines ~24 and ~38 (`std::pow(x - y, 2)`) — same one-line treatment.

---

## Kit 2 — stanc3 issue (+ optional PR): fuse the `eigenvectors_sym`/`eigenvalues_sym` pair

**Title:** Codegen emits two full eigendecompositions where one suffices (`eigenvectors_sym(A)` + `eigenvalues_sym(A)`)

**Body draft:**

For a Stan program using both `eigenvectors_sym(A)` and `eigenvalues_sym(A)`
on the same matrix (common in GP kernels: kronecker / latent-factor models),
stanc3 emits two separate calls. Each stan-math primitive constructs its own
full `SelfAdjointEigenSolver` in ComputeEigenvectors mode (the reverse-mode
`eigenvalues_sym` cannot use the cheaper EigenvaluesOnly path because its
adjoint needs V), so **every gradient evaluation runs 4 full decompositions
where 2 would suffice**.

stan-math 5.3.0 already ships the combined primitive (`eigendecompose_sym`,
also exposed in the language since 2.39). Measured on kronecker_gp
(2 × eigh of 30×30 + 2×2 per gradient; callgrind + matched-wall protocol):

| arm | Ir/grad | µs/call | draws |
|---|---|---|---|
| stock (two-call) | 5.254M | 393.0 | — |
| `eigendecompose_sym` rewrite | 4.238M (−19.4%) | 337.0 (−14.3%) | **bit-identical** (draws md5, same 5094 gradient calls) |

Bit-identity is structural, not luck: the two-callback adjoints and the
combined adjoint accumulate into the same zero-initialized operand adjoint,
and the values are computed by the same Eigen solver either way.

**Ask:** a stanc3 peephole (or at least a pedantic-mode note) that rewrites
the `eigenvectors_sym(A)`, `eigenvalues_sym(A)` pair on the same `A` to the
`eigendecompose_sym` form. Full evidence and the adjoint derivation:
`results/eigh_reuse_w32.md` in our benchmark repo (happy to attach).
Regression-test candidate: models with near-degenerate eigenvalue clusters
(exp-quad kernels) — the same jitter floor that makes FD checks unreliable
there (see Kit 4).

---

## Kit 3 — bridgestan issue: `compile_model` silently reuses a cached `.so`

**Title:** `compile_model` returns a cached `<stem>_model.so` even when `make_args` differ

**Body draft:**

`bridgestan.compile_model` (2.9.0) checks for `<stem>_model.so` next to the
`.stan` file and returns it if present, **ignoring the requested
`make_args`**. Concretely:

```python
bridgestan.compile_model("m.stan")                        # builds default
bridgestan.compile_model("m.stan", make_args=["STAN_THREADS=True"])
# returns the SAME default-mode .so (same mtime), no warning
```

We hit this shipping default binaries into an experiment that believed it
had `STAN_THREADS=True` builds (caught only via md5 comparison), and it
compounds with the fact that model `.so` names do not encode the build mode
(only the bridge object gets a `_threads` suffix). Any workflow that varies
`STAN_*` or `CXXFLAGS` between builds against one source dir silently gets
stale binaries.

**Suggest:** encode the relevant build mode in the `.so` name (or a sidecar
stamp), and/or have `compile_model` compare the cached build's stamp with
the requested `make_args` and warn/rebuild on mismatch.

**Second, related issue (file separately if you prefer):** the default
(non-`STAN_THREADS`) model `.so` is silently unsafe when a model instance is
evaluated concurrently: we reproduce `free(): double free detected` /
SIGSEGV (3/3) driving two chains on one instance from two threads, while
`STAN_THREADS=True` builds are clean and serialized use of the default
build is clean and bit-identical. The information exists in `model_info()`
and the docs, but nothing signals at the point of misuse; even a
`std::once_flag`-style thread-count assertion would catch it.

---

## Kit 4 — gcc / stan-math: `-march=native` gradient miscompile (report pending W-35)

Status: minimization in progress (WORKLOG W-35). Characterization (W-27):
self-contained single-make bridgestan build of kronecker_gp with
`-O3 -march=native -mtune=native` produces gradients wrong at up to 1.7 rel
with sign flips (250–305 of 438 components; the `lkj_corr_cholesky` block)
while logp matches to 1e-16; Richardson FD sides with the default build;
`-O3` alone is bit-identical to default. Kit will be appended here once the
minimal reproducer + sanitizer classification exist — do not file before
that. Docs-facing ask in the meantime (cmdstan/bridgestan): mention that
`-march=native` has a measured silent-wrongness mode, not just a speed
question (our measured upside was ≤ ~10% per call anyway).

---

## Kit 5 — walnutpie upstream: safe adaptation defaults

**Title:** Multi-chain controller's default cross-chain tolerances can stop warmup at iter 50–80 and destroy post-warmup quality

**Body draft:** with the default `WarmupConfig`, the controller's cross-chain
tolerances (mass 1.0 / step 0.1) declare warmup converged as early as
iteration 50–80 given good inits (e.g. Pathfinder); on hierarchical models
this silently destroys quality (hier_2pl bulk-ESS-min 519 → 61; with the
old flag restored: 519 → 24 median). No tolerance-based gate we tested
fixes this (a 2-window step/mass-drift gate: 519 → 126; a 50-draw pilot
gate with lag-1/R-hat vetoes: safe only by never exiting — the lp-stream
statistics of marginal and easy models overlap: 0.71–0.91 vs 0.62–0.74).
**Proposal:** `WarmupConfig::allow_early_exit` default `false` — fixed
budget out of the box, criteria still computed for diagnostics, old
behavior behind an explicit opt-in. Implemented + gated on our branch
`exp/safe-adapt-defaults` (canary: default-path draws bit-identical 12/12;
default `--chains 4` now equals the full-warmup baseline bit-for-bit 24/24).
Evidence: WORKLOG W-25/W-28/W-31.
