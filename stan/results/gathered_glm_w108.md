# W-108 — the gathered-GLM primitive (`bernoulli_logit_lpmf_gathered`): ALL GATES PASS, bit-identical, −40.9% Ir/grad on the composed stack

Executed 2026-08-28 per WORKLOG "W-108 PRE-REGISTRATION" (increment 1:
primitive + hand-rewritten model gate, no codegen). Deliverable: branch
**`gathered-glm` @ ea96b3c9fa** (parent `fork/develop` 344d7167a0) in worktree
`external/math_dev_w108` — one new header
`stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp` (246 lines) + one new
unit-test TU. Nothing else in math is touched, so the branch is independently
reviewable. Artifacts in `scratch/w108/`.

**Headline: the math-side primitive for hier_2pl's exact likelihood line is a
bit-identical drop-in (values, every gradient component, and full same-seed
draws md5 `fe7c57c99a7a6530ce2dcc408d6e9c65` digit-for-digit on the stock
stack) that removes the entire gathered eltwise complex: Ir/grad 4,795,704 →
2,831,876 = −40.95% vs the W-103 kernel-arm reference with the likelihood
interior held constant (`w46::fwd_avx2` Ir identical to the digit). The
pre-registered bit-identity uncertainty is resolved affirmatively: no
statistical-class re-gate is needed. Increment 2 (stanc3 pattern detection +
emission) is a GO.**

## 1. The primitive (design from the generated code)

The generated likelihood line (models/hier_2pl.hpp:399, rev instantiation) is

```cpp
bernoulli_logit_lpmf<propto__>(y,
  elt_multiply(rvalue(alpha, "alpha", index_multi(ii)),
               subtract(rvalue(theta, "theta", index_multi(jj)),
                        rvalue(beta,  "beta",  index_multi(ii))))
```

