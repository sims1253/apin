# W-132 — family-3 EMISSION, the composed USER-FUNCTION matcher: ALL FOUR GATES GREEN — the novel matcher class (matching through the inlined body of a user function) lands as registry entry 4, and the compiler output alone (no manual C++ anywhere) reproduces the W-126 stock reference draws md5 `a342848b18bf6eebe360097c0681a633` DIGIT-FOR-DIGIT with 100-point lp/gradient/constrained-output parity EXACT-ZERO

Executed 2026-08-30 per the WORKLOG "W-132 PRE-REGISTRATION" (family 3,
increment 2). Deliverable: stanc3 branch **`gathered-pcm-emit`** in the
dedicated worktree `external/stanc3_w132` (off gathered-registry `50e8c9d`):
`ab4d8b7` (registry row 4 + the through-the-inlined-function matcher +
per-family emission spellings) + `1379471` (the operand-swap fix the gate-(a)
control matrix caught) + `d879d68` (integration model + regenerated
expectations). DCO + AI notes; NOT pushed. Artifacts under `scratch/w132/`.

**Headline: the pre-registered central question is answered with the favorable
outcome the pre-registration hinted at — at `--O1` `function_inlining` (the
suite's FIRST pass) has already expanded the `pcm` user function into the
likelihood loop, so `gathered_families` (the LAST pass) matches the
softmax(cumulative_sum(append_row(0, gathered-bilinear))) +
categorical_lpmf body as a plain inlined statement sequence: the novel
"through the user function" matcher class is simply an inlined-body matcher,
with the inliner's fresh `inline_pcm_*` locals guaranteeing the loop-locality
side condition by construction. On match, exactly the loop becomes
`pcm_lpdf_gathered<propto__>(y, theta, jj, alpha, ii, beta, pos, m)` (the
W-126-gated primitive, math#23) with the per-term accumulator pushes; the
double-mode instantiation, the priors, and every other statement keep their
`--O1` stock forms.**

---

## 0. Preflight: the level-matrix (recorded before any matcher code)

The `a342848b…` reference is a DEFAULT-level (O0) v2.39-stanc artifact, and
at `--O1` the parent itself changes this model (pcm inlined in both log_prob
modes, the theta prior rewritten to `normal_id_glm_lpdf` by the O1-only glm
rewrite, SoA reads) — the W-131 hazard, but with the glm difference OUTSIDE
the rewrite's reach. Measured on the `bs_w132` bundle (W-29 protocol, seed
20260819, w100/s50/mw50, W-80 data + pf init):

| arm | .so md5 | draws md5 | 510-error spam |
|---|---|---|---|
| parent (50e8c9d) at DEFAULT | `79a7ea02…` | **`a342848b…`** | yes |
| parent at `--O1` | `43e7bbbe…` | **`a342848b…`** | yes |
| EMITTED at `--O1` | `7bc8cc87…` | **`a342848b…`** | yes |

The reference is level-INSENSITIVE for this model+protocol (the near-frozen
trajectory does not flip any draw on the O1 differences), so gate (c) held
in its literal pre-registered form — no attribution table needed (the
parent-O1 arm stands as the level control anyway).

## 1. What was implemented (branch `gathered-pcm-emit` @ `d879d68`)

- **`src/middle/Gathered_Families.ml/.mli`**: row 4 — `pcm_lpdf_gathered`,
  header `stan/math/rev/prob/pcm_lpdf_gathered.hpp`,
  `PerObservation ("auto", "pcm")`. The `PerObservation` variant now carries
  each family's gated hand-edit spelling (decl-type string + variable
  prefix); entry 3 keeps `("const std::vector<stan::math::var>", "lp")`, so
  its committed output is unchanged.
- **`src/stan_math_backend/Lower_stmt.ml`**: the per-observation push block
  is emitted with the family's own spelling — the pcm family prints
  `auto pcm_terms__ = …; for (const auto& pcm_term__: pcm_terms__)
  lp_accum__.add(pcm_term__);`, token-for-token the W-126 hand-edit's block.
