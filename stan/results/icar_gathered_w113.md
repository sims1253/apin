# W-113 — dot_self_gathered_diff (the gathered ICAR prior primitive): bit-identity gates ALL PASS; −17.0% Ir/grad on bym2 (band underrun disclosed)

Executed 2026-08-29 per WORKLOG "W-113 PRE-REGISTRATION" (increment 1:
primitive + hand-edited model gate, no codegen). Deliverable: branch
**`gathered-icar` @ 3b9ee1b7dd** (parent `fork/develop` 344d7167a0) in worktree
`external/math_dev_w113` — one new header
`stan/math/rev/fun/dot_self_gathered_diff.hpp` + one new unit-test TU
(placement: `rev/fun`, next to `dot_self.hpp` — it is a function in the
dot_self family, not a distribution). Nothing else in math is touched.
Artifacts in `scratch/w113/`.

**Headline: the math-side primitive for bym2's ICAR line is a bit-identical
drop-in (values, every gradient component, 100-point model parity exact-zero,
and full same-seed draws md5 `54c62090686b17e0cab8d21a2d56df7a` digit-for-digit
on the ALL-LAYERS stack) that deletes the entire gathered ICAR complex —
but the measured gradient-subtree saving is −17.0% G, BELOW the pre-registered
−20..−35% band. The bit-identity question is resolved affirmatively (no
statistical-class re-gate needed); the performance band was optimistic about
the primitive's own retained interior. Increment 2 (stanc3 emission) is a GO
on correctness grounds; the PI arbitrates whether the −17% is enough for the
class story or W-113.1 should tighten the primitive first.**

## 1. The primitive (design from the actual stock chain)

The generated line (both instantiations of the model hpp) is
`-(0.5) * dot_self(subtract(rvalue(phi, "phi", index_multi(node1)), rvalue(phi,
"phi", index_multi(node2))))`; the −0.5 stays OUTSIDE the primitive. Stock
mechanics read from the bundle and replicated exactly:

- **Which rvalue/dot_self paths actually run depends on phi's operand layout**,
  and the model uses a THIRD layout beyond the two pre-registered in the design:
  the deserializer hands the var-mode instantiation
  `Eigen::Map<const Matrix<var_value<double>,-1,1>>` (not `var_value<VectorXd>`
  as assumed). For that layout `rvalue` takes the **lazy `Holder<IndexedView>`
  path (rvalue.hpp)** — a view, NO gather copy, NO gather callback — `subtract`
  materializes a `Matrix<var_value<double>>`, and `dot_self` runs the
  **sequential `res += x*x` loop** (43,754 Ir/call ≈ 8/elem, scalar — measured,
  matching this overload). The primitive therefore implements per-layout
  schedules:
  - `Matrix<var>` / `Map<Matrix<var_value<double>>>` (AoS-class; **the model's
    actual case**): value = the sequential accumulation loop verbatim;
    reverse = per edge, node1 `+=` then node2 `-=` (subtract's callback order
    through the aliased/lazy views; no gather callbacks exist).
  - `var_value<VectorXd>` (SoA): value = `d_val.dot(d_val)` where `d_val` is an
    `arena_matrix<VectorXd>` — **the identical Eigen template instantiation**
    stock's `v.val().dot(v.val())` compiles (same Derived, same size). The
    redux grouping is size-determined only: `traits<CwiseBinaryOp>` lacks
    `DirectAccessBit`, so `first_default_aligned` returns 0 always — no pointer
    alignment dependence. Reverse = TWO passes, all node1 then all node2 — see
    the gate (a) bug below.
- Bounds checking mirrors the rvalue loops: all node1 indices (ascending), then
  all node2; first offender through the same `check_range` with the layout's
  exact exception function string ("vector[multi] indexing" AoS-class /
  "vector[multi] assign range" SoA). Name in the message: "phi".
- Per-edge adjoint increment `2*w*d[e]` with `s = 2.0*w` formed ONCE, exactly
  as stock's `2.0 * res.adj()`.