with `theta` a `var_value<VectorXd>` (the deserializer's SoA read) and
`alpha`/`beta` `Matrix<var>` (per-element transformed-parameters loop). The
primitive takes the index vectors instead of the gathered matrices:

```cpp
bernoulli_logit_lpmf_gathered<propto>(y, theta, jj, alpha, beta, ii)
```

- **Value path** — exactly the stock composed op order, per element: one
  subtraction `theta[jj[k]] - beta[ii[k]]`, then one multiplication by
  `alpha[ii[k]]` (stock evaluates subtract first, elt_multiply second; both
  materialize through memory, so no contraction is possible — and the model
  builds at `-O3` on baseline x86-64, where FMA is not in the ISA). The lpmf
  interior is then the *stock* code copied verbatim over the same Eigen
  expression types (`signs = to_ref(2 * as_array_or_scalar(n_double) - 1)`,
  `ntheta = signs * eta`, `exp(-ntheta)`, the two nested `Select` trees, and
  `sum(...)` over the same expression — Eigen redux order included).
- **No gathered `Matrix<var>`**: the operands are never copied into arena
  matrices; the forward pass keeps `sub_val`/`a_val` (2N doubles), `ii`/`jj`
  (2N ints), and one `vari*` per coefficient element (`J + 2I` pointers) for
  `Matrix<var>` operands, or just the single matrix `vi_` for `var_value<>`
  (SoA) operands. Both layouts are supported (the model uses SoA theta, AoS
  alpha/beta).
- **Reverse** — ONE `make_callback_var` (the returned logp's own chain) doing
  the same scatter-adds stock performs through the aliased records / the SoA
  gather callback (`stan/src/stan/model/indexing/rvalue_varmat.hpp:72`), in
  the same k order:
  `alpha[ii[k]] += (t−b)·(w·d[k])`, `theta[jj[k]] += a·(w·d[k])`,
  `beta[ii[k]] −= a·(w·d[k])`, with `w = vi.adj_` and `d` = the lpmf partials
  (bug-compatible branch behavior at `|ntheta| > 20` preserved, since the
  interior is the stock expression).
- Checks mirror stock (`check_bounded` on y costs the same 679.6M Ir in every
  arm, incl. stock's own).

**Kernel-interior variant** (measurement only, `scratch/w108/
bernoulli_logit_lpmf_gathered_w46.hpp`, generated mechanically by
`scratch/w108/make_kernel_variant.py` which asserts the interior block is
swapped verbatim): identical except the interior is delegated to
`internal::w46::bernoulli_logit_fwd` — the exact call the W-103 kernel-arm
`bernoulli_logit_lpmf` makes in the same tree. This is what is dropped into
`scratch/w108/bs_prim` (a `cp -al` copy of the W-103 kernel bundle
`scratch/w103/bs_w103_kernel`, primitive header at a private inode) so gate
(c) measures the plumbing change with the interior held constant.

## 2. Gate (a) — unit, bitwise: PASS

`scratch/w108/test_prim.cpp` vs the composed stock expression **using the real
`stan::model::rvalue` + `index_multi`** (model-exact), on randomized shapes
and values: the real hier_2pl grid (I=32, J=600, N=19,200), N up to 49,999,
I/J up to 100/97, tiny shapes (N=1..8), single-cell repeats, all-y=0/all-y=1
(signs edge), and a big-scale sweep that drives `|ntheta|` past the ±20
branch cuts. Three operand layouts per case: all-`Matrix<var>`, the model's
layout (theta `var_value`, alpha/beta `Matrix<var>`), all-SoA.

**9,000 bitwise checks (memcmp on the lp value and every gradient component),
0 mismatches — on BOTH bundles** (stock interior `bs_prim_stock` and kernel
interior `bs_prim`): `==== GATE (a): 9000 bitwise checks, 0 mismatches => PASS ====`.
A development bug was caught by this gate (leftover unconditional vi-fill
loops that wrote a size-0 arena map OOB and pushed `vari_view` records on the
stack for SoA operands — segfault, found by instrumented tracing); the shipped
header is clean and every number below is from the final header.

## 3. Gate (b) — hand-rewritten model, bit-identity: PASS

Hand-edited copy of the generated `hier_2pl.hpp`
(`scratch/w108/model_hier2pl_prim*/hier_2pl.hpp`): exactly **two** line groups
differ — the `#include <stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp>`
after `model_header.hpp`, and the likelihood statement of the **rev-mode
instantiation only** (the double-mode instantiation keeps the stock
expression, so plain log_density paths are untouched). Built on the
bs-copy wiring (`rm src/bridgestan.o && make src/bridgestan.o` on `bs_prim`,
private inode; `bs_prim_stock` keeps the W-103-era prebuilt bridge exactly),
`CXX=scratch/w46/gxx_fixed TBB_CXX_TYPE=gcc`, `/usr/bin/make -j2`, nice 19,
`env -u LD_LIBRARY_PATH`.

| check | result |
|---|---|
| parity 100 pts (`gate_parity_w108.py`, W-103 point scheme), stock pair (prim on `bs_prim_stock` vs W-103 stock-form .so) | **exact-zero**: lp mismatches 0/100, grad-vector mismatches 0/100 (every component bitwise) |
| parity 100 pts, kernel pair (prim variant on `bs_prim` vs W-103 kernel-form .so) | **exact-zero**: 0/100, 0/100 |
| full sampler draws, W-29 protocol (walnutpie `build_w36exp/examples/stan_cli` READ-ONLY, seed 20260819, pf init rep0/chain_0, warmup 100, samples 50, `--metric-window 50`), prim on stock stack | md5 `fe7c57c99a7a6530ce2dcc408d6e9c65` = the recorded stock reference **digit-for-digit** (verified both plain and under valgrind) |
| same protocol, prim variant on the kernel stack | md5 `1744c2087c7049203b0e78bc6f4b5107` = the W-103 kernel-arm draws **digit-for-digit** (bit-identical trajectory on the composed current-best stack) |

The pre-registered md5 gate (`fe7c57…`) is against the STOCK model .so / stock
math stack; on the kernel bundle the reference is necessarily the kernel arm's
own md5 (the W-103 kernel's 1-ulp log1p change moves it), and the primitive
arm reproduces THAT exactly — bit-identity holds on both stacks.

## 4. Gate (c) — callgrind, the honest current-stack delta: PASS at −40.9%

W-29 protocol verbatim (valgrind 3.23 `~/vginstall`, one job at a time).
All arms traced the **identical 4,493 gradient calls** (draws md5s above prove
identical trajectories).

| arm | total Ir T | Ir / grad | delta |
|---|---|---|---|
| W-103 kernel-form reference (`scratch/w103/profile/kernel`) | 21,547,099,162 | 4,795,704 | — |
| **W-108 primitive, kernel interior** (`scratch/w108/profile/prim_k_final`) | **12,723,618,586** | **2,831,876** | **−40.93% T / −40.95% Ir/grad** |
| W-103 stock-form reference (`scratch/w103/profile/stock`) | 29,491,052,342 | 6,563,777 | — |
| W-108 primitive, stock interior (bonus arm, `scratch/w108/profile/prim`) | 22,519,964,565 | 5,012,233 | −23.63% |

Pre-registered gate was **≤ −15%** (expectation band −15..−25%): **PASS with
the band overrun disclosed**, same disclosure class as W-103's own −26.9% vs a
−15..−22% band. The primitive deletes per-element *work*, not just op
boundaries, so it lands beyond the band.

### Attribution (kernel pair, exclusive Ir self-costs)

| complex | W-103 kernel arm | W-108 prim arm |
|---|---|---|
| elt_multiply forwards (2 instantiations) | 3,738,182,675 | **0** |
| subtract forward | 2,888,712,739 | **0** |
| `rvalue`/IndexedView gathers (2) | 2,803,802,904 | **0** (10,064,320 residual = the tp block's non-likelihood indexed views) |
| subtract reverse callback | 1,104,287,912 | **0** |
| `update_adjoints` (lpmf edge application) | 714,051,296 | 8,494,080 |
| `ops_partials_edge` ctor (`to_arena` of the elt_multiply result) | 583,701,552 | **0** |
| composed `bernoulli_logit_lpmf` rev self | 2,039,795,800 | **0** |
| primitive forward | — | 3,897,004,272 |
| primitive scatter callback (chain) | — | 1,783,862,976 |
| `w46::fwd_avx2` (interior) | 2,994,415,368 | 2,994,415,368 **(identical to the digit)** |
| `check_bounded` (y) | 679,619,304 | 679,619,304 (same check, same cost) |

Reading: the whole eltwise+gather complex (**13.87e9 Ir**, 64% of the kernel
arm's G-class work) is replaced by the primitive's 5.68e9 forward+scatter —
the net −8.8e9 is the measured T delta, i.e. the −28.2% W-34 ceiling lane is
reached *and exceeded* because the primitive also folds the lpmf's operand
materialization (edge ctor + edge application + the `to_ref` of the
elt_multiply values) into its single pass. On the stock-interior pair the
interior symbols are identical in both arms too (`__log1p` 4,596,520,171 and
the Eigen Select/sum redux 2,204,589,439, to the digit), which is the
symbol-level proof of value bit-identity.

Cumulative vs the W-34-era stock baseline (pristine math, 7,745,272 Ir/grad):
the composed current stack (SoA + W-103 kernel + W-108 primitive) runs
hier_2pl at 2,831,876 Ir/grad = **−63.4%**.

## 5. ctest / hygiene: PASS

- `test/unit/math/rev/prob/bernoulli_logit_lpmf_gathered_test.cpp` (new, on
  the branch): **3/3 PASSED** — `BitIdenticalToComposedStock` (8 randomized
  shapes × 2 operand layouts, memcmp), `ScalarValueMatchesReference`
  (hand-computed 2-point value + all four gradient components),
  `SizeZeroAndPropto`.
- Control (different header, must be unaffected):
  `test/unit/math/rev/prob/bernoulli_logit_glm_lpmf_test.cpp` **22/22 PASSED**
  on the branch.
- `external/math_soa` (the develop slice): status is exactly the 14-file
  W-53/W-59 SoA slice, lpmf pristine (md5 `2954671f…`), **no W-108 edits**;
  `external/math_dev_soa` is back on W-107's `log1p-kernel-avx2` with no
  W-108 files left in it.

## 6. Disclosures

- **Worktree collision**: `external/math_dev_soa` (the pre-registered
  worktree) was checked out back to `log1p-kernel-avx2` and advanced by the
  W-107 agent mid-session. The primitive was moved to a dedicated worktree
  `external/math_dev_w108` created from the same repo, branch `gathered-glm`
  off `fork/develop` 344d7167a0 exactly as pre-registered (commit
  `ea96b3c9fa`, adds only the two new files). No builds were run in
  `math_dev_soa` after the collision was noticed.
- **Two interior variants by construction** (this is what makes bit-identity
  provable on BOTH stacks): the branch header carries the stock select-tree
  interior (bit-identical to any stock-math tree — the upstream story); the
  measurement bundle `bs_prim` carries the mechanically generated w46-interior
  variant so gate (c)'s comparison holds the interior constant. Both variants
  passed gate (a) 9,000/9,000 bitwise on their own bundles; the variant's only
  diff is the interior block (`make_kernel_variant.py` asserts it verbatim).
- The model-gate hpp diff is 2 line groups (include + rev-mode likelihood
  statement); the double-mode instantiation keeps the stock expression.
- `bs_w53`, `bs_w103_kernel` and the W-103 profiles/draws were only read;
  `bs_prim`'s rebuilt `bridgestan.o` is a private inode (the W-103 artifact's
  link is intact; the kernel-arm draws md5 reproduces through it, so the
  rebuild is not a confound).
- No wall-time gate was pre-registered for increment 1; none is reported.

## 7. Increment-2 verdict: GO

All pre-registered gates green, and the open design question ("value
bit-identity impossible because X?") is answered **no** — the composed stock
path's value ops and adjoint scatter order are exactly reproducible in a
math-side primitive, including the SoA/AoS operand mix the compiler actually
emits. Increment 2 (stanc3 pattern detection + emission) should target the
MIR shape `bernoulli_logit_lpmf(y, elt_multiply(gather(a, ii), subtract(
gather(t, jj), gather(b, ii))))` with data-typed index vectors, emitting the
call this experiment hand-tested, with the runtime completeness check W-48 §6
already sketched (grid models get the GEMM rewrite instead, W-34 arm B).

## 8. Artifacts

- Branch: `external/math_dev_w108`, `gathered-glm` @ `ea96b3c9fa` (files:
  `stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp`,
  `test/unit/math/rev/prob/bernoulli_logit_lpmf_gathered_test.cpp`). Not
  pushed (no upstream PRs).
- `scratch/w108/`: `bs_prim/` (kernel bundle + variant header),
  `bs_prim_stock/` (stock bundle + branch header), `test_prim.cpp` +
  `hier2pl_data.inc` + `test_prim_{stock,kernel,final,final_k}` binaries,
  `make_kernel_variant.py` + `bernoulli_logit_lpmf_gathered_w46.hpp`,
  `gate_parity_w108.py`, `model_hier2pl_prim{,_k}/` (hand-edited hpp + .so),
  `draws/` (final draws + logs), `profile/{prim,prim_k,prim_k_final}/`
  (callgrind.out, ann.txt, incl_ann.txt, cli.log, draws.csv).
- References reused read-only: `scratch/w103/{profile,model_hier_2pl_stock,
  model_hier_2pl_kernel}`, `external/walnutpie/build_w36exp/examples/stan_cli`.