- **`src/analysis_and_optimization/Optimize.ml`** — entry 4,
  `pcm_loops_rewrite`, the THROUGH-THE-INLINED-FUNCTION class:
  - **Match**: `for (n in 1:N)` (bare data bound) whose body is exactly the
    inlined user-function shape — `Block [Decl ret; Block [FnValidateSize;
    Decl unsummed; FnValidateSize; Decl probs; unsummed =
    append_row(rep_vector(0, 1), Minus__(bilinear,
    segment(beta, pos[ii[n]], m[ii[n]]))); probs =
    softmax(cumulative_sum(unsummed)); ret = categorical_lpmf(y[n] + 1 |
    probs)]; target += ret]`. The bilinear is
    `(EltTimes__|Times__)(theta[jj[n]], alpha[ii[n]])` (both scalar-product
    spellings); the segment's item index must be one of the bilinear
    operands' index vectors, and BOTH operand bindings swap together (never
    a mix — see §3).
  - **Side conditions** (any doubt ⇒ no rewrite): the loop bound is the bare
    data variable that is ALSO the declared array size of `y`, `jj` and
    `ii` (checked against the program's sized `input_vars` — the primitive
    consumes all four whole); `y` is never written in the reverse-mode log
    prob; the response read is exactly `y[n]` with the `+1` shift. The
    loop-local `inline_pcm_*` variables are gensym-fresh and declared inside
    the loop — extra uses are structurally impossible, which is exactly why
    matching post-inlining is EASIER (the W-131 O1-fma lesson, now for a
    whole function body).
  - **Rewrite**: the `for` becomes an `SList` of 11 no-op `Skip`s carrying
    every interior statement location in the numbering pass's post-order
    (the whole `locations_array__` stays byte-identical) plus the primitive
    `TargetPE` carrying the `for`'s own location — the entry-3/4 convention.
    The `<propto__>` template argument matches the gated hand-edit (the
    pcm interior has no constant terms — the parameter is inert, W-126
    header doc).
  - Reverse-mode log prob only; ON at `--O1`+`--Oexperimental`, OFF at
    `--O0` (registry convention). (At `--Oexperimental` nothing fires in
    practice: lazy code motion hoists the loop bodies before the pass runs
    — the W-131-recorded level behavior of the loop class.)
- **Tests**: `test/integration/good/compiler-optimizations/gathered-pcm.stan`
  (2 firing loops — canonical + commuted spelling — and 6 in-model
  non-firing controls); `cpp/cppO1/cppO0.expected` regenerated.

## 2. Gate (a) — pattern discipline: PASS

- **Standalone matrix** (`scratch/w132/negctl/`, `--O1`): 8 true negatives
  never fire — softmax result read elsewhere (an extra use inside the user
  function), cumulative_sum reused, non-gathered bilinear operand (both
  `theta[n]` and `alpha[n]` spellings), extra statement in the loop body,
  non-bare loop bound (`1:N-1`), dense accumulation outside the loop,
  no loop at all, and the O0 level. 4 positives fire — the canonical gpcm
  shape, the commuted spelling, the plain `*` spelling, and
  commuted-with-segment-through-jj.
- **`neg_seg_other_index` reclassified, disclosed**: a segment gathered
  through `jj` (the theta-side index) while alpha gathers through `ii` DOES
  fire — its MIR is indistinguishable from a legitimately commuted source
  spelling, and the emitted call is the faithful swap
  `(y, alpha, ii, theta, jj, beta, pos, m)` (scalar multiplication commutes
  exactly; the item tables read the same index the source used). The
  primitive's internal index-check ORDER follows the swapped slots — a
  disclosed, throw-path-only consequence.
