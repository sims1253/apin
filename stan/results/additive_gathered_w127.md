# W-127 — the ADDITIVE multi-gather `bernoulli_logit_lpmf` family (gathered-GLM campaign family 4): ALL BIT-IDENTITY GATES GREEN (gate (a) 13,076 checks at both flag levels; gate (b) draws md5-exact INCLUDING the 11,566 `y_hat` output columns + 100-pt parity exact-zero; TU + controls green) — with ONE pre-registered design refinement owned below (the tp-WRITEBACK variant, forced by a precisely-diagnosed stack-sweep reordering in the priors-first model layout) and ONE pre-registered cost expectation missed UNFAVORABLY (increment-1 total-run +11.5%: the accepted double-compute, now quantified; the increment-2 headroom measured at 55.2% of the stock run)

Executed 2026-08-30 per WORKLOG "W-127 PRE-REGISTRATION" (family 4, increment
1: primitive + hand-edit gate ONLY; the emission registry row is increment 2).
Deliverable: branch **`gathered-additive`** in worktree `external/math_dev_w127`
(4 commits on top of the gathered-glm-mapfix tip `eb8fe63f9c`): `f1658f013d`
(the additive overload), `b2acaeeea8` (two bit-parity fixes the unit gate
caught), `6c31a35c66` (the tp-writeback variant), `5267fb4858` (the TU). Not
pushed. Artifacts under `scratch/w127/`.

**Headline: the additive eta shape
`eta[n] = intercept + Σ (coef·xd1[·xd2]) + Σ coefs_k[idx_k[n]]` (the
election88 class) is now a bit-identical math-side primitive in every operand
layout the stanc deserializer produces — values, every gradient component, the
full same-seed draws file (md5 `d2e2f896e81dc03aff55e0f2a54f6065`,
transformed-parameter output columns included) and a 100-point
lp/gradient exact-zero parity — after machine-code-verified replication of
stock's forward op order, its aliasing special cases (`var*1.0` creates NO
vari), and its reverse sweep order (elements DESCENDING, leaves in reverse
declaration order, fused/unfused increment forms per the decoded
`vfmadd132sd`/`vaddsd` schedule). The one structural discovery: in
priors-before-likelihood models (election88), the var-stack sweep applies the
prior edges BETWEEN the likelihood edge and the transformed-parameter chains,
so the likelihood's adjoints must be routed THROUGH the retained tp chain (the
`_tp` writeback variant) to stay bit-identical; direct scattering (right for
likelihood-last models, the hier_2pl/radon class) reorders each coefficient's
accumulation by one term and lands 1 ulp off (mechanism measured and
documented below). The family's stock cost baseline is established
(18.26M Ir/grad, 1,578 Ir/elem) and increment 1's honest price is measured:
+11.5% total-run — the retained tp loop is untouched by design and the
primitive's eta recompute costs more than the stock likelihood complex it
replaces; the increment-2 headroom (eliminating the tp loop compiler-side) is
55.2% of the stock run.**

## 1. What was implemented (branch `gathered-additive` @ `5267fb4858`)

`stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp` gains, alongside the
landed 2PL overload (untouched):

- **Leaf tags** (with deduction guides and explicit ctors, both call syntaxes):
  `gather_term{name, coefs, idx}` (a `coefs[idx[n]]` term; AoS
  `Matrix<var>`, SoA `var_value<Matrix<double>>`, and `Map<const
  Matrix<var>>` layouts all routed), `slope_term{coef, xd}`
  (`coef·xd[n]`), `slope2_term{coef, xd1, xd2}` (`(coef·xd1[n])·xd2[n]`,
  the `beta[5]*female*black` form).
- **`bernoulli_logit_lpmf_gathered_additive(y, intercept, leaves...)`** —
  value path = stock's per-element op order, decoded from the stock
  election88 .so built at the MODEL FLAGS (`-O3 -mavx2 -mfma`): each product
  leaf a rounded `vmulsd` chain (left-associated for slope2; `volatile`
  barriers so no accumulation add can contract into an fma with a leaf
  product — stock adds are pure `vaddsd`s over already-rounded products),
  summed left-to-right; interior = the `bernoulli_logit_lpmf` expression
  verbatim. Reverse = ONE callback: elements DESCENDING, leaves in REVERSE
  declaration order (the var-stack reverse sweep), gathered terms pure adds,
  single-product terms FUSED multiply-adds (`multiply_vd_vari::chain`'s
  decoded `vfmadd132sd`), two-product terms a rounded intermediate then a
  fused multiply-add, intercept last.
