# W-112 — `normal_lpdf_gathered` (loop-form radon class): ALL GATES PASS, bit-identical, −65.5%/−66.4% Ir/grad inside both pre-registered bands

Executed 2026-08-29 per WORKLOG "W-112 PRE-REGISTRATION" (gathered-GLM
campaign FAMILY 1, increment 1: primitive + hand-edited model gates, no
codegen). Deliverable: branch **`gathered-normal` @ bc00891778** (parent
`fork/develop` 344d7167a0) in dedicated worktree `external/math_dev_w112` —
one new header `stan/math/rev/prob/normal_lpdf_gathered.hpp` (two public
overloads + shared impl) + one new unit-test TU. Nothing else in math is
touched. Artifacts in `scratch/w112/`.

**Headline: the math-side primitive for the LOOP-form normal likelihood is a
bit-identical drop-in (values, every gradient component, and full same-seed
draws md5s `4a9ca34923b6d2c314e636d6b335338d` /
`bbafc6523f1bfd40804c6bbafc4c4dec` digit-for-digit on the W-109 all-layers
stack) that deletes the per-element scalar-lpdf complex: Ir/grad
4,305,737 → 1,483,625 (−65.54%) on radon_pp and 470,351 → 157,960 (−66.40%)
on radon_var — both inside the pre-registered bands (−60..−85% /
−55..−80%). Increment 2 (stanc3 loop matcher + emission) is a GO.**

## 1. The primitive (design from the generated loop)

The generated likelihood (radon_pp hpp, rev instantiation) is the loop

```cpp
for (int n = 1; n <= N; ++n) {
  stan::model::assign(mu, stan::model::rvalue(alpha, "alpha",
      stan::model::index_uni(county_idx[n])), "assigning variable mu",
      stan::model::index_uni(n));
  lp_accum__.add(stan::math::normal_lpdf<false>(rvalue(log_radon, ..., n),
                                                rvalue(mu, ..., n), sigma_y));
}
```

(radon_var's `mu[n] = alpha[c[n]] + floor[n] * beta[c[n]]` adds one multiply
and one add vari per element.) The primitive takes the operands directly:

```cpp
std::vector<var> normal_lpdf_gathered<false>(y, alpha, ii, sigma);              // A
std::vector<var> normal_lpdf_gathered<false>(y, alpha, ii, x, beta, ii2, sigma); // B
```

- **Value path** — per element the SCALAR `normal_lpdf<propto>(double, var,
  var)` op order verbatim: `(y - mu) * inv(sigma)` with `inv(sigma) = 1/sigma`
  computed once and the double reused (deterministic value), the square,
  `-0.5 *` of the scalar sum, then stock's constant-term statement order
  (`+= NEG_LOG_SQRT_TWO_PI`, `-= log(sigma)` — each guarded by the same
  `include_summand` constexprs, so `propto` semantics match exactly, including
  the data-sigma case where `target +=` still carries `-log(sigma)`). The
  gathered `mu` values are computed with the loop's op order (shape B:
  multiply first, then add — through a `volatile` intermediate, see §6).
- **Returns one `var` per observation, not one var** (the W-108 single-var
  return is IMPOSSIBLE here — §2). The hand-edited model pushes each term
  into `lp_accum__` in n order, so the model's accumulation schedule is
  stock's exact schedule; each term wraps the ordinary no-chain
  `vari_value<double>` (plain `var(double)`: value + adjoint storage only,
  never chained).
