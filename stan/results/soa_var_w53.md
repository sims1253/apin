# W-53 — staged SoA-var rewrite for stan-math, phase 0/1: pointer-semantics inventory, migration plan, 3-level utility estimate, and the elt_multiply vertical slice

Date: 2026-08-23. Pre-registration: WORKLOG.md W-53 (attempt 3; two prior
attempts died on infra rate limits with no surviving artifacts). Inputs:
W-47 (`results/sota_arena_w47.md` — typed-pool ceiling −32% of the tape
complex; Increment A/B design), W-34 (`results/hier2pl_plumbing_w34.md`),
upstream_candidates.md #9, WORKLOG W-47/W-47-close-out. Tree:
`external/math_soa` = fresh clone of stan-dev/math develop @
**344d7167a03783c1515079e0384be3859c00ca99** (2026-08-23; submodules
Eigen 5.0.1 / boost 1.87 / sundials 6.1.1 / tbb 2020.3). Arena machinery
verified BYTE-IDENTICAL to the bridgestan 2.9.0 bundle's stan-math 5.3.0
(vari.hpp, autodiffstackstorage.hpp, chainablestack.hpp,
reverse_pass_callback.hpp, grad.hpp, recover_memory{,_nested}.hpp,
elt_multiply.hpp, arena_matrix.hpp); the only diff is develop's
stack_alloc `len + pad` bugfix (allocation padding only — no FP effect).
Model gates therefore run on the bridgestan bundle tree + the identical
patch (W-47-validated recipe), keeping stock-vs-patched internally
consistent.

