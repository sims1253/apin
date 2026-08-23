# Design conversation: the reverse-mode tape tax is forward-pass record machiner: batch allocation + span registration could recover ~8–12% of gradient time, bit-identically

This is a conversation starter, not a PR. I measured where reverse-mode
time goes on eltwise-heavy models, inventoried what a representation
change would touch, refuted one common worry (vtable dispatch), and built
a vertical slice with bit-identical sampler output and −7.7% total
instructions. I have no stake in which increment, if any, gets adopted.
The goal is to put numbers on the table so effort goes where the time is.

## Problem

On eltwise-heavy models, the dominant autodiff overhead is not virtual
dispatch, not the `grad()` loop, and not the reverse pass. It is the
forward-pass per-record machinery: one arena bump-allocation and one
`var_nochain_stack_.emplace_back` per `vari` created, plus the inlined
constructor stores. In stan-math 5.3.0 and current develop, an eltwise op
over `Matrix<var>` creates one nochain `vari` per element (empty
`chain()`, registered only so `set_zero_all_adjoints` can find it) and one
`reverse_pass_callback` per op. Gradient dispatch is therefore already
O(#ops), not O(N), but record construction and registration are O(N) with
a real constant.

Decomposition, from callgrind on a hierarchical 2PL IRT model (N = 19,200;
one gradient = 4,424 var-mode log_prob calls):

| component | share of total program Ir | calls | Ir/call |
|---|---|---|---|
| `stack_alloc::alloc` (exclusive) | 6.4% | 172.4M | ~13.0 |
| chainstack `emplace_back` (exclusive) | 4.5% | 173.5M | ~9.0 |
| inlined vari-ctor stores (inside op exclusives) | ~4–6% | — | — |
| `grad()` loop + dispatch + recover | 0.27% | — | — |

About 11% of all instructions in the program are bump-alloc plus
vector-push per record. The same complex is 7.1% on kronecker_gp and 14.1%
on accel_gp: the tax is larger on small-matrix/eltwise models, smaller on
big-GEMM models.

## Evidence

Three measurement layers, each gated on bitwise correctness.

1. Microbench ceiling (typed pools). A framework replicating the model's
   hot line with identical array traffic, toggling record layout (stock AoS
   with per-record bump-alloc, vptr store, nochain emplace, versus a dense
   typed pool) and callback mechanism (virtual `chain()` vector versus a
   flat {fnptr,data} array):
   - Pool layout: −32% of the per-record tape complex in instructions
     (51.12 → 34.56 Ir/record). Build wall −65%.
   - Flat callbacks: zero gain (51.12 vs 51.12 Ir/record. Pool+flat is
     indistinguishable from pool+virtual). With per-op callbacks there are
     about two dispatches per gradient on this line. The vtable fear is
     solving a problem stan-math no longer has. I state this so effort goes
     to records, not dispatch.
   - Cachegrind on the same pair: last-level data misses of the record
     complex drop 96.7% (0.413 → 0.014 misses/record). The dense record
     array fills cache lines. Per-record bump-allocation scatters 24-byte
     stores across arena blocks.
2. Pointer-semantics inventory. I classified all 1,900 headers in
   `stan/math/` by script. Pointer semantics are concentrated:
   - Registration seam: 19 textual push sites in 5 files (11 in
     `rev/core/vari.hpp`, 1 in `reverse_pass_callback.hpp`, plus OpenCL and
     one cvodes site).
   - Identity comparison on var pointers: exactly 2 sites, both
     `vi_ == nullptr` null guards.
   - `var` as a map key or hashed: zero uses. Address-of escapes: zero.
     Pointer-ordering assumptions: zero. Sorting and equality on `var` are
     value-based.
   - The long tail is an 89-file `.vi_` reach-through plus the serialize
     family (`save_varis`, `read_var`, `deep_copy_vars`, …). All are
     fixed-offset dereferences (`val_`, `adj_`) that layout-compatible
     storage satisfies unchanged.
   - Conclusion: typed pools that keep records address-stable and `var` a
     pointer are compatible with essentially everything found. An
     index-based `var` is not.
3. Vertical slice (feasibility, ground truth). One op branch
   (`elt_multiply` rev-rev output), rewritten to build its whole output
   record array as one arena allocation plus one nochain span registration
   (9-file patch; `set_zero`, `recover`, and nested bookkeeping made
   span-aware). All gates pass:
   - Gradients bitwise identical on a 4-model battery: values and every
     gradient component, 100 deterministic points each, exact-zero parity.
   - Full sampler draws md5-identical to stock (warmup 100 + 50 draws,
     fixed seed), and identical to a stock md5 recorded in an earlier
     session.
   - Touched-target unit tests green.
   - −7.7% total and −8.2% gradient instructions at sampler level, with
     identical gradient-call trajectories (4,493 calls in both arms). The
     op's forward inclusive share −27.7%. The untouched sibling op
     (`subtract`) and all reverse callbacks are instruction-identical.
     `stack_alloc::alloc` and emplace each roughly halve (−49.2%, −48.9%) —
     exactly the one op's share. Wall: −21 to −23% in repeated-evaluation
     (bridgestan-style serving) regimes where the locality upside shows;
     −0.7 to −2.2% inside the sampler, where out-of-order execution hides
     part of the removed instructions behind memory stalls.

## Proposed direction

Two shippable increments, in order.

1. Batch construction + span registration (the slice, generalized).
   `make_nochain_vari_array(val, n)`: one arena allocation for n records,
   placement-constructed, adjoints zero-filled in one pass, one span
   `{begin, count, stride}` registered on the chainstack in place of n
   `push_back`s. `set_zero_all_adjoints{,_nested}`, `recover_memory`,
   `start_nested`, and profiling walk spans. The nochain stack's only
   consumers are those walks (6 consumer sites, all in rev/core), so a span
   registry covers the whole semantic surface. Records keep the 24-byte
   `vari_value<double>` layout, `var` stays a pointer: no API break, no
   stanc3 change, bit-identity by construction (same doubles, same zero
   init, same zeroing coverage). Measured ceiling on the eltwise-heavy
   model: the full alloc+emplace complex is 10.9% of program instructions;
   the slice's per-record net saving was −13.0 Ir/record (−40% of the
   record tax) in the real model TU. Migrating all eltwise ops bounds to
   about −8 to −12% of gradient instructions on this model class.
