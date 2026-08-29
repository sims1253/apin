# W-122 — source-level fusion of the poisson_log_glm interior (bit-identical)

Executed 2026-08-29 per the WORKLOG "W-122 PRE-REGISTRATION". Branch
`poisglm-fused` in worktree `external/math_dev_w122` (base 344d7167a0, the
standard campaign base), commits `c013ce51a5` (header) + `22403e719b` +
`03c5e17783` (TU). Not pushed. Artifacts `scratch/w122/`. WORKLOG.md and
comms.md not written by this agent (PI-owned).

**Headline.** The measured exp(θ) recompute is eliminated and the
elementwise frame fused: the family interior drops **248.52 → 196.39
Ir/elem (−21.0%)** at the census posture (propto=false, int y, N=12573,
K=2, avx2) — inside the pre-registered −20..−30% band — with the second
exp site → 0 EXACTLY (72.00 → 36.00 Ir/elem; 36.0 is the one remaining
call), lgamma call cost unchanged (110.47 both arms), reverse still free
(0.01), and every gate bit-identical: 55-case unit (both flag levels),
6/6 bespoke-model sampler cells digit-for-digit, 200-point parity
exact-zero, TU + neighbor controls green.

## 1. The two exp sites and how they were unified

Stock header (md5 2173b2e2, unchanged lines since the census — its line
numbers 111/125 are still exact):

- site 1 (lines 110–111):
  `theta_derivative = as_array_or_scalar(y_val_vec) - exp(theta.array());`
- site 2 (lines 124–125):
  `logp += sum(as_array_or_scalar(y_val_vec) * theta.array() - exp(theta.array()));`

Same input `theta`, deterministic function → the recompute is pure waste.
THE MECHANISM FINDING (disassembly, this tree's Eigen 5.0.1, and the
bundle's Eigen 3.4.0 alike): whether the two sites provably evaluate the
SAME scalar function depends on y's element type.

- **Non-double y (the stanc `array[int]` class — every Stan-language
  model):** both sites are mixed-scalar Eigen expressions
  (`scalar_difference_op<A,B>` has `PacketAccess = is_same<A,B>`), so
  Eigen compiles BOTH to scalar DefaultTraversal passes calling glibc
  `exp` per element (verified: `exp@plt` at 0x134e7 in stock site-1 loop
  and 0x1383c/0x13893 in the site-2 redux loop, avx2 build; the census's
  glibc-exp attribution reproduces). Both sites produce identical
  per-element values → unified into ONE `std::exp` per element.
- **Double-typed y (C++-API-only; unreachable from Stan code):** both
  sites are pure-double expressions Eigen evaluates with packet
  traversals — vectorized pexp bodies with per-site glibc scalar tails
  (stock disasm: the Eigen pexp polynomial chain at 0x16308–0x1643e and
  packed `vfmsub132pd` redux at 0x16745+). A shared recompute is not
  provably value-identical there (pexp vs glibc exp differ in ULPs), so
  **that class keeps the stock interior byte-identical** — the interior
  is routed by the post-`value_of` y scalar type. Disclosed as the
  honest scope of the prereg's determinism argument; the mission class
  is fully covered.

## 2. The fused interior (non-double y)

One scalar-sequential loop replaces stock's three elementwise passes
(derivative, constant lgamma fold, term fold):

```
e = exp(theta[i]);  td[i] = y[i] - e;                 // stock site-1 ops
terms_sum += theta[i] * y[i] - e;                     // stock site-2 ops
lgamma_sum += lgamma(y[i] + 1);                       // stock lgamma site
```

- per-element op order preserved: `td` = cvt + plain `vsubsd` (stock
  site-1 shape); the term keeps stock's contraction —
  `vfmsub132sd(theta, y, e)` at −O3 −mavx2 −mfma (stock 0x13859/0x138b6;
  patched 0x13969/0x139da), `mulsd`+`subsd` at −O2 (both arms) —
  contraction points MATCHED at both flag levels;
- fold orders are Eigen's DefaultTraversal redux left folds starting AT
  element 0 (`terms_sum = t0; += t_i`), and the final combination keeps
  stock's `(0 − lgamma_sum) + terms_sum` shape (`vsubsd` then `vaddsd`,
  patched 0x13c11/0x13c19);