**Headline.** (1) Phase 0 inventory: pointer semantics are CONCENTRATED —
a 19-site/5-file registration seam + an 89-file `.vi_` reach-through tail +
exactly 2 identity comparisons (both null checks) and 1 direct chain()
call site; no `std::hash<var>`, no `std::map<var,...>` anywhere in
stan/math. Pointer-stable typed pools (W-47 Increment B) are compatible
with essentially everything found; an index-based `var` is not (W-47
verdict re-confirmed structurally, now with file counts). (2) The
vertical slice (elt_multiply rev-rev output records as ONE batched arena
allocation + ONE nochain span) passes ALL gates — bitwise-identical
gradients on the 4-model battery (0/100 mismatches), sampler draws
md5-identical (and equal to W-47's recorded stock md5), unit tests 3/3 —
and MEASURES: **−7.69% total / −8.23% gradient Ir at sampler level**
(identical 4,493-gradient trajectories), elt_multiply forward −27.7%
with the reverse callback instruction-identical, wall −0.7..−2.2%
in-sampler and −21..−23% in repeated-evaluation regimes. (3) 3-level
utility: (a) arithmetic bound full rollout −8..−12%G hier_2pl /
−10..−14%G accel_gp / −5..−7%G kronecker_gp / −3..−4%G gp_regr;
(b) locality bound: −96.7% of the record-complex last-level data
misses (0.413 → 0.014 LLd misses/record, idealized pool); (c) ground
truth from the slice as above. VERDICT: GO for the staged batch-API
rollout; bit-identity not structurally blocked; codegen-sensitivity
risk measured (develop/Eigen-5 TU: −9.2% Ir but +17% wall on the
isolated line — restructure the record loop before batch 1).

## 1. Phase 0 — pointer-semantics inventory (develop @344d7167)

Method: scripted greps (`scratch/w53/inventory/inv.sh`, raw tables in
`scratch/w53/inventory/*.txt`) over all 1,900 headers of
`stan/math/`, manually classified. Categories: (i) mechanical (works
unchanged under any pointer-stable record layout), (ii) needs API shim
(keep `var` a pointer backed by typed-pool storage — W-47 Increment B),
(iii) structural (blocks any representation change; nested arenas,
TLS chainstack, STAN_THREADS).

### 1.1 Headline counts

| pattern class | sites (files) | classification |
|---|---|---|
| raw `vari*`/`vari_value<T>*` in signatures/members | 57 files (p1) | (ii) allocation seam; pointer copies are (i) |
| `.vi_`/`->vi_` reach-through outside var/vari core | 61 files (p2); **union with p1 = 89 files** | (ii) accessor seam (only for SoA-proper; layout-compatible pools need nothing) |
| stack registration push sites (`var_stack_`/`var_nochain_stack_.push_back`) | **19 textual sites / 5 files** — rev core: vari.hpp ×11 + reverse_pass_callback.hpp ×1; peripheral: opencl/rev/vari.hpp ×5, cvodes_integrator_adjoint.hpp ×1 | (ii) THE registration seam |
| identity comparisons on var pointers | **2 sites, 1 file** — `rev/core/var.hpp:291,1010`, both `vi_ == nullptr` guards | (i) |
| `vi_ == vi_` pointer-equality between vars | **0** | — |
| direct `chain()` invocations | **1 site** — `rev/core/grad.hpp:30` (the dispatch loop) | (ii) dispatch seam |
| `reinterpret_cast` on vari pointers | 20 sites / 6 files (gevv_vvv_vari, vector_vari, mdivide_left_{tri,spd}, squared_distance, cvodes cast) | (ii) pointer-stable pools OK; index-var breaks |
| containers of `vari*` | `std::vector<ChainableT*>` ×2 (the stacks), `alloc_array<vari*>` ×14, `Eigen::Matrix<vari*>` typedefs ×3 (`matrix_vi`/`vector_vi`/`row_vector_vi`) + `Eigen::Map` over `vari*` | (ii) |
| dump/serialize family | 18 files (`save_varis`, `read_var`, `deep_copy_vars`, `count_vars`, `collect_adjoints`, `accumulate_adjoints`, `filter_var_scalar_types`) | (ii) fixed-offset val_/adj_ reads; layout-compatible pools OK |
| var as map key / hashed | **0** (`std::hash<var>`, `std::unordered_map<var,...>`: none) | — |
| var sorted in containers | `prim/fun/sort_{asc,desc,indices}.hpp` — all compare `val()` (operator< on var is value-based, `rev/core/operator_less_than.hpp`) | (i) |
| `operator==` on var | `rev/core/operator_equal.hpp` — value comparison | (i) |
| address-of var/vari | 0 (`std::addressof`: 0; `&x.vi_`: 0) | — |
| nested arena machinery | `start_nested`, `recover_memory_nested`, `set_zero_all_adjoints_nested`, `nested_rev_autodiff`, `nested_*_sizes_` (7 files) | (iii) |
| TLS chainstack / threads | `STAN_THREADS_DEF __thread` singleton pointer (autodiffstackstorage.hpp), TBB pool init, reduce_sum/map_rect child stacks | (iii) |
| OpenCL varis | `opencl/rev/vari.hpp` (`vari_cl_base : vari_base`, 118 files under opencl/rev) — STAN_OPENCL only | (ii) under flag |
| callbacks holding raw pointers | `reverse_pass_callback`/`callback_vari`/`chainable_object`: 118-file reach (p12) — lambda + arena-captured pointers | (i) pointer copies |

### 1.2 The structural reading

- **`var` is the pointer.** `var_value<T>::vi_` is a public member,
  copied by value in user code and stanc3 output; `var(vari*)` is a
  public trivial ctor; `Matrix<var>` is literally an array of 8-byte
  pointers. Everything found in (i)/(ii) is pointer *copying* or
  fixed-offset *dereferencing* (`val_` at +8, `adj_` at +16 of the 24B
  `vari_value<double>`). There is NO use of pointer *identity* between
  live vars (the only comparisons are null guards), NO hashing, NO
  ordering on pointers, NO address-of escapes. **Conclusion: typed
  pools that keep records address-stable and layout-compatible (W-47
  Increment B) require zero changes outside the 6-site registration
  seam + the allocation seam.** What an index-based/SoA-proper `var`
  would break is exactly the 61-file `.vi_` reach-through + the
  serialize family + stanc3/user pointer copies — the W-47 rewrite
  verdict, now with file-level counts.
- **The nochain stack has exactly 6 consumer sites** (verified by grep,
  all in rev/core): the two push sites in `vari.hpp`, the two
  `set_zero_all_adjoints{,_nested}` walks, `start_nested` /
  `recover_memory{,_nested}` size bookkeeping, plus `profiling.hpp`
  accounting. This is the whole semantic surface a span/batch registry
  must cover — the slice covers it.
- **Nested arenas (iii):** `start_nested()` snapshots the three stack
  sizes + `memalloc_.start_nested()` (bump-pointer rollback). Typed
  pools must replicate the rollback exactly (the slice's span resize +
  record-total recompute demonstrates the pattern; deep per-type pools
  would need per-type rollback pointers).
- **STAN_THREADS (iii):** the stack is a TLS singleton
  (`__thread` pointer for fast access); `reduce_sum`/`map_rect`
  workers construct their own child `AutodiffStackSingleton`. Pools
  must live inside `AutodiffStackStorage` (the slice puts them there)
  — a global pool would be a data race.

## 2. The ordered MIGRATION PLAN (fresh-session handoff artifact)

Seam (all batches): records stay `vari_value<double>` (24B, vptr, val_,
adj_) laid out contiguously in ONE arena allocation per op output;
registration via `make_nochain_vari_array` + one nochain span;
`set_zero`/`recover`/`nested` already span-aware (slice substrate in
`scratch/w53/w53_soa_slice_develop.patch`). Bit-identity holds by
construction at every batch (same records, same values, same zeros,
same zeroing coverage); each batch runs the full gate battery
(4-model exact-zero parity, draws md5, touched-target unit tests)
before the next.

| batch | files | what changes | risk | expected gain (hier_2pl) |
|---|---|---|---|---|
| **0 (DONE, this slice)** | 8 core + elt_multiply | span registry + batch builder + elt_multiply rev-rev branch | lowest (measured: gates PASS, [SLICE] %G) | elt_multiply alloc+emplace ≈ 3.15+2.18%T − new costs |
| 1 | `rev/fun/{subtract,add,divide,multiply}` + eltwise `rev/core/operator_{addition,subtraction,multiplication,division}.hpp` Matrix<var> branches (~10-14 files) | same batch construction for the remaining eltwise output records | GCC codegen in real model TUs (W-47's span-prototype was +11 Ir/record in-model vs −3 in-bench — batch registration avoids the per-record check, but VERIFY per model) | second half of the eltwise record tax; with batch 0 ≈ the full 10.9%T alloc+emplace complex |
| 2 | mixed var×arith branches of the same ops + broadcast shapes | extend the `if constexpr` to the one-autodiff branches | low; same code shape | small on our battery (hier_2pl hits rev-rev) |
| 3 | `rev/functor/*` ODE adjoint + `reduce_sum` | audit only: they hold vari* across nested recovers; pointer-stable pools keep semantics | lifetime audit (no code change expected) | 0 direct; unlocks nothing new |
| 4 | serialize family (save_varis/read_var/deep_copy/count/collect) | audit only under layout-compatible pools; accessor-shim only if SoA-proper | 0 code change expected | 0 |
| 5 | old-style scalar varis (dv/vv/vdd classes, gevv, precomputed_gradients, ~20 files) | allocation seam: retarget `vari_base::operator new` to typed pool (keep per-record var_stack_ registration — they dispatch) | medium: they are var_stack_ records; keep vptr + dispatch; only the ALLOCATION changes | small on stanc3-2.39 models (O(#ops)) |
| 6 | `opencl/rev` under STAN_OPENCL | same registration seam behind the flag | build-matrix-only | n/a |
| NOT planned ( Increment C) | 400+ files + stanc3 | index-based `var` | full rewrite, W-47 verdict | ceiling per W-47 microbench −32% of record complex |

Per-batch gates (pre-registered, non-negotiable): (a) exact-zero
gradient parity (values AND every gradient component, bitwise) on
hier_2pl/kronecker_gp/gp_regr/accel_gp, 100 deterministic points;
(b) full sampler draws md5 via read-only walnutpie
`build_w36exp/examples/stan_cli`; (c) unit tests for touched targets
only; (d) callgrind Ir/grad must not regress (the W-47 codegen lesson
makes this a GATE, not a measurement). ANY nonzero parity or Ir
regression = stop and diagnose before proceeding.

## 3. Utility estimate — level (a): arithmetic bound

Anchors (W-47 §2, from W-29/W-34 callgrind; shares of total program
Ir T, G/T ≥ 0.93): per-record machinery = `stack_alloc::alloc` +
chainstack `emplace_back` (+ inlined ctor stores, ~4–6%T inside op
exclusives on eltwise-heavy models). Microbench net saving per record
migrated to the pool: −16.6 Ir/record (F_SS 51.12 → F_PS 34.56),
i.e. ≈ 74% of the 22.4 Ir/record alloc+emplace tax, plus part of the
ctor loop. Full-rollout arithmetic bound (all eltwise records
migrated, batches 0–2):

| model | alloc %T | emplace %T | sum %T | bound (−0.74 × sum, +%T≈%G) | with ctor share (est) |
|---|---|---|---|---|---|
| hier_2pl (stock) | 6.41 | 4.47 | 10.88 | **−8.1%G** | −8..−12%G |
| accel_gp | 7.38 | 6.68 | 14.06 | **−10.4%G** | −10..−14%G |
| kronecker_gp | 3.96 | 3.10 | 7.06 | **−5.2%G** | −5..−7%G |
| gp_regr | 0.88 | 3.09 | 3.97 | **−2.9%G** | −3..−4%G |

(W-47's quoted "−10…−16%G" for hier_2pl assumed ~full ctor removal;
the −0.74 net-of-new-costs row is the defensible arithmetic bound; the
ctor column is the optimistic end. Post-W-34 hier_2pl the same bound
applies to the surviving 8.1%T tape complex → ≈ −6%G.) Level (a) is
labeled: arithmetic extrapolation of microbench ratios, no model
measurement.

## 4. Utility estimate — level (b): locality bound (cachegrind, W-47 microbench pair)

Cachegrind (system valgrind 3.25.1, `--cache-sim=yes`; W-47's bench in
`scratch/w47/`, arms F_SS = AoS stock-like records vs F_PS = typed
pool; 200 iters × 38,400 records = 7.68M records/program; the bench's
own bitwise gates passed in-run):

| metric | F_SS (stock-like) | F_PS (pool) | delta |
|---|---|---|---|
| I refs | 392,630,577 | 265,405,789 | −32.4% |
| D refs (rd+wr) | 228.2M (128.3+99.9) | 165.8M (70.2+95.6) | −27.4% |
| D1 misses (rd+wr) | 13.87M (6.59+7.28) | 10.97M (6.58+4.39) | −20.9% |
| **LLd misses (rd+wr)** | **3.169M (0.834+2.336)** | **0.106M (0.015+0.091)** | **−96.7%** |
| LLd misses / record | 0.413 | 0.014 | 30x |

Reading: the pool layout removes essentially ALL last-level DATA
misses of the record complex — the write side (2.34M → 0.09M, −96%)
first: stock's per-record bump-allocations scatter 24B stores across
arena blocks interleaved with vptr/pointer traffic, while a dense
record array is perfectly line-filled. Read-side D1 misses are
unchanged (the gathers dominate reads). BOUND interpretation: beyond
the −32% Ir saving W-47 measured on this pair, there is a
memory-system upside worth up to ~0.4 avoided LL misses per record;
how much materializes at model level depends on regime (§5.3: a lot in
repeated-evaluation, little inside the sampler). NOTE: F_PS's pool is
the idealized 16B no-vptr SoA of W-47's framework; the SLICE keeps
24B layout-compatible records, so the slice captures only the
contiguity component of this bound (batched = contiguous), not the
record-shrinking component.

## 5. Phase 1 — the vertical slice: elt_multiply's output records as one batched typed-pool allocation + one nochain span

Design (exactly W-47 Increment A, scoped to ONE op branch): in
elt_multiply's rev-rev branch, the stock path
`arena_t<ret_type> ret(arena_m1.val().cwiseProduct(arena_m2.val()))`
performs, per element: `memalloc_.alloc(24)` (≈13 Ir) +
`var_nochain_stack_.push_back` (≈9 Ir) + inlined ctor stores (vptr,
val, adj=0.0). The slice replaces it with:
`make_nochain_vari_array(prod_expr)` — ONE `alloc_array<char>(n*24)`,
placement-`::new` of each `vari_value<double>(coeff(i), vari_no_stack)`
(no per-record allocation, NO per-record stack push), ONE
`NoChainSpan{begin, count, 24}` registration; the output
`Matrix<var>` is filled with trivial `var(recs+i)` pointer stores; the
reverse callback is byte-for-byte the stock lambda. Substrate changes
(the only other edits): span registry + nested bookkeeping in
`AutodiffStackStorage`; `set_zero_all_adjoints{,_nested}` walk spans
(typed walk, devirtualized `set_zero_adjoint` — same single store as
stock); `start_nested`/`recover_memory{,_nested}` snapshot/rollback
spans; `profiling.hpp` counts span records. Patch:
`scratch/w53/w53_soa_slice_develop.patch` (9 files, +1 new header,
applies to develop@344d7167 AND byte-identically to the bridgestan
5.3.0 bundle tree).

### 5.1 Bit-identity by construction + what bit-identity cannot see

- Values: same per-element products of the same doubles (elementwise
  multiply of two `.val()` doubles is order-independent; `coeff(i)`
  reads the same operands the Eigen assignment loop reads).
- Adjoint init: `adj_{0.0}` NSDMI — identical store pattern.
- set_zero: spans cover exactly the batch records; zeroing writes the
  same 0.0 to the same offsets (stock dispatches virtually through
  `vari_base*`; the slice's typed walk stores directly — same final
  memory state).
- grad(): iterates `var_stack_` only; batch records are nochain in
  BOTH designs (stock per-element varis have empty chain() and are
  never dispatched).
- recover/nested: span vector cleared/resized in lockstep with
  `var_nochain_stack_`; the arena rollback is stock's
  (`memalloc_.recover_all/recover_nested`) since records live in the
  same arena.
- What bit-identity CANNOT see (documented per pre-registration):
  (i) nochain registration ORDER across the whole tape changes
  (batch spans appended after interleaved per-vari entries) —
  zeroing is order-independent, so no observable effect; (ii)
  `print_stack`-style diagnostics (none exist for nochain — verified)
  and `profile` counts (patched to parity) differ in mechanism;
  (iii) exception-in-mid-op leaves a partially-filled span vs
  partially-pushed vector — both are unreachable-after-recover
  garbage; (iv) the vptr store remains (records stay 24B
  layout-compatible — deliberate, this is Increment A not B).

### 5.2 Gates

| gate | result |
|---|---|
| probe bit-identity (develop tree + Eigen 5.0.1, stock via git-stash A/B, lp + full adjoint sums) | **PASS** — bitwise identical (`scratch/w53/{stock,patch}.out`) |
| (a) exact-zero parity, 4-model battery, 100 deterministic pts each (values AND every gradient component, `np.array_equal`) | **PASS 4/4** — hier_2pl (D=669) 0/100 value, 0/100 grad mismatches; kronecker_gp (D=438) 0/100, 0/100; gp_regr (D=3) 0/100, 0/100; accel_gp (D=66) 0/100, 0/100 |
| (b) full sampler draws md5 (walnutpie `build_w36exp/examples/stan_cli`, READ-ONLY; W-29 protocol: warmup 100, samples 50, seed 20260819, pf init, --metric-window 50) | **PASS** — stock and patched BOTH md5 `fe7c57c99a7a6530ce2dcc408d6e9c65`, digit-for-digit the md5 W-47 recorded for the same protocol (cross-session protocol continuity) |
| (c) unit tests, touched target (`test/unit/math/mix/fun/elt_multiply_test` — the file exercising rev-mode elt_multiply) | **PASS 3/3** |

### 5.3 Measurements (the utility ground truth)

Callgrind (W-29 protocol verbatim, valgrind 3.23 `~/vginstall`, one job
at a time; stock/patched built from the SAME bridgestan bundle + the
SAME protocol via walnutpie `build_w36exp` stan_cli, read-only):

| metric | stock | patched | delta |
|---|---|---|---|
| total program Ir T | 37,128,497,671 | 34,272,961,754 | **−7.69%** |
| logp_grad subtree G | 34,699,206,054 | 31,843,619,562 | **−8.23%** |
| gradient calls | 4,493 (3,737 warmup + 756 sampling) | 4,493 — IDENTICAL | — |
| Ir / gradient (G/calls) | 7,722,948 | 7,087,385 | **−8.23%** |
| draws.csv md5 (under valgrind) | fe7c57c99a7a6530ce2dcc408d6e9c65 | fe7c57c99a7a6530ce2dcc408d6e9c65 | identical |

(Stock G/grad 7.723M vs W-34's 7.745M on build_e27: 0.3% cross-binary
drift — continuity OK.) Attribution (callgrind_annotate, threshold 90):

| symbol | stock | patched | delta |
|---|---|---|---|
| `elt_multiply` fwd inclusive | 3,992,863,504 (10.75%T) | 2,888,774,713 (8.43%T) | **−27.7%** |
| `elt_multiply` reverse callback (lambda) | 1,189,224,288 | 1,189,224,288 | **0.0% — identical to the instruction** |
| `subtract` fwd inclusive | 4,332,644,400 | 4,332,644,400 | 0.0% (untouched op — clean control) |
| `subtract` reverse callback | 1,104,287,912 | 1,104,287,912 | 0.0% |
| `stack_alloc::alloc` | 2,246,152,545 (6.05%T) | 1,141,922,145 (3.33%T) | −49.2% |
| chainstack `emplace_back` | 1,564,528,830 (4.21%T) | 800,061,565 (2.33%T) | −48.9% |
| `__memcpy_avx_unaligned_erms` | 1,028,014,845 | 1,027,753,326 | −0.0% |

Reading: the slice removed EXACTLY elt_multiply's per-record machinery
— alloc calls −49.2% (its share of all arena allocations; refines
W-47's "98% from the eltwise pair" to a 49.2/50.x split between
elt_multiply/subtract on this binary), emplace −48.9% — while the
reverse pass and the untouched sibling op are instruction-identical.
Per-record accounting: elt_multiply constructs 19,200 records/gradient
call × 4,424 var-mode calls = 84.9M records over the run; removed
13.0 (alloc) + 9.0 (emplace) Ir/record; the batch construction loop
(vptr/val/adj placement-new stores + `Matrix<var>` pointer fill)
costs +9.0 Ir/record more than the stock inlined Eigen-assignment
ctor stores; NET −13.0 Ir/record = −40% of the 32.6 Ir/vari stock
record tax, −8.23% of the whole gradient. The +9.0 Ir/record new-cost
term is the slice's honest overhead (labeled for future work: fused
record+pointer loop or scratch-buffer evaluation could shave 1–2
Ir/record; NOT attempted here — gates green and utility measured take
priority). This is the model-TU codegen lesson of W-47 again, but now
the batch API wins NET in the real TU where the per-record span check
lost: the W-47 span prototype was −16.6 Ir/record in the bench TU but
+11 Ir/record WORSE per record in model TUs; the slice's batch version
is −13.0 Ir/record NET in the model TU itself.

Wall clock — THREE regimes measured, all stock-vs-patched on the same
.so pair (shared-machine caveat per W-46; ratios from interleaved
protocols, stock absolute ~4-6% inflated vs W-34's quiet-machine
numbers):

1. **In-sampler** (walnutpie stan_cli native stanza, 2 interleaved
   rounds × both arms): warmup 954.7/954.8 → 942.3/947.9 µs/call
   (−1.3%/−0.7%); sampling 983.2/978.2 → 961.5/968.4 (−2.2%/−1.0%).
   In-sampler wall: **−0.7..−2.2%** — LESS than the −8.2% Ir: the
   removed per-record instructions were largely hidden by
   out-of-order execution behind the likelihood's memory stalls in
   the sampler's colder working-set regime.
2. **Repeated-evaluation regime** (python/bridgestan driver, 50 fixed
   wild points back-to-back, 3 interleaved rounds × both arm ORDERS):
   stock 994.0-1007.4, patched 778.3-788.4 µs/call, medians ratio
   0.773-0.789 → **−21.1..−22.7%**, tight non-overlapping
   distributions, order-independent. Instruction anchor for the same
   regime (valgrind on the venv python, 200 calls, patched .so fixed
   +24.8M loader constant subtracted): stock 8.288M vs patched
   7.334M Ir/call = **−11.5%** — wall beats Ir ~1.9x here: the
   level-(b) locality upside materializes when the working set is
   hot and the per-record allocation/store scatter is on the critical
   path. (Methodological note: `uv run` under valgrind silently
   skips the model load — use `.venv/bin/python` directly; a 20-call
   variant of this measurement produced a sign-flipped artifact
   because the fixed loader constant dominated — resolved at 200
   calls.)
3. **Pure develop-tree TU** (the isolated eltwise line, develop
   headers, Eigen 5.0.1, -O3 non-PIC; `scratch/w53/wild_driver.cpp`):
   patched Ir −9.2% (534.7M→485.5M) but WALL **+17%** (301→351
   µs/call, reproducible): GCC cannot vectorize/reorder across the
   per-record placement-`::new` boundaries, and under Eigen 5 the
   stock assignment loop it replaces is better scheduled. The
   production model config (bundle math 5.3.0, Eigen 3.4.0, -fPIC)
   shows the opposite (elt_multiply self −27.7%) — the batch loop's
   codegen is TOOLCHAIN-SENSITIVE, so migration batch 1 must gate on
   wall (not just Ir) per toolchain, and the loop should be
   restructured to avoid per-record placement-new (e.g. raw
   vptr-store + memcpy'd val block) before the upstream PR.

**Extrapolation to the full rollout (labeled estimate):** subtract has
the same Matrix<var>-shape construction path and similar inclusive
share (4.333e9 vs 3.993e9); applying the measured −27.7% elt_multiply
fwd ratio to subtract adds ≈ −1.199e9 Ir → hier_2pl full-eltwise-batch
estimate ≈ **−10.9%T / −11.2%G**, inside the level-(a) arithmetic band
(−8..−12%G). For the other battery models the level-(a) table carries
the estimate (accel_gp −10..−14%G, kronecker −5..−7%G, gp_regr
−3..−4%G); their elt_multiply/subtract traffic shares are smaller and
were not sliced.

## 6. Verdict

**GO for the staged batch-API rollout (Increment A lineage); bit-identity
is NOT structurally blocked — it held at every level tried.**

1. All four gates PASS on the first full build: exact-zero gradient
   parity on the 4-model battery, sampler draws md5-identical
   (reproducing W-47's stock md5 digit-for-digit — the strongest
   bit-identity evidence available short of nothing), touched-target
   unit tests green, and the arena-semantics reasoning documented
   (§5.1) — nested spans, TLS storage, recover/nested lockstep all
   exercised by the sampler run.
2. The utility is real but regime-split: **−7.69% total / −8.23%
   gradient Ir at sampler level** (deterministic, identical
   trajectories), wall −0.7..−2.2% inside the sampler, −21..−23% in
   repeated-evaluation regimes (locality upside realized). The
   sampler number is the one that matters for walnutpie-style
   embedding; the repeated-eval number matters for
   bridgestan-style gradient serving. Full-eltwise-batch rollout
   (batches 0-1) arithmetic estimate ≈ −11.2%G on hier_2pl.
3. Two risks are now MEASURED, not hypothetical: (a) codegen
   sensitivity — the same patch wins −27.7% on the production
   bundle TU but loses +17% wall on an isolated develop/Eigen-5 TU
   (placement-new serialization) — batch 1 must gate on wall per
   toolchain and the record loop should be restructured first;
   (b) the bridgestan prebuilt-`bridgestan.o` hazard bit AGAIN
   (first `make` left the hardlinked pristine .o in place — silently
   up-to-date; must `rm src/bridgestan.o` + `make src/bridgestan.o`
   — now documented with the exact command).
4. The full SoA/typed-pool (Increment B, no-vptr records) is NOT
   needed to realize most of the value — the batch API alone
   captured −8.2%G at sampler level (vs the −10..−16%G Increment-B
   ceiling), because the dominant costs were the per-record
   allocation call and registration push, not the record layout.
   Increment B's remaining upside is the record-shrink/locality
   component (level (b) suggests up to −96.7% of record-complex LL
   misses) — pursue only if the fusion lane (W-34/W-48) removes the
   eltwise complex first on the hot models.
5. Utility table (3 levels, hier_2pl): (a) arithmetic bound full
   rollout −8..−12%G [−10..−14% accel_gp, −5..−7% kronecker, −3..−4%
   gp_regr]; (b) locality bound: −96.7% of record-complex LLd misses
   available beyond Ir (idealized pool; slice captures the contiguity
   part); (c) ground truth from the slice: −8.23%G Ir sampler-level /
   −21.7% wall repeated-eval / −0.7..−2.2% wall in-sampler,
   bit-identical everywhere. GO/NO-GO per batch stays with the
   pre-registered gate battery (§2).

## 7. Reproduction

```
cd stan/scratch/w53
# probe-level gate (develop tree): build probe (patched) + probe_stock
# (via git stash in external/math_soa), diff outputs — bitwise identical
# model builds: scratch/w53/build_models.py (stock=pristine bundle,
#   patched=bs_w53 hardlink copy + w53_soa_slice_develop.patch;
#   HAZARD: rm bs_w53/src/bridgestan.o && make src/bridgestan.o first)
# gates: gate_parity.py <model> <ref|test>;  gate_draws.sh
# timing: gate_timing.py (+ gate_timing_rev.py reversed order);
#   native stanza: stan_cli runs in /tmp per arm, parse 'time per call'
# Ir: run_callgrind.sh (W-29 protocol, valgrind 3.23);
#   python-regime Ir: child_ir.py via .venv/bin/python under valgrind
# locality: run_cachegrind_w47pair.sh (+ --cache-sim=yes rerun, cg2_*)
# isolated-line driver: wild_driver.cpp (stock build via git stash)
# inventory: bash scratch/w53/inventory/inv.sh
```
