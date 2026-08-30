# W-131 — family 4 increment 3, the ADDITIVE EMISSION ("tp loop → the factory call"): ALL FOUR GATES GREEN in their strongest form — the regenerated election88 model reproduces the stock reference draws md5 `d2e2f896e81dc03aff55e0f2a54f6065` DIGIT-FOR-DIGIT (the emitted call IS the W-130-gated construction: same draws, same gradients, same machine-code FMA schedule), the emitted-vs-parent diff is EXACTLY the intended two-hunk rewrite, the token sequence of the factory statement is IDENTICAL to the W-130 hand-edit, and the pass is a no-op on everything else in a 2,562-model census

Executed 2026-08-30 per the WORKLOG "W-131 PRE-REGISTRATION" (family 4, increment 3).
Deliverable: stanc3 branch **`gathered-additive-tp-emit`** in the dedicated worktree
`external/stanc3_w131` (off gathered-registry `50e8c9d`): `e274ef5` (the registry entry
+ matcher + backend case) + `03b5180` (integration model + regenerated expectations).
DCO + AI notes; NOT pushed. Artifacts under `scratch/w131/`.

**Headline: `Optimize.gathered_families` gains entry 4, the TP-LOOP emission class —
the matcher recognizes the tp-built gathered-additive predictor pattern
(`for (i in 1:N) y_hat[i] = beta[1] + beta[2]*xd[i] + … + a[idx[i]]` with `y_hat`'s
only other use a downstream `bernoulli_logit` likelihood) in the reverse-mode log
prob at `--O1`/`--Oexperimental`, and rewrites exactly the loop to
`y_hat = stan::math::gathered_additive_tp(N, slot_term(…), slot_slope_term(…), …,
gather_term(…))` — the W-130-gated per-element custom-vari factory, leaf-for-leaf
in the composed expression's declaration order, with the likelihood line, the
priors, the double-mode instantiations and the `write_array` output path fully
stock. The end-to-end arm built from the compiler output alone (no manual C++
anywhere) reproduces the W-127/W-130 stock reference draws md5
`d2e2f896e81dc03aff55e0f2a54f6065` digit-for-digit including all 11,566 `y_hat`
output columns, with 100-point lp/gradient/constrained-output parity EXACT-ZERO
against the stock `.so`, the identical 305/42/23 vfmadd/vfmsub/vfnmadd instruction
mix as the W-130 gated hand-edit arm, and the W-130 wall-clock class (1.67 s vs
stock's 5.73 s; the perf carries by construction — the emitted call IS the gated
one, so no callgrind was run, per the pre-registration).**

---

## 1. What was implemented (branch `gathered-additive-tp-emit` @ `03b5180`)

- **`src/middle/Gathered_Families.ml/.mli`**: a fourth registry row
  (`gathered_additive_tp`, header `stan/math/rev/prob/
  bernoulli_logit_lpmf_gathered.hpp`) and the new `TpLoop` emission variant.
  The include fires automatically (the existing scan finds the emitted call's
  `StanLib` name in the reverse-mode log prob) at the hand-edit's exact position
  (right after `model_header.hpp`).
- **`src/analysis_and_optimization/Optimize.ml`** — entry 4, the TP-LOOP class:
  - **Leaf decomposition** of the loop body's eta into its declaration-ordered
    leaves: a leading coefficient-slot intercept (`beta[1]` → `slot_term`) plus
    `slot_slope_term` (`beta[k]*xd[i]`), `slot_slope2_term`
    (`(beta[k]*xd1[i])*xd2[i]`) and `gather_term` (`a[idx[i]]`) leaves. BOTH eta
    spellings decompose identically: the plain left-associated sum and the
    `--O1` multiply-add-fused right-nested `fma` chain (the fusion keeps the
    accumulated sum in the addend, so reading the addend first recovers the
    source order; a slot folded into a later fma's addend — the
    `beta[2]*x + beta[1]` spelling — decomposes with the slot first, which is
    rounding-commutative for values and routes to a different coefficient's own
    vari for increments, bitwise-neutral either way).
  - **Loop match**: bound starts at literal 1 and is a bare data integer
    variable; the body is exactly one elementwise assignment through the loop
    variable to an AutoDiffable vector.
  - **Whole-program side conditions** (any doubt ⇒ no rewrite): `y_hat`
    declared exactly once, a sibling of the loop, sized by the same bound;
    `y_hat`'s only other mentions in the whole reverse-mode log prob are direct
    whole-vector arguments of a `bernoulli_logit_lpmf`/`lupmf` call (at least
    one — the downstream likelihood); `y_hat` never read by a user
    generated-quantities statement. The GQ check is shape-aware:
    `generate_quantities` carries the full output scaffold (the double-space
    decls, the tp loop copy, the `FnWriteParam` writes, wrapped in
    `if (emit_transformed_parameters__)`) which mentions every tp variable by
    construction — only statements OUTSIDE that scaffold (real user GQ reads)
    disqualify.
  - **The rewrite**: the `for` becomes an `SList` of two no-op `Skip`s carrying
    the interior statement locations (keeping every `current_statement__`
    number and the whole `locations_array__` exactly what the un-rewritten
    program prints) plus the whole-vector factory assignment carrying the
    `for`'s own location. Suite position LAST, ON at `--O1` +
    `--Oexperimental`, OFF at `--O0` (the W-108/W-115 convention; reverse-mode
    log prob only — the factory requires var operands).