- **`bernoulli_logit_lpmf_gathered_additive_tp(y, adjoint_target, intercept,
  leaves...)`** — the tp-writeback variant for models whose predictor ALSO
  lives in a transformed parameter kept materialized for output (§3).

Two machine-level subtleties the bitwise gate caught (commit `b2acaeeea8`):

1. **The `var * 1.0` alias**: stock's `operator*(var, Arith)` returns its var
   operand unchanged when the multiplier is exactly 1.0 — NO vari exists, so
   for those elements the composed increment is the outer product's SINGLE
   fused multiply-add, not the two-step chain. election88's `black`/`female`
   are 0/1 data, so this is the COMMON case in-model. The fix carries an
   aliased branch, with a `volatile` copy of `e` in the generic path so GCC
   cannot CSE the two branches' `e*xd2` products (the shared product left the
   aliased branch's add unfused — two roundings — found by disassembling the
   gate binary after it kept failing 1 ulp).
2. **Check order**: the gathered range checks must fire BEFORE
   `check_bounded` on `n` (the composed path's tp loop runs ahead of the
   likelihood statement) — mixed bad-index-and-bad-y states are now
   stock-ordered.

Checks mirror stock with stock's function name in messages
(`bernoulli_logit_lpmf`: `check_bounded` on `n`, the indexed
`check_not_nan` on the assembled predictor) and `rvalue`'s exact
"vector[uni] indexing" text per gathered leaf, in the composed per-element
leaf order.

## 2. Gate (a) — bitwise unit, MODEL FLAGS + -O2: PASS

