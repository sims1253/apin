# W-108 increment 2 — stanc3 emission of `bernoulli_logit_lpmf_gathered`: ALL GATES PASS, the compiler now emits the primitive call itself

Executed 2026-08-28 per WORKLOG "INCREMENT-2 PRE-REGISTRATION" (the section
appended with the W-108 increment-1 close-out). Deliverable: stanc3 branch
**`gathered-glm-emit` @ 58e6824** (parent `master` 90c6532 — w48-fusion's
parent lineage; the repo's only develop-equivalent branch is `master`) in a
dedicated worktree `external/stanc3_w108`, created with `git worktree add`
so the `w48-fusion` checkout `external/stanc3` is untouched (verified clean
at 4b07a23 before and after). Not pushed.

**Headline: the MIR pass recognizes hier_2pl's exact likelihood shape in the
reverse-mode log prob and rewrites the call to the W-108 primitive, and the
fully compiler-generated model is bit-identical end-to-end — regenerated
hier_2pl.hpp ≡ the increment-1 hand-edit except for whitespace in the
likelihood statement, parity vs the stock-form .so exact-zero (0/100 lp,
0/100 gradient vectors), and full sampler draws md5
`fe7c57c99a7a6530ce2dcc408d6e9c65` digit-for-digit — the same md5 the
hand-edit produced. The W-108 compiler+math pair is now closed: model in,
primitive call out, no manual C++ anywhere.**

## 1. The pass (design + where it sits)

- **`Optimize.gather_bernoulli_logit`** (src/analysis_and_optimization/
  Optimize.ml, exported in the .mli): matches `TargetPE
  (bernoulli_logit_lpmf(rv, eta))` where `rv` is a data integer-vector Var
  and `eta` is the literal three-leaf tree `EltTimes__(gather(a, ii),
  Minus__(gather(t, jj), gather(b, ii)))` over AutoDiffable vector Vars
  multi-indexed by data integer index-vector Vars (`input_vars` membership +
  `DataOnly`/`UArray UInt` meta, the same double condition W-48's
  `chain_leaves` used), with the SAME index variable for the outer
  multiply-gather and the subtrahend (`ix1 = ix2`). Rewrites ONLY
  `mir.reverse_mode_log_prob` — the double-mode instantiation keeps the
  stock expression, exactly like the gated hand-edit — preserving the
  `FnLpmf` suffix (`~` → `<propto__>`, `target +=` → `<false>`) and the
  call metadata. New call:
  `FunApp (StanLib ("bernoulli_logit_lpmf_gathered", suffix, mem),
  [y; theta; jj; alpha; beta; ii])` — the W-108 header's exact parameter
  order `(n, theta, jj, alpha, beta, ii)`.
- **Suite position**: runs LAST in `optimization_suite` (after
  `block_fixing`; W-48's pass sat last for the same reason — nothing may
  rewrite the produced call). Guarded by a new `optimization_settings`
  field `gather_bernoulli_logit`, wired exactly like every other pass
  flag. **Level decision (stated per the pre-registration): ON at `--O1`
  and `--Oexperimental`, OFF at `--O0`.** The repo convention is that
  correctness-preserving suite passes run at `--O1` (every master pass
  does; W-48's neutral-perf experiment opted out to Oexperimental-only),
  and this transform is gated bit-identical — so it follows the convention
  and `--O1` models get the primitive. This is the paired-branch behavior:
  the emitted call needs stan-math branch `gathered-glm`
  (`external/math_dev_w108` @ ea96b3c9fa); an upstream submission would
  gate it behind `--Oexperimental` until the primitive lands in stan-math
  (stated in the commit message and the pass docstring).
- **Backend**: no lowering special-case needed — the rewritten MIR flows
  through `Lower_expr.lower_fun_app`'s default path, emitting
  `stan::math::bernoulli_logit_lpmf_gathered<propto__>(y, theta, jj,
  alpha, beta, ii)`. The ONLY backend change is `Lower_program.ml`: when
  the program's reverse-mode log prob contains the call, `#include
  <stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp>` is emitted right
  after `model_header.hpp` (the include position of the hand-edit);
  pattern-free models keep their exact include list.
- **Tests**: new integration model
  `test/integration/good/compiler-optimizations/gathered-bernoulli.stan`
  (2 firing statements incl. the `target +=` form; 4 non-firing: plain
  eltwise, gathered `normal`, three-term gather, mixed index vectors);
  `cpp/cppO0/cppO1.expected` regenerated — the diff vs the old
  expectations is a SINGLE pure insertion (the new model's section) at
  every level: no existing model's output changed.

## 2. Gate (a) — pattern discipline: PASS

- In-repo (O1 expectations + fresh compiles at O0/O1/Oexperimental): the
  two firing statements rewrite (rev-mode only; the double-mode copies 5
  lines above keep stock `bernoulli_logit_lpmf`); O0 fires nothing
  (0 gathered calls, no include).
- External standalone negative controls (scratch/w108i2/neg_*.stan,
  compiled `--O1 --print-cpp`): non-gathered eltwise bernoulli (0),
  gathered eltwise feeding `normal_lpdf` (0), three-term gather (0) —
  none fires, none includes the header. Extra controls in the integration
  model: four-leaf tree, `beta[jj]` mixed-index form — no fire.

## 3. Gate (b) — regenerated hier_2pl.hpp ≡ the W-108 hand-edit: PASS

Regenerated with the branch's stanc at the models' own convention
(`--O1 --debug-optimized-mir`, input at the same path so the location
table matches; `models/hier_2pl.hpp` itself restored byte-intact after
capture — the shared reference .hpp is NOT modified by this increment).
`diff` vs `scratch/w108/model_hier2pl_prim/hier_2pl.hpp` (the gated
hand-edit): the include line, the stancflags line and every other line are
byte-identical; the ONLY difference is the line wrapping of the likelihood
statement itself:

```
<         lp_accum__.add(
<           stan::math::bernoulli_logit_lpmf_gathered<propto__>(
<                          y, theta, jj, alpha, beta, ii));
---
>         lp_accum__.add(stan::math::bernoulli_logit_lpmf_gathered<propto__>(y,
>                          theta, jj, alpha, beta, ii));
```

Same tokens, OCaml pretty-printer wrapping vs the hand edit's. The emitted
rev-mode instantiation keeps the real operand mix (`theta` read as
`var_value<VectorXd>` SoA at line 316, `alpha`/`beta` `Matrix<var>` AoS),
which the header's `if constexpr` routes handle.

## 4. Gate (c) — end-to-end: PASS

The regenerated .hpp (no manual edit) compiled on the W-108 stock-interior
bundle `scratch/w108/bs_prim_stock` (W-103-era prebuilt bridge reused
untouched; `CXX=scratch/w46/gxx_fixed`, `TBB_CXX_TYPE=gcc`,
`/usr/bin/make -j2`, nice 19, `env -u LD_LIBRARY_PATH`) →
`scratch/w108i2/model_hier2pl_emit/hier_2pl_model.so`.

- **Parity 100 pts** (W-103 point scheme, `default_rng(20260822)`,
  `standard_normal(D)*0.5`, propto/no-jacobian; bridgestan C ABI via
  ctypes — the python module's env was broken, the ABI calls are the ones
  `StanModel.log_density_gradient` makes): emit-arm vs the W-103
  stock-form reference .so — **lp mismatches 0/100, gradient-vector
  mismatches 0/100, exact-zero class** (`scratch/w108i2/gate_parity_ctypes.py`).
- **Full sampler draws, W-29 protocol** (walnutpie
  `build_w36exp/examples/stan_cli` READ-ONLY, seed 20260819, pf init
  `inits_w25/hier_2pl/rep0/chain_0.txt`, warmup 100, samples 50,
  `--metric-window 50`): md5 **`fe7c57c99a7a6530ce2dcc408d6e9c65`** —
  digit-for-digit the pre-registered stock reference AND the increment-1
  hand-edit's recorded md5 (`scratch/w108i2/draws/draws_emit.csv`).

## 5. Gate (d) — no-op elsewhere: PASS

`blr`, `diamonds`, `eight_schools_centered` compiled at `--O1
--debug-optimized-mir` by the base compiler (w48-fusion build, whose O1
behavior is identical to master 90c6532 — its only delta is the
Oexperimental-only W-48 pass) and by this branch, same input paths, same
output path: **byte-identical** (cmp clean; 21,750 / 28,720 / 21,602
bytes). Bonus: all five existing `models/*.hpp` references (accel_gp,
arma11, gp_regr, kronecker_gp, lotka_volterra) regenerate identical modulo
the invocation-embedded path/flag strings — i.e. codegen is unchanged
everywhere outside the pattern.

## 6. Test suite hygiene: PASS

`dune runtest -j2` (opam switch w39) exit 0 on the full tree; explicit
`@test/integration/good/code-gen/runtest`,
`@.../compiler-optimizations/runtest`, `@test/integration/bad/runtest`
also exit 0 (dune is silent-on-success).

## 7. Disclosures

- `--O1` default-on is the paired-branch behavior (see §1); the commit
  message records the upstream gating plan (`--Oexperimental` until the
  primitive lands in stan-math).
- `models/hier_2pl.hpp` was regenerated in place to reproduce the exact
  stancflags/location strings, captured to
  `scratch/w108i2/hier_2pl_regenerated.hpp`, and the original restored
  (cmp-verified) — the shared reference artifacts are unchanged; the
  draws/parity runs used the scratch copy only.
- The base-compiler arm of gate (d) is the `external/stanc3` w48-fusion
  build's stanc at `--O1` (identical-to-master O1 behavior; running a
  pristine master build would have required a second full OCaml build for
  zero information — the W-48 record already establishes its O1 output is
  bit-identical to vanilla).
- Machine: all builds/tests ≤2 cores, nice 19, `env -u LD_LIBRARY_PATH`;
  load stayed ≤1.8 (W-109's single analysis job coexisted); no waits
  needed.

## 8. Artifacts

- Branch: `external/stanc3_w108`, `gathered-glm-emit` @ 58e6824 (7 files:
  Optimize.ml/.mli, Lower_program.ml, the new gathered-bernoulli.stan,
  3 regenerated .expected files). Signed-off (DCO) + AI note; NOT pushed.
- `scratch/w108i2/`: `hier_2pl_regenerated.hpp` + `hier_2pl_stock_backup.hpp`,
  `model_hier2pl_emit/` (the .hpp, .so, build.log), `draws/draws_emit.csv`
  + `cli_emit.log`, `gate_parity_ctypes.py`, `neg_{nongathered,
  normal_gathered,threeterm}.stan` (+ compiled `*_mine.hpp`), `gate_d/`.
- Reused read-only: `scratch/w108/{bs_prim_stock,model_hier2pl_prim,draws}`,
  `scratch/w103/model_hier_2pl_stock`, `scratch/w46/gxx_fixed`,
  `external/walnutpie/build_w36exp/examples/stan_cli`,
  `data/hier_2pl.json`, `inits_w25/hier_2pl/rep0/chain_0.txt`.