- **`src/stan_math_backend/Lower_stmt.ml`**: an `Assignment` of a registered
  `TpLoop` factory call to a bare lvalue emits the plain `y_hat = call;`
  (the gated hand-edit's exact shape) instead of `stan::model::assign` — the
  same kind of registry-keyed backend wiring W-115 added for the
  per-observation push loops.
- **Tests**: integration model `gathered-additive-tp.stan` (2 firing predictors
  — the election88 shape incl. slot-sharing and a slope2 leaf — plus 10
  non-firing controls in one model); `cpp/cppO1/cppO0.expected` regenerated.

## 2. Gate (a) — pattern discipline: PASS

- **In-model controls** (`gathered-additive-tp.stan`, verified through the
  regenerated expectations at all three levels): read-after-likelihood,
  printed, GQ-read (`mean(y)` in generated quantities), partially indexed
  (`y[1]` in a later statement), nonlinear leaf (`square(x)`), non-plain loop
  bound (`1 : N-1`), non-bernoulli_logit consumer (`normal_lpdf`), no
  likelihood consumer, gathered-coefficient-times-data leaf (`a[idx[i]]*x[i]`),
  and a scalar predictor assigned in a loop — **none fire at any level**. The
  two positives fire at `--O1` with verified leaf sequences. At `--O0`:
  0 fires. At `--Oexperimental`: 0 fires — lazy code motion hoists the loop
  bodies before the pass runs there, the same level behavior as the W-112
  loop-class entry recorded in W-115's `gathered-families.stan` expectations.
- **Standalone controls** (`scratch/w131/negctl/`, `--O1`/`--O0`): extra
  statement in the loop body, lower bound not 1, and the likelihood consuming
  `yh + 1` (a wrapped, non-direct use): 0 fires. Positive controls: the
  commutative spelling (`beta[2]*x + beta[1] + a[idx]`) and the
  product-after-gather spelling (`beta[1] + a[idx] + beta[2]*x`) fire with
  correct leaf orders.
- **Full-tree census**: all 2,562 `.stan` files under `test/` at `--O1`:
  exactly **3 factory calls in 2 models** — `expr-prop-fail3.stan` (an
  in-repo verbatim copy of the election88 model; intended fire, see §6) and
  the new integration model (its 2). Nothing else changes.

## 3. Gate (b) — regenerated election88 hpp vs the W-130-GATED hand-edit: PASS
(the W-115 gate-b standard, whitespace-wrapping only)

`diff(emitted --O1, parent-50e8c9d --O1 pristine)` is EXACTLY two hunks and
nothing else (61 diff lines, `scratch/w131/logs/gate_b_diff.txt`):

1. `+#include <stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp>` right
   after `model_header.hpp` — the hand-edit's exact position;
2. the REV-template tp `for` loop (46 lines, fma-fused at `--O1`) replaced by
   `y_hat = stan::math::gathered_additive_tp(N, …);` with
   `current_statement__ = 15;` (the `for`'s label) as unchanged context.

The factory statement itself is **token-sequence-identical to the W-130
hand-edit's replacement (127/127 tokens)** — the same
`slot_term("beta", beta, 1), slot_slope_term("beta", beta, 2, black), …,
slot_slope2_term("beta", beta, 5, female, black), …,
gather_term("e", e, region_full)` leaf order; only the OCaml pretty-printer's
wrapping differs. `locations_array__` is byte-identical (6,985 chars) and the
`.so`'s remaining `stan::math::fma` source count drops 12 → 8 exactly as
intended (the REV template's four; the base and `write_array` copies keep
theirs — they are not touched).

**One textual deviation vs the hand-edit reference, owned**: the hand-edit
also printed `current_statement__ = 13;` (the inner assignment's label)
between the `for`'s label and the call. One MIR statement carries one
location, so the emission prints the `for`'s label (15) and the call; labels
13/14 stay allocated via the `Skip`s (numbering and `locations_array__`
identical; total printed label lines 171 → 170). The dropped line is
runtime-inert in-domain (it is immediately overwritten); throw attribution
moves from the assignment's span to the enclosing loop's span. A full
double-print would require changing `Skip` lowering globally, which would
change W-115's recorded entry-3 emissions — rejected.

## 4. Gate (c) — end-to-end bit-identity: PASS, in the literal pre-registered form

Emitted hpp `322b1fae…` (no manual edit anywhere) built on `scratch/w131/bs_w131`
(`cp -al` of W-130's bundle: the gathered-additive-tpvari header
`b2428750…` first on the include path, the in-copy rebuilt `bridgestan.o`
`e4b6077b…`), `gxx_fixed`, `-O3 -mavx2 -mfma`, `env -u LD_LIBRARY_PATH`,
direct compile+link (the recorded W-129/W-130 command lines); `.so`
`f71c1cb4933c13fed9950392d7ac0a27`. Protocol verbatim (walnutpie
`build_w36exp` CLI READ-ONLY, seed 20260819, warmup 100, samples 50,
`--metric-window 50`, the w80 pf init `rep0/chain_0`, real data):

| check | result |
|---|---|
| draws md5 | **`d2e2f896e81dc03aff55e0f2a54f6065` — identical to the stock reference DIGIT-FOR-DIGIT, the 11,566 `y_hat` columns included** |
| 100-pt parity vs the stock `.so` (`2cf00ef9…`, ctypes C ABI, W-103 points, W-130's saved reference values reused read-only) | **lp 0/100, gradients 0/100, constrained output (params + all `y_hat` cols) 0/100 EXACT-ZERO** |
| FMA provenance (objdump, all widths) | emitted **305/42/23 = the W-130 tpvari arm EXACTLY** (stock 300/41/22) |
| wall / grad calls | 1.67 s / 2,999 (stock 5.73 s / 2,999) — the W-130 class carried by construction |

**The preflight that could have broken this gate, measured and resolved**: the
reference is a default-level artifact, and at `--O1` the parent compiler
fma-fuses the eta in all THREE template copies. The unmodified parent at
`--O1` does NOT reproduce the reference (stock-O1 draws
`00bf1d084d8b85a07557dba521905f0a`; ALL 90 parameter and ALL 11,566 `y_hat`
columns differ — its REV-template `fma` nest on vars is genuinely
single-rounding, changing gradients and hence the trajectory). The emitted arm
nevertheless reproduces the reference exactly because (1) its REV path IS the
factory = the W-127-certified unfused value/chain order (= default-stock
semantics — the W-130 property), and (2) in the DOUBLE paths (base `log_prob`
and `write_array`) the `--O1` source-level `fma` nest and the default
unfused chain compile to the same machine code at the model flags (GCC's
`-ffp-contract=fast` contracts `(x*y)+z` into `vfmadd`, flattening both
associations to the same fused chain), so the `y_hat` output columns are
bit-identical. The stock-O1 arm stands as the level-attribution control
proving the emitted arm's value class is the DEFAULT reference class, not the
`--O1` class. No diagnostic hand-edit arm was needed — the literal gate held.

## 5. Gate (d) — no-op elsewhere: PASS

- `blr`, `diamonds`, `eight_schools_centered` + the existing-registry
  regressions `hier_2pl` (entry 1), `bym2_offset_only` (entry 2), both radons
  (entry 3) at `--O1 --debug-optimized-mir`: generated cpp AND optimized MIR
  **byte-identical** to the parent `50e8c9d` (e.g. 21,687 / 28,652 / 21,520 /
  47,135 / 37,546 / 29,934 / 40,661 cpp bytes).
- The five committed `models/*.hpp` references (accel_gp, arma11, gp_regr,
  kronecker_gp, lotka_volterra) regenerate **byte-identically** with
  `--O1 --debug-optimized-mir --o=<ref>`; `models/hier_2pl.hpp` modulo the
  known invocation-embedded flags string (`--print-cpp` vs `--o=`, the W-115
  artifact). `kidscore_momiq` / `logmesquite_logvash` (the W-128
  glm-emission models) byte-identical — the const-hoist and glm-default
  pattern families are untouched (this branch does not contain those passes;
  the census shows their models' output unchanged).
- `dune runtest -j2` on the full tree: **exit 0** (true exit captured).
  Disclosure: the first run failed on `cli-args/debug-flags.t` with
  `Error writing to file 'basic.hpp': Permission denied` — a PRE-EXISTING cram
  quirk (the test's side-effect write gets promoted back as a gitignored
  leftover, which then blocks the next run's write); removing the leftovers
  and re-running gives exit 0. Unrelated to the pass (that test exercises no
  optimization), not counted as a gate deviation.
- Expectation regeneration footprint: a SINGLE PURE INSERTION of the new
  model's section at `--O0` and `--Oexperimental`; at `--O1` additionally the
  existing `expr-prop-fail3.stan` fires exactly as intended (§2/§6).

## 6. Deviations / disclosures (all owned)

1. **Branch name**: `gathered-additive-tp-emit`, not the obvious
   `gathered-additive-emit` — that name is checked out (at the same base
   commit, zero commits) in sibling `stanc3_w129`; the sibling was not
   touched.
2. **The `current_statement__ = 13;` line** (§3): the one textual difference
   vs the hand-edit reference; runtime-inert, numbering-preserving, mechanism
   documented. This is the only respect in which the regenerated hpp is not
   byte-equal to the W-130 hand-edit file modulo whitespace — and it is a
   static-print difference only: values, gradients, draws, parity and the FMA
   schedule are all exactly the gated construction's (§4).
3. **Two matcher hardenings found during debugging, before any gate number
   was recorded**: the decl-size check originally used structural
   `Expr.Typed.compare` (which includes location metas — always failed); fixed
   to a bare-variable bound with name equality (strictly in-pattern). The GQ
   side condition originally treated ANY mention in `generate_quantities` as
   disqualifying — which blocks every rewrite, since the output scaffold
   mentions every tp variable; replaced by the shape-aware scaffold rule (a
   real user GQ read still disqualifies, per the pre-registration).
4. **`expr-prop-fail3.stan` fires at `--O1` in-repo** (it is election88
   verbatim): intended behavior on real in-repo code, the same class as
   W-115's `expr-prop-fail4`/ICAR disclosure; its committed expectations are
   default-level so `dune runtest` needed the regenerated `cppO1.expected`
   (the 46-line rewrite + include inside that model's section).
5. **No callgrind**, per the pre-registration: the emitted call IS the gated
   one — same draws, same FMA instruction mix (305/42/23), same wall class;
   the W-130 attribution carries by construction.
6. **Build/log hygiene**: the emitted arm was compiled+linked with the exact
   recorded W-129/W-130 command lines (direct `gxx_fixed`, no bridgestan
   make); `bs_w131` is a hardlink copy sharing read-only inodes with W-130's
   bundle (header `b2428750…`, `bridgestan.o` `e4b6077b…` re-verified
   intact post-session). Read-only reuse: `scratch/w80` (data + init),
   `scratch/w127` (stock `.so` + reference draws), `scratch/w130` (bundle,
   parity reference values, hand-edit hpp), `scratch/w46/gxx_fixed`, the
   walnutpie CLI, the parent compiler build in `stanc3_w115`. Sibling
   integrity re-verified: `stanc3_w115/w124/w128/w129` and `math_dev_w130`
   clean at their recorded commits; no pushes; WORKLOG.md and comms.md not
   written by this agent (PI-owned).
7. Machine: ≤2-core builds (`nice 19`, `gxx_fixed`, `env -u LD_LIBRARY_PATH`),
   sampler cells single-process `OMP_NUM_THREADS=1` `nice 19`; no callgrind at
   all; OCaml build ~10 min wall with the shared dune cache.

## 7. Artifacts

- Branch `gathered-additive-tp-emit` @ `03b5180` (base `50e8c9d`): `e274ef5`
  (`src/middle/Gathered_Families.{ml,mli}`, `src/analysis_and_optimization/
  Optimize.ml`, `src/stan_math_backend/Lower_stmt.ml`) + `03b5180`
  (`test/integration/good/compiler-optimizations/gathered-additive-tp.stan` +
  3 regenerated `.expected`). DCO + AI notes. Not pushed.
- `scratch/w131/`: `notes.md` (full session state), `preflight/` (parent
  DEF/O1 hpps + MIR dumps, the stock-O1 arm `.so` `50ed88cc…` + draws
  `00bf1d08…` — the level-attribution control), `bs_w131/` (bundle),
  `model_election88_emit/` (hpp `322b1fae…`, `.so` `f71c1cb4…`),
  `gate_parity_w131.py`, `runs/emit_w100s50.csv` (md5 `d2e2f896…`),
  `negctl/` (5 standalone controls), `gate_d/` (byte-identity artifacts),
  `logs/` (gate-b diff, md5 table, census summary, run + runtest logs).