- `theta` construction (GEMV + broadcast add), `sum(theta_derivative)`
  (Eigen's own vectorized redux), every check in stock's exact order
  with byte-identical messages (incl. the quirky third deferred check on
  `theta` under the "Matrix of independent variables" label), the edge
  partials, and `build` are untouched; the reverse path is untouched
  (0.01 Ir/elem before and after).
- the folds run before the deferred `isfinite` check (stock ran them
  after); throw parity holds — same exception, message, first-failing
  index — the extra pre-throw FP work is unobservable (side-effect-free
  calls; errno/FP-flag state disclosed in §6).

## 3. Gates

| gate | evidence | verdict |
|---|---|---|
| (a) bitwise unit, −O3 −mavx2 −mfma AND −O2 | `scratch/w122/test_gate_a.cpp` + `build_gate_a.sh` (pristine-header overlay md5-asserted vs branch, same Eigen per arm): N∈{1..8×K1..3, 8×K4..8, 97, 100, 1000×2, 12573×2}, scalar/vector alpha, int/VectorXi/double y, all-zero y, var-x (x edge), row-vector x (T_x_rows==1) incl. N=1, propto true/false, theta +695 (e~1e301) and −750 (e=0 graceful), repeated-grad, 11 throw-set cases + post-throw valid-state re-evals | **55 cases, 674 hex bit-words/arm/level, 0 mismatches at BOTH levels**; 9 throw cases byte-identical messages/element indices (y-neg, y-NaN, β-inf, β-NaN, α-inf, x-inf, β/α/y dim), 2 identical graceful −inf returns (vec-α −inf, θ=710), post-throw states identical. phi: not in the signature |
| (b) bespoke model gate (no suite model uses poisson_log_glm — bespoke per prereg) | `poisreg.stan` (`y ~ poisson_log_glm(x, alpha, beta)`, N=2000 K=3, fixed-seed counts, 510 zeros) + `poisreg_full.stan` (`target +=`); stock/patched .sos from the SAME bs_prim_stock-lineage bundles (Eigen 3.4.0), stanc 2.39.0 default level, model flags; sampler `external/walnutpie/build_w36exp/examples/stan_cli` read-only, seed 20260819+c, warmup 100, samples 50, metric-window 50, deterministic per-chain plain-text inits; hpp parity asserted between arms | **stock md5s recorded FIRST, patched 6/6 digit-for-digit**: c2fee4ec…, 22f7f065…, fa7796dd… (poisreg), 2ad17806…, 22f7f065…, 490f75c6… (poisreg_full); **parity 100 pts/variant (ctypes C ABI): lp 0/100, grad-vectors 0/100 exact-zero** both variants |
| (c) callgrind band −20..−30% | `probe_pois.cpp` census discipline (client requests, ops outside region), 200 iters, N=12573, one run at a time, no sibling collision (W-118's driver was between runs; my refusal check + theirs) | **pois_glm full 248.52 → 196.39 = −21.0% (IN BAND)**; fwd −21.0%; rev 0.01 both; exp 72.00 → 36.00 (**second site → 0 exactly**; remaining 36.0 = the one call); lgamma 110.47 → 110.47 (calls unchanged); lpmf-self 53.03 → 36.91 (frame −16.1); propto arm (lgamma compiled out) 125.97 → 76.84 = −39.0%; double-y control −0.1%. Stock anchored vs census 249.4 (0.4% agreement) |
| (d) TU + controls | branch TU extended: `poisson_glm_throw_set_parity_w122` (exact stock messages/indices, the W-112.2 lesson) + `poisson_glm_fused_interior_paths_w122` (all-zero y, deep-underflow θ, row-vec x, zero-then-reeval repeated grad); worktree builds (Eigen 5.0.1, gxx_fixed, ≤2 cores) | rev poisson_log_glm **24/24 PASSED** (22 pre-existing + 2 new), mix **1/1**, UNTOUCHED controls: prim poisson_log_test **2/2**, prim poisson_test **5/5** |

## 4. Attribution vs the pre-registered decomposition

Census prediction: exp recompute −33 + frame fusion ≈ −25 → −25..−30%.
Measured: **−36.0 (exp site) + −16.1 (frame/self) = −52.1 → −21.0%**.
The exp site delivered slightly more than predicted (−36 vs −33; the
census's exp attribution 66.0 vs my 72.0 at the same posture — glibc
exp's Ir is mildly value-dependent); the frame fusion delivered less
(−16.1 vs −25 — the census's frame estimate was a W-119-ratio
extrapolation; the honest floor here is one fused transcendental-bound
loop + the retained Eigen td-sum + GEMV passes). Net: in band, at the
low end. The propto=true emission (the `~` idiom, lgamma out) sees
−39.0% — the biggest per-model win for Stan-written poisson models.

## 5. Hygiene

`bs_prim_stock` untouched (bridgestan.o mtime unchanged); sibling trees
read-only (tbb .so copied FROM w118 into w122's gitignored lib/tbb);
branch tree clean at 03c5e17783; nothing pushed. WORKLOG/comms not
modified. Machine: ≤2 build cores, nice 19, `env -u LD_LIBRARY_PATH`,
gxx_fixed, callgrind 3.23 (`~/vginstall`), one at a time.

## 6. Deviations / disclosures (owned)

- **Double-y routing is a scope narrowing owned as mechanism**: the
  prereg's "compute exp(theta) once" is implemented only where stock's
  two sites provably evaluate the same scalar function (non-double y);
  double y keeps stock's interior (its sites use Eigen packet pexp with
  per-site scalar tails — unification not provably value-identical).
  Stan-language models cannot produce double y (poisson y is `array[int]`).
- The folds precede the deferred check (unobservable; errno/FP-flag
  state at throw time disclosed as the one theoretical difference —
  stock also evaluates the same transcendental calls pre-throw).
- W-118's census-era `ps grep callgrind` false-positive class recurred
  (wrapper command strings); the real-binary check showed no sibling
  valgrind running during my sequence.
- Model-gate CSVs carry draw columns only (no lp__ column) — the
  cross-variant c1 md5 coincidence (poisreg == poisreg_full at chain 1)
  is rng-stream identity, irrelevant to the within-variant gate.
- Unit-gate arms compare at the SAME Eigen (5.0.1 worktree for (a)/(d),
  3.4.0 bundle for (b)/(c)); stock itself is not bit-stable across flag
  levels (GEMV contraction differs −O2 vs avx2), so all parity is
  same-level, per protocol.
- First TU draft had my own fixture errors (1-based message indices,
  scalar-α adjoint sum, root-list re-chain on second grad()) — fixed in
  03c5e17783; the header never changed after c013ce51a5.

## 7. Artifacts

`scratch/w122/`: `test_gate_a.cpp` + `build_gate_a.sh` + `ga_{stock,
patched}_{O3,O2}.txt`; `setup_gate_b.sh` + `bs_stock/` + `bs_patched/` +
`model_poisreg*/` + `run_cells.sh` + `runs_{stock,patched}/` +
`gate_parity_w122.py`; `probe_pois.cpp` + `build_probe.sh` +
`run_callgrind_w122.sh` + `extract.py` + `logs/` (8 callgrind sets +
cell/build logs); `disasm_probe.cpp` + `build_disasm.sh` +
`{stock,patched}_{inty,dbly}_{avx2,o2}.asm` + the gate-a binaries.