- **Full-tree census**: two-arm compiles (mine vs parent, `--O1 --print-cpp`)
  over 1,798 of the 2,562 in-repo models (the un-run remainder is the
  auto-generated function-signatures probes, each pathologically slow to
  compile): exactly **1 firing model** — the new integration model (2 calls,
  both intended); **1,797/1,798 byte-identical** (the one difference IS the
  firing model's rewrite); **0 exit-code differences**. Fire-closure over
  the WHOLE tree by source: exactly one of the 2,562 `.stan` files contains
  both `softmax` and `cumulative_sum` (both required by the pattern) — the
  integration model. Non-fire byte-identity carries from the 1,798 two-arm
  compiles, the §5 reference set, and the pure-insertion expectation
  regeneration.
- **In-model controls** (verified through the regenerated expectations at
  all three levels): the 6 non-firing loops in `gathered-pcm.stan` stay
  stock; O0 = 0 fires; O1 = exactly the 2 intended; Oexperimental = 0 (the
  LCM-hoisting class).

## 3. A real bug caught by the controls before any number depended on it

The first version of the either-index segment fallback returned the FIRST
bilinear operand in BOTH the theta and alpha slots when the segment matched
the first operand's index — silently dropping a container, the exact W-115
§6 ICAR bug class. `pos_commuted` (source `alpha[ii] .* theta[jj]`, segment
through `ii`) emitted `(y, alpha, ii, alpha, ii, …)` — alpha twice, theta
gone. Fixed in `1379471`: both bindings swap together. All spellings now
emit all four containers; the gpcm gate-model hpp is UNCHANGED by the fix
(md5-verified `b40a370b…` before and after), so no recorded gate number was
tainted.

## 4. Gates (b) + (c) — emission fidelity and end-to-end bit-identity: PASS

The W-126 hand-edit (`8bb3c3ef…`) is a DEFAULT-level artifact; from a `--O1`
compiler the literal byte-comparison is impossible for level reasons the
parent itself exhibits (§0). The W-131-operationalized form:

- **(b) primary**: `diff(emitted --O1, parent-50e8c9d --O1 pristine)` is
  EXACTLY two hunks and nothing else (112 diff lines,
  `scratch/w132/logs/gate_b_diff.txt`): `+#include
  <stan/math/rev/prob/pcm_lpdf_gathered.hpp>` right after
  `model_header.hpp` (the hand-edit's exact position), and the 102-line
  inlined REV loop replaced by the 6-line primitive block.
- **(b) numbering**: `locations_array__` byte-IDENTICAL to the parent
  (5,411 chars, 94 entries). The `for`'s label line (`= 23`) is retained by
  the emitted call; the five interior label lines (`15/17/19/20/21`) are
  not printed (the `Skip` convention) — the W-131-owned static-only class.
- **(b) tokens**: the emitted block vs the hand-edit's replacement:
  **34/34 tokens identical** (`auto pcm_terms__ =
  stan::math::pcm_lpdf_gathered<propto__>(y, theta, jj, alpha, ii, beta,
  pos, m); for (const auto& pcm_term__ : pcm_terms__)
  lp_accum__.add(pcm_term__);`) modulo (i) the label number on the retained
  label line (`23` = the for's O1 label vs the hand-edit's `15` = the
  target statement's default-level label) and (ii) the printer's
  `pcm_term__:` colon-binding — the W-115-recorded cosmetic.
- **(c)**: the emitted hpp built on `bs_w132` (`cp -al` of W-126's bundle;
  the primitive header dropped in at a PRIVATE inode `11921261`;
  `bridgestan.o e4b6077b…` intact; `gxx_fixed`, model flags
  `-O3 -mavx2 -mfma`, `env -u LD_LIBRARY_PATH`, the recorded W-129 command
  lines): **draws md5 `a342848b18bf6eebe360097c0681a633` digit-for-digit,
  the 510-exception pattern byte-identical**; **100-pt parity vs the W-126
  stock reference values (npz reused read-only): lp 0/100, gradients 0/100
  (D=530), constrained output 0/100 (DC=545) EXACT-ZERO**. No callgrind run,
  per the pre-registration's W-131 precedent: the emitted call IS the
  W-126-gated primitive call — the −88.28% Ir class carries by construction.

## 5. Gate (d) — no-op elsewhere: PASS

- **Standing set** (`--O1 --print-cpp` AND `--O1 --debug-optimized-mir`,
  mine vs parent, byte-compared): `blr`, `diamonds`, `eight_schools_centered`,
  `hier_2pl` (entry-1 regression), `bym2_offset_only` (entry-2), both radons
  (entry-3), plus W-128's `kidscore_momiq`/`logmesquite_logvash` — all
  **byte-identical**.
- **Committed `stan/models/*.hpp` references**: `accel_gp`, `arma11`,
  `gp_regr`, `kronecker_gp`, `lotka_volterra` regenerate **byte-identically**
  with the recorded invocation shape (relative path from `models/`; the
  first attempt with an absolute path differed only in the embedded source
  path string — the W-115 invocation-embedded-strings lesson re-confirmed).
  `hier_2pl.hpp` matches the parent exactly (the stored file's `--print-cpp`
  capture artifact, documented since W-115). All six restored intact from
  backups.
- **Expectation regeneration footprint**: one PURE INSERTION of the new
  model's section at each of `cppO0`/`cppO1`/`cpp` (zero changed lines
  elsewhere).
- **`dune runtest -j2`**: **TRUE-EXIT=0**. Disclosure: the first run failed
  on `cli-args/debug-flags.t` with `Error writing to file 'basic.hpp':
  Permission denied` — the PRE-EXISTING cram quirk W-131 recorded (the
  test's side-effect write gets promoted back as a gitignored leftover,
  which then blocks the next run's write); removing the three leftover
  `basic.hpp` files and re-running gives exit 0 with zero permission
  errors. Unrelated to the pass (that test exercises no optimization).
- **Symbol provenance**: the emitted `.so` carries the primitive's symbols
  (`nm -C`: 18 `pcm_lpdf_gathered` matches); the parent-O1 `.so` has 0.
- Sibling integrity re-verified: `stanc3_w115` @ `50e8c9d`, `stanc3_w131` @
  `03b5180`, `math_dev_w126` @ `e355b14535` all clean; W-126's artifacts
  (prim .so `1a5e98d9…`, stock draws `a342848b…`, bundle header at inode
  `11893441`) byte-intact.

## 6. Deviations / disclosures (all owned)

1. **The hand-edit byte-identity gate, W-131-operationalized** (§4): the
   registered "≡ the W-126 hand-edit (whitespace-only)" is unreachable from
   a `--O1` compiler for level reasons that pre-date the pass (§0 — the
   parent at O1 already differs from the default-level hand-edit basis);
   the emission is instead proven at the same-base standard (exact-hunk
   diff + token identity to the hand-edit's replacement + the semantic
   gates).
2. **`neg_seg_other_index` fires** (§2): intended-behavior reclassification,
   swap-faithful, throw-order consequence disclosed.
3. **The swap bug** (§3): caught by the controls, fixed before any recorded
   gate number; gpcm output unchanged.
4. **The census ran 1,797/2,562 models as two-arm compiles** with the
   fire question closed over the whole tree by the source grep (exactly one
   candidate) — the remainder (function-signatures probes) costs hours of
   compile time for zero information; the alternative was disclosed rather
   than silently skipped.
5. **No callgrind**, per the pre-registration: the emitted call IS the gated
   one (draws + parity + the W-126 attribution carry).
6. **Label-line print differences** (§4b): the W-131-owned class, static
   only, `locations_array__` identical.

## 7. Artifacts

- Branch `gathered-pcm-emit` @ `d879d68` (base `50e8c9d`): commits
  `ab4d8b7` (`Gathered_Families.{ml,mli}`, `Lower_stmt.ml`,
  `Optimize.ml`), `1379471` (swap fix), `d879d68`
  (`gathered-pcm.stan` + 3 regenerated `.expected`). DCO + AI notes.
  Not pushed.
- `scratch/w132/`: `notes.md` (full session log), `bs_w132/` (bundle,
  private-inode header), `model_{parentDEF,parentO1,emitO1}/` (hpps + .sos),
  `runs/{parentDEF,parentO1,emitO1}/draws.csv` (all `a342848b…`),
  `gate_parity_w132.py` + logs, `negctl/` (14 controls),
  `gate_d/` (model + reference byte-identity artifacts),
  `census/` (1,797 two-arm compiles + analysis), `mir_*.txt` (the preflight
  MIR study), `logs/`.
- Read-only reuse: `scratch/w126` (stock hpp/.so, hand-edit, parity npz,
  bundle lineage, run scripts), `scratch/w80` (data + pf init),
  `scratch/w46/gxx_fixed`, the walnutpie `build_w36exp` CLI, the parent
  compiler build in `stanc3_w115`.
- Machine: ≤2-core builds (`nice 19`, `gxx_fixed`, `env -u LD_LIBRARY_PATH`),
  sampler cells single-process `OMP_NUM_THREADS=1`; no callgrind.
