# W-130 — family 4 increment 2' (the bit-identity lane): the TP-BLOCK custom-vari construction `gathered_additive_tp` — ALL FOUR GATES GREEN, and the W-129 refuted claim is now PROVEN in the strongest form: bit-identity to the fully-stock composed path at stock's own delivery position (draws md5 `d2e2f896…` DIGIT-FOR-DIGIT, 100-pt parity EXACT-ZERO on lp + gradients + all 11,566 `y_hat` columns, priors-before AND priors-after) with the tp-chain complex eliminated at −67.5% total Ir — EXCEEDING both the W-129 statistical-class arm (−56.7%) and the registered −55..−60% band

Executed 2026-08-30 per the WORKLOG "W-130 PRE-REGISTRATION" (family 4,
increment 2', the PI-chosen bit-identity lane after W-129's refutation).
Deliverable: branch **`gathered-additive-tpvari`** in worktree
`external/math_dev_w130` (2 commits on top of the gathered-additive tip
`5267fb4858`): `330f6db2f7` (the factory + slot leaf tags + the custom
vari) + `a2593a12fe` (the TU). Not pushed. Artifacts under `scratch/w130/`.

**Headline: the pre-registered construction — ONE custom vari per element
CREATED AT THE TRANSFORMED-PARAMETERS LOOP, forward = the W-129-validated
value-only eta path, `chain()` = the W-127-certified element backward, the
likelihood line LEFT FULLY STOCK — delivers exactly what the W-129 causal
triangle demanded: the likelihood's increments arrive at stock's
delivery position (swept LAST, after every prior edge) regardless of where
the likelihood statement sits, because the varis carrying them are created
in the tp block by construction. The election88 model with ONLY its tp
loop rewritten (`y_hat = gathered_additive_tp(N, slot_term(beta,1),
slot_slope_term(beta,2,black), …, gather_term("e", e, region_full))`;
likelihood, priors, double template, `write_array` untouched) reproduces
the stock draws file md5 `d2e2f896e81dc03aff55e0f2a54f6065`
digit-for-digit including the y_hat output columns, with 100-point
lp/gradient/constrained-output parity EXACT-ZERO — the same-seed
trajectory, not a statistical class. The prize is bigger than both prior
arms measured it: 54.76e9 → 17.79e9 Ir = −67.51% (wall 5.73 → 1.39 s),
because eliminating ~23 varis per element also collapses the sweep and
adjoint-zeroing frames themselves (`bs_log_density_gradient` self:
4.36e9 → 0.35e9).**

---

## 1. What was implemented (branch `gathered-additive-tpvari` @ `a2593a12fe`)

`stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp` gains, alongside the
landed W-127 overloads (untouched):