`scratch/w127/test_prim.cpp` vs the composed stock expression using the REAL
`stan::model::rvalue`/`index_uni` (the generated hpp's exact operand order),
on `scratch/w127/bs_w127` (cp -al of the w108 `bs_prim_stock` lineage: SoA
deserializer slice + W-102 gather fix, NO W-103 kernel — stock interior both
sides), branch header FIRST on the include path, built at `-O3 -mavx2 -mfma`
AND `-O2` (`test_prim_{O3,O2}`):

**13,076 bitwise checks + 8 throw-set checks, 0 mismatches at BOTH levels** —
patterns P1 (1 gather), P2 (2 gathers + slope), P3 (3 gathers + 2 slopes +
slope2), P4 (2 gathers SHARING one coefficient vector — slot-sharing within
element), P5 (the exact election88 line over the REAL data
`election88_data.inc`, generated from w80's data.json: N=11,566, 5 gathered
vectors, 3 slopes + 1 slope2, binary AND real data vectors), P6 (P5 + prior
statements BEFORE the likelihood — the sweep-order certification for the
writeback variant); each × 3 layouts (AoS/SoA/Map); N ∈ {1,2,3,5,8,17,100,
919,2000}; 6 seeds; all-y=0/all-y=1; a scale sweep past the ±20 branch cuts
(×2 on the real data); the big-scale E88 case. Throw set: OOB index (both
leaf orders), index 0, NaN coefficient (stock's indexed message text
byte-identical), y=2, y=-1, N=0 — all byte-identical messages.

## 3. Gate (b) — election88 model, bit-identity: PASS (after the §3b refinement)

Both arms built on `bs_w127` at model flags with the same bundle stanc
(v2.39.0, hpp md5 `d0557507…` regenerated pristine) and the same rebuilt
`bridgestan.o`. Protocol (W-29, verbatim): walnutpie `build_w36exp` CLI
READ-ONLY, seed 20260819, warmup 100, samples 50, `--metric-window 50`, the
w80 pf init `rep0/chain_0` (90 coords), real data
(`scratch/w80/model_election88_full/data.json`).

| check | result |
|---|---|
| STOCK arm reference (2,999 grad calls) | draws md5 **`d2e2f896e81dc03aff55e0f2a54f6065`** (50 × 11,656 columns: 90 params + 11,566 `y_hat`) |
| PRIM arm (hand-edited hpp: include + likelihood line ONLY, rev instantiation; tp loop FULLY STOCK; double-mode instantiation stock) | **md5-identical digit-for-digit, `y_hat` columns included** |
| 100-pt parity (`gate_parity_w127.py`, ctypes C ABI, W-103 point scheme) | **lp 0/100, grad 0/100 EXACT-ZERO** |
| under valgrind (both arms) | both reproduce the same md5 |

### 3b. The sweep-order mechanism (owned refinement, NOT a silent pass)

The first prim arm used the direct-scatter overload. Its draws
(`295549186964b50693df3cff63ddbbe4`) diverged with lp EXACTLY equal at all
100 parity points and ~35 of 90 gradient components 1 ulp off. Mechanism
(diagnosed from the source-level sweep semantics — `grad()` walks
`var_stack_` top-down): election88's model block puts the prior statements
(`a ~ normal(0, sigma_a); …`) BEFORE the likelihood, so stock's stack is
[tp varis][prior-edge callbacks][likelihood callbacks] and the sweep applies
the prior edges BETWEEN the likelihood edge and the tp chains — each
coefficient accumulates `prior + Σw`. A callback at the likelihood's stack
position scatters `Σw` FIRST, then the prior lands — `RN(Σw + prior)` vs
stock's `RN(prior + Σw)`, a 1-ulp reorder per coefficient. The
hier_2pl/radon gathered families never hit this because their likelihood
operands are gathered AT the likelihood statement (their composed callbacks
sit at the same stack position as the primitive's). The cure inside the
increment-1 boundary (still ONE line group in the hpp):
`bernoulli_logit_lpmf_gathered_additive_tp` keeps the gathered value path
(bit-identical, gate (a)) but writes its increments into
`adjoint_target[k]`'s vari with the stock edge's decoded arithmetic (one
fused multiply-add per element, ascending), letting the RETAINED tp chains
propagate at their own stack position — bit-identical by construction for
the priors-first layout. Both variants are documented in the header with
their applicability (scatter = likelihood-last models; `_tp` =
tp-fed/priors-first models); the P6 unit pattern certifies the `_tp` path
bitwise INCLUDING the prior statements.

### 3c. Wiring deviations owned

- The first stock .so linked the bundle's W-103-era PREBUILT `bridgestan.o`
  (md5 `7be1e36c…`, default flags) — it HEAP-CORRUPTED at the wide
  (11,566-column) `y_hat` output write (the mixed-ABI object class W-106
  warned about; the family's prior gate models have no wide tp output, so
  this was never exercised). Rebuilt in-copy at model flags
  (`e4b6077bf7bdc28fccbb87361375040f` = the canonical all-layers bridge
  md5) — crash gone. Both arms link the rebuilt object.
- The `build_w36exp` CLI and `walnutpie_lowrank/build_gates` CLI produce
  byte-identical draws on the fixed .so (verified on a tiny run); the
  pre-registered `build_w36exp` was used for all recorded runs.
- The .so `strings` assertion (W-118) is vacuous for the prim arm (full
  inlining under `-fvisibility=hidden` leaves no symbol): replaced by the
  hpp-md5-pre/post-build assertion (the edit is the only call site — if the
  hpp survives, the primitive is in) plus the bit-identity result itself.

## 4. Gate (c) — callgrind: the family baseline + the honest increment-1 price

W-29 protocol, one arm at a time, draws md5-identical under tracing.

| arm | total Ir T | Ir/grad (2,999) | wall |
|---|---|---|---|
| stock (FAMILY BASELINE — unmeasured until now) | **54,761,167,358** | **18.26 M** | 5.73 s |
| prim (writeback) | 61,050,081,754 (**+11.49%**) | 20.36 M | 6.35 s |

Pre-measurement expectation (stated first): −2..+2% (noise class), since the
tp loop is retained by design and only the lpmf edge machinery is replaced.
**Outcome: MISSED UNFAVORABLY at +11.49%** — the accepted-and-disclosed
double-compute is larger than the saved complex. This is the increment-1
trade the prereg accepted, now quantified; there is no win to claim at this
increment, and none was claimed.

Attribution (per-function self Ir; every shared complex IDENTICAL to the
digit — the retained-tp-loop disclosure rows):

| complex | stock | prim |
|---|---|---|
| tp-loop forward `operator+` | 15,033,091,318 | 15,033,091,318 (=) |
| tp-loop forward `operator*` | 5,870,128,908 | 5,870,128,908 (=) |
| add-varis `chain()` | 3,469,140,738 | 3,469,140,738 (=) |
| `multiply_vd_vari::chain()` | 951,907,992 | 951,907,992 (=) |
| vari-stack pushes (`emplace_back`) | 4,898,303,691 | 4,898,270,364 (≈) |
| `bs_log_density_gradient` | 4,356,975,729 | 4,356,975,729 (=) |
| interior `__log1p` + Select/sum redux | 2,802,390,986 + 1,111,770,583 | identical (=) |
| composed lpmf forward complex (checks, edge ctor) | 1,837,166,081 | **0** |
| lpmf edge application (`update_adjoints`) | 302,990,569 | **3,047,569** |
| `ops_partials_edge` ctor | 246,027,320 | 4,643,562 |
| `log_prob_impl` self | 11,342,940,728 | 11,221,371,238 |
| **primitive forward (`additive_impl`)** | — | **4,075,811,028** |
| **`resolved_gather` forward (per-element `check_range` + reads)** | — | **4,068,745,310** |
| **primitive writeback callback** | — | **299,839,316** |
| memcpy (arena/resolved copies) | 40,823,895 | 383,572,116 |

Reading: the writeback callback (299.8 M) costs EXACTLY the stock edge
application it replaces (299.9 M) — parity by construction. The net +6.29e9
Ir is the primitive's eta recompute (8.14e9 = forward + gather, ≈235
Ir/elem/grad: the per-element `check_range` call and the volatile barriers
dominate) minus the removed stock complex (2.38e9). The increment-2
headroom this measurement establishes: the tp-loop complex (`operator+` +
`operator*` + their chains + the vari pushes) is **30.22e9 Ir = 55.2% of the
stock run** (~871 Ir/elem/grad) — the compiler-side elimination target; a
second-order target is the primitive's own gather pass (fold the checks,
drop the barriers where the fused form is provably identical).

