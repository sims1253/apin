# W-115 — the gathered-families stanc3 REGISTRY: all four gates run; the pass is bit-exact at its own level and reproduces the bym2 recorded md5 digit-for-digit; two of the three recorded md5s are proven UNREPRODUCIBLE at --O1 by the unmodified parent compiler (level effect, not the pass)

Executed 2026-08-29 per WORKLOG "W-115 PRE-REGISTRATION". Deliverable: stanc3
branch **`gathered-registry`** in the dedicated worktree
`external/stanc3_w115` (created with `git worktree add ... 58e6824`; the
`w48-fusion` checkout `external/stanc3` and `external/stanc3_w108` were never
touched — verified). 3 commits: `0787842` (registry + entries 1-3 + backend),
`b8171fc` (a matcher bug the gate-(a) controls caught), `50e8c9d`
(integration model + regenerated expectations). DCO-signed + AI note; NOT
pushed. Artifacts under `stan/scratch/w115/`.

**Headline: `Optimize.gather_bernoulli_logit` is now `Optimize.gathered_families`,
a table-driven registry (the table itself is the new `Middle.Gathered_Families`
module: one row per landed primitive = {StanLib name, #include, emission
class, doc}) that emits all three landed gathered primitives. The
compiler-generated radon_pp/radon_var/bym2 models differ from the parent
compiler's --O1 output by EXACTLY the intended rewrite (include + mu-decl
removal + loop/ICAR-line replacement), parity vs the same-level stock arm is
exact-zero 3/3, bym2's sampler draws reproduce the recorded md5
`54c62090686b17e0cab8d21a2d56df7a` digit-for-digit, and hier_2pl regenerates
byte-identically to `gathered-glm-emit` (entry 1 preserved).**

**The one pre-registration conflict, resolved by measurement (§5): the
W-112/W-113 hand-edits were generated at the bundle stanc's DEFAULT level
(no --O flag), while the pass is ON at --O1 per the same pre-registration.
At --O1 the parent compiler's own output already differs from those recorded
files (multiply-add fusion in the transformed-parameters blocks, dropped
decl initializers, SoA reads), and the recorded radon_pp/radon_var draws md5s
are not reproducible by the UNMODIFIED parent at --O1 either. Every deviation
of the emitted arms from the recorded references is therefore attributable to
the level, with an explicit three-arm attribution table.**

---

## 1. What was built

- **`src/middle/Gathered_Families.ml/.mli`** (new): the registry table.
  Row = `{primitive; header; emission; doc}`, `emission` ∈ {`SingleVar`,
  `PerObservation`}. Shared by the optimizer (matchers) and the backend
  (include emission, per-observation push loop) without a dependency edge.
  Adding family 4 (pcm/ordered_logistic) is ONE row here plus one matcher in
  Optimize.ml.
- **`Optimize.ml`**: `gathered_families` applies each registered family's
  statement-list rewriter to **`reverse_mode_log_prob` only** (double-mode
  instantiations keep the stock forms). Suite position LAST (after
  `block_fixing`), settings field `gathered_families` (renamed from
  `gather_bernoulli_logit`), ON at `--O1` + `--Oexperimental`, OFF at `--O0`.
  - **Entry 1** (bernoulli_logit, expression class): the W-108 i2 matcher,
    code-for-code unchanged (now `bernoulli_logit_statement`).
  - **Entry 2** (ICAR `dot_self`, expression class): rewrites exactly the
    `dot_self(Minus__(phi[node1], phi[node2]))` call — same AutoDiffable
    container on both sides, both index vectors data int arrays — to
    `dot_self_gathered_diff(phi, node1, node2)`; the −0.5 and everything
    wrapping it untouched; operand layout left to the C++ overload set.
  - **Entry 3** (normal, LOOP class — the new matcher class): matches
    `for (n in 1:N) { mu[n] = <eta>; target += normal_lpdf(y[n] | mu[n],
    sigma) }` with a data bound, a two-statement body, eta = `alpha[ii[n]]`
    (shape A) or `alpha[ii[n]] + x[n] * beta[ii2[n]]` (shape B, matched BOTH
    as the plain mul-add and as the --O1-fused
    `fma(x[n], beta[ii2[n]], alpha[ii[n]])`), y a data real vector read only
    at `[n]`, sigma scalar and free of `n`/`mu`, every index expression
    exactly `idx[n]`. Side conditions checked against the whole
    reverse-mode log prob: `y` never written anywhere; `mu` declared exactly
    once (a sibling of the loop) and mentioned nowhere else. Any doubt ⇒ no
    rewrite. The `for` is replaced by an `SList` of no-op `Skip`s carrying
    the loop's interior locations + the primitive's `target +=` call carrying
    the `for`'s own location, so every `current_statement__` number and the
    whole `locations_array__` stay EXACTLY what the un-rewritten program
    prints; the `mu` decl becomes a `Skip` for the same reason.
