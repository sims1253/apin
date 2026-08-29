# F-10 log — sampler-loop package (2a scratch-hoist + W-20 endpoint cache + mallopt)

Started: 2026-08-26. Binding scope: WORKLOG "F-10 pre-registered BEFORE building".
Worktree: external/stanli-f7, branch fortk/t2-coverage @ 9b2bf80 (F-12 consolidated).

## Session start

- Read in order: WORKLOG (F-12 VERDICT + F-10 pre-reg), stan-2a2-scratch-hoist-PLAN.md,
  logs/fortk-f4b.md (census: 630 heap allocs/transition; esnc 10.41 grads/iter exact;
  85-95% bookkeeping share), HANDOFF item A (W-20: exactly 1 redundant grad/transition,
  gate = bit-identical draws).
- Plan of record (sequencing): (0) build PRE-PATCH (stock) binary FIRST and keep a copy;
  (i) deps/stan patch applied ATOMICALLY (patch file under patches/deps-stan/ in fork +
  deps/fetch.sh idempotent hook + apply once + verify git diff == patch) — another agent
  waits on this; (ii) W-20 1-entry grad cache at ExecutorModel adapter seam; (iii) mallopt
  in regions.cpp sampling driver; then gates (a)-(d).

## Log

### ATOMIC DEPS/STAN PATCH APPLICATION — COMPLETE (2026-08-26 20:22)

**deps/stan (shared, symlinked into other worktrees) now carries the 2a
scratch-hoist patch, applied ATOMICALLY. Other agents/builds may proceed
against it.** Evidence:

- Patch: `patches/deps-stan/0001-base_nuts-scratch-hoist.patch` in the fork
  (tracked, commit e750504), 6 hunks, applied with `git apply` (atomic,
  all-or-nothing) — never a partial state on disk.
- `git -C deps/stan status --short` = exactly ` M src/stan/mcmc/hmc/nuts/base_nuts.hpp`;
  `git -C deps/stan diff --stat` = 1 file, +63/-13; reverse-apply check PASSES
  (working tree contains exactly the patch); patch-id 1b61ada9c25da5d41c0612de908711e2ef7814a3;
  file content byte-identical (cmp) to the reviewed patched source.
- `deps/fetch.sh` (tracked) now applies the patch after fetching stan
  $STAN_SHA, idempotently: `git apply --check --reverse` succeeds => "already
  applied" skip. NOTE (bug caught pre-apply): deps/stan is a SYMLINK to
  ../../stanli/deps/stan, so a repo-relative patch path resolves against the
  PHYSICAL repo dir and misses; the hook anchors the patch path at the
  script's own $PWD. Fresh clones (real dir) and symlinked worktrees both work.
- Full `fetch.sh` NOT re-executed (would re-fetch/checkout the shared repo
  while other lanes build); the hook's apply logic was executed verbatim by
  hand instead.