## 5. Gate (d) — TU + controls: PASS

`test/unit/math/rev/prob/bernoulli_logit_lpmf_gathered_test.cpp` extended
(the landed 2PL three UNTOUCHED): **7/7 PASSED** — the landed trio +
`AdditiveBitIdenticalToComposedStock` (randomized shapes/values, 3 layouts,
binary+real slope data, branch-cut scale), `AdditiveTpWritebackPriorsFirst`
(the sweep-order certification), `AdditiveScalarValueMatchesReference`
(hand-computed), `AdditiveThrowSet` (three classes, stock message texts).
Controls on the branch: `rev/prob/bernoulli_logit_glm_lpmf_test` **22/22**,
`prim/prob/bernoulli_logit_test` **5/5**, `prim/prob/bernoulli_logit_glm_rng_test`
**3/3**, `mix/prob/bernoulli_logit_glm_lpmf_test` **1/1** — all PASSED.

## 6. Deviations / disclosures (all owned)

- **The `_tp` writeback variant** (§3b): the pre-registered "primitive call
  consuming the gathered coefficients independently" is implemented AND
  bit-certified (gate (a)) as the scatter overload, but the election88 gate
  model — priors before likelihood — requires the writeback routing for
  bit-identity. The hand edit remains ONE line group (include + likelihood
  line); the tp loop is fully stock; the double-compute is accepted,
  disclosed, and now measured (§4). The scatter-mode arm's divergent md5 is
  recorded as the mechanism's evidence, not as a gate result.
- **Gate (c) band missed unfavorably** (+11.49% vs the stated −2..+2%): the
  pre-registered expectation was wrong about the SIZE of the double-compute
  (the eta recompute's check/barrier overhead was not priced). Owned; the
  favorable increments are quantified for increment 2.
- **The bridgestan.o mixed-ABI crash** (§3c) — first wide-tp model on this
  bundle lineage; rebuilt in-copy; both arms identical wiring.
- The stock reference for this model/stack combination is established BY THIS
  RUN (no prior election88 arm on the bernoulli family stack); the w80 .so
  (different stack, default flags) was used read-only only to source the data
  and init.
- Machine: ≤2-core builds (nice 19, `gxx_fixed`, `/usr/bin/make`,
  `env -u LD_LIBRARY_PATH`), callgrind serialized (one at a time, 0 running
  at each check), sampler cells single-process nice 19 OMP_NUM_THREADS=1.
  WORKLOG.md not written by this agent.
- Read-only reuse: `scratch/w80` (data.json + inits), `scratch/w108`
  (bs_prim_stock lineage + gate-harness patterns), `scratch/w46/gxx_fixed`,
  walnutpie CLIs, `scratch/w127/hpp` (predecessor's verified-stanc hpp).
  Sibling integrity: `bs_prim_stock` untouched (bs_w127 is a hardlink copy;
  every modified file was rm-firsted to a private inode); no pushes.

## 7. Artifacts

- Branch `gathered-additive` @ `5267fb4858` (base `eb8fe63f9c`):
  `f1658f013d` + `b2acaeeea8` + `6c31a35c66` + `5267fb4858`. DCO + AI notes.
  Files: `stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp`,
  `test/unit/math/rev/prob/bernoulli_logit_lpmf_gathered_test.cpp`.
- `scratch/w127/`: `notes.md` (session state), `election88_data.inc` +
  `test_prim.cpp` + `build_gate_a.sh` + `test_prim_{O3,O2}` (gate a),
  `bs_w127/` (bundle), `model_election88_{stock,prim}/` (both .sos),
  `gate_parity_w127.py` (gate b), `runs/` (both draws CSVs),
  `profile_{stock,prim}/` (callgrind.out + ann.txt + draws),
  `logs/` (builds, runs, callgrind, TU/controls).