2. Typed pools (later). `var_value<T>::vi_` points into per-size typed
   pools instead of the monolithic arena. Pointer stability keeps `var`'s
   public type, all 400+ rev/ files, stanc3 codegen, and user code
   compiling unchanged. It requires pool interchange with `stack_alloc`
   for `arena_matrix` storage, exact replication of the nested-arena
   bump-pointer rollback, and living inside `AutodiffStackStorage` (TLS. A
   global pool would race under STAN_THREADS / reduce_sum workers). Ceiling
   per the microbench: the −32% Ir / −96.7% LLd-miss numbers above. Not
   needed to realize most of the value, the batch API alone captured
   −8.2% of gradient Ir at sampler level in the slice.

Not worth doing, measured: flat/index-based callback chains (0.00 delta at
per-op granularity), `grad()` loop micro-optimization (0.27%T),
virtual-dispatch elimination (O(#ops) entries).

## Feasibility

The slice is the existence proof: sampler-bit-identical output with a
material instruction reduction, on a patch that touches only arena
bookkeeping and one op branch. The sampler run exercised nested arenas,
the TLS chainstack, and recover/nested lockstep. What changes: nochain
registration order across the tape, zeroing is order-independent, so
there is no observable effect. Profiling counts were patched to parity. I
can share the 9-file patch and the gate battery (exact-zero parity
harness, draws-md5 protocol) as a reference implementation.

## Risks

- Codegen sensitivity (measured, the important one). The same batch loop
  that wins −27.7% on the production toolchain (math 5.3.0 bundle,
  Eigen 3.4.0, -fPIC) loses +17% wall on an isolated develop/Eigen-5
  translation unit: GCC cannot vectorize or reorder across per-record
  placement-`new` boundaries. Any rollout must gate on wall clock per
  toolchain, not just Ir, and the record loop should be restructured to
  avoid per-record placement-new (raw vptr store plus a memcpy'd value
  block) before broad adoption. LLVM codegen untested.
- Deployment hazard for layout-touching patches. bridgestan links a
  prebuilt `src/bridgestan.o`, compiled against pristine headers, into
  every model .so. A patched-headers build silently keeps the stale .o
  unless it is removed first (`rm src/bridgestan.o && make
  src/bridgestan.o`). Worth documenting wherever arena internals change;
  it will bite downstream packagers the same way.
- Migration discipline. Value comes from migrating the whole eltwise
  family. Per-op wins are proportional to the op's record count. Each
  batch should run a bitwise-parity gate battery (exact-zero gradient
  parity plus draws md5) before the next. The inventory says the seam is
  small, but the serialize family and the ODE/adjoint integrators hold
  varis across nesting boundaries and deserve an audit pass
  (pointer-stable pools keep their semantics. No code change expected, but
  verify).

## References

- Measurements, inventory scripts, patch, and gate harness:
  https://github.com/sims1253/apin, `stan/results/sota_arena_w47.md`
  (tax decomposition, microbench ceilings, span prototype and its codegen
  result), `stan/results/soa_var_w53.md` (pointer-semantics inventory,
  migration plan, the bit-identical slice and its −7.7%T / −8.2%G sampler
  measurement). Pre-registered protocols in `stan/WORKLOG.md` (W-47,
  W-53). I can attach any of it here or re-run on a model of the
  maintainers' choosing.
- stanc3 #1666 (`vectorize_loops`) targets the same eltwise complex from
  the codegen side. The lanes are complementary: on my battery, roughly
  two-thirds of the eltwise complex is expression glue, one-third tape
  machinery. math develop's Eigen 5 migration is a natural epoch for a
  representation change, if one is ever taken.
