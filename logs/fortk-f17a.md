# F-17a — Static cost-center decomposition of ONE fused NUTS transition (esnc-class)

Read-only static analysis, 2026-08-26, while F-16 owns the box. No builds, no benchmarks.
Baseline being decomposed: post-F-10 trunk (fortk/t2-coverage @ 4690a00, deps/stan carries the
scratch-hoist patch), esnc --sample 200 200: **2.070 ms / 400 transitions = 5.175 µs/transition**,
4079 grad evals (61 cache hits) ≈ **10.2 evals/transition** (treedepth ~3), direct grad floor
34.8 ns → **unattributed ≈ 4.75 µs/transition** (the target of section B).

All file:line anchors below are from the vendored/post-F-10 sources as read today.

---

## A. Annotated walk of one transition()

Call path from the driver (all layers):

```
stanli::run_nuts (runtime/src/nuts.cpp:79 step lambda, :98-101 loops)
 └─ adapt_diag_e_nuts::transition (deps/stan/.../nuts/adapt_diag_e_nuts.hpp:25)
     └─ base_nuts::transition (deps/stan/.../nuts/base_nuts.hpp:78)      [sam pler core]
         └─ build_tree recursion (base_nuts.hpp:249)
             └─ expl_leapfrog::evolve (integrators/expl_leapfrog.hpp, base_leapfrog.hpp:17)
                 └─ hamiltonian dtau_dp / dphi_dq (hamiltonians/diag_e_metric.hpp:32-50)
                     └─ base_hamiltonian::update_potential_gradient (base_hamiltonian.hpp:61)
                         └─ stan::model::gradient (deps/stan/src/stan/model/gradient.hpp:24)   <-- stringstream per call!
                             └─ stan::math::gradient (deps/math/.../rev/functor/gradient.hpp:46)
                                 └─ ExecutorModel::log_prob<var> (stanli model_adapter.hpp)
                                     └─ Executor::gradient (runtime/src/executor.cpp:381)      <-- alloc-free, ~35 ns
```

### A.1 Per-transition prologue (base_nuts.hpp:80-117)