- **`gathered_additive_tp(n_obs, intercept, leaves...)`** — returns
  `vector[n_obs] y_hat` as a `Matrix<var>` whose elements are ONE
  `internal::additive_tp_vari : vari_value<double>` EACH, pushed on the
  var_stack AT THE FACTORY CALL (the transformed-parameters block — before
  the model block's prior and likelihood callbacks; swept LAST, elements
  descending = stock's tp-chain position, by construction).
- **Forward**: per element `t = intercept_val; t = t + leaf.fwd(k)…` in
  the composed expression's declaration order — the W-127-certified
  rounded-leaf/barriered value path (= the W-129-validated value-only
  arithmetic, output-invisible there, load-bearing here: `val_` IS the
  y_hat the stock likelihood consumes). The gathered range checks fire
  here, in stock's per-element leaf order (the tp-loop position).
- **`chain()`**: `e = adj_` — the adjoint the STOCK likelihood edge wrote
  (one fused multiply-add per element over the zero-initialized adjoint =
  the exact increment stock's top add-vari receives) — then
  `rev_leaves(leaves, k, e)` (REVERSE declaration order) and the intercept
  pure-add LAST: the W-127-certified element backward verbatim.
- **NEW slot leaf tags** — `slot_term{name, coefs, slot}` (the intercept),
  `slot_slope_term{name, coefs, slot, xd}`,
  `slot_slope2_term{name, coefs, slot, xd1, xd2}` — route the coefficient
  VECTOR + slot (not an `rvalue` view of it), so the factory reaches the
  adjoint destination stock's own per-element `rvalue` machinery writes
  to, per operand layout:
  - **AoS / `Map<const Matrix<var>>`** (what the built election88 actually
    carries — see §5): `rvalue` aliases the coefficient's own vari, and
    stock's `multiply_vd_vari::chain` accumulates with a FUSED
    multiply-add into that shared vari — the tags keep the
    W-127-certified single-expression forms (incl. the slope2
    1.0-multiplier alias branch).
  - **SoA `var_value<>`**: stock's per-element `rvalue` creates a fresh
    view vari + `reverse_pass_callback`, whose schedule is ROUNDED PRODUCT
    + PURE ADD into the matrix adjoint slot (the W-108.1 SoA discipline);
    the tags implement exactly that (1.0-multiplier alias classes are
    exact on this route: `RN(1.0·e) = e`, so no branch is needed). This
    route is exercised by the unit gate (§2) for stacks whose deserializer
    produces `var_value<>`.
- One arena-allocated shared state per factory call (intercept route +
  resolved leaf routes); no other varis exist. The state is never
  destructed (recovered with the arena; the resolved gathers' heap value
  buffers are released never — the documented `make_callback_var` capture
  discipline, the same class as the landed scatter overload's captures).

## 2. Gate (a) — bitwise unit, MODEL FLAGS + −O2: PASS

`scratch/w130/test_prim.cpp` (W-127's harness, upgraded) vs the
FULLY-STOCK composed path — the real per-element expression through real
`stan::model::rvalue`/`index_uni` (for SoA beta this creates the real
view varis + `reverse_pass_callback`s the generated model creates),
followed by the STOCK `bernoulli_logit_lpmf(y, y_hat)`; the tpvari arm =
the factory + the same stock likelihood. **W-130 harness upgrade over
W-127: the slope coefficient vector beta is layout-varied too** (in the
built .so every parameter vector is a `Map`/AoS operand — W-127's harness
fixed beta as AoS `Matrix<var>`, so the slope-coefficient routing was only
exercised for one layout). On `scratch/w130/bs_w130` (cp −al of bs_w127;
branch header first on the include path at a PRIVATE inode), built at
`-O3 -mavx2 -mfma` AND `-O2`:

**440,067 bitwise checks + 9 throw checks, 0 mismatches at BOTH levels** —
patterns P1 (1 gather), P2 (2 gathers + slope), P3 (3 gathers + 2 slopes +
slope2), P4 (slot-sharing: two gathers on one vector), P5 (the exact
election88 line over the REAL data `election88_data.inc`, N=11,566, binary
AND real slope data), each × 3 layouts for beta AND the gathered vectors ×
N ∈ {1,2,3,5,8,17,100,919,2000} × 6 seeds; branch-cut scale sweeps (×4,
incl. ×30 on the real data); all-y∈{0,1}; **P6 = the election88 layout
(priors BEFORE the likelihood) and P7 = priors AFTER — BOTH exact, the
causal-triangle control** (this is the case the W-129 scatter arm failed);
compared per run: lp + EVERY parameter adjoint + **the y_hat VALUES
bitwise**. Throw set: OOB gather index (both leaf orders), index 0, NaN
gathered/slope/intercept coefficient (stock's indexed message text
byte-identical), y=2, y=−1, N=0.

## 3. Gate (b) — election88 model, bit-identity: PASS

Hand-edit (`scratch/w130/make_tpvari_edit.py`, reproducible): pristine hpp
`d0557507…` → `6af014755973c02235d235fc80bd734c` — the diff is EXACTLY the
include + the tp for-loop → the factory call (verified by full diff; the
base/double template, `write_array`, the priors, and THE LIKELIHOOD LINE
are untouched). Built on `bs_w130` at the model flags with the bundle's
rebuilt `bridgestan.o` (`e4b6077b…`), gxx_fixed, `env -u LD_LIBRARY_PATH`,
direct compile+link (the exact recorded W-129 command lines — no make
hpp-regeneration path). .so md5 `117cbc6b48f37846bb96c95aff453b10`; FMA
provenance stock 300/41/22 vs tpvari 305/42/23 (vfmadd/vfmsub/vfnmadd —
FMA-capable schedule both arms). Protocol: walnutpie `build_w36exp` CLI
READ-ONLY, seed 20260819, warmup 100, samples 50, `--metric-window 50`,
the w80 pf init `rep0/chain_0`, real data.

| check | result |
|---|---|
| STOCK arm (W-127's `.so`, reused read-only; md5 `2cf00ef9…`) | draws md5 **`d2e2f896e81dc03aff55e0f2a54f6065`** |
| TPVARI arm | **md5-identical digit-for-digit, the 11,566 `y_hat` columns included** (2,999 grad calls; wall 5.73 → 1.39 s) |
| 100-pt parity (`gate_parity_w130.py`, ctypes C ABI, W-103 points) | **lp 0/100, gradients 0/100, constrained output (params + all y_hat cols) 0/100 EXACT-ZERO** |
| under callgrind (both arms) | both reproduce the same md5 |

### 3b. Disassembly verification (the pre-registered requirement)

- **The edge application on a custom vari == stock's on a stock
  gather-record vari**: the likelihood's edge loop is the BYTE-IDENTICAL
  instruction sequence in both .sos (stock @`0x4be64`, tpvari @`0x51f84`):
  `vmovsd partial[k]` → `vfmadd213sd 0x10(%rdx),%xmm1(w),%xmm0` →
  `vmovsd %xmm0,0x10(%rdx)`, ascending — writing the adjoint at offset
  `0x10` of the vari (the `vari_value<double>` vptr/val_/adj_ layout my
  derived class preserves), i.e. into MY varis exactly as into stock's
  top-of-chain varis.
- **`additive_tp_vari::chain()`** (out-of-line @`0x1d4c0`):
  `vmovsd 0x10(%rdi),%xmm0` (e = the edge-written adjoint); FIVE pure
  `vaddsd`+`vmovsd` pairs into the gathered varis (e, d, c, b, a — reverse
  declaration); the slopes as SINGLE `vfmadd213sd 0x10(%rcx)` (the fused
  AoS form); slope2 = `vmulsd` through the volatile stack slot (rounded
  intermediate) then `vfmadd231sd`, with the 1.0-alias branch
  (`vfmadd231sd %xmm2,%xmm0,%xmm1`) — the W-127-certified pattern
  verbatim; the intercept's pure `vaddsd` LAST.

## 4. Gate (c) — callgrind: **−67.51%** (band −55..−60% EXCEEDED
favorably; the elimination mechanism verified row by row)

Both arms traced with the SAME tool this time (system valgrind 3.25.1; one
at a time, 0 running at launch; W-29 protocol; draws md5 `d2e2f896…` under
tracing on BOTH arms = bit-identity certified under tracing). The fresh
stock trace (54,761,372,248 Ir) cross-checks W-127's recorded baseline
(54,761,167,358, tool 3.23.0) to within 0.0004% (loader noise).

| metric | stock | tpvari | delta |
|---|---|---|---|
| PROGRAM TOTALS Ir | 54,761,372,248 | **17,788,218,162** | **−67.51%** |
| Ir/grad (2,999 both) | 18.26 M | 5.93 M | −67.5% |
| Ir/elem (N=11,566) | 1,578 | 513 | −67.5% |
| sampler wall (untraced) | 5.73 s | 1.39 s | −75.7% |
| sampler wall (traced) | 191.06 s | 44.02 s | −77.0% |

Attribution (self Ir):

| complex | stock | tpvari |
|---|---|---|
| tp-loop forward `operator+` / `operator*` (var) | 15.033e9 / 5.870e9 | **0 / 0 (symbols gone)** |
| add-varis chain / `multiply_vd_vari::chain()` | 3.469e9 / 0.952e9 | **0 / 0 (gone)** |
| vari-stack pushes (`emplace_back`) | 4,898,303,691 | **386,760,787** (~1/13: one larger vari/element vs ~23 small ones) |
| `bs_log_density_gradient` self (the sweep/zeroing frames) | 4.357e9 | **0.347e9** (the sweep now walks 1/23 as many varis — the mechanism behind the band overshoot) |
| `__log1p` (shared interior) | 2,802,390,986 | **2,802,390,986 — IDENTICAL to the digit** |
| Select/sum redux | 1,111,770,583 | **1,111,770,583 — IDENTICAL** |
| lpmf edge application (`update_adjoints`) | 302,990,569 | **302,990,569 — IDENTICAL** (the stock likelihood line retained, verbatim cost — parity by construction) |
| log_prob_impl self | 11.343e9 | (inlined; the tp frames gone) |
| **`gathered_additive_tp` factory (forward)** | — | **5.013e9** |
| **`additive_tp_vari::chain()`** | — | **3.206e9** |
| memcpy | 40.8e6 | 39.9e6 |

Pre-measurement expectations, scored (stated in `scratch/w130/notes.md`
BEFORE measuring): tp complex → ~0 — **EXACTLY MET** (all four tp-complex
symbols gone; pushes 4.898e9 → 0.387e9 in the predicted ~0.3–0.5e9 class);
`__log1p` identical to the digit — MET; edge application retained at
stock cost — MET (digit-identical); draws md5 under tracing = untraced —
MET; net run — my refined estimate was −50..−57% and the registered band
−55..−60%: **EXCEEDED FAVORABLY at −67.51%**. The overdelivery mechanism:
the registered band was calibrated on W-129's arm, which retained a
(dead) value-only rvalue loop and whose sweep frames did not collapse;
eliminating the per-element var population itself collapses the
`grad()`-sweep and `set_zero_all_adjoints` frames (`bs_log_density_gradient`
self 4.36e9 → 0.35e9) — a compounding the per-complex accounting had not
priced. Owned as a favorable deviation, not an in-band result. The arm is
also cheaper than W-129's statistical-class rewrite (23.73e9 → 17.79e9:
the factory computes eta ONCE — no likelihood-side recompute — and one
chain replaces both the scatter callback and the tp chains).

## 5. Gate (d) — TU + controls: PASS

`test/unit/math/rev/prob/bernoulli_logit_lpmf_gathered_test.cpp` extended
(the W-127 seven untouched): **11/11 PASSED** — the landed seven +
`TpVariBitIdenticalToComposedStock` (ALL NINE beta × gather layout
combinations), `TpVariPriorsBothSides` (the causal triangle, both orders),
`TpVariValueMatchesReference` (hand-computed + the stock double lpmf),
`TpVariThrowSet` (three classes, stock message texts). Controls:
`rev/prob/bernoulli_logit_glm_lpmf_test` **22/22**,
`prim/prob/bernoulli_logit_test` **5/5**,
`prim/prob/bernoulli_logit_glm_rng_test` **3/3**,
`mix/prob/bernoulli_logit_glm_lpmf_test` **1/1** — all PASSED.

## 6. Deviations / disclosures (all owned)

- **Band exceeded favorably** (§4): −67.51% vs the registered −55..−60%
  (and my own refined −50..−57%): the sweep/zeroing-frame collapse. Owned.
- **A design refinement found while deriving, BEFORE any code**: the
  pre-registration sketched the vari holding "the gathered coefficient
  varis (routes)"; routing an `rvalue` VIEW var cannot express the SoA
  slot destination (a view's adjoint is copied once by its callback), so
  the leaf vocabulary gained the SLOT tags (vector + slot) — required for
  correctness on SoA-deserializer stacks and harmless on the AoS/Map
  layout the gate model actually carries. The gate-(a) harness was
  upgraded accordingly (beta layout-varied) — closing a gap in W-127's
  harness (its beta was fixed AoS, so slope-coefficient routing was
  single-layout).
- **A predecessor-notes correction, evidence attached**: the W-127 notes'
  claim that the built election88's parameter vectors are SoA
  (`var_value<>`) is wrong — the deserializer's
  `require_var_matrix_t<Matrix<var>>` is false, so `read` returns
  `Map<const Matrix<var>>` (AoS over the params buffer); the
  `gathered_additive_tp` symbol's tag types in the built .so are the
  evidence. Harmless then and now (the leaf routing adapts); the SoA
  discipline remains implemented and gate-a-certified for stacks that do
  produce `var_value<>`.
- **The TU's prior-position tests restrict to AoS/Map operand combos**:
  this math's `normal_lpdf` does not accept `var_value` vectors (the
  bundle's newer math does); the SoA+prior combinations are certified by
  the gate-(a) harness instead (noted in the test).
- The TU needed three test-side fixes after its first run (a hand-arithmetic
  typo, a looser OOB-message match in line with the landed tests' style,
  and a 1-based index in a NaN message) — all TEST bugs, no header change;
  the recorded PASS runs are the final state.
- Two HARNESS bugs found and fixed before any recorded gate number (a
  `Map` copy-assignment compile error; a throw-case shape mismatch) — no
  wrong-arm number was ever recorded.
- Build wiring: the model .so was compiled+linked with the exact recorded
  W-129 command lines (direct gxx, no bridgestan make — no hpp-regeneration
  path exists to trap); the branch header lives at a PRIVATE inode in
  `bs_w130` (rm-first; `bs_w127`'s copy re-verified `7367df51…` post-session).
- Read-only reuse: `scratch/w127` (bundle lineage, pristine hpp, STOCK .so,
  draws), `scratch/w80` (data.json + pf inits), `scratch/w46/gxx_fixed`,
  the walnutpie `build_w36exp` CLI, `scratch/w129/gate_parity_w129.py`
  (adapted). Sibling integrity re-verified post-session: bs_w127's header
  `7367df51…`, `bridgestan.o` `e4b6077b…`, the stock .so `2cf00ef9…`, the
  stock draws `d2e2f896…` — all byte-intact; `stanc3_w129` clean; no
  pushes; WORKLOG.md and comms.md not written by this agent (PI-owned).
- Machine: ≤2-core builds (nice 19, gxx_fixed, `/usr/bin/make` for TUs,
  `env -u LD_LIBRARY_PATH`), callgrind serialized (one at a time, 0
  running at each check), sampler cells single-process nice 19
  OMP_NUM_THREADS=1.

## 7. Artifacts

- Branch `gathered-additive-tpvari` @ `a2593a12fe` (base `5267fb4858`):
  `330f6db2f7` (header) + `a2593a12fe` (TU). DCO + AI notes. Not pushed.
- `scratch/w130/`: `notes.md` (session state incl. the design derivation,
  the expectation statements, and the gate results), `test_prim.cpp` +
  `build_gate_a.sh` + `test_prim_{O3,O2}` (gate a),
  `make_tpvari_edit.py` + `model_election88_tpvari/` (hpp `6af01475…`,
  .so `117cbc6b…`), `gate_parity_w130.py` + `parity_{ref,tpvari}.npz`
  (gate b), `run_callgrind_w130.sh` + `profile_{stock,tpvari}/` (gate c),
  `bs_w130/` (bundle copy, private-inode header), `runs/tpvari_w100s50.csv`
  (md5 `d2e2f896…`), `logs/` (builds, runs, TU/controls, callgrind).
