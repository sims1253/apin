# W-126 — `pcm_lpdf_gathered` (family 3, the LAST gathered family): STEP ZERO GO + ALL FOUR GATES GREEN, bit-identical (draws md5 `a342848b…` DIGIT-FOR-DIGIT on a doubly-anchored stock reference, 100-pt parity EXACT-ZERO, 20,764 unit component checks + 13 throw checks at BOTH flag levels), and the family-3 baseline lands at **−88.28% total Ir** (214.3e9 → 25.1e9; wall 22.6 s → 2.3 s, 9.7×) — the campaign's largest single-model reduction, exceeding the registered −25..−45 band favorably with the mechanism owned

Executed 2026-08-30 per WORKLOG "W-126 PRE-REGISTRATION" (family 3, increment
1: primitive + hand-edit gate only; emission row later). Deliverable: branch
**`gathered-pcm` @ `42fa0ecbf4`** (base `fork/develop` `344d7167a0`) in
worktree `external/math_dev_w126`: one new header
`stan/math/rev/prob/pcm_lpdf_gathered.hpp` + one new unit-test TU. Nothing
else in math touched. Artifacts in `scratch/w126/`.

---

## 0. STEP ZERO — the pre-registered decisive question, answered FIRST

**Question**: is the category LSE reduction of the stock interior replicable
bit-identically in a single-pass primitive (Eigen redux semantics + the
accumulator order decide), or is this a STOP?

**Verdict: REPLICABLE — GO.** With two findings the pre-registration did not
anticipate, both resolved empirically before any gate:

1. **The gate model has no stock `pcm_lpmf` to read** — none exists in any
   stack (`prim/prob` carries categorical/ordered_logistic only). The model
   defines its own `pcm` user function; the generated hpp compiles it to
   `append_row(rep_vector(0,1), subtract(theta*alpha, beta_seg))` →
   `softmax(cumulative_sum(·))` → `categorical_lpmf(y+1 | ·)`. The "stock
   interior" is that composed path — read at source level, then probe-verified.

