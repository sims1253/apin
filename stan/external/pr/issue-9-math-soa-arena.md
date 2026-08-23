# Design conversation: the reverse-mode tape tax is forward-pass record machinery — batch allocation + span registration (and, later, typed pools) could recover ~8–12% of gradient time bit-identically

This is a conversation starter, not a PR: measured decomposition of where
reverse-mode time goes on eltwise-heavy models, a pointer-semantics
inventory of what a representation change would actually touch, a
refutation of one common worry (vtable dispatch), and a proof of
feasibility (a vertical slice with **bit-identical sampler output** and
−7.7% total instructions). We have no stake in which increment (if any)
gets adopted; the goal is to put measured numbers on the table so effort
goes where the time is.

## Problem

On eltwise-heavy models the dominant autodiff overhead is not virtual
dispatch, not the `grad()` loop, and not the reverse pass at all — it is
the FORWARD-pass per-record machinery: one arena bump-allocation call plus
one `var_nochain_stack_.emplace_back` per `vari` created, plus the inlined
constructor stores. In stan-math 5.3.0 (and current develop — the arena
machinery is byte-identical apart from an unrelated stack_alloc padding
fix), an eltwise op over `Matrix<var>` creates **one nochain `vari` per
element** (empty `chain()`, registered only so `set_zero_all_adjoints`
can find it) plus **one `reverse_pass_callback` per op**, so gradient
dispatch is already O(#ops), not O(N) — but record construction and
registration are O(N) with a real constant.

Measured decomposition (callgrind, hierarchical 2PL IRT model,
N = 19,200 observations, one gradient = 4,424 var-mode log_prob calls):

| component | share of total program Ir | calls | Ir/call |
|---|---|---|---|
| `stack_alloc::alloc` (exclusive) | **6.4%** | 172.4M | ~13.0 |
| chainstack `emplace_back` (exclusive) | **4.5%** | 173.5M | ~9.0 |
| inlined vari-ctor stores (inside op exclusives) | ~4–6% | — | — |
| `grad()` loop + dispatch + recover | **0.27%** | — | — |

So ≈ 11% of ALL instructions in the program are bump-alloc +
vector-push per record, and ~22.4 Ir/record of a total ~32.6 Ir/vari
record tax (the rest is ctor stores). On other battery models the same
complex is 7.1% (kronecker_gp) and 14.1% (accel_gp) — the tax matters
MORE on small-matrix/eltwise models, less on big-GEMM models.

## Evidence

Three independent measurement layers (all bitwise-correctness-gated):

1. **Microbench ceiling (typed pools).** A framework replicating the
   model's hot line with identical array traffic, toggling record layout
   (stock-like AoS with per-record bump-alloc + vptr store + nochain
   emplace vs a dense typed pool) and callback mechanism (virtual
   `chain()` vector vs flat {fnptr,data} array):
   - pool layout: **−32% of the per-record tape complex** in
     instructions (51.12 → 34.56 Ir/record); build wall −65%.
   - **flat callbacks: measured 0.00 gain** (51.12 vs 51.12 Ir/record;
     pool+flat indistinguishable from pool+virtual). With per-op
     callbacks there are ~2 dispatches per gradient on this line — the
     vtable/index-chain fear is solving a problem stan-math no longer
     has. Stated here so effort goes to records, not dispatch.
   - cachegrind on the same pair: last-level DATA misses of the record
     complex **−96.7%** (0.413 → 0.014 LLd misses/record) — the dense
     record array is perfectly line-filled where per-record
     bump-allocation scatters 24-byte stores across arena blocks.
2. **Pointer-semantics inventory (what a representation change
   touches).** Scripted classification of all 1,900 headers in
   `stan/math/`: pointer semantics are CONCENTRATED. The registration
   seam is **19 textual push sites in 5 files** (11 in
   `rev/core/vari.hpp`, 1 in `reverse_pass_callback.hpp`, plus OpenCL
   and one cvodes site); identity comparison on var pointers appears at
   exactly **2 sites, both `vi_ == nullptr` null guards**; there are
   **0 uses of `var` as a map key or hashed** (`std::hash<var>`,
   `std::unordered_map<var,…>`: none), 0 address-of escapes, 0
   pointer-ordering assumptions; sorting/equality on `var` is
   value-based. The long tail is an 89-file `.vi_` reach-through +
   the serialize family (`save_varis`/`read_var`/`deep_copy_vars`/…),
   all of which are fixed-offset dereferences (`val_`/`adj_`) that
   layout-compatible storage satisfies unchanged. Conclusion: typed
   pools that keep records address-stable and `var` a pointer are
   compatible with essentially everything found; an index-based `var`
   is not.
3. **Vertical slice (feasibility, ground truth).** One op branch
   (`elt_multiply` rev-rev output) rewritten to build its whole output
   record array as ONE arena allocation + ONE nochain span registration
   (9-file patch; `set_zero`/`recover`/nested bookkeeping made
   span-aware): all gates PASS —
   - gradients **bitwise identical** on a 4-model battery (values AND
     every gradient component, 100 deterministic points each, exact-zero
     parity);
   - **full sampler draws md5-identical** to stock (warmup 100 + 50
     draws, fixed seed) — and identical to a previously recorded stock
     md5 from an earlier session, i.e. protocol-level reproducibility;
   - touched-target unit tests green;
   - **−7.7% total / −8.2% gradient instructions at sampler level** with
     identical gradient-call trajectories (4,493 calls both arms); the
     op's forward inclusive share −27.7%; the untouched sibling op
     (`subtract`) and all reverse callbacks instruction-identical;
     `stack_alloc::alloc` and emplace each roughly halved (−49.2%/−48.9%),
     exactly the one op's share. Wall: −21..−23% in repeated-evaluation
     (bridgestan-style serving) regimes where the locality upside
     materializes; −0.7..−2.2% inside the sampler (removed instructions
     partly hidden by out-of-order execution behind memory stalls).

## Proposed direction

Two shippable increments, in order:

1. **Batch construction + span registration** (the slice, generalized):
   `make_nochain_vari_array(val, n)` — ONE arena allocation for n
   records, placement-constructed, adjoints zero-filled in one pass, ONE
   span `{begin, count, stride}` registered on the chainstack in place of
   n `push_back`s; `set_zero_all_adjoints{,_nested}`, `recover_memory`,
   `start_nested` and profiling walk spans. The nochain stack's ONLY
   consumers are exactly those walks (verified: 6 consumer sites, all in
   rev/core) — a span registry covers the whole semantic surface.
   Records stay 24-byte `vari_value<double>` layout-compatible, `var`
   stays a pointer: no API break, no stanc3 change, bit-identity by
   construction (same doubles, same zero init, same zeroing coverage).
   Measured ceiling on the eltwise-heavy model: the full alloc+emplace
   complex is 10.9% of program instructions; the slice's per-record net
   saving was −13.0 Ir/record (−40% of the record tax) in the REAL model
   TU; arithmetic bound for migrating all eltwise ops ≈ −8..−12% of
   gradient instructions on this model class.
2. **Typed pools (Increment B)**: `var_value<T>::vi_` points into
   per-size typed pools instead of the monolithic arena — pointer
   stability keeps `var`'s public type and all 400+ rev/ files, stanc3
   codegen and user code compiling unchanged. Requires pool interchange
   with `stack_alloc` for `arena_matrix` storage, exact replication of
   the nested-arena bump-pointer rollback, and living inside
   `AutodiffStackStorage` (TLS; a global pool would race under
   STAN_THREADS / reduce_sum workers). Ceiling per the microbench: the
   −32% Ir / −96.7% LLd-miss numbers above. NOT needed to realize most
   of the value — the batch API alone captured −8.2% of gradient Ir at
   sampler level in the slice.

Explicitly NOT worth doing (measured): flat/index-based callback chains
(0.00 delta at per-op granularity), `grad()` loop micro-optimization
(0.27%T), virtual-dispatch elimination (O(#ops) entries).

## Feasibility proven

The slice is the existence proof: sampler-bit-identical output with a
material instruction reduction, on a patch that touches only the arena
bookkeeping and ONE op branch. Nested arenas, TLS chainstack, and
recover/nested lockstep were all exercised by the sampler run and
documented (what changes: nochain registration ORDER across the tape —
zeroing is order-independent, so no observable effect; profiling counts
patched to parity). We are happy to share the 9-file patch and the gate
battery (exact-zero parity harness, draws-md5 protocol) as a reference
implementation of the derivation above.

## Risks

- **Codegen sensitivity (measured, the important one):** the same batch
  loop that wins −27.7% on the production toolchain (math 5.3.0 bundle,
  Eigen 3.4.0, -fPIC) LOSES +17% wall on an isolated develop/Eigen-5
  translation unit (GCC cannot vectorize/reorder across per-record
  placement-`new` boundaries). Any rollout must gate on WALL clock per
  toolchain, not just Ir, and the record loop should be restructured to
  avoid per-record placement-new (raw vptr store + memcpy'd value block)
  before broad adoption. LLVM codegen untested.
- **Deployment hazard for layout-touching patches:** bridgestan links a
  PREBUILT `src/bridgestan.o` compiled against pristine headers into
  every model .so — a patched-headers build silently keeps the stale .o
  unless it is removed first (`rm src/bridgestan.o && make
  src/bridgestan.o`). Worth documenting wherever arena internals change,
  since it will bite downstream packagers the same way.
- **Migration discipline:** value comes from migrating the whole eltwise
  family (per-op wins are proportional to the op's record count); each
  batch should run a bitwise-parity gate battery (exact-zero gradient
  parity + draws md5) before the next — the inventory says the seam is
  small, but the serialize family and ODE/adjoint integrators hold varis
  across nesting boundaries and deserve an audit pass (pointer-stable
  pools keep their semantics; no code change expected, but verify).

## References

- Measurements, inventory scripts, patch and gate harness: public
  benchmark repo **https://github.com/sims1253/apin** —
  `stan/results/sota_arena_w47.md` (tax decomposition, microbench
  ceilings, span prototype + its codegen result),
  `stan/results/soa_var_w53.md` (pointer-semantics inventory, migration
  plan, the bit-identical vertical slice and its −7.7%T/−8.2%G sampler
  measurement); pre-registered protocols in `stan/WORKLOG.md` (W-47,
  W-53). Happy to attach any of it here or re-run on a model/PR of the
  maintainers' choosing.
- Adjacent upstream context: stanc3 #1666 (`vectorize_loops` /
  O(1)-autodiff-node motivation) targets the same eltwise complex from
  the codegen side — the two lanes are complementary (expression glue vs
  tape machinery; roughly two-thirds/one-third of the eltwise complex on
  our battery). math develop's Eigen 5 migration is a natural epoch for
  a representation change if one is ever taken.
