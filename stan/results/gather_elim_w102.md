# W-102: gather/index-copy elimination in rvalue<index_multi> — ALL GATES PASS

Branch class: pure restructuring, bit-identity gates (no FP arithmetic
changes anywhere; values, order, and accumulation identical).

## Premise correction (important)

The pre-registration located the code at "prim/fun/rvalue.hpp" in
stan-math. That file does not exist — in Stan 2.36+ the indexing
machinery lives in the **stan repo**: `stan/src/stan/model/indexing/`
(index types, rvalue, assign), inside the cmdstan bundle and in the
cmdstan/stan submodule. stan-math's involvement is limited to
`prim/meta/holder.hpp` (make_holder machinery), which needs NO changes.
Consequences:

- math_dev_soa (soa-eltwise-batch-records lineage): ZERO edits; no
  `gather-elimination` branch was created there (an empty branch would
  falsely imply math edits). The SoA lineage is untouched by design.
- The "two-tree pattern" collapses to the two trees that actually hold
  the files: **bundle** `scratch/w53/bs_w53/stan` (model builds + gates,
  working-copy edits) and **develop** `external/cmdstan/stan` (real git
  repo, submodule of external/cmdstan @ d13c50c0f, 2.38 lineage;
  branch `gather-elimination` created off that HEAD, commit faa973bb7).
  index.hpp was byte-identical across both trees before the edit; the
  only pre-existing tree difference is `Eigen::all` vs
  `Eigen::indexing::all` in rvalue.hpp (untouched).

## AUDIT — where the per-call vector<int> deep copies happen

Per logp_grad call on hier_2pl (I=32, J=600, N=19200; 4424 log_prob
calls in the W-29 protocol run; 4493 bs_log_density_gradient calls):

1. **THE COPIES (1.023e9 Ir = 3.35% of G)** —
   `stan/src/stan/model/indexing/index.hpp:35-45` (pre-edit):
   `struct index_multi { std::vector<int> ns_; }` stores the index
   vector BY VALUE, and its forwarding constructor
   `ns_(std::forward<T>(ns))` copy-constructs from lvalues.
   stanc3-generated code (hier_2pl.hpp:278-284) calls
   `rvalue(alpha, "alpha", index_multi(ii))`,
   `rvalue(theta, "theta", index_multi(jj))`,
   `rvalue(beta, "beta", index_multi(ii))` — `ii`/`jj` are lvalue
   model DATA members (immutable across the run), so each construction
   deep-copies 19,200 ints: **3 copies × 76.8KB per logp_grad call**.
   Callgrind evidence (W-59 patched dump, caller edges from model
   log_prob): `std::vector<int>::vector(const&)` calls=4424 ×3,
   costs 341,510,953 + 341,028,423 + 340,665,336 = 1,023,204,712 Ir.
2. **Holder heap-move (small, NOT the ints)** —
   `stan/lib/stan_math/stan/math/prim/meta/holder.hpp:377-382`:
   `holder_handle_element(T&& a, T*& res) { res = new T(std::move(a)); }`
   heap-moves the rvalue index_multi for the lazy Holder expression
   (`operator new(24)` visible at hier_2pl_model.so:0x20654 in the
   rvalue disassembly). The vector<int> MOVE steals the buffer (no int
   copy). Left unchanged (generic math machinery; ~1 new+delete pair
   per rvalue call, ~13K/run, negligible Ir).
3. **rvalue check loops (2.80e9 Ir = 9.9% of G)** —
   `rvalue.hpp:158-172` (vector[multi]) and matrix[multi] paths:
   `for (auto idx_i : idx.ns_) check_range(...)`. Disassembly
   (0x20620-0x20646): 8 Ir/element scalar loop (load, test, jle, cmp,
   jg, add, cmp, jne) with check_range fully inlined. Bounds checking
   is the behavioral contract — KEPT IDENTICAL (same loop, same order,
   same throw on first offender).
4. **Who does NOT copy**: `bernoulli_logit_lpmf(const
   std::vector<int>& y, ...)` — const& ✓; `rvalue(..., MultiIndex&&)`
   ✓; `subtract`/`elt_multiply` take `const Holder&` ✓. The only
   forcing shape is index_multi's by-value `ns_` — an INTERNAL holder,
   changeable without touching any math API.

## IMPLEMENTATION

`index.hpp` — new `stan::model::internal::multi_index_view` replaces
`std::vector<int>` as the type of `index_multi::ns_`:

- lvalue `std::vector<int>` -> **view** (ptr+size, no copy) — the
  generated-code path; caller must keep the vector alive (model data
  members always do).
- rvalue `std::vector<int>` -> **move-own** (storage stolen).
- other integral vectors (e.g. `vector<size_t>`) -> converting copy
  into owned storage, exactly as before.