- **`Lower_stmt.ml`**: a `TargetPE` whose head is a registered
  `PerObservation` primitive emits
  `{ const std::vector<stan::math::var> lp_terms__ = <call>;
     for (const auto& lp_term__ : lp_terms__) lp_accum__.add(lp_term__); }`
  — the W-112 accumulator contract (the rev `accumulator<var>` partial
  specialization's 128-element chunk-collapse buffer forces one push per
  observation).
- **`Lower_program.ml`**: `#include` of every fired family's header, in
  registry order, right after `model_header.hpp`; pattern-free models keep
  their exact include list.
- **Test model** `test/integration/good/compiler-optimizations/
  gathered-families.stan`: 3 firing statements + 6 non-firing controls;
  `cpp/cppO1/cppO0.expected` regenerated.

## 2. Gate (a) — negative controls never fire: PASS

16 standalone controls in `scratch/w115/negctl/` compiled `--O1 --print-cpp`
(counting `stan::math::*_gathered` calls and gathered includes):

| control | fires? |
|---|---|
| neg_nongathered (eltwise bernoulli, no gathers) | no |
| neg_normal_gathered (gathered chain feeding normal_lpdf) | no |
| neg_threeterm (four-leaf eltwise tree) | no |
| icar_diffvars (`dot_self(phi[n1] - psi[n2])`, two vectors) | **no (after the fix, §6)** |
| icar_sum (`dot_self(phi[n1] + phi[n2])`) | no |
| icar_singlegather (`dot_self(phi[n1])`) | no |
| icar_nonhead (gathered difference feeding `sum`, not dot_self) | no |
| loop_mu_used_after (`mu` read after the loop) | no |
| loop_sigma_varies (`sigma[n]`) | no |
| loop_extra_stmt (third statement in the body) | no |
| loop_head_cauchy (`cauchy_lpdf`) | no |
| loop_nested_index (`alpha[c2[c1[n]]]`) | no |
| loop_cross_iter (`mu[n] = mu[n-1] + ...`) | no |
| loop_y_not_data (y a transformed parameter) | no |
| loop_shapeA_pos / loop_shapeB_pos (positive controls) | **yes / yes** |
| the three gate models at **--O0** | no (0 calls, 0 includes) |

In-repo: the `gathered-families.stan` integration model (6 non-firing + 3
firing) verified at --O0/--O1/--Oexperimental through the regenerated
expectations.

## 3. Gate (b) — regenerated hpp vs the hand-edits: PASS at the same-base
standard; the recorded files are --O0-base

**Primary comparison (the W-108 i2 standard applied at the same base).**
`diff(emitted --O1, parent-58e6824 --O1 pristine)` is EXACTLY the intended
transformation and nothing else, for all three models:

- radon_pp: `+#include <stan/math/rev/prob/normal_lpdf_gathered.hpp>`,
  − the `Eigen::Matrix ... mu = ...Constant(N, DUMMY_VAR__);` decl,
  − the whole `for` loop, `+` the `lp_terms__` block (tokens identical to
  the W-112 hand-edit; only OCaml-pretty-printer wrapping differs:
  `county_idx, sigma_y);` indented differently, `lp_term__:` vs
  `lp_term__ :`).
- radon_var: same three groups; the replaced loop is the --O1-fused
  `stan::math::fma(...)` form.
- bym2: `+#include <stan/math/rev/fun/dot_self_gathered_diff.hpp>`,
  `dot_self(subtract(rvalue,rvalue))` → `dot_self_gathered_diff(phi, node1,
  node2)`; nothing else.