- **Reverse** — ONE `reverse_pass_callback` performing the loop's adjoint
  accumulation in the order `grad()` visits the loop's nodes (reverse-n):
  `m = adj(term_k) * (inv_sigma * y_scaled_k)`, `alpha[ii[k]] += m`,
  `beta[ii2[k]] += m * x[k]` (shape B — the two-step multiply propagation),
  `sigma += adj(term_k) * (inv_sigma * y_scaled_sq_k - inv_sigma)`. Operand
  routes as W-108: `Matrix<var>` (AoS, the models' tp-loop alpha/beta) keeps
  one `vari*` per coefficient; `var_value<VectorXd>` (SoA) keeps the single
  matrix vari; sigma as var or double.
- **Checks**: size matches and per-element index bounds (the `check_range`
  stock's rvalue performs) kept; `check_positive` once on sigma. The scalar
  call's per-element `check_not_nan(y)` / `check_finite(mu)` are dropped
  (disclosed, §6) — they only fire on invalid inputs, never on valid ones.

## 2. The accumulator discovery (why the primitive returns per-element terms)

`accumulator<var>` is NOT the primary template in prim/fun/accumulator.hpp:
`stan/math/rev/fun/accumulator.hpp` defines a partial specialization for
`require_var_t<T>` with a **128-element chunk-collapse buffer** —
`check_size()` collapses `buf_` to one element via `sum(buf_)` every 128
pushes, and `add(std::vector<var>)` pushes ONE grouped `sum(xs)` entry, not
per-element pushes (all probe-verified in `scratch/w112/probe_accum*.cpp`:
`sum(std::vector<var>)` itself equals the plain sequential double sum
bit-exactly — the `val()` expression is a non-packetizable CwiseUnaryView —
but the buffer's chunk tree depends on the push schedule). Consequently a
W-108-style single-var return (or one grouped push) changes the model's lp
VALUE by the changed addition tree: 1-ulp probe differences within minutes.
The primitive therefore returns the N per-element terms and the model edit
pushes them one by one — identical buffer, identical chunk schedule,
identical tree, bit-identical lp (and the chunk weights carry each term's
adjoint to the primitive's master callback through the same no-chain varis).
This is the one structural deviation from the W-108 recipe; the per-element
push + no-chain vari replaces stock's per-element ops-partials vari + stack
push (cheaper: no edge construction, no chain call).

## 3. Gate (a) — unit, bitwise: PASS

`scratch/w112/test_prim.cpp` vs the composed stock loop using the REAL
`stan::model::rvalue`/`index_uni`/`assign` machinery (bundle `stan/src`) and
the REAL `accumulator<var>` on BOTH sides, compiled on the all-layers math
with the branch header first on the include path (`build_gate_a.sh`),
`-mavx2 -mfma -O3` (model flags). Coverage: the real grids (radon_pp
N=12573/J=386, radon_var N=919/J=85 incl. the real county_idx and floor x),
N ∈ {1..8, ..13000}, J up to 400, sigma ∈ {0.5, 1, 1e-3, 1e3} as var and
double, x vectors with zeros/negatives, repeated indices (2000 obs on one
county), permuted indices, both operand layouts (AoS / SoA), same-index and
two-index shape B, and a propto=true spot check.

**22,360 bitwise checks (lp value, every alpha/beta/sigma gradient
component, memcmp), 0 mismatches** — plus the 12,573 per-element term
values on the real radon_pp grid bitwise-identical.
`==== GATE (a): 22360 bitwise checks, 0 mismatches => PASS ====`.

The gate earned its keep during development: it caught two real op-order
defects (§6 FMA disclosure) at exactly the 1-ulp class they cause.

## 4. Gate (b) — hand-edited models, bit-identity: PASS

Hand-edited copies of the stanc-generated hpps (bundle stanc, same as the
W-109 .so arms): the diff is (i) the primitive include after
`model_header.hpp`, (ii) the rev-mode likelihood loop replaced by the
primitive call + per-term `lp_accum__.add` loop, (iii) the now-unused `mu`
local declaration removed (its N `var(NaN)` varis were pure loop machinery).
The double-mode instantiation and `write_array` keep the stock loop.
`scratch/w112/edit_models_w112.py` asserts the replaced blocks verbatim;
models live in `scratch/w112/model_radon_{pp,var}_prim/`; built on a
`cp -al` copy of the W-106 all-layers bundle (`bs_w112`, primitive header at
a private inode, `src/bridgestan.o` rm'd and rebuilt in-copy — the W-109
artifacts untouched), `CXX=scratch/w46/gxx_fixed TBB_CXX_TYPE=gcc
CXXFLAGS="-mavx2 -mfma"`, `/usr/bin/make -j2`, nice 19,
`env -u LD_LIBRARY_PATH`.

| check | radon_pp | radon_var |
|---|---|---|
| stock reference draws md5 (W-29 protocol, w36exp CLI read-only, seed 20260819, pf init rep0/chain_0, warmup 100, samples 50, `--metric-window 50`) — recorded FIRST | `4a9ca34923b6d2c314e636d6b335338d` | `bbafc6523f1bfd40804c6bbafc4c4dec` |
| native stock run reproduces the W-111 callgrind-era draws csv | yes (md5 equal) | yes (md5 equal) |
| primitive-arm draws md5 | `4a9ca34923b6d2c314e636d6b335338d` **digit-for-digit** | `bbafc6523f1bfd40804c6bbafc4c4dec` **digit-for-digit** |
| parity 100 pts (`gate_parity_w112.py`, bridgestan C ABI via ctypes, W-103 point scheme) | lp 0/100, grad-vector 0/100 (D=389) **exact-zero** | lp 0/100, grad-vector 0/100 (D=175) **exact-zero** |

## 5. Gate (c) — callgrind: PASS, both bands hit

W-29 protocol verbatim (valgrind 3.23 `~/vginstall`, one job at a time,
nice 19; no sibling callgrind running — checked 0 before start). All four
arms traced the identical trajectories (draws md5s above reproduce under
callgrind in every arm; gradient calls identical: 6,113 / 3,669).

| model | arm | total Ir T | G (incl. `bs_log_density_gradient`) | grad calls | Ir/grad |
|---|---|---|---|---|---|
| radon_pp | stock (W-109 all-layers .so) | 28,271,857,394 | 26,318,425,661 (93.1% of T) | 6,113 | 4,305,737 |
| radon_pp | **primitive** | **11,022,871,343** (−61.0%) | **9,069,536,624** (−65.54%) | 6,113 | **1,483,625** |
| radon_var | stock | 2,445,920,682 | 1,725,754,026 (70.6% of T) | 3,669 | 470,351 |
| radon_var | **primitive** | **1,299,597,691** (−46.9%) | **579,780,181** (−66.40%) | 3,669 | **157,960** |

Pre-registered bands: radon_pp **−60..−85% G** → −65.54% **in band**;
radon_var **−55..−80% G** → −66.40% **in band**. No overrun/underrun.

### Attribution (exclusive Ir self-costs)

radon_pp:

| complex | stock | primitive |
|---|---|---|
| scalar `normal_lpdf<false, double, var, var>` body | 11,221,542,405 | **0** |
| `log_prob_impl` loop machinery (rvalue/assign/index_uni, loop, priors) | 4,387,098,371 | 1,082,190,503 |
| glibc `log(sigma)` — per element in stock | 3,489,466,612 | 1,641,796 (once per call) |
| chainstack `emplace_back` (vari pushes) | 2,773,738,479 | 698,606,688 |
| ops-partials chain callbacks | 1,169,624,742 | 16,743,507 (priors only) |
| lp accumulation `sum(vector<var>)` + its callback — **identical both arms** (the preserved stock tree) | 1,001,297,174 + 470,468,706 | 1,001,370,530 + 470,468,706 |
| primitive forward (terms, partials, index arena) | — | 4,957,282,333 |
| primitive scatter callback | — | 999,243,206 |

radon_var:

| complex | stock | primitive |
|---|---|---|
| scalar lpdf body | 492,317,427 | **0** |
| `log_prob_impl` machinery | 510,467,970 | 49,087,551 |
| glibc `log` | 155,685,920 | 870,728 |
| chainstack emplace | 178,611,671 | 31,964,955 |
| ops-partials callbacks + eltwise add/multiply chain varis | 55,343,196 (+30.3e6 add callbacks) | 4,766,031 |
| accumulator sum+callback (identical) | 44,504,970 + 20,825,244 | 44,504,970 + 20,825,244 |
| primitive forward | — | 280,348,290 |
| primitive scatter | — | 60,769,647 |

Reading: on radon_pp the whole loop complex (~23.3e9 of per-element work)
becomes the primitive's 5.96e9 forward+scatter — ~77 Ir/element vs stock's
~276. The accumulator complex is deliberately untouched (it IS the stock lp
tree). The residual `log_prob_impl` self and emplace costs are the retained
push loop, priors, and one no-chain vari per element.

## 6. Disclosures

- **The return type is `std::vector<var>` (per-element terms), and the model
  edit contains a per-element `lp_accum__.add` loop** — forced by the rev
  `accumulator<var>` partial specialization (§2). This deviates from the
  W-108 single-`var` shape and from the pre-registration's phrasing ("lp
  accumulated with a plain sequential n-order loop") in mechanism but not in
  effect: the accumulation IS stock's exact schedule, gate-proven at three
  levels. The stanc3 increment-2 emission must emit the push loop (or an
  equivalent per-element add) — noted for the matcher design.
- **Two FMA-contraction fixes were required** (both found by gate (a), both
  verified by disassembly of `internal::multiply_vd_vari::chain()` which
  compiles to `vfmadd132sd`): (i) the shape-B forward `alpha + x * beta`
  needs a `volatile` barrier — stock's value round-trips through two vari
  members so stock is un-contracted; (ii) the beta scatter must stay
  CONTRACTIBLE on the AoS route (stock's multiply chain is a fused pointer
  RMW) but UN-contracted on the SoA route (stock's `var_value::coeff` adds
  through a read-vari callback with a plain add). These barriers are
  documented in the header.
- **Per-element `check_not_nan(y)` / `check_finite(mu)` are dropped** (the
  scalar stock call pays them per element). Behavior differs only for
  invalid inputs (NaN data / non-finite mu), which the gates never exercise;
  documented in the header. Sigma positivity and index ranges are still
  checked (cheap, and stock pays them too).
- **The `mu` local declaration is removed in the edited rev instantiation**
  (unused once the loop is gone; stock constructs N `var(NaN)` varis for
  it). The double-mode instantiation keeps the stock loop and its `mu`.
- **First callgrind attempt aborted** (rc=134, all four arms identically at
  ~113M Ir): my run script passed the init-file DIRECTORY instead of
  `rep0/chain_0.txt` ("--init-file dimension mismatch: file has 0, model
  has 389"). Fixed and rerun cleanly; the aborted outputs were deleted.
- Parity harness is raw ctypes against the bridgestan C ABI (the python
  `bridgestan` package has a broken dependency `dllist` on this box);
  one .so per process, same as W-108.
- Machine: callgrind serialized (checked against W-113; count 0 before
  start), nice 19, `env -u LD_LIBRARY_PATH`, `/usr/bin/make`, gxx wrapper,
  ≤2 compile jobs. The W-106/W-109 artifacts were only read (`cp -al` copies
  with private inodes for everything rebuilt).
- No wall-time gates (pre-registered none).

## 7. Gate (d) — untouched-control ctest + new TU: PASS

On the branch worktree (`runTests.py -j2`):
- `test/unit/math/rev/prob/normal_lpdf_gathered_test.cpp` (new): **4/4
  PASSED** — `BitIdenticalToComposedStock` (8 randomized shapes × 2 layouts,
  memcmp), `BitIdenticalToComposedStockSlope` (8 randomized shape-B cases ×
  2 layouts, sigma var/dbl), `ScalarValueMatchesReference`,
  `SizeZero`.
- Control (the normal distribution's existing TUs — there is no
  `normal_lpdf_test.cpp`; the lpdf coverage lives in `normal_test.cpp`):
  `prim/prob/normal_test.cpp` **4/4**, `rev/prob/normal_log_test.cpp`
  **1/1**, `mix/prob/normal_test.cpp` (`mathMixScalFun_normal_lpdf`)
  **1/1** — all PASSED, nothing else in math touched.

## 8. Increment-2 verdict: GO

All pre-registered gates green; the open design question ("can the loop form
be bit-identical in a math-side primitive?") is answered **yes**, including
the subtleties the answer surfaced (chunked accumulator schedule; FMA
contraction schedules of the eltwise chain nodes; SoA read-vari hop).
Increment 2 (stanc3 pattern detection + emission) should target the MIR
shape of the stereotyped likelihood loop — `for n: mu[n] = <gather tree over
n>; target += normal_lpdf(y[n] | mu[n], sigma)` with `mu` loop-local,
element-wise, and sigma scalar — matching both the `alpha[ii[n]]` and
`alpha[ii[n]] + x[n] * beta[ii[n]]` eta shapes (same or distinct index
arrays), emitting the primitive call plus the per-term accumulator pushes
this experiment hand-tested. The runtime completeness check W-48 §6 applies
(sigma/eta shape guard), and the W-111 census bounds the family's remaining
unexploited targets (ICAR next, W-113).

## 9. Artifacts

- Branch: `external/math_dev_w112`, `gathered-normal` @ `bc00891778` (files:
  `stan/math/rev/prob/normal_lpdf_gathered.hpp`,
  `test/unit/math/rev/prob/normal_lpdf_gathered_test.cpp`). Not pushed.
- `scratch/w112/`: `probe_accum*.cpp` (the accumulator forensics),
  `test_prim.cpp` + `radon_{pp,var}_data.inc` + `build_gate_a.sh` (gate a),
  `bs_w112/` (bundle copy + primitive header), `model_radon_{pp,var}_prim/`
  (hand-edited hpp + .o + .so), `edit_models_w112.py`, `draws/` (stock +
  prim csv + md5s), `logs/` (build + CLI logs), `gate_parity_w112.py`,
  `run_callgrind_w112.sh`, `profile_radon_{pp,var}_{stock,prim}/`
  (callgrind.out, ann.txt, incl_ann.txt, cli.log, draws.csv).
- References reused read-only: `scratch/w109/model_radon_*_alllayers/*.so`,
  `scratch/w106/bs_alllayers`, `external/walnutpie/build_w36exp/.../stan_cli`.