| Line | Operation | Allocation? | Notes |
|---|---|---|---|
| :80 | `sample_stepsize()` | no | jitter=0 → no RNG, 1 store |
| :82 | `seed(q)` — copy q from `sample` | no | 80 B copy; **the carried `sample` type has DROPPED g and V — root cause of the redundant re-eval below** (stan/mcmc/sample.hpp:12 keeps only q, log_prob, accept_stat) |
| :84 | `sample_p` (diag_e_metric.hpp:44) | no | boost 1.87 **ziggurat** normals, n=10 draws + 10 sqrt; ~0.2-0.3 µs |
| :85 | `hamiltonian_.init(z_, logger)` | see A.4 | **THE carried-state re-eval** (W-20's ~1/transition redundancy; deterministic function of q, already computed last transition inside z_sample.g/.V) |
| :86 | `init_scratch()` | no | size check, early-out after first transition |
| :88-92 | `ps_point z_fwd(z_), z_bck(z_fwd), z_sample(z_fwd), z_propose(z_fwd)` | **16 heap pairs** | diag_e_point copy-ctor = q,p,g,inv_e_metric (4 Eigen allocs each). SURVIVED F-10 (hoist only covered build_tree + rho_extended) |
| :95-111 | 9 momentum `Eigen::VectorXd` constructions: p_fwd_fwd, p_sharp_fwd_fwd (dtau_dp RVO), p_fwd_bck, p_sharp_fwd_bck, p_bck_fwd, p_sharp_bck_fwd, p_bck_bck, p_sharp_bck_bck, rho | **9 heap pairs** | copy-ctors from z_.p / from each other; also survived F-10 |
| :115 | `H0 = hamiltonian_.H(z_)` | no | T = 0.5·p·(invM∘p) dot, no temp |

### A.2 Outer doubling loop (base_nuts.hpp:124-195), ~3 iterations at treedepth 3

| Line | Operation | Allocation? | Notes |
|---|---|---|---|
| :126-127 | `rho_fwd = VectorXd::Zero(n); rho_bck = VectorXd::Zero(n)` | **2 heap pairs PER iteration** (≈6/transition) | **F-10 GAP** — these live in the while-loop, the hoist only covered build_tree internals + rho_extended |
| :132 | direction `rand_uniform_()` | no | 1 mixmax draw per iteration |
| :134/:146 | `z_.ps_point::operator=(z_fwd/z_bck)` | no (reuse) | 3×80 B + V copy |
| :139/:151 | `build_tree(...)` by reference into z_propose / scratch | see A.3 | |
| :143/:155 | `z_fwd/z_bck.ps_point::operator=(z_)` | no | 240 B copy |
| :164-170 | z_sample selection; `rand_uniform_()` drawn ONLY in the else-branch (log_sum_weight_subtree <= log_sum_weight) | no | RNG draw count is DATA-DEPENDENT — lean-rewrite hazard |
| :172-173 | `log_sum_exp` merge | no | scalar overload (log_sum_exp.hpp:53): 1-2 exp + log1p |
| :176 | `rho = rho_bck + rho_fwd` | no | lazy expr, assign in place |
| :179-191 | 3× `compute_criterion` dot products (+3 more per internal build_tree node) | no | ~30 dim-10 dynamic dots/transition |

### A.3 build_tree (base_nuts.hpp:249-365) — leaf (depth 0), per leapfrog (×9.2 avg)

| Line | Operation | Allocation? | Notes |
|---|---|---|---|
| :256 | `integrator_.evolve` — 3 **virtual** calls (base_leapfrog.hpp:19-21) | 3 heap pairs | see below |
| — | `begin_update_p`: `z.p -= eps * dphi_dq(z)` | 1 pair | **dphi_dq returns z.g BY VALUE** (diag_e_metric.hpp:40) → copy materialized per call |
| — | `update_q`: `z.q += eps * dtau_dp(z)` | 1 pair | dtau_dp returns cwiseProduct **materialized to VectorXd** (:37) |
| — | `update_potential_gradient` → **the full stan::math::gradient wrapper** | see A.4 | 1× per leapfrog |
| — | `end_update_p` | 1 pair | another dphi_dq copy |
| :258-283 | `++n_leapfrog`, `H(z)`, divergence check, `log_sum_exp`, `sum_metro_prob`, `z_propose = z_` (ps_point copy, 240 B, no alloc), `dtau_dp` for p_sharp_beg (**1 pair**), `rho += p`, p_beg/p_end assigns | 1 pair | |
| Recursion :288-345 | scratch slots (F-10 — hoisted, no alloc); `z_propose_final = z_` per internal node (~7×240 B copies); multinomial uniform only in else-branch; rho_subtree merges | 0 | |

Per-leaf total: **~5 heap alloc/free pairs** (3 momentum temps + p_sharp + wrapper's internal pairs)
plus ~8-10 separate dim-10 dynamic-size Eigen loop executions (each with runtime-size setup).

### A.4 The gradient wrapper — what one eval costs beyond Executor::gradient (~35 ns)

Every `update_potential_gradient` (1×/leapfrog + 1×/transition at :85 + during init_stepsize) goes
through, in order (per eval):

1. **`std::stringstream ss;` constructed unconditionally** — model/gradient.hpp:25, the logger
   overload. Libstdc++ stringstream ctor+dtor ≈ 100-300 ns. Then `ss.str()` twice after (:29,:33).
2. `nested_rev_autodiff` (start_nested/recover): 3 vector push_backs/resizes + arena pointer
   save/restore — ~10-30 ns (autodiffstackstorage, start_nested.hpp, recover_memory_nested.hpp).
3. `Eigen::Matrix<var,-1,1> x_var(x)` — heap alloc (n×8 B) + n=10 `vari_value` arena allocations,
   **each pushing to `ChainableStack::var_stack_`** (vari.hpp:107) — ~60-100 ns.
4. Adapter (model_adapter.hpp, stanli-f7 post-1bfcbb5): theta_ element copy loop, W-20 memcmp
   against cache_theta_ (80 B compare), `std::vector<var> ops(q.data(), q.data()+n)` — **heap
   pair** — then `ex_->gradient(grad_.data())` (**the only real work, ~35 ns**).
5. `precomputed_gradients(value, ops, grad_)` — vari on arena + 2 arena arrays (varis, gradients)
   + `check_consistent_sizes` + copy loops (precomputed_gradients.hpp:118-145) — ~40-80 ns.
6. `grad(fx_var.vi_)` — walks var_stack_ (~11 entries), **11 virtual chain() calls** (10 no-ops +
   1 doing the n-FMA loop) (grad.hpp:24-36, precomputed_gradients.hpp:149-155).
7. `grad_fx = x_var.adj()` — 80 B copy into z.g; then base_hamiltonian negates z.V, z.g (:64-69).

Estimated wrapper cost: **~250-550 ns per eval, ×10.2 evals ≈ 2.6-5.6 µs/transition.** This is the
single largest candidate for the unattributed 4.75 µs. F-4b's "grad = 6.7% of wall" measured the
executor floor (34.8 ns × 10.2 ≈ 355 ns); the wrapper is counted as bookkeeping — i.e. most of it
lands in the unattributed bucket.

### A.5 Per-transition epilogue + adaptation + driver

| Where | Operation | Cost |
|---|---|---|
| base_nuts.hpp:197-205 | `z_ = z_sample` (240 B), final `H(z_)`, `return sample(z_.q, -V, stat)` — **sample ctor copies q → 1 heap pair** | ~30-50 ns |
| adapt_diag_e_nuts.hpp:28-41 (warmup only, 200/400 transitions) | `learn_stepsize` (2 pow + sqrt + exp, stepsize_adaptation.hpp:55-71) + `learn_variance` → welford `add_sample` only inside adaptation window (var_adaptation.hpp:17-28; **`Eigen::VectorXd delta(q-m_)` = 1 heap pair per warmup-in-window iter**, welford_var_estimator.hpp:26); at window END: sample_variance + regularization (1-2 pairs, rare) + `init_stepsize` re-search (extra sample_p normals + evals — a handful of iterations) | ~100-250 ns/warmup transition, ~0 post-warmup (adapt_flag_ disengaged at nuts.cpp:100) |
| nuts.cpp step lambda :79-96 | `s = sampler.transition(s, logger)` (move-assign frees old q), `s.cont_params(qd)` (copy), `get_sampler_params` (5 push_backs, capacity retained), stats row (array<double,7> amortized), `draws.emplace_back` per kept draw, `observe` null for CLI | ~50-100 ns |
| regions.cpp --sample | **timing brackets run_nuts only** (t_ex1_sample around :3859-3866); CSV write + constrained-column re-forward (ex0.run_forward_only per row) happen OUTSIDE the timed region; mallopt at :2868 | CSV NOT in the 5.175 µs |

### A.6 RNG inventory per transition (mixmax, boost 1.87; byte-identity-critical)

- 10 ziggurat normals (sample_p) — each 1+ engine draws (tail/wedge retries possible).
- 1 uniform per outer iteration for direction (~3).
- 1 uniform per z_sample accept **only in the else-branch** (~1-3).
- 1 uniform per internal build_tree multinomial **only in the else-branch** (~3-7).
- 0 for sample_stepsize (jitter 0), 0 for init/evals.
Total ≈ 13-23 engine draws/transition, count is data-dependent (branch structure must be
replicated exactly by any rewrite).

---

## B. Hypothesis table for the unattributed ~4.75 µs/transition

Budget arithmetic: 5.175 µs measured − 0.355 µs grad floor ≈ 4.82 µs. Estimates below are
orders of magnitude from code structure + F-10's empirical ~1.4 ns/removed-alloc-pair (lower
bound; glibc tcache pairs are typically 5-20 ns — the F-10 attribution is likely an
undercount). ALL rows to be confirmed by F-17's perf run.

| # | Hypothesis (cost center) | Est. µs/trans | Basis: calls × unit | Distinguishing signal |
|---|---|---|---|---|
| **H1** | **AD-wrapper around each grad eval** (stringstream ctor/dtor ×10.2, var tape: x_var varis + var_stack pushes, ops vector, precomputed_gradients vari, virtual chain walk, recover) — everything between `update_potential_gradient` and `ex_->gradient` | **2.3-4.5** | 10.2 × (250-450 ns); stringstream alone 10.2 × 100-300 ns | callgrind: `basic_stringbuf`/`_M_construct`, `vari_value::vari_value`, `precomputed_gradients_vari_template::chain` instruction share; rdtsc probe pair (wrapper vs executor); probe build with direct-double gradient seam |
| **H2** | **Eigen dynamic-size momentum ops + return-by-value temps** (dphi_dq copies z.g ×2, dtau_dp materializes ×2 per leaf; each op = separate runtime-size dim-10 loop) | 0.6-1.5 | ~5 pairs × 10.2 × (5-20 ns) + ~80-100 Eigen loop setups × 5-10 ns | instructions/branch-misses per transition; probe build with out-param dphi_dq/dtau_dp |
| **H3** | **ps_point residual copies + transition-start constructions** (16+9 pairs at :88-111, ~15 assigns × 240 B, 7 × z_propose_final copies) | 0.3-0.6 | ~25 pairs + ~4.5 KB memmove/transition | perf mem; probe build hoisting :88-111 to members |
| **H4** | **RNG** (10 ziggurat normals with /sqrt per element + ~13-23 mixmax uniforms) | 0.2-0.35 | ~25 draws × 8-15 ns | counting shim + isolated mixmax µ-bench |
| **H5** | **log_sum_exp scalar chain** (~8 leaves + 2×7 internal + 3 outer ≈ 25 calls, each exp+log1p+branches) | 0.2-0.4 | 25 × 8-15 ns | callgrind `log1p_exp` share |
| **H6** | **Virtual/indirect dispatch layers** (evolve→3 virtual calls/leaf; dtau_dp/dphi_dq/sample_p virtual — likely devirtualized by the template instantiation, VERIFY) + ~30 criterion dots | 0.1-0.4 | ~70 potential indirect calls + 30 dots | branch-misses; objdump/perf annotate for indirect-branch share |
| **H7** | **Adaptation (warmup half only)**: DA update + Welford add_sample (1 pair) amortized; window-end work rare | 0.05-0.15 | ~0.5 × (100-250 ns) | warmup-only rdtsc probe (phase flag) |
| **H8** | **Driver glue**: sample copy-ctor/assign, get_sampler_params, stats row, draws row | 0.05-0.1 | ~1 pair + ~10 small pushes | rdtsc around step lambda minus transition() |
| **H9** | **Outer-loop rho_fwd/rho_bck Zero allocations (F-10 gap)** | 0.01-0.06 | 6 pairs | same probe as H3 |
| H10 | CSV/telemetry | ~0 | outside timed region (regions.cpp) | n/a |
| H11 | icache cold effects | small | loop is hot over 400 iters | perf L1i-miss share |

Sum of ranges: 4.2-8.1 µs vs 4.82 available → **H1 is 50-90% of the bucket if the upper range
holds; H2+H3 are the solid second tier.** F-17's job is to split H1 from H2 — they are both
"per-eval overhead" but need different fixes (wrapper removal vs Eigen specialization).

---

## C. The four pre-registered designs, mapped to code

### C.1 Endpoint threading in base_nuts (the carried-state re-eval)

- **Where it happens**: base_nuts.hpp:82-85 — `seed(init_sample.cont_params())` copies q, then
  `hamiltonian_.init(z_, logger)` recomputes V and g at that same q. Both are deterministic
  functions of q (executor is deterministic), and the previous transition ALREADY computed them:
  `z_sample` is a ps_point whose `.V`/`.g` were copied from the evaluated leaf
  (build_tree :274 `z_propose = this->z_`; :169/:203). The redundancy is pure waste: ~1 eval per
  transition ≈ 9.7% of evals (matches F-10's ~400/4164).
- **Why the value gets lost**: `stan::mcmc::sample` (sample.hpp) carries only q + log_prob +
  accept_stat — g and V are dropped at the transition boundary.
- **What must thread**: only (q, V, g) at the transition seam. NOTHING needs to thread through
  build_tree's recursion — z_sample already carries V/g; the recursion is untouched. Two
  implementations:
  (a) base_nuts member `ps_point z_carry_` + skip `init()` when `init_sample.cont_params()`
      matches z_carry_.q byte-wise (in-fork patch, same mechanism F-10 established);
  (b) a 2-entry cache at the adapter seam: entry A = last eval (the W-20 cache), entry B =
      recorded at transition end (`z_sample.q/V/g`) and consulted at transition start — 400/400
      hits expected, vs 61/400 for the 1-entry version.
- **Bit-identity**: init consumes no RNG (sample_p runs before it, unchanged); V/g recomputed at
  the same q are bit-identical to the threaded copy; domain-error case leaves V=inf and g
  untouched on BOTH paths. Gate check: GRAD_COUNTER drop exactly == transitions (4079 → ~3679 on
  esnc 200+200).
- **Expected win**: one full eval ≈ 0.3-0.5 µs/transition (mostly wrapper cost, H1-priced).

### C.2 Warmup early-exit (step-drift gate + pilot burst) — stanli driver, NOT stan

- **Counters**: per-transition iteration count is implicit in the driver loop (nuts.cpp:98);
  window state lives in windowed_adaptation.hpp:80-110 (`adapt_window_counter_` incremented per
  `learn_variance` call, i.e., per warmup transition — var_adaptation.hpp:40/:44);
  stepsize DA counter in stepsize_adaptation.hpp:56. None of these are public — BUT the gate
  does not need them: `sampler.get_nominal_stepsize()` (base_hmc.hpp:184) and
  `sampler.z().inv_e_metric_` (base_hmc.hpp:168, diag_e_point.hpp:18 public member) are both
  readable from nuts.cpp.
- **Hook point**: extend the warmup loop in nuts.cpp:98-99 — after each transition, record
  (nom_epsilon, inv_e_metric); gate = |log(eps_t / eps_{t-k})| < tau AND relative L2 metric
  drift < rho sustained over a pilot burst of P further transitions, then break early and call
  `disengage_adaptation()` (which freezes eps via complete_adaptation, adapt_diag_e_nuts.hpp:45).
  Metric drift is only meaningful inside variance windows; check at window-scale intervals
  (k ≈ 25).
- **What it changes**: total warmup iterations — the post-warmup RNG stream and draw count
  differ from stock → **CANNOT be byte-identical; gate relaxes to statistical equivalence**
  (ESS/draw parity bands, R-hat, divergence rates vs stock at matched seeds; 3 reps).
  Plausible saving on esnc-class: windows end at 99/149/199 for W=200 — a gate firing after the
  2nd window (~iter 120-150) saves ~25-40% of warmup wall.
- **Guard**: never fire before the first variance window completes (metric would freeze at a
  25-sample estimate); keep `init_stepsize` re-search behavior at whatever window boundary the
  gate lands after (it runs inside learn_variance's `update` path, untouched).

### C.3 Deeper base_nuts surgery beyond F-10

Ranked by expected yield from section B:
1. **Momentum-temp elimination** (H2): change `dphi_dq`/`dtau_dp` to write into caller-owned
   buffers (out-params) in the vendored diag_e_metric + expl_leapfrog (in-fork patch, same
   carried-patch mechanism). Kills ~4 pairs + 4 loop setups per leapfrog. Bit-identity: same
   arithmetic, same order.
2. **Hoist the transition-start constructions** (H3/H9): :88-111 (4 ps_points + 9 vectors) and
   :126-127 (rho_fwd/rho_bck per iteration) into F-10-style scratch members. ~31 pairs/transition.
3. **Fixed-size Eigen for small dims** (H2): ps_point is a non-template class used across
   stan/mcmc — templating it is upstream-scale surgery. Cheaper 80%: keep VectorXd but note the
   F-10 lesson — allocation is ~1.4 ns/pair here; the REAL cost is per-op loop setup. Recommend
   NOT templating dims; instead reduce the NUMBER of separate dim-10 ops (fuse momentum updates
   by hand: p update and p_sharp share one pass — requires care to preserve op order → NOT
   bit-identical if reassociated; keep expression structure identical).
4. **z_propose copy discipline**: leaf `z_propose = z_` (×8) and internal `z_propose_final = z_`
   (×7) are semantically required; can only shrink by narrowing ps_point copies to (q,V,g) —
   they already skip the metric. Low yield; skip.

### C.4 Lean-loop rewrite (walnutpie-style minimal NUTS over ExecutorModel)

**What it drops** (all of H1 + most of H2/H3/H6):
- the var-tape pretense entirely — call `ex_->gradient(double*)` directly into z.g (no var, no
  precomputed_gradients, no nested_rev_autodiff, **no per-eval std::stringstream**);
- ps_point/diag_e_point hierarchy → flat struct, buffers allocated once;
- callbacks::logger plumb-through, stan::mcmc::sample (keep raw q + scalars);
- virtual hamiltonian/integrator dispatch → inlined leapfrog step;
- stan::services adaptation wrappers → own copy of the schedule.

**What it must reproduce bit-for-bit for the byte-identity gates**:
1. **RNG stream order and COUNT** — incl. data-dependent draws: direction uniform per outer
   iteration; accept uniforms drawn ONLY in else-branches (base_nuts :168, :343); ziggurat
   normals in sample_p element order with the `/sqrt(inv_e_metric(i))` op; init_stepsize search
   (driver-initiated, easiest to keep calling stock code for).
2. **FP op order** — every Eigen expression must keep its structure: dim-10 dot reductions,
   `p -= eps * g` elementwise, `T = 0.5 * p.dot(inv ∘ p)`, log_sum_exp/log1p_exp call sequence,
   the negations z.V = -logp / z.g = -grad (base_hamiltonian :64-69). FMA contraction is the
   hazard: hand-rewritten loops can fuse differently than Eigen's kernels at the same -O flags.
3. **Adaptation schedule** — DA formula (stepsize_adaptation :55-71), Welford update + the
   n/(n+5)/1e-3·(5/(n+5)) regularization (var_adaptation :26-28), window constants 75/50/25
   (nuts.cpp:62), window-end `init_stepsize` re-search + `set_mu(log(10·eps))` + `restart()`.
**What CAN'T stay bit-identical in practice**: (a) any FMA/reassociation slip in the lean
leapfrog — last-ulp divergence compounds through log_sum_weight comparisons and can flip an
else-branch, changing RNG consumption (silent draw-stream divergence — the nastiest failure
mode); (b) if coupled with C.2 early-exit, adaptation timing itself diverges. **Gate that
relaxes**: statistical equivalence — matched-seed K-S/ESS-band + divergence-rate parity + R-hat,
plus a bounded-drift check (N first draws' lp__ within 1e-9 relative before streams may diverge).
**Recommendation**: phase the rewrite — step 1 keeps stock stan leapfrog arithmetic and only
replaces the gradient seam (C.5 below), which IS bit-identical; the full lean loop only if F-17
shows residual H2/H3 ≥ 1 µs after step 1.

### C.5 (NEW, from this reading) The direct-double gradient seam — H1 without touching base_nuts

`base_hamiltonian::update_potential_gradient` (base_hamiltonian.hpp:61) and `init` (:48) are
both **non-virtual**, and `expl_leapfrog`/`base_nuts`/`base_hmc::init_stepsize` reach them
through the concrete `Hamiltonian` template parameter (static dispatch). A stanli-side
`diag_e_metric_direct : stan::mcmc::diag_e_metric` that SHADOWS BOTH (`update_potential_gradient`
— note `init` internally calls the BASE version, so shadowing init too is required to intercept
the transition-start :85 eval) to call `ExecutorModel::gradient_direct(q, V, g)` (raw doubles,
same negation convention V=-logp/g=-grad, same catch→V=inf-leaves-g semantics) — plus a
stanli-side copy of adapt_diag_e_nuts instantiating base_nuts with it — removes the ENTIRE
wrapper (stringstream, var tape, ops vector, chain walk) with **zero change to deps/stan
transition logic**. Same doubles, same order, no RNG → draws byte-identical by the same argument
F-10's cache used. This is the cheapest test of H1 and the single most promising lever; it also
composes with C.1 (the :85 eval it misses is the one C.1 deletes).

---

## D. Recommended F-17 measurement plan (runs AFTER F-16 frees the box)

### D.1 Instruments, mapped to hypotheses

1. **rdtsc probe build (primary, cheapest)** — 3 counters on a probe binary (never merged):
   (a) whole `transition()`, (b) bracketing `ex_->gradient()` inside the adapter, (c) bracketing
   `stan::model::gradient` in a shimmed `update_potential_gradient`. Differences give
   executor / wrapper / rest per transition directly → splits H1 vs (H2+H3) vs H4-H9.
   Run esnc --sample 200 200, report median per-phase µs over the 400 transitions, warmup and
   sampling separated (isolates H7).
2. **callgrind on 100 transitions** (deterministic, box-load-immune): instruction counts per
   function — `std::__cxx11::basic_stringbuf` (H1-stringstream), `vari_value` ctor /
   `precomputed_gradients_vari_template::chain` (H1-tape), `log1p_exp` (H5), mixmax (H4),
   Eigen kernels (H2), malloc/free (H2/H3 total pairs). Callgrind's exact instruction counts are
   the cleanest per-hypothesis attribution; wall from perf, attribution from callgrind.
3. **perf stat** (`-e cycles,instructions,branches,branch-misses,L1-dcache-load-misses` adaptive
   sampling around the sampling loop): branch-miss share tests H6 (indirect dispatch);
   dcache-miss + malloc counter (`perf stat -e dummy`) tests the alloc-pair accounting.
4. **A/B probe builds per lever** (the decisive discriminator once H1 is confirmed):
   - lever-1 build: C.5 direct seam (byte-identity gate applies);
   - lever-2 build: C.1 endpoint threading (GRAD_COUNTER arithmetic gate);
   - lever-3 build: C.3.1+C.3.2 hoists (byte-identity gate).
   Each vs trunk, same-loop interleaved ratios (F-4b's instrument rule).

### D.2 Models

- **esnc** (dim 10, treedepth ~3): the decomposition target — bookkeeping-dominated.
- **blr**: second bookkeeping class (28.5 evals/transition — H1 scales with evals, H3 doesn't:
  the eval-count scaling itself is a discriminator).
- **hier_2pl** (92% grad): control — NO bookkeeping lever should move its wall more than noise;
  a change there means something broke (regression tripwire).

### D.3 Pre-registration draft for F-17's gates

- **G0 (environment)**: quiet box post-F-16 (same rules as F-16; no concurrent builds;
  same-loop interleaved ratios only).
- **G1 (attribution completeness)**: rdtsc three-way decomposition accounts for ≥ 80% of the
  5.175 µs/transition baseline within overlapping error bars; H1 confirmed/rejected by
  explicit numbers.
- **G2 (lever-1, direct seam)**: draws BYTE-IDENTICAL vs trunk on esnc/blr/hier_2pl --sample
  200 200; ctest 64/64; esnc nuts-loop wall target ≥ 1.3x trunk (H1 mid-range predicts
  ~1.5-1.9x; informative-if-miss with the decomposition attached); hier_2pl parity within noise.
- **G3 (lever-2, endpoint threading)**: GRAD_COUNTER drop == transitions exactly (esnc
  4079 → ~3679); draws byte-identical; wall gain ≥ the measured per-eval wrapper cost (cross-check
  against G1's H1 number).
- **G4 (lever-3, hoists)**: draws byte-identical; informative wall target ≥ 1.05x.
- **G5 (statistical levers only)**: C.2 early-exit — no byte-identity claim; ESS/draw within
  ±10% of stock, R-hat < 1.01, divergence rate not worse, on esnc/blr/kidscore, 3 reps.
- **Ordering**: G1 first (nothing else is pre-registered until H1 is sized); then levers in
  measured-yield order; levers compose only after individual gates pass (F-11's
  multiplicative-attribution lesson).

---

## E. Verdict summary

The unattributed 4.75 µs is most plausibly dominated by the **var-tape gradient wrapper**
(H1: stringstream per eval + vari machinery + virtual chain walk, ×10.2 evals/transition) —
NOT by base_nuts tree bookkeeping itself (F-10 already took the cheap alloc wins there; the
residual ps_point/Eigen costs are the second tier, H2/H3). The wrapper is removable with a
non-virtual seam swap at the stanli side (C.5) at zero bit-identity risk, before any lean-loop
rewrite is attempted. Endpoint threading (C.1) is a clean second ~0.3-0.5 µs. Warmup early-exit
(C.2) buys wall, not per-transition cost, and pays in statistical-gate currency.