**Secondary (the pre-registration's literal wording).** The RECORDED
hand-edits (`scratch/w112/model_radon_{pp,var}_prim`,
`scratch/w113/model_bym2_prim`) were generated by the bundle stanc v2.39.0 at
its DEFAULT level (no `--O` flag — verified: the pristine diff is exactly the
documented edit). Byte-identity to them from a --O1 compiler is impossible
for reasons that predate this pass; the residual (excluding
path/stancflags/stanc_version strings) is 40/72/77 changed lines, all of one
kind and ALL present identically in the parent's --O1 output:

- `add(mu_alpha, multiply(sigma_alpha, alpha_raw))` → `fma(...)` (--O1
  multiply-add fusion; radon_var's loop too);
- dropped `= std::numeric_limits<...>::min()` / `Constant(J, DUMMY_VAR__)`
  initializers (--O1 allow_uninitialized_decls + DCE);
- bym2: SoA reads (`var_value<Eigen::Matrix<double,-1,1>>`) for
  theta/phi/convolved_re (--O1 optimize_soa) and `-(0.5)` → `-0.5`.

## 4. Gate (c) — end-to-end, no manual C++: bym2 digit-for-digit; pp/var
bit-identical to the same-level stock arm

Bundle `scratch/w115/bs_all3`: `cp -al` of `scratch/w106/bs_alllayers` +
the three primitive headers dropped in (private inodes verified;
`src/bridgestan.o` removed and rebuilt in-copy; the w106 original verified
untouched). `CXX=scratch/w46/gxx_fixed TBB_CXX_TYPE=gcc CXXFLAGS="-mavx2
-mfma"`, `/usr/bin/make -j2`, nice 19, `env -u LD_LIBRARY_PATH`. The
compiler-emitted hpps (no manual edit anywhere) built clean.

**Draws (W-29 protocol: seed 20260819, warmup 100, samples 50,
--metric-window 50, pf inits, `build_w36exp/examples/stan_cli` READ-ONLY):**

| model | emitted-arm md5 | recorded md5 | same verdict |
|---|---|---|---|
| bym2 | `54c62090686b17e0cab8d21a2d56df7a` | `54c62090686b17e0cab8d21a2d56df7a` | **digit-for-digit** |
| radon_pp | `b442ad18049103363394856cdc8a2df4` | `4a9ca34923b6d2c314e636d6b335338d` | = parent-O1-stock md5 |
| radon_var | `9392801036b9af71843ef7e8fa503583` | `bbafc6523f1bfd40804c6bbafc4c4dec` | = parent-O1-stock md5 |

**Parity, 100 pts (W-103 scheme), one-process form** — necessary because the
models' Eigen reductions are allocation-alignment sensitive and the process's
malloc layout depends on early string allocations INCLUDING THE .SO PATH
(measured: the SAME .so via an absolute vs a relative path gives different
last-bit gradients; a control pair that really differs still differs when
loaded together, so the method is sound). Harness:
`scratch/w115/gate_parity_oneproc.py`.

| comparison | radon_pp | radon_var | bym2 |
|---|---|---|---|
| **emitted vs parent-O1-stock** | **0/100 lp, 0/100 grad** | **0/100 lp, 0/100 grad** | **0/100 lp, 0/100 grad** |
| emitted vs recorded (W109) stock | 5/100 lp | 9/100 lp | 24/100 lp |
| parent-O1-stock vs recorded stock | 5/100 lp (2.35e-16) | 9/100 lp (2.3e-16) | 24/100 lp (4.1e-16) |

The emitted arms' deviation from the recorded references is **identical in
count and magnitude** to the parent compiler's own --O1-vs-default deviation
— i.e. 100% level-attributed, 0% pass-attributed.

## 5. The pre-registration conflict and its resolution (measured, not assumed)

The pre-registration demands BOTH "O0 fires nothing / ON at --O1" AND
"reproduce the recorded W-112/W-113 md5s digit-for-digit". Those recorded
references are default-level artifacts. Pre-flight matrix
(`scratch/w115/preflight/`, same bundle, same protocol):

| arm | radon_pp md5 |
|---|---|
| W-109 recorded .so (default level) | `4a9ca349…` (reproduced — protocol validated) |
| **parent stanc 58e6824 at DEFAULT** | `4a9ca349…` (**= recorded**; the version drift 2.39→master is arithmetic-neutral) |
| bundle stanc 2.39 at **--O1** | `b442ad18…` |
| parent stanc 58e6824 at **--O1** | `b442ad18…` |

So --O1 itself changes the draws (radon_pp: the tp-block `fma(sigma_alpha,
alpha_raw, mu_alpha)` — stan-math's matrix fma evaluates `(x*y)+z` in one
Eigen pass, which `-mfma -O3` contracts; radon_var additionally the loop's
fused scalar fma). bym2's --O1 output happens to be value-identical (its
recorded md5 reproduces). Resolution taken: keep the pre-registered level
policy (ON at O1) and report both comparisons with the attribution table;
the alternative (firing at default level) would have violated gate (a)'s
"O0 fires nothing" directly. This is a PI-visible decision point, not a
silent choice.

**Second, smaller disclosure:** at --O1 the loop matcher accepts the fused
`fma(x[n], beta[ii[n]], alpha[ii[n]])` form and emits the primitive, which
computes mu UNfused (`x*beta` rounded, then `+alpha`) — the source/default
semantics and the W-112-gated contract. Measured consequence on radon_var:
none (emitted vs parent-O1-stock is exact-zero and the draws md5s are equal,
i.e. the fused and unfused mu agree on this data); in principle it is a
1-ulp-class difference vs the --O1 stock form, disclosed here.

## 6. A real bug caught by gate (a)

The first ICAR implementation guarded "same container on both sides" with
`var_name` applied to the two gathered operands — but those are `Indexed`
expressions, so `var_name` returned `""` for both and the guard always held:
`dot_self(phi[node1] - psi[node2])` was rewritten to
`dot_self_gathered_diff(phi, node1, node2)`, **silently dropping `psi`**.
Caught by the `icar_diffvars` negative control (it fired); fixed in `b8171fc`
(the guard now compares the container names extracted by `gathered_leaf`).
The three gate models' emitted code was verified unchanged by the fix.

## 7. Gate (d) — no-op elsewhere: PASS

- `blr`, `diamonds`, `eight_schools_centered` at `--O1 --debug-optimized-mir`:
  parent vs this branch, same input and output paths — **byte-identical**
  (21,175 / 27,500 / 21,008 bytes; cmp clean).
- **hier_2pl (entry-1 regression)**: parent (= `gathered-glm-emit` @ 58e6824)
  vs this branch — **byte-identical** (45,383 bytes), i.e. the refactor
  preserved the W-108 pass exactly.
- The five committed `models/*.hpp` references (accel_gp, arma11, gp_regr,
  kronecker_gp, lotka_volterra) regenerate **byte-identically** with
  `--O1 --debug-optimized-mir --o=<ref>` (the `--o=` form keeps the embedded
  stancflags string identical). `models/hier_2pl.hpp` regenerates identical
  modulo the invocation-embedded path/flags string (it was captured at a
  different cwd with `--print-cpp`); the code body is covered by the parent
  comparison above.
- `dune runtest -j2` on the full tree (opam switch w39): **exit 0**; explicit
  `@test/integration/good/compiler-optimizations/runtest` also exit 0.
- Expectation regeneration footprint: at --O0 the only change is the new
  model's section; at --O1/--Oexperimental additionally the ICAR line of the
  EXISTING `expr-prop-fail4.stan` (a BYM/ICAR model whose model block is
  exactly the matched pattern) is rewritten with the matching include — the
  pass working on real in-repo code, disclosed as the one existing-model
  output change (4 deleted lines, all inside that pattern).

## 8. Registry completeness — what a family-4 (pcm/ordered_logistic) entry needs

One row in `Middle.Gathered_Families` (name `ordered_logistic_gathered`,
header, `emission`: per-observation — the cutpoint vector is per-observation
so the terms must be pushed one by one like W-112) + one LOOP-class matcher
in `Optimize.ml`: the same stereotyped loop with eta = `dot(thresholds[k],
dummies)`-shaped per-observation cutpoint assembly and a `ordered_logistic/
gpcm` head, plus the same data-index/y-not-written/mu-loop-local side
conditions. The backend (include + push loop) needs no change. The open
math-side question is the primitive's interior (LSE over categories), which
is where the bit-identity work would be.

## 9. Artifacts

- Branch `gathered-registry` @ `50e8c9d` (commits `0787842`, `b8171fc`,
  `50e8c9d`): `src/middle/Gathered_Families.{ml,mli}` (new),
  `src/analysis_and_optimization/Optimize.{ml,mli}`,
  `src/stan_math_backend/{Lower_stmt,Lower_program}.ml`, the new
  `gathered-families.stan` + 3 regenerated `.expected`. Not pushed.
- `scratch/w115/`: `bs_all3/` (three-header bundle), `emit/` + `emit_arm/`
  (emitted hpps and .sos), `preflight/` (level/version matrix arms),
  `negctl/` (16 controls), `gate_parity_oneproc.py` (+ the two-process
  `gate_parity_w115.py` kept as the cautionary artifact),
  `run_parity_o1.sh`, `mir/`, `probe/`, draws csvs + cli logs in
  `emit_arm/*/`.
- Reused read-only: `scratch/w106/bs_alllayers`, `scratch/w109/model_*`,
  `scratch/w112/{model_radon_pp_prim,model_radon_var_prim,draws}`,
  `scratch/w113/{model_bym2_prim,draws}`, `scratch/w46/gxx_fixed`,
  `external/{math_dev_w108,math_dev_w112,math_dev_w113}`,
  `external/walnutpie/build_w36exp/examples/stan_cli`, `stan/data`,
  `stan/inits_w36`, `stan/inits_w63`.
- Machine: ≤2 cores, nice 19, `env -u LD_LIBRARY_PATH` on every build/run;
  one OCaml build ~6 min incremental; no callgrind (per the pre-registration:
  the emitted calls ARE the gated primitive calls).