2. **The softmax interior's arithmetic is EXPRESSION-TYPE-DEPENDENT and
   STACK-DEPENDENT.** The stock rev softmax feeds prim softmax a `val()` view
   over an AoS var matrix. On the family bundle (bs_w130 lineage, Eigen 3.4)
   that view stays lazy → Eigen takes the SCALAR traversal everywhere (glibc
   `exp` per element, a sequential ascending sum, per-element divide); a
   direct dense call packetizes (Eigen's polynomial `pexp`, striped sum) and
   DIFFERS in the last ulp (3,554/14,000 elements probed). On the branch base
   (`344d7167a0`, Eigen 5, the `apply_vector_unary` softmax) the view is
   materialized and the PACKET path is what the model runs — there the dense
   call matches and the scalar spelling does not. **Resolution: the primitive
   calls `softmax(<val() view over an arena AoS var matrix>)` — the exact
   instantiation the composed stock path hits — bit-identical on EVERY stack
   (probe: 0 diffs against the composed stock path on both stacks).** The
   pre-registered "Eigen redux semantics" risk dissolved: whatever traversal
   the stack compiles is inherited by construction. (Found via a harness
   mistake worth recording: an early probe put the whole branch repo first on
   the include path, shadowing the bundle's math — the W-112 discipline of
   shadowing ONLY the new header is load-bearing.)

The rest of the interior is sequential scalar arithmetic, fully derived and
probe-verified (400/400 trials bitwise, K = 3..9): forward `t = θ_j·α_i`;
`c₀ = 0; c_k = c_{k−1} + (t − β_k)`; softmax; `lp_n = log(p[y_n])`. Backward:
`r = 0` except `r[y] = e/p[y]` (a DIVISION — the log node's chain);
`dot = p·r`; `A = p⊙(r − dot)`; the cumulative_sum reverse relay makes
`adj(u_k) = A_k + (A_{k+1} + …)` (RIGHT-nested); the subtract node's loop
accumulates `adj_t = ((adj(u₀) + adj(u₁)) + …)` ASCENDING left-associated;
`θ_j += adj_t·α_i` / `α_i += adj_t·θ_j` (single-statement, FMA-contractible —
the compiled `multiply_vv_vari::chain` form); `β_k −= adj(u_k)` (pure
subtracts). The softmax adjoint's dot redux is sparse-immune (`r` has one
nonzero), so the adjoint path is stack-independent. Observations scatter in
reverse-n (the stock sweep order); the accumulator keeps the W-112
per-observation-term shape (the rev `accumulator<var>`'s 128-chunk buffer
forces it — unchanged conclusion for family 3).

## 1. The primitive (branch `gathered-pcm` @ `42fa0ecbf4`)

```cpp
std::vector<var> pcm_lpdf_gathered<propto>(
    const std::vector<int>& y,        // 0-based categories, y[n] in 0..m[ii[n]]
    const T_theta& theta, const std::vector<int>& jj,     // 1-based
    const T_alpha& alpha, const std::vector<int>& ii,     // 1-based
    const T_beta& beta,               // concatenated steps, sum(m) entries
    const std::vector<int>& pos, const std::vector<int>& m);
```

- **Forward** (per observation, stock op order): one double multiply for `t`,
  the sequential cumsum, the view-based softmax (§0), then
  `check_bounded("categorical_lpmf", "Number of categories", y+1, 1, K)` and
  `check_simplex("categorical_lpmf", "Probabilities parameter", p)` —
  categorical_lpmf's own order and strings; `lp_n = log(p[y_n])` wraps a plain
  no-chain `vari` (one per observation, the accumulator's push targets).
- **Reverse** — ONE `reverse_pass_callback` reproducing the §0 adjoint chain
  per observation in reverse-n order. Operand routes: `Matrix<var>` /
  `Eigen::Map` (the model's deserializer layouts) accumulate through the
  coefficient varis with the fused single-statement form; `var_value<>` (SoA)
  takes the two-rounding form (rounded product behind a volatile barrier,
  then a plain add into the matrix adjoint slot — the stock per-read view-node
  schedule, W-108.1 discipline).
- Index checks in stock's evaluation order (`jj`/`theta` then `ii`/`alpha`,
  `vector[uni] indexing` messages) — the compiled stock expression's order,
  gate-proven byte-identical.

## 2. Gate (a) — bitwise unit, MODEL FLAGS + −O2: PASS

`scratch/w126/test_prim.cpp` vs the composed stock arm built from the EXACT
generated loop (real `stan::model::rvalue`/`index_uni`, `segment`, the user-fn
body, the real `accumulator<var>`), on the bs_w130-family bundle math with
ONLY the new header shadowing (`inc/`, the W-112 discipline), built at
`-O3 -mavx2 -mfma` AND `-O2`:

**802 cases / 20,764 bitwise component checks (lp + every θ/α/β adjoint,
memcmp), 0 mismatches + 13/13 throw cases byte-identical, at BOTH levels**
(`logs/gate_a_{O3,O2}.out`). Coverage: P1 — 6 seeds × N ∈ {1,2,3,5,8,17,100} ×
randomized I/J/m (K = 2..8), repeated and permuted indices, 18 operand
layouts; P1b — N ∈ {919, 2000}, all-y-min/all-y-max boundary responses; P2 —
the REAL gpcm shape (N=5500, I=11, J=500, m from the W-80 data) on three
layout combos including the model's (Map θ/α + AoS β); P3 — priors BEFORE the
likelihood (the model's statement order; AoS/Map combos — this math's lpdfs
don't take `var_value` vectors, W-130's precedent). Throw set: y low/high,
NaN/inf θ, NaN α, NaN β, jj/ii low/high, N=0, baseline.

**Layout disclosure**: β is compared on AoS/Map only — the generated model's
β is ALWAYS a local `Matrix<var>`, so no composed-stock SoA-β form exists
(`segment`/`subtract`/`append_row` on `var_value` don't compose to the
generated spelling); the primitive's SoA-β route is implemented and
compile/value-certified in the TU instead. θ/α are certified on all three.

## 3. Gate (b) — gpcm model, bit-identity: PASS

Bundle `bs_w126` = cp −al of `bs_w130` (primitive header at a PRIVATE inode,
`11893441`; bridgestan.o `e4b6077b` — the canonical rebuilt one; the W-129
command lines, direct gxx, no make). Pristine hpp from the bundle's stanc 2.39
(md5 `9151275b`); stock .so `32d5b3fe`; hand-edit
(`make_prim_edit.py`, blocks asserted verbatim) = the include + the REV-mode
loop → the primitive call + per-term `lp_accum__.add` loop ONLY (double-mode
instantiation and `write_array` untouched), hpp md5 `8bb3c3ef`, .so
`1a5e98d9`. Protocol (W-29 verbatim): w36exp CLI READ-ONLY, seed 20260819,
warmup 100, samples 50, `--metric-window 50`, the W-80 gpcm data
(N=5500) + W-80 pathfinder init `rep0/chain_0` — **data and inits FOUND, not
generated** (W-80 assets, read-only; disclosed).

| check | result |
|---|---|
| STOCK reference (recorded FIRST, before the prim arm existed) | draws md5 **`a342848b18bf6eebe360097c0681a633`**; 3,102+1,550 grad calls; 510 NaN-exception spam (the W-80-documented gpcm pattern — priors throw before the likelihood) |
| DOUBLE ANCHOR: the W-80 SHIPPED .so (cmdstan-2.39.0 stack, default flags) | **same md5, same 510 errors** — the family stack is output-equivalent to the shipped artifact for this model+protocol |
| PRIM arm | **md5-identical digit-for-digit**; same grad-call counts; same 510-exception pattern |
| 100-pt parity (`gate_parity_w126.py`, ctypes C ABI, W-103 points) | **lp 0/100, gradient-vector 0/100 (D=530), constrained output 0/100 (DC=545) EXACT-ZERO** |
| under callgrind (both arms) | both reproduce `a342848b…` |

Reference-trajectory disclosure: with w100/s50 the chain moves at ~1e-15
relative scale (stddev of the draws) around the init — ulp-gradient-sensitive
but a near-frozen trajectory; the 100-pt parity (healthy, randomized points)
carries the gradient-level proof, and the error-spam pattern (510 exceptions,
byte-identical) exercises the throw path end-to-end.

## 4. Gate (c) — callgrind: **−88.28%** (band −25..−45 EXCEEDED FAVORABLY; family-3 baseline ESTABLISHED)

W-29 protocol verbatim, one trace at a time (0 running at launch, checked),
system valgrind 3.25.1, draws md5 `a342848b…` reproduced under tracing on
BOTH arms (bit-identity certified under tracing).

| metric | stock | prim | delta |
|---|---|---|---|
| PROGRAM TOTALS Ir | 214,271,454,670 | **25,116,551,792** | **−88.28%** |
| Ir/grad (4,652 both) | 46.05 M | **5.40 M** | −88.3% |
| Ir/observation-eval (25.6 M both) | 8,366 | **981** | −88.3% |
| untraced wall (two CLI phases) | 14.56 s + 8.03 s | **1.52 s + 0.82 s** | 9.7× |

Attribution (self Ir):

| complex | stock | prim |
|---|---|---|
| pcm body (stock user fn) / primitive forward | 8.557e9 | 7.163e9 (6.416 impl + 0.747 entry) |
| softmax instantiation | 10.486e9 | 3.641e9 |
| cumulative_sum | 5.517e9 | **0 (symbol gone)** |
| subtract | 4.540e9 | **0 (gone)** |
| copy complex (see below) | 115.799e9 | **0.005e9** |
| malloc/free | 18.687e9 | 2.894e9 |
| arena stack_alloc | 7.039e9 | 0.605e9 |
| vari-stack pushes | 2.407e9 | 0.693e9 |
| primitive scatter callback | — | 2.611e9 |
| libm exp (the LSE interior) | 2.785e9 | 2.808e9 (retained) |
| libm log | 1.014e9 | **1.014e9 (identical to the digit)** |
| log_prob_impl self | 3.261e9 | 0.277e9 |

**The copy complex**: stock's 115.8e9 (54% of the run) shows under
string-class symbols (`max_size`/`min`/`_M_append`/`_S_copy`) because
`stan_cli` carries no debug info and the copy helpers resolve into its
address range — the caller tree shows the bulk reachable from the stock
`softmax<Matrix<var>>` instantiation (22.8 M calls; `_M_append` fired 91.1 M
times ≈ 3.5 per observation-eval). It is the per-observation expression
materialization of the stock graph — exactly what the primitive deletes.
**The overshoot mechanism, owned**: the registered band priced only the
likelihood-symbol complex (~35e9); with the per-observation expression graph
gone, the copy/alloc complexes (~141.5e9) collapse with it — the W-130-class
compounding (there: sweep/zeroing frames; here: materialization copies). The
remaining prim headroom for increment 2: per-observation heap churn (2.9e9
malloc/free + resize) — the per-obs `c`/`p` vectors can be hoisted.

## 5. Gate (d) — TU + controls: PASS

- TU `test/unit/math/rev/prob/pcm_lpdf_gathered_test.cpp` (branch worktree —
  i.e. the NEWER math with Eigen 5.0.1, where the softmax instantiation takes
  the packet path: a genuine cross-stack certification of the view-based
  interior): **5/5 PASSED** — `BitIdenticalToComposedStock` (6
  shape/seed/layout cases incl. SoA θ/α, N up to 519),
  `PriorsBeforeLikelihood` (2), `ValueMatchesReference`, `ThrowSet`,
  `SizeZero`.
- Controls (same build): `prim/prob/categorical` 6/6, `mix/fun/softmax` 1/1,
  `mix/fun/cumulative_sum` 1/1, `mix/fun/log_softmax` 1/1,
  `rev/fun/log_softmax` 2/2 — all PASSED.
- Sibling integrity re-verified: bs_w130's bernoulli gathered header,
  bridgestan.o `e4b6077b`, W-127's stock .so `2cf00ef9` — byte-intact;
  worktrees w112/w127/w130 untouched.

## 6. Deviations / disclosures (all owned)

- **Gate (c) band exceeded favorably** (−88.28% vs the registered −25..−45):
  the materialization-copy collapse, §4. The family-3 baseline is this
  increment's deliverable — stock 8,366 Ir/obs-eval → 981.
- **The stock interior is the model's own user function, not a math-library
  `pcm_lpmf`** (§0.1) — the primitive's contract is against the generated
  composed path, which is what the gates compare.
- **The softmax instantiation is stack-dependent** (§0.2); the primitive
  routes through the stock view instantiation, making it bit-identical on
  every stack — verified on the bundle (Eigen 3.4, scalar path) AND the
  branch (Eigen 5, packet path). A hand-spelled interior would have matched
  only one of them.
- **Data/inits are W-80 assets** (found, read-only), not generated — the
  pre-registration's "find/generate" satisfied on the "find" branch.
- **The stock reference trajectory is near-frozen** (moves at ~1e-15 relative
  scale; 510-exception spam — both W-80-documented behavior for this model at
  w100/s50/mw50). Disclosed with the parity carrying the strong gradient
  proof; the double-anchored md5 (two independent stock builds on different
  stacks) pins the reference itself.
- **β layouts**: AoS/Map compared; SoA-β has no stock counterpart (no
  generated model produces it) — implemented + value-certified, not
  bit-compared (§2).
- **Two harness bugs found before any recorded number** (gate (a)): operand
  vectors constructed outside the nested scopes (adjoint leakage across arms —
  the 2× pattern); an SoA constructor arity error. Two TU-side bugs (§5): the
  stock arm's accumulation spelling and the prim arm running the primitive
  BEFORE the prior — the latter reproduced the W-129 delivery-position
  mechanism (θ₀ 1 ulp) and confirms it LIVE in family 3; both were TEST
  fixes, no header change.
- **The early-probe `-I` mistake** that found §0.2 (whole branch repo
  shadowing the bundle math) — no wrong-arm number was recorded from it; the
  probes that mattered were rebuilt under the correct discipline.
- Machine: ≤2-core builds (nice 19, gxx_fixed, `env -u LD_LIBRARY_PATH`),
  one callgrind at a time (0 running at launch), OMP_NUM_THREADS=1 for all
  sampler cells.

## 7. Increment-2 verdict: GO

All four gates green; the open design questions are answered: the category
LSE interior is bit-replicable on every stack through the view-based softmax
call; the priors-before sweep order holds with the likelihood-site callback
(gpcm gathers at the likelihood statement — the hier_2pl/radon case, and the
TU's priors test proves it). Increment 2 (the stanc3 matcher for the pcm loop
form + the registry row) should target the stereotyped shape — `for (n)
target += pcm(y[n], theta[jj[n]] .* alpha[ii[n]], segment(beta, pos[ii[n]],
m[ii[n]]))` with the user-fn body the model carries — emitting the primitive
call plus the per-term accumulator pushes this experiment hand-tested.
Headroom beyond: per-observation heap churn (§4).

## 8. Artifacts

- Branch: `external/math_dev_w126`, `gathered-pcm` @ `42fa0ecbf4`
  (`6d4e94e49b` header + `42fa0ecbf4` TU). DCO + AI notes. Not pushed.
- `scratch/w126/`: `notes.md` (full session log incl. STEP ZERO forensics and
  pre-measurement expectations), `probe_*.cpp` (types, adjoint dump, softmax
  instantiation, both-stack view-vs-dense, segment path, 4-path isolation,
  400-trial hand chain), `test_prim.cpp` + `gpcm_data.inc` + gate-a binaries
  (both levels), `bs_w126/` (bundle copy, private-inode header),
  `model_gpcm_{stock,prim}/` (hpp/.o/.so), `make_prim_edit.py`,
  `runs/` (stock/prim/w80so draws + md5s), `gate_parity_w126.py` +
  `parity_ref.npz`, `run_callgrind_w126.sh` + `profile_{stock,prim}/`,
  `logs/` (builds, runs, TU/controls, callgrind).
- References reused read-only: `scratch/w80` (gpcm data.json, pf inits, the
  shipped .so), `scratch/w130/bs_w130` (bundle lineage, bridgestan.o),
  `scratch/w46/gxx_fixed`, the walnutpie `build_w36exp` CLI.
