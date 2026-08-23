# W-47 — SoA-arena / typed-pool / flat-callback tape refactor: tax decomposition, microbench ceilings, and a span-chainstack prototype

Date: 2026-08-23. Pre-registration: WORKLOG.md W-47. Research item X1.
Inputs: W-29 atlas (tape/arena fixed tax: 12.6%G hier_2pl, 16.9%G accel_gp,
8.2%G kronecker, 4.9%G gp_regr), W-34 plumbing ceiling, upstream scan
2026-08 (NO SoA-arena work exists in stan-dev/math; stanc3 #1666
`vectorize_loops` is the adjacent upstream effort). The bridgestan
stan-math tree (5.3.0) is byte-identical to develop's arena machinery
(verified by diff against `external/math_dev` @46a3133: one unrelated
stack_alloc pad bugfix) — findings apply to develop.

**Headline.** (1) The tape tax decomposes into three measurable pieces:
arena bump-alloc calls (~13.0 Ir each), chainstack `emplace_back`
(~9.0–9.2 Ir each), and vari-ctor stores inlined into op bodies; at
hier_2pl that is 6.41%T + 4.47%T + ~4–6%T of the eltwise op exclusives.
(2) In stan-math 5.3.0 the tape is NOT per-element callbacks: eltwise ops
build one vari per element on the NOCHAIN stack (empty `chain()`) plus ONE
`reverse_pass_callback` per op — so virtual dispatch and the `grad()`
loop are ~0.3%T total, and a flat/index-based callback array saves a
measured ZERO. The SoA/typed-pool ceiling is −32% of the per-record tape
complex (microbench, bitwise-correct), ≈ −10…−16%G at model level;
realizing it means changing `var`'s pointer representation → rewrite →
stopped at the ceiling per pre-registration, design doc below. (3) The
one genuinely small, upstream-shippable increment — span-based nochain
registration (no per-vari chainstack push) — was implemented as a
shadow-header patch and validated to BITWISE-IDENTICAL SAMPLER OUTPUT
(draws md5 equal), but GCC 16.2 -O3 -fPIC generates the per-record
registration ~11 Ir/record WORSE than the out-of-line emplace inside real
model TUs (model Ir +1.0%T) while winning −25.7% wall on the isolated
eltwise complex: not shippable as per-record checks; the doc specifies
the op-level batch-registration API that would make it real.

## 1. Anatomy first: what the 5.3.0 tape actually is (source read)

Files: `stan/math/rev/core/{vari.hpp, autodiffstackstorage.hpp,
chainablestack.hpp, reverse_pass_callback.hpp, grad.hpp, recover_memory.hpp}`,
`stan/math/memory/stack_alloc.hpp`, `stan/math/rev/fun/elt_multiply.hpp`
(all in `~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math`).

- `var` is a POINTER (`vi_`); `var(double)` → `new vari_value<double>(x,false)`
  → arena `alloc(24B)` + `var_NOCHAIN_stack_.push_back` (the single-arg
  `vari_value(x)` variant pushes `var_stack_`; the `var(double)` ctor uses
  `stacked=false`).
- An eltwise op over `Matrix<var>` (e.g. hier_2pl's `subtract`,
  `elt_multiply`): materializes two arena copies of its inputs (arrays of
  8B var pointers), constructs its output as `Matrix<var>` — one
  `var(double)` per element (arena alloc + nochain push + vptr/val/adj
  stores) — and registers ONE `reverse_pass_callback` vari (arena alloc +
  `var_stack_` push) whose lambda loops the whole matrix in `grad()`.