Hunk summary vs the PLAN (d13c50c0f -> vendored c96d0411): the file is
structurally IDENTICAL in all touched regions (verified by full read); only
line numbers shifted. Adaptation notes: (a) the PLAN's H1 member block landed
after `bool divergent_;` with a `private: init_scratch()` sizer (PLAN's
"resize on first transition" option); z_propose_final uses a PER-DEPTH
ps_point stack (the PLAN's "if cleanest" alternative) since ps_point has no
default ctor; (b) H2 exactly as planned — per-depth refs for p_init_end,
p_sharp_init_end, rho_init (setZero), p_final_beg, p_sharp_final_beg, rho_final
(setZero), z_propose_final (assign where the copy-ctor stood, AFTER child1),
rho_subtree (3 sequential reuses keep the one buffer); (c) H3 exactly as
planned (rho_extended member, 2 reuses). rho_fwd/rho_bck in the transition
loop left ALONE (not in the PLAN). Leaf z_propose=this->z_, compute_criterion,
integrator/hamiltonian internals, RNG order: untouched per the never-touch
register. Recursion-safety: node at depth d uses slot d only; children d-1;
ps_point/vector slots never alias across levels.

Stock binary preserved BEFORE any of this: bench/fortk_f10/fortk_t1r.stock +
stanli_run.stock (copies of build-f7 @ 9b2bf80, suite 63/63, binaries newer
than all sources — verified pre-copy).

## Implementation (ii) + (iii), build

- (ii) ExecutorModel (runtime/include/stanli/model_adapter.hpp): 1-entry cache
  in log_prob<var> — per-call theta_ scratch, memcmp vs cache_theta_ (byte
  identity, full n), hit => precomputed_gradients(cache_value_, ops, grad_)
  with grad_ itself as the gradient half (only ever written by gradient(),
  read by precomputed_gradients); miss path unchanged + stores theta/value.
  Exception path NOT cached (deterministic executor: a throwing theta can
  never be in the cache). Kill switch STANLI_ENDPOINT_CACHE=0. NOTE: walnuts
  does NOT pass through ExecutorModel (own ExecLogpGrad functor ->
  ex->gradient directly), so the cache serves the NUTS/optimizer/pathfinder
  seam only — as pre-registered ("read how nuts.cpp calls it").
- Counters: Executor gains n_endpoint_cache_hits()/note_endpoint_cache_hit()
  (graph.hpp); the tool prints GRAD_COUNTER exec0/hits0/exec1/hits1/iters/gpi
  around each --sample run pair. Hits skip gradient() so the existing
  n_grad_evals drops by construction.
- (iii) regions.cpp main(): mallopt(M_MMAP_THRESHOLD, 64 MiB=67108864) +
  mallopt(M_TRIM_THRESHOLD, 128 MiB=134217728) before anything allocates
  (values = F-2b finding; trim = 2x mmap, glibc's default coupling); prints
  MALLOPT line. Child processes (stanc/clang) exec fresh spaces, unaffected.
- Rebuild: graph.hpp touched by nearly every TU -> full lib rebuild; first
  make -j4 OOM-killed cc1plus (concurrent lanes), -j2 clean. nuts.cpp.o /
  regions.cpp.o verified rebuilt (stale-.o runbook), binaries relinked.

## GATE RESULTS

### (a) BYTE-IDENTICAL draws — PASS (all 3 models)

--sample 200 200, default init, seed 20260826, chain 1, taskset -c 2, stock
binary (bench/fortk_f10/fortk_t1r.stock @ 9b2bf80) vs patched (all three
parts active). cmp of sample_nuts_seed20260826_chain1.csv:
- eight_schools_noncentered: BYTE-IDENTICAL
- blr: BYTE-IDENTICAL
- hier_2pl: BYTE-IDENTICAL
Cross-checks: cache-OFF patched CSVs also byte-identical to cache-ON
(STANLI_ENDPOINT_CACHE=0); pf-init smoke works (F-9 signature reproduced:
2/4 paths fail on blr, khat 0.080). The tool-internal "bitwise=NO" lines
compare ex0-vs-ex1 (unfused-vs-fused, the known statistical-equivalence
class, F-4 doctrine) — the GATE compares the fused CSV across binaries.

### (b) Grad counter — MECHANISM VERDICT: arithmetic exact, pre-registered
### expectation (drop == transitions) NOT met; W-20's redundancy confirmed
### present but NOT adjacent; honest FAIL of the 1-entry-capture assumption

Exact counters (GRAD_COUNTER, 400 transitions = 200 warmup + 200 draws):

| model | arm | exec1 evals | gpi | hits | drop |
|---|---|---|---|---|---|
| esnc | cache OFF | 4140 | 10.350 | 0 | — |
| esnc | cache ON | 4079 | 10.198 | 61 | 4140-4079 = 61 = hits EXACT |
| blr | cache OFF | 11480 | 28.700 | 0 | — |
| blr | cache ON | 11418 | 28.545 | 62 | 11480-11418 = 62 = hits EXACT |
| hier_2pl | cache OFF | 15184 | 37.960 | 0 | — |
| hier_2pl | cache ON | 15166 | 37.915 | 18 | 15184-15166 = 18 = hits EXACT |

- Instrument validated: cache-OFF exec0 on esnc = 4164 evals, gpi 10.4100 —
  the F-4b census number (10.41, its cross-check vs stanli_run's own 4164)
  EXACTLY. Expected ~9.41 net per pre-registration; measured 10.198.
- Mechanism (read from base_nuts + counters): the W-20 redundancy is REAL —
  every transition's hamiltonian_.init re-evaluates theta_start, already
  evaluated mid-tree in the previous transition (~400/run ≈ 9.7% of evals) —
  but stan NUTS's LAST eval of a transition is its far-end leaf, NOT the
  carried state (z_sample is evaluated mid-tree; line-202 H() uses cached
  z.V, no eval). A 1-entry cache captures only ADJACENT duplicates: the 61/
  62/18 hits are depth-1 transitions whose single leaf IS z_sample (=
  last eval). W-20's dups==iters+1 arithmetic held on walnutpie because its
  transition evaluates its endpoint LAST. Full capture on stan NUTS requires
  W-20's original design — threading (theta, grad, lp) through sampler
  state (z_sample already holds V/g from its leaf eval; the next
  transition's init could reuse them) — which touches the hamiltonian-init
  path, outside F-10's charter. Cache arithmetic itself is provably correct
  (drop == hits everywhere; draws byte-identical on AND off).

### (c) Perf: sampler walls --sample 200 200, 3 reps medians, interleaved
### stock/patched per rep, taskset -c 2, load 5.1-6.2 (other lanes' cc1plus;
### recorded per rep) — TARGET >= 1.1x MET on esnc + blr; hier_2pl parity
### (expected: grads dominate)

| model | exec tier | stock med s | patched med s | ratio |
|---|---|---|---|---|
| esnc | fused (exec1) | 0.002415 | 0.002070 | **1.167x** |
| esnc | unfused (exec0) | 0.003866 | 0.003582 | 1.079x |
| blr | fused | 0.008079 | 0.006362 | **1.270x** |
| blr | unfused | 0.015456 | 0.012461 | 1.240x |
| hier_2pl | fused | 3.5648 | 3.6181 | 0.985x |
| hier_2pl | unfused | 8.2810 | 7.9032 | 1.048x |

(--census does not exist on the consolidated branch — 0243aad was not in
the F-12 cherry-pick set; --sample 200 200 walls + exact counters are the
same instrument family: sampler-phase-only, ex0+ex1 per invocation.)

Ranked breakdown (target met on the gated models; hier informative):
- mallopt-only arm (stock binary + LD_PRELOAD shim calling the same
  mallopt pair, 3 reps): esnc 0.997x, blr 1.023x, hier 0.943x (last within
  load noise) — mallopt is NEUTRAL on this runtime's sampler loop
  (stanli's arenas don't hit the glibc pathology F-2b found in the bare-C
  host; kept as documented insurance).
- endpoint cache: ~0 wall effect by arithmetic (61 hits x ~0.035 us/call
  ≈ 2 us of a 2.1 ms run on esnc; 1.5% of evals).
- scratch-hoist: effectively the WHOLE win. Bookkeeping-share estimate
  (cheap counter method, no perf available): esnc fused stock = 4140
  evals x ~0.035 us ≈ 0.145 ms of 2.415 ms wall (6% grad share, matches
  F-4b's 6.7%) => bookkeeping ≈ 2.27 ms; patched cuts ~0.35 ms ≈ 15% of
  the bookkeeping side, ≈ 1.4 ns per removed alloc/free pair (~252k pairs
  = 630/transition x 400) — consistent with tcache-hit costs. hier_2pl
  fused: ~15.2k evals x ~215 us ≈ 3.3 s of 3.6 s wall (≈ 92% grad share)
  => the ~15% bookkeeping cut is invisible under ±5% load noise — as the
  charter predicted ("expect smaller — grads dominate there").

### (d) ctest — PASS: 63/63 (build-f7, post-everything).

## Deliverables / state

- Fork fortk/t2-coverage: e750504 (patch file + fetch.sh hook),
  1bfcbb5 (adapter cache + counters + mallopt + GRAD_COUNTER). NOT pushed.
- deps/stan: exactly the one patch applied (M base_nuts.hpp, +63/-13,
  reverse-apply check passes); fetch.sh reproduces it idempotently.
- Bench artifacts: bench/fortk_f10/{stock,patched,nocache}/logs+CSVs,
  walls.txt, walls_shim.txt, cache/ (shared emit cache), fortk_t1r.stock.
- Open item handed to the next session (needs its own pre-registration):
  endpoint threading inside base_nuts (reuse z_sample's (V,g) for the next
  transition's init) — worth ~9.7% of gradient evals on esnc-class, more
  on hier_2pl (~1/38 evals there is a smaller fraction but the evals are
  expensive); requires touching the never-touch register's hamiltonian
  init path, so it was NOT done under F-10.