## 2. Gate (a) — unit, bitwise vs the REAL stan::model::rvalue: PASS

`scratch/w113/test_prim.cpp` (bundle `bs_icar`, all-layers math): the composed
stock expression with the REAL `stan::model::rvalue` + `index_multi`, vs the
primitive, on the real bym2 graph (N=1921, E=5461 — the actual arrays from
`stan/data/bym2_offset_only.json`), 20 randomized graphs (N≤2000, E≤5500,
unsorted/repeated endpoints, forced self edges), tiny graphs E=1..4, and a
hub graph, in THREE operand layouts (Matrix<var>, var_value<>, and
Map<Matrix<var_value<double>>> = the model's true layout). Compares the raw
dot_self value, the `-(0.5*...)` model wrapper lp, and every phi gradient
component, all memcmp-exact.

**59,178 bitwise checks, 0 mismatches.**

**A real bug was caught by this gate** (the pre-registered purpose of the
real-rvalue reference): the first implementation scattered SoA adjoints
node2-first-then-node1, reading the generated expression left-to-right. That
produced last-bit gradient mismatches on exactly the components touched by
BOTH endpoint arrays. Mechanism: **GCC evaluates `subtract`'s arguments
right-to-left**, so `rvalue(node2)` registers its reverse scatter FIRST and
runs LAST in the LIFO sweep — node1's scatter fires first. After the swap:
0 mismatches. (AoS was correct from the start: its lazy gathered views carry
no callbacks, so subtract's own per-edge interleaved order is the whole
schedule.)

## 3. Gate (b) — hand-edited model, bit-identity: PASS

- Stock reference recorded FIRST (W-29 protocol, walnutpie `build_w36exp`
  stan_cli READ-ONLY, seed 20260819, pf init `inits_w36/bym2_offset_only/
  rep0/chain_0.txt`, warmup 100, samples 50, metric-window 50, against the
  W-109 ALL-LAYERS .so untouched): draws md5 **`54c62090686b17e0cab8d21a2d56df7a`**
  — which also reproduces the W-111 census run's draws bit-exact.
- Primitive arm: `scratch/w113/model_bym2_prim/` (fresh stanc hpp from the
  bundle's stanc, then a TWO-line-group hand edit: the include + the ICAR
  statement of the **var-mode instantiation only**; the double-mode
  instantiation keeps the stock expression — diff vs a pristine regeneration
  is exactly those two groups). Built on the `cp -al` bundle copy
  `scratch/w113/bs_icar` (private inodes for the added header and the rebuilt
  `src/bridgestan.o`; the w106 original verified untouched), `CXX=gxx_fixed
  TBB_CXX_TYPE=gcc`, `-mavx2 -mfma`, `/usr/bin/make -j2`, nice 19,
  `env -u LD_LIBRARY_PATH`.
- **Draws: `54c62090686b17e0cab8d21a2d56df7a` DIGIT-FOR-DIGIT** (plain and
  under callgrind — the traced primitive arm's draws md5 is the same).
- **Parity 100 pts** (`gate_parity_w113.py`, W-103 point scheme, D=3845):
  lp mismatches **0/100**, full-gradient-vector mismatches **0/100**
  (every component bitwise) vs the stock W-109 .so.

## 4. Gate (c) — callgrind: −17.0% G, BELOW the −20..−35% band (underrun disclosed)

W-29 protocol verbatim (valgrind 3.23 `~/vginstall`, one job, nice 19,
sibling-agent priority checked — no other callgrind running). Stock arm =
the W-111 census profile of the SAME stock .so under the SAME protocol (draws
md5 re-verified identical this session); primitive arm run fresh. Both arms
traced the identical **4,652** gradient calls.

| arm | total Ir T | G (bs_log_density_gradient incl.) | Ir/grad |
|---|---|---|---|
| stock (W-109 ALL-LAYERS .so) | 18,028,810,629 | 5,010,955,427 (27.79% T) | 1,077,313.6 |
| **primitive** | **17,176,837,260** | **4,158,951,110** | **894,218.4** |

ΔT = −851,973,369 (−4.73%); ΔG = −852,004,317 (**−17.00%**) — the entire
saving sits inside the gradient subtree (outside G the arms are identical).

### Attribution (exclusive Ir self-costs)

| complex | stock arm | primitive arm |
|---|---|---|
| `subtract<Holder<IndexedView<Map<Matrix<var_value>>>>>` forward | 889,908,992 | **0** |
| `rvalue` index_multi gather (clone) | 559,477,432 | **0** |
| subtract reverse callback `chain()` | 304,915,340 | **0** |
| `dot_self<Matrix<var_value<double>>>` forward | 203,534,304 | **0** |
| dot_self reverse lambda | 203,385,440 | **0** |
| complex total | 2,161,221,508 (43.1% of G — matches W-111's census) | 1,310,617,264 |
| `dot_self_gathered_diff` forward | — | 980,292,700 (210,747/call) |
| primitive scatter `chain()` | — | 330,324,564 (71,022/call) |

The whole gathered ICAR complex is **deleted** (zero occurrences of the stock
symbols in the primitive .so profile) and replaced by the primitive's
fwd+scatter. Net complex reduction −850.6M = **−39.3% of the complex** — but
the complex is only 43% of G, and the primitive retains 281,774 Ir/call
(≈51.6 Ir/edge vs stock's ≈85.1 Ir/edge), so the model-level number lands at
−17.0%.

**Why the band (−20..−35% G) was missed:** it assumed the primitive keeps
~10–20 Ir/edge. What it actually keeps, per gradient call (E=5461, N=1921):
(i) the scalar-sequential dot accumulation — bit-identity FORCES this (stock's
own loop is scalar; SIMD reassociation would break it), ≈38k/call;
(ii) two bounds-check passes with a `check_range` per index (10,922 checks —
kept because fusing/ordering them would deviate from stock's first-offender
exception semantics), (iii) materializing two arena int index vectors (2E
ints) + the AoS `vari*` route fill (N pointers — the model's Map layout takes
the AoS branch), (iv) the value_of gather of phi (N). Reaching −20% of G would
need the primitive at ≤1.16e9 complex (−8% less) — plausibly recoverable by
dropping the arena index copies (capture data pointers instead) and a
cheaper fused check, at the cost of small disclosed semantics deviations;
that is a PI call (W-113.1), not taken here.

Honest framing (as pre-registered): bym2's G is only 27.8% of program T, so
the model-level wall effect is −4.7% T; the upstream interest is the
ICAR/CAR disease-mapping class, not this instance.

## 5. Gate (d) — ctest/hygiene: PASS

- New TU `test/unit/math/rev/fun/dot_self_gathered_diff_test.cpp` (on the
  branch): **3/3 PASSED** — `BitIdenticalToComposedStock` (8 randomized
  shapes × 2 layouts + tiny graphs; the TU's SoA reference is a verbatim copy
  of rvalue_varmat's gather, since `stan::model` lives in the Stan repo —
  the strict real-rvalue gate is (a)), `ValueMatchesHandComputed`,
  `SizeZeroAndBounds` (incl. first-offender order). One dev fix during the
  run: `arena_t` lives in `stan::`, and the hand-computed expectation
  initially dropped the 4th edge (test bug, primitive was right).
- Controls (runTests.py -j2, on the branch, all PASSED):
  `mix/fun/dot_self_test` (1), `mix/fun/columns_dot_self_test` (1),
  `mix/fun/rows_dot_self_test` (1), `mix/fun/operator_subtraction_test` (42),
  `mix/core/operator_subtraction_test` (6), `mix/fun/elt_multiply_test` (3)
  — **54/54 tests**.
- Bundle hygiene: `bs_icar` is a `cp -al` clone; only-private-inode files are
  the added header and the rebuilt `src/bridgestan.o`; `w106/bs_alllayers`
  verified untouched (no gathered header present; original bridgestan.o inode
  intact); the W-109 stock .so only read (md5 recorded).

## 6. Disclosures

- **Band underrun (gate c)**: −17.0% G vs the pre-registered −20..−35%;
  mechanism analyzed in §4. Direction and complex-level story (−39.3% of the
  complex, stock symbols → 0) are as designed.
- **The model's true operand layout is a third one** — `Map<const
  Matrix<var_value<double>>>` via the deserializer — not the
  `var_value<VectorXd>` the pre-registration assumed. Consequence: in the
  model the primitive takes its AoS-class branch (sequential loop +
  interleaved scatter), and that combination was NOT in the original gate (a)
  layout set; it was proven bitwise at the model level (parity + draws), then
  added to gate (a) as layout 2 (all 59,178 checks include it).
- **GCC argument-evaluation order is load-bearing for the SoA scatter
  schedule** (right-to-left argument evaluation swaps the two gather
  callbacks' LIFO order). The primitive replicates what the compiler actually
  emits (arbitrated empirically by gate (a)); a hypothetical left-to-right
  compiler would need the loops swapped — flagged for increment-2 emission
  notes.
- Deviations from stock exception semantics (unreachable in the model):
  node1/node2 size mismatch throws from `check_size_match` with function
  name "dot_self_gathered_diff" (stock throws from subtract's
  `check_matching_dims`, function "subtract"); identical exception types.
  Bounds messages match the per-layout rvalue strings exactly, with the
  container name fixed to "phi".
- The stock-arm callgrind is the W-111 census run (same .so, same protocol,
  draws md5 re-verified identical this session) rather than a fresh rerun —
  machine-discipline + the profile is the census's own reference. The
  primitive arm was run fresh.
- W-108's TU needed no `arena_t` in namespace math — this one did
  (`stan::arena_t`); fixed in the TU.
- No wall-time gate pre-registered; none reported. /tmp used only for the
  parity ref npz; all artifacts under `scratch/w113/`.

## 7. Increment-2 (stanc3 emission) readiness: GO

Bit-identity is proven at all three levels for the exact hand-edited call
`dot_self_gathered_diff(phi, node1, node2)` (with the −0.5 outside, as
generated). The stanc3 matcher should target the MIR shape
`dot_self(subtract(gather(phi, node1), gather(phi, node2)))` with data-typed
index vectors — the existing W-108 expression-matcher class; the runtime
emission needs the operand layout left to the C++ overload set (the primitive
handles all three layouts bit-exactly, which the model gate proved is
required). Caveat to carry: the SoA scatter order is GCC-arg-order-dependent
(documented in the header comment).

## 8. Artifacts

- Branch: `external/math_dev_w113`, `gathered-icar` @ `3b9ee1b7dd` (commits:
  `0a92fa21fa` primitive + TU, `2040745a9b` SoA scatter-order fix,
  `3b9ee1b7dd` TU fixes; parent `344d7167a0`; adds only the two new files).
  Not pushed (no upstream PRs).
- `scratch/w113/`: `bs_icar/` (bundle clone + header), `model_bym2_prim/`
  (hand-edited hpp + .so), `model_bym2_pristine.hpp` (diff reference),
  `test_prim.cpp` + `bym2_data.inc` + `test_prim`, `debug1.cpp`/`debug2.cpp`
  (the layout/order probes), `gate_parity_w113.py`, `draws/{stock_ref,prim}.
  {csv,log}` + md5s, `profile_prim/` (callgrind.out, ann.txt, incl_ann.txt,
  cli.log, draws.csv), `build_prim.log`.
- References reused read-only: `scratch/w109/model_bym2_offset_only_alllayers`
  (stock .so), `scratch/w111/profile_bym2_offset_only` (stock-arm callgrind),
  `scratch/w106/bs_alllayers` (bundle original), `external/walnutpie/
  build_w36exp/examples/stan_cli`.