- copy of a view -> **always deep-own** (a copy never depends on the
  original's lifetime); moves keep the storage relationship.
- read-only interface `size()/data()/operator[]/begin()/end()/empty()`
  is source-compatible with every in-repo consumer (rvalue.hpp,
  rvalue_at.hpp, rvalue_varmat.hpp, assign.hpp, tests) — none changed.

Test helper adaptation (`test/unit/model/indexing/util.hpp`):
`convert_to_multi` returned `index_multi(v)` where `v` is a local
vector that dies at return — with view semantics that would dangle, so
5 sites became `index_multi(std::move(v))` (restores stock ownership
semantics for the returned object); added `<utility>` include.

Semantic caveat for any upstream port: lvalue construction now VIEWS
rather than copies — an implicit lifetime-contract change of the public
`index_multi` struct. All in-repo call sites verified (generated code
always passes long-lived data members; tests consume within scope).

No FP arithmetic is touched anywhere: the view yields the identical
int sequence to the check loop and the `Eigen::Map<const Array<int>>`
gather in the make_holder lambda.

Trees: identical edits in `scratch/w53/bs_w53/stan` (bundle) and
`external/cmdstan/stan` (develop, branch `gather-elimination` @
faa973bb7). Patch: `scratch/w102/w102_gather_elim_stan.patch`.
Standalone behavioral check (scratch/w102/w102_behavior):
gather values correct, **0 allocations** in the lvalue-index rvalue
path (stock: 1 deep copy + holder move), identical
`std::out_of_range` on bad indices, rvalue-idx owns, matrix[multi]
path correct, copy-of-view independent of source mutation.

## GATES (all PASS)

- **(a) Parity**: 4 models × 100 deterministic points, stock refs
  dumped FRESH, patched rebuilt .so compared: hier_2pl / kronecker_gp /
  gp_regr / accel_gp all `PASS: value_mismatch=0/100 grad_mismatch=0/100`
  (exact-zero, np.array_equal).
- **(b) Draws md5** (W-29 protocol: warmup 100, samples 50, seed
  20260819, pf init rep0 chain_0, --metric-window 50, build_w36exp
  stan_cli READ-ONLY): stock and patched BOTH
  `fe7c57c99a7a6530ce2dcc408d6e9c65`, `cmp` identical — equal to the
  recorded W-53..W-59 lineage value. The callgrind-run draws.csv has
  the same md5.
- **(c) Callgrind** (single patched arm vs RECORDED W-59 reference,
  same binary lineage/protocol, valgrind 3.23 ~/vginstall):
  - T: 30,514,462,110 -> 29,497,308,808 = **−3.33%**
  - G (bs_log_density_gradient inclusive): recorded 28,087,600,877 ->
    27,068,343,850 = **−1,019,257,027 Ir = −3.63%** — PASS the ≥1%
    bound, inside the pre-registered −3..−6% band.
  - Attribution: the vector<int> copy-ctor function is GONE from the
    profile (0 occurrences; was 1,023,204,712). rvalue<Matrix<var>&,
    index_multi> 1,869,157,696 -> 1,869,148,848 (−0.0005%) and
    rvalue<Map<var> const&, index_multi> 934,605,392 -> 934,654,056
    (+0.005%): check loops intact, layout noise only.
  - Protocol identity: 4493 gradient calls, 69 rejected evals —
    matches the W-59 reference run exactly.
  - Transparency note: develop-tree test compiles ran concurrently
    with the callgrind job (2-core budget); Ir is a deterministic
    simulated counter, unaffected by load (wall gates were never part
    of W-102).
- **(d) Unit tests** (develop stan, gather-elimination branch,
  runTests.py -j2): index_test 6/6, rvalue_test 28/28,
  rvalue_index_size_test 5/5, assign_test 50/50, deep_copy_test 6/6,
  rvalue_varmat_test 47/47, assign_varmat_test 50/50 —
  **192/192 PASS**. (assign_cl/rvalue_cl skipped: the OpenCL
  multi-index path uses matrix_cl<int>, not index_multi.)

Build hazards respected: bs_w53/src/bridgestan.o removed and rebuilt
before model rebuilds; model_*_patched/*.so deleted (compile_model
cache); env -u LD_LIBRARY_PATH; /usr/bin/make -j2; one callgrind job.

## Cumulative position

On the batch012+fused lineage: G 28,087,600,877 (W-59) ->
27,068,343,850 (W-102) on top of the stock->W-59 −19.06%; draws md5
unchanged throughout. The remaining gather complex (~2.8e9 Ir) is the
mandatory per-element bounds-check loop (8 Ir/elem) plus the lazy
IndexedView construction — behavior-bound, not removable without
changing the checking contract (e.g. vectorized first-offender scan
would be a separate, riskier pre-registration).

## Artifacts

- Develop branch: external/cmdstan/stan `gather-elimination` (faa973bb7)
- Bundle edits: scratch/w53/bs_w53/stan/src/stan/model/indexing/index.hpp,
  scratch/w53/bs_w53/stan/src/test/unit/model/indexing/util.hpp
- Patch: scratch/w102/w102_gather_elim_stan.patch
- Gates: scratch/w102/gate_draws_w102.sh, scratch/w102/draws_w102/,
  scratch/w102/run_callgrind_w102.sh, scratch/w102/profile_w102/
- Rebuilt .so: scratch/w53/model_{hier_2pl,kronecker_gp,gp_regr,accel_gp}_patched/
- Behavioral check: scratch/w102/w102_behavior (source /tmp/w102_behavior.cpp
  copied below)