- `grad()` iterates ONLY `var_stack_` (virtual `chain()` per entry —
  O(#ops), not O(N)); the nochain stack exists solely so
  `set_zero_all_adjoints{,_nested}` can find those records.
  `recover_memory()` clears both vectors (capacity kept), `recover_all()`
  the arena, and deletes `chainable_alloc` objects.
- Consequence for the refactor question: the "virtual callback dispatch"
  and "linked-list cache effects" concerns are largely OBSOLETE at this
  granularity — the per-element cost is records+registration, not
  dispatch. (Old per-element operator varis — the pre-Callbacks design —
  are what stanc3 PR #1666 is still fighting at the codegen level.)

## 2. Tax decomposition (existing W-29/W-34 callgrind dumps; no fresh model profiling needed)

Parser: `harness/w47/alloc_edges.py` over `results/profile/w29/<m>/ann_tree.txt`
(caller-edge attribution; exclusive Ir from `ann_exclusive.txt`). Sub-shares
as % of total program Ir T (G/T ≥ 0.93 everywhere):

| component | hier_2pl | accel_gp | kronecker_gp | gp_regr | w34 armB |
|---|---|---|---|---|---|
| `stack_alloc::alloc` excl | **6.41%T** (2.246e9) | **7.38%T** (42.3e6) | **3.96%T** (1.094e9) | 0.88%T | **4.75%T** (1.196e9) |
| — calls (Ir/call) | 172.36M (13.0) | 3.24M (13.1) | 83.78M (13.1) | 20.8k (20.0) | — |
| chainstack `emplace_back` excl | **4.47%T** (1.565e9) | **6.68%T** (38.3e6) | **3.10%T** (0.855e9) | **3.09%T** (1.465e6) | **3.32%T** (0.838e9) |
| — calls (Ir/call) | 173.54M (9.0) | 4.28M (8.95) | 93.35M (9.2) | 162.7k (9.0) | — |
| grad() loop + inlined recover (inside `bs_log_density_gradient` excl) | 0.27%T | — | — | — | — |
| `recover_memory_nested` | 0.00%T | 0.35+0.09%T | 0.01%T | 0.36+0.15%T | — |
| rev callback BODIES (`reverse_pass_callback_vari<...>::chain()`) | 8.62%T | ~20%T | ~25%T | ~17%T | — |

Attribution details (hier_2pl): 98.4% of arena-alloc Ir comes from the two
eltwise ops (subtract 84.97M calls = 19,195 per log_prob call ≈ N+5;
elt_multiply ditto); the eltwise pair also owns ~98% of the emplace calls.
`subtract` inclusive 12.37%T = alloc 3.16 + emplace 2.18 + exclusive 7.02;
`elt_multiply` inclusive 11.40%T = 3.15 + 2.18 + 6.07 exclusive. The two
exclusives (13.1%T) contain the inlined vari ctors + IndexedView reads +
value math + var-pointer writes — the microbench separates these.
Cross-checks: alloc+emplace = 3.811e9 = EXACTLY W-34's measured tape
complex (10.9%T stock; armB 2.033e9 = 4.75+3.32 ✓).

Per-gradient, per-record accounting (hier_2pl, 4,424 var-mode log_prob
calls, 19,200 elements/op): 38,390 allocs and 39,213 pushes per gradient →
22.4 Ir/record for alloc+emplace alone; the microbench's stock floor arm
(A1) measures the full per-vari cost at **32.6 Ir/vari** (§3) — i.e. the
inlined ctor+loop adds ~10 Ir. `grad()` dispatch + recover ≈ 0.27%T.
TAKEAWAY: the tax is (a) per-record arena bump calls, (b) per-record
nochain registration, (c) per-record ctor stores — all FORWARD-pass costs;
the reverse pass is callback bodies (math), not machinery.

## 3. Microbench (scratch/w47/, pure C++ against the bridgestan stan-math 5.3.0 headers, -O3, bitwise-correctness-gated)

Reproduces hier_2pl's line at N=19,200: `lp = sum(alpha[ii] .* (theta[jj]
− beta[ii]))` with complete-grid ii/jj (W-34 data fact), including
`rvalue<index_multi>` gathers, `grad()`, `recover_memory()`. Arms: A0 =
real stan-math ops; A1 = bare `var(double)` loop (stock per-vari floor);
framework arms replicate the same math with identical array traffic and
toggle record layout (AoS stock-like records with per-record bump-alloc
call + vptr store + nochain vector emplace vs POD SoA val/adj pool) and
callback mechanism (virtual `chain()` objects in a vector vs flat
{fnptr,data} array replayed in reverse). Fidelity anchors: F_SS (replica)
must sit between A0 (adds Eigen/var glue) and the pool arms; framework
gradients are BITWISE identical to A0's (rel-L2 = 0.0e0, gate ≤1e-12).

Wall (medians of 5 interleaved reps × 300 iters, taskset 0-3; per
iteration = 38,400 records):

| arm | build µs/iter | rev µs/iter | ps/record build | ps/record total |
|---|---|---|---|---|
| A0 stock stan-math | 416.2 | 163.0 | 10.84 | 15.08 |
| F_SS AoS+virtual (replica) | 152.5 | 152.4 | 3.97 | 7.94 |
| F_PS **pool**+virtual | 53.8 | 150.4 | **1.40** | 5.32 |
| F_SF AoS+**flat cb** | 153.7 | 151.8 | 4.00 | 7.95 |
| F_PF pool+flat | 53.3 | 151.2 | 1.39 | 5.33 |
| A1 `var(double)` floor | 79.3 | ~0 | 2.06 | 2.07 |

Ir (callgrind 3.23, 200 iters/program, one job at a time; per record):

| arm | total Ir/record | breakdown highlights (Ir/iter ÷ 38,400) |
|---|---|---|
| A0 | **101.91** | subtract fwd 48.0/record (incl. inlined alloc; emplace out-of-line 9.16); elt_multiply fwd 45.0; glue (params+rvalue+sum) 22.5; callback bodies 17.0; memcpy 6.1 |
| F_SS | 51.12 | fw build 26.3 incl. 10.0 arena-alloc calls/record |
| F_PS | 34.56 | fw build 11.75 (gathers+math+memset) |
| F_SF | 51.12 | flat-callback delta = **0.00** |
| F_PF | 34.55 | |
| A1 | **32.57** | the intrinsic stock per-vari tax: ~13 alloc + ~9.2 emplace + ~10 ctor/loop |

Readings:
- **Typed-pool ceiling**: F_SS→F_PS = −16.6 Ir/record = **−32% of the
  tape complex** (wall: build −65%: 3.97→1.40 ps/record). At hier_2pl
  model level this corresponds to removing alloc (6.41%T) + emplace
  (4.47%T) + ctor stores (~4–6%T inside op exclusives) ≈ **−10…−16%G**.
- **Flat callbacks: measured ZERO.** F_SF vs F_SS and F_PF vs F_PS are
  indistinguishable (51.12 vs 51.12; 34.56 vs 34.55 Ir; wall within
  noise). With per-op callbacks there are 2 callbacks per gradient on
  this line; dispatch through `var_stack_[i]->chain()` + the grad loop +
  recover = 0.27%T at model level. An index-based chain solves a problem
  stan-math no longer has (per-element varis), and would only matter if
  the eltwise fusion lane REGRESSED to per-element callbacks.
- **The A0−F_SS gap (50.8 Ir/record, wall 6.9 ps/record)** is NOT tape:
  it is Eigen/Holder/IndexedView expression evaluation, arena copies of
  var-pointer arrays, the `ret_type` materialization and rvalue glue —
  addressable only by expression fusion (W-34's GEMM rewrite removed it
  at −28.2% Ir/grad; stanc3 #1666 is the general fix). Strategic split:
  of hier_2pl's eltwise complex (40.4%G stock), roughly two thirds is
  expression glue, one third is tape machinery — so the arena-refactor
  lane and the fusion lane are complementary, and the arena ceiling on a
  post-W-34 model is the surviving 8.1%T tape block minus new costs.

## 4. Integration verdict (pre-registered decision rule)

- **SoA / typed-pool / index-based `var`: REWRITE — stopped at the
  ceiling, per pre-registration.** `var` is `vari_value<T>*` across all
  of `rev/` (400+ files), stanc3-generated code, and user code; `var`
  is passed by value, compared, sorted, and used as a map key;
  `save_varis`/`read_var`/`deep_copy_vars`/`count_vars` walk `vi_`
  pointers; `arena_matrix` maps into stack_alloc blocks; nested AD and
  `scoped_chainablestack` (STAN_THREADS interop) snapshot the whole
  ChainableStack. An SoA representation breaks all of it. The API
  surface a real proposal would need is in §6.
- **Batched allocation / span chainstack (the small increment):
  PROTOTYPED, correctness-perfect, perf-codegen-blocked.** Below.

## 5. The span-chainstack prototype (shippable-increment attempt)

Design: the nochain stack exists ONLY for `set_zero_all_adjoints{,
_nested}`. Records of an eltwise op's output are contiguous in the arena
(same-size, construction order). Replace per-vari
`var_nochain_stack_.push_back` with a span registry
`{begin, count, stride}`: register_nochain(p, sizeof) extends the current
span iff p is exactly adjacent AND the (8-padded) size matches; else
starts a new span (safe fallback — semantically identical to per-vari
registration in all cases, including interleaved var_stack_ pushes and
foreign allocations). set_zero iterates spans; recover/nested logic
resized to span counts; profiling counts via span sums. Patch: 8 headers,
~120 changed lines — `scratch/w47/w47_span_chainstack.patch` (generated
against 5.3.0 = develop-identical files). Implemented as a shadow include
dir (the pristine bridgestan tree was NEVER modified; md5-verified after:
`scratch/w47/pristine_md5/core.md5`, all OK).

Correctness gates (all PASS):
- microbench: framework + patched-stock gradients bitwise identical to
  stock (rel-L2 0.0); `set_zero_all_adjoints` through spans zeroes every
  record exactly (max |adj| = 0.0); rebuilt tape after zero+recover is
  bitwise identical.
- model level (hier_2pl .so built with consistent-ABI bridgestan.o from
  a hardlinked bridgestan copy; first mixed-ABI attempt segfaulted —
  `src/bridgestan.o` is prebuilt with pristine headers and links into
  every model .so, a deployment hazard for ANY layout-touching patch
  worth recording): logp+grad bitwise identical on 50 random points, and
  a FULL SAMPLER RUN (stan_cli, warmup 100 + 50 draws, seed 20260819,
  W-29 protocol) produced **draws.csv md5-identical to stock**
  (fe7c57c99a7a6530ce2dcc408d6e9c65) with identical trajectory.

Performance:
- microbench (controlled, interleaved 7 reps): build **−25.7%**
  (9690→7203 ps/record; distributions non-overlapping), reverse 0.0%,
  complex total −18.4%; Ir −2.5% (the emplace symbol disappears; the
  eliminated 300KB/iter of nochain-vector stores dominate the wall win).
- model level: total Ir 35.023e9 → 35.363e9 (**+1.0%**): subtract
  exclusive +25.5%, elt_multiply +19.0% — GCC 16.2 -O3 -fPIC inlines the
  per-record registration into the Eigen assignment loops ~11 Ir/record
  WORSE than the out-of-line emplace it replaces (the same source
  inlines ~3 Ir/record BETTER in the bench TU). Process-interleaved wall
  on the shared machine is noise-bound (stock 1160µs/call vs patched
  1193µs median-of-medians, ±3% band) — point estimate slightly
  negative, certainly not a win.

**Verdict: not shippable as per-record address checks.** The mechanism is
sound (sampler-bitwise) and the wall evidence says the nochain store
traffic matters — but the per-record check-registrand codegen loses to
the status quo in real model TUs. What would make it real: op-level BATCH
registration — construct an op's whole output array with ONE arena alloc
+ ONE span + a zero-filled adjoint block (§6 API). That also kills the
per-record alloc call (13 Ir) which per-record spans cannot touch. Note
for upstream: LLVM codegen of the same patch is untested (the bench/model
GCC divergence alone justifies a clang check before any filing).

## 6. Design document: the API surface an SoA/typed-pool arena needs (upstream conversation starter)

Context to cite: no existing SoA-arena work upstream (scan 2026-08 §3 —
only long-closed PRs #1103/#2928 adjacent); stanc3 #1666's "O(1) autodiff
nodes" motivation is the same evidence class; W-34's measured −28.2%
Ir/grad GEMM rewrite shows the expression-glue share dwarfs the tape
share on this model class; math develop just migrated to Eigen 5.0.1 —
a natural epoch for a representation change.

Increment A (shippable, measured ceiling −(6.4+4.5)%T hier_2pl stock,
minus new costs; needs Eigen-assignment plumbing):
1. `ChainableStack::register_nochain_span(vari_base* begin, size_t n,
   size_t stride)` — internal; set_zero/recover/nested already span-aware
   (this prototype's 8-file patch is the substrate).
2. `vari_value<double>* make_vari_array(const double* val, size_t n)` —
   ONE arena alloc for n records, adjoint block zero-filled in a single
   pass, ONE span registered. (SoA variant: parallel val[]/adj[] arrays —
   same signature.)
3. Eigen assignment specialization: `arena_matrix<Matrix<var>> ←
   double-expression` evaluates into a double scratch then calls (2) and
   writes var pointers — replaces the per-coeff `var(double)` loop inside
   eltwise ops WITHOUT touching any op's public semantics.
   Numerics: values bitwise identical (same doubles stored); adjoints
   identical (same zero init); `set_zero` identical by construction.

Increment B (the SoA-arena proper; breaking, versioned):
- `var_value<T>` stays 8 bytes but `vi_` points into TYPED pools
  (per-size arenas) — pointer stability keeps `var`'s public type, all
  400+ rev/ files, stanc3 codegen and user code COMPILING, but requires:
  (a) pool interchange with `stack_alloc` for arena_matrix storage
  (matrix varis embed Eigen Maps — pool must serve them);
  (b) `vari_base`'s vtable removed for nochain records only (chain stays
  for var_stack_ records) — i.e. two record families, dispatch by stack
  membership, not by per-record vptr;
  (c) `save_varis`/`read_var`/`deep_copy_vars`/ODE+adjoint integrators
  (which hold varis across nesting boundaries) audited for
  pointer-stability assumptions — nesting currently recovers arena by
  bump-pointer rollback, which typed pools must replicate exactly;
  (d) a one-release deprecation path via the `ChainableStack` interface
  (all registration already funnels through 6 call sites — this
  prototype's patch maps them).
  Measured ceiling (F_PS/F_PF + batched alloc): removes ~28 of the 32.6
  Ir/vari record tax → −10…−16%G on eltwise-plumbing models, ~−6…−8%T
  post-W-34, ZERO reverse-pass effect.
- What does NOT need doing (negative results worth stating upstream):
  flat/index-based callback chains (measured 0.00 delta at per-op
  granularity), grad()-loop micro-optimization (0.27%T), virtual-dispatch
  elimination (O(#ops) entries).

## 7. Honest verdict

1. The tape tax is real, forward-pass-side, and precisely localized:
   22.4 Ir/record (alloc+emplace) + ~10 Ir/record ctor = 32.6 Ir/vari
   stock; hier_2pl pays 10.95%G in alloc+emplace alone.
2. A full SoA/typed-pool arena would recover at most ~one third of the
   eltwise complex (≈ −13%G stock hier_2pl, −8%T after the W-34 GEMM
   fix); the other two thirds is expression glue that belongs to the
   fusion/stanc3 lane. On kronecker_gp/accel_gp the same machinery tax
   is 7.1%/14.1%T (alloc+emplace) — the pool matters MORE on small-matrix
   models, less on big-GEMM models.
3. The one small increment upstream could take today (span-chainstack)
   is correctness-proven to sampler-bitwise level but perf-blocked by
   per-record codegen; the fix is the batch API (Increment A), which is
   a real but Eigen-plumbing-sized PR, not a tweak.
4. The flat-callback/vtable concern is a dead end at current granularity
   — worth stating publicly so effort goes to records, not dispatch.
5. This direction should be pitched as a design conversation (the scan's
   "no existing work" finding + these ceilings + the bitwise-identical
   span prototype), not as a ready PR.

## 8. Reproduction

```
cd stan/scratch/w47
env -u LD_LIBRARY_PATH /usr/bin/make -j2 bench bench_patched
env -u LD_LIBRARY_PATH ./bench A0 300 1        # reference + gates + timing
for a in A1 F_SS F_PS F_SF F_PF; do env -u LD_LIBRARY_PATH ./$b ...; done
env -u LD_LIBRARY_PATH ./run_wall.sh           # interleaved wall table
env -u LD_LIBRARY_PATH ./run_callgrind.sh      # Ir per arm (serialized)
env -u LD_LIBRARY_PATH ./run_patchcmp.sh       # stock vs span-patched
# model-level (needs consistent-ABI bridgestan copy; see WORKLOG W-47):
env -u LD_LIBRARY_PATH taskset -c 0-3 uv run python \
  scratch/w47/model_probe.py bs_models/model_hier_2pl.so ref
env -u LD_LIBRARY_PATH taskset -c 0-3 uv run python \
  scratch/w47/model_probe.py scratch/w47/model_build/hier_2pl_model.so test
# tax decomposition from existing dumps:
python3 harness/w47/alloc_edges.py results/profile/w29/<m>/ann_tree.txt alloc|emplace
```

File index: `scratch/w47/` — bench.cpp (all arms + gates), Makefile
(shadow-first include order matters), shadow/ (8 patched headers),
w47_span_chainstack.patch (the kit), pristine_md5/core.md5 (restore gate,
all OK), out/ (wall_raw.txt, cg_*.ann.txt + w47_ir_table.json,
patchcmp_raw.txt, model_timing.txt, profile/{stock,patched}/ full
callgrind + md5-identical draws), model_probe.py, run_*.sh;
`harness/w47/alloc_edges.py`. Raw model probe reference /tmp/w47_ref_model.npz.
The pristine bridgestan tree and walnutpie were never modified
(md5-verified; the hardlinked bridgestan-w47shadow copy was deleted).
