# F-4b log — single-region direct path + sampler-overhead census (fortk lane)

Started: 2026-08-26. Binding scope: WORKLOG "F-4b pre-registered BEFORE building".

## Session start

- Read: WORKLOG fortk lane (F-4 verdict + F-4b pre-reg), logs/fortk-f4.md, logs/fortk-f3.md.
- Inherited: external/stanli branch fortk/t1-regions @ d1f234d (parent fortk/t1-emitter
  @ a2e8615), clean, not pushed. Suite 63/63 at handoff.
- F-4's motivating finding (the item-(i) target): esnc region fns 22.7-25.3 ns vs
  F-3 single-fn 19.4 ns (+17-30%) — the executor's two-call Kernel ABI (fwd ctx
  refresh, bwd ctx refresh) forces a partial round-trip through scratch that F-3's
  single-function scope kept in registers. Visible only on overhead-bound models.

## Scope (binding)

(i) Direct path: extend tools/fortk/regions.cpp so a carved graph that is EXACTLY
one region covering all ops ALSO emits `void fortk_grad_direct(const double* params,
int nparams, double* grad_out, double* logp_out)` — one call: fwd sweep into
scratch/arena, adjoint memset+seed, reverse sweep, harvest params' adjoints; no
dispatch tables, no ctx objects, one function scope. Tool mode: verify AND bench
through fortk_grad_direct alongside the executor-installed path.
GATES: (a) grad rel-L2 < 1e-9 AND logp rel < 1e-9 vs UNMODIFIED executor gradient
at 64 seeded points (seed 20260826) on esnc/blr/diamonds; (b) esnc direct-path
µs/call within noise of 19.4 ns (F-3), taskset-pinned, 3-rep medians, kernel-only
in-C loop; report blr/diamonds too. Never loosen gates.
Additive only; no runtime source changes; commits on fortk/t1-regions or child;
no push.

(ii) Census (informational, no gate): stanli_run nuts/walnuts on esnc + blr, fused
executor-installed vs unfused, fixed seed, 200/200 warmup/draws, 3 reps; decompose
total wall, iters/sec, implied grad share from item-(i) µs/call × est grads/iter at
observed treedepth. Table model × {unfused, fused} × {nuts, walnuts}.

## Design (pinned before coding)

- Eligibility: plans.size()==1 AND plans[0] covers g.ops[0..n) AND live_out ==
  {result_slot} AND snap empty AND no op consumes result_slot. (esnc/blr/diamonds
  qualify; hier_2pl does not — island splits it into 2 regions, as designed.)
- Reuse the F-4 per-op emitters unchanged; add a `direct` flag to the Emitter that
  remaps ONLY the storage accessors:
  vref: param -> params[off] (params are the arena prefix per bind_), fill ->
  D{off}[i] (per-fill static array in the .so), result -> local `res`; aref_adj:
  param -> ga[off] (local adjoint array, F-3 style), result -> literal 1.0 (the
  executor seeds exactly 1.0 at gradient(); read-only context, tool asserts the
  result slot is never an op input), internal -> la[] as in region bwd; vptr:
  param -> params+off, fill -> D{off}.
- One fn: guard nparams; locals S (scratch), ga[np], la[iadj], res; fwd body;
  *logp_out = res; memset ga/la; bwd body; memcpy grad_out <- ga. The single
  scope is the point: clang SROA can forward the fwd->bwd spills through
  registers, which the two-call region ABI structurally forbids.
- Fills: NOT baked as literals (F-3 style) but installed at load: per-fill
  `static double D{arena_off}[len]` in .bss, tool dlsym's each and memcpys
  cm.fills values in. Keeps F-4's dataset-independent structure-keyed cache
  doctrine (a different dataset re-installs, no re-emit). Decision recorded here.
- Cache: key = region key + "-d1" (bump on any direct-emitter change).
- Tool: automatic when eligible (`--no-direct` to disable); VERIFY_DIRECT (64
  pts seed 20260826 vs ex0 = UNMODIFIED executor) + BENCH_DIRECT (in-C loop,
  bench_grad-matched theta, 250ms-calibrated count, 3 reps, median + reps
  printed) alongside the existing VERIFY/BENCH_EXEC/BENCH_KERNEL blocks.

## Item (i) build log

- Implemented in tools/fortk/regions.cpp only (no runtime source changes):
  - Emitter `direct` flag remapping vref/vptr/aref_adj (see design above).
  - emit_region_c(direct=true) emits ONLY fortk_grad_direct (first cut also
    emitted the region pair with direct accessors — compile error, fixed).
  - Fill arrays: first `static` (dlsym can't see local symbols), then
    `__attribute__((used)) static` (still local), finally exported globals
    `fortk_D{arena_off}[len]` — dlsym-able, structure-keyed cache intact.
  - Beyond the pre-registered minimum (same arithmetic, one scope): in
    direct mode the bwd reads the fwd's v/t locals directly — the spill-to-S
    round-trip exists only to cross the region ABI's two calls. No semantic
    change (same doubles); dropped the spill blocks + S decl. Direct cache
    key bumped -d1 -> -d2 for this.
  - FORTK_DIRECT_REF=<f3.so>: interleaves the F-3 artifact (fortk_logp_grad,
    same signature, same flags, same theta) in the SAME bench loop — the
    same-protocol reference the gate needs ("within noise of 19.4 ns").
- Tool output: DIRECT / VERIFY_DIRECT / BENCH_DIRECT lines; --no-direct opts
  out. Suite 63/63 green (fortk_t1r_smoke exercises the direct path on the
  es fixture: -d2 artifact present in the smoke cache).

## Item (i) FINAL RESULTS (taskset core 2; clean-box sets quoted, noisy sets
recorded below; a 17GB niced python ingest job ran on the box all session)

### Gate (a) correctness — PASS all 3 (direct fn vs UNMODIFIED executor ex0,
64 pts seed 20260826, limits 1e-9/1e-9):

| model | direct grad rel-L2 | direct logp rel | (fused-executor gate, same) |
|---|---|---|---|
| eight_schools_nc | 0.0 (bitwise) | 2.485e-16 | 0.0 / 2.485e-16 |
| blr | 3.249e-16 | 2.423e-16 | 3.249e-16 / 2.423e-16 |
| diamonds | 3.882e-16 | 2.491e-16 | 3.882e-16 / 2.491e-16 |

(DIRECT == fused-executor numbers exactly — the two emissions produce the
same arithmetic; both match the oracle.)

### Gate (b) perf — kernel-only in-C loop, 3-rep medians, F-3 artifact timed
interleaved in the same process (the honest same-protocol reference):

| model | direct ns/call | F-3 ref ns/call (same loop) | direct/ref | region fns | fused exec | unfused exec |
|---|---|---|---|---|---|---|
| esnc | 20.1 [19.6,20.1,20.2] | 20.5 [20.4,20.5,20.8] | 0.977 | 25.5 | 34.8 | 279.1 |
| blr | 136.6 [136.4,136.6,136.9] | 133.1 [132.9,133.1,134.3] | 1.027 | 145.3 | 181.3* | 584.9 |
| diamonds | 40034 [38884,40034,40283] | 40213 [39651,40213,41668] | 0.996 | 40626 | 39046 | 36245 |

- esnc GATE (b): PASS. All runs' direct/ref 0.977-1.037 with overlapping rep
  ranges — within noise of the F-3 artifact under the same protocol. NOTE:
  F-3's logged absolute 19.4 ns does not reproduce TODAY for F-3's own
  binary (20.1-21.4 across 4 sets on core 2; the ingest job's L3 traffic is
  the plausible cause) — the ratio-vs-same-loop comparison is the gate
  evidence; absolute today is 20.1 vs the reference's own 20.5.
- blr: parity within wobble (earlier sets had direct FASTER: 0.899/0.962;
  final tight set 1.027; both ~130-140 ns, F-3 logged 134.2).
- diamonds: parity 0.996 (memory-bound, as F-3/F-4 both found; F-3 logged
  40.13 µs — matches).
- The F-4 overhead ladder on esnc today: direct 20.1 < region fns 25.5
  (two-call ABI + scratch round-trip = +5.4 ns) < fused exec 34.8 (executor
  sweep wrapper adds +9.3 ns) < unfused exec 279.1. The direct path
  recovers the ABI loss exactly as pre-registered.
- Noisy sets recorded (protocol): diamonds set under a load spike (load
  2.95): direct 48.68 µs / ref 50.13 (ratio 0.971 — ratio held, absolutes
  +22%); blr first set: direct 131.8 [129.0,131.8,143.5] / ref 144.3
  [133.9,144.3,164.5]. esnc first set: 22.0/21.4.
- hier_2pl: direct correctly INELIGIBLE (2 regions — island splits the
  graph; message printed; region path unchanged, gate (a) still 1.0e-15).
- Cache: -d2 artifacts 4-16 KB source, clang 0.14-0.44 s cold, ~0 s cached;
  dataset-independent (fills installed at load).

## Item (ii): sampler-overhead census (informational, no gate)

Method: fortk_t1r --census 200 200 (commit 0243aad): {nuts, walnuts} x
{unfused ex0, fused ex1} at seed 20260826 chain 1, max_depth 10, 3 timed
reps inner-repeated to >=120 ms; wall per 400-iteration run, EXACT
grads/iter from the executor gradient counter (not an estimate), NUTS
treedepth from stats rows; implied grad shares from in-process µs/call
medians (exec tier = the installed path; direct = the F-4b floor).
stanli_run cross-check (unfused nuts, same seed/200/200): its gradient
evaluations 4164 (esnc) / 11282 (blr) match the census counters exactly.
Load context: the 17 GB python ingest ran all session; an F-7 lane's
compiles (external/stanli-f7) overlapped the census reps (load 2-6);
rep spreads ~10-20% on walls, shares stable.

### Census table (medians of 3 reps; grad-share = grads/run x µs/call / wall)

esnc (200+200, 10 params):
| sampler | tier | wall ms/run | draws/s | grads/iter (exact) | treedepth | grad-share exec | grad-share direct |
|---|---|---|---|---|---|---|---|
| nuts    | unfused | 4.46 | 44.9k | 10.41 | 3 | 30.7% | 2.1% |
| nuts    | fused   | 2.38 | 84.2k | 10.35 | 3 | 6.7%  | 3.9% |
| walnuts | unfused | 2.09 | 95.8k | 8.47  | — | 50.0% | 3.7% |
| walnuts | fused   | 0.85 | 236k  | 8.47  | — | 14.1% | 8.9% |

blr (200+200, 6 params, N=100 D=5):
| sampler | tier | wall ms/run | draws/s | grads/iter (exact) | treedepth | grad-share exec | grad-share direct |
|---|---|---|---|---|---|---|---|
| nuts    | unfused | 15.4 | 13.0k | 28.20 | 3 | 46-54% | 11% |
| nuts    | fused   | 7.8  | 25.5k | 28.70 | 3 | 18-26% | 17-25% |
| walnuts | unfused | 19.9 | 10.0k | 61.34 | — | 78-81% | 16-21% |
| walnuts | fused   | 7.7  | 26.0k | 61.34 | — | 50-62% | 44-57% |

stanli_run whole-process walls (unfused nuts): esnc 0.02-0.05 s,
blr 0.03-0.04 s — i.e. on esnc ~85-90% of a single stanli_run invocation
is fixed pipeline cost (stanc + lower + CSV), sampling ~4 ms of it.

### Where does wall-time go now (the one-paragraph answer)

With fused gradients installed, esnc-class models are sampler-bound, not
gradient-bound: the gradient is 6.7% (nuts) / 14% (walnuts) of sampling
wall through the installed fused executor, and only 4-9% at the F-4b
direct floor — i.e. 85-95% of NUTS/WALNUTS wall is now tree bookkeeping,
adaptation, and per-iteration service work, exactly the regime where
further kernel work buys nothing and sampler-loop work buys a lot.
Fusing also flips the sampler ranking: walnuts' leaner loop goes from
2.2x slower than nuts per wall on unfused blr (19.9 vs 15.4 ms) to
parity-or-better fused (7.7 vs 7.8 ms) because its extra gradients
(61 vs 28 per iter) became cheap while its cheaper loop did not; on esnc
fused walnuts is 2.8x faster than fused nuts (0.85 vs 2.38 ms/run).
blr (28-61 grads/iter at treedepth 3) still shows 18-62% grad share
fused — mid-size models sit near the crossover; diamonds-class
(bandwidth-bound) is gradient-dominated and stays so. Estimates labeled:
grad-shares combine exact counters with measured µs/call under load;
walls carry the session's load noise (±10-20%).

## Deliverables / state

- Branch fortk/t1-regions (decision: stayed on the F-4 branch rather than
  a child — the change is one additive tool TU touching nothing else),
  commits b7a3fd5 (direct path) + 0243aad (--census), NOT pushed.
  Runtime diff remains the ONE inert F-4 opcode line; F-4b adds zero
  runtime source changes.
- Suite 63/63 (fortk_t1r_smoke covers emit+verify+bench of both the
  region path and the direct path).
- Artifacts: bench/fortk_emitted/regions/cache/*-d2.{c,so}.
- Surprises: (1) F-3's 19.4 ns absolute does not reproduce today for
  F-3's own binary (20.1-21.4 ns on core 2 under the session's load) —
  the same-loop interleaved ratio is the honest gate instrument;
  (2) dropping the scratch spill round-trip (reading fwd locals in bwd)
  mattered little on esnc (21.0 -> 20.8 ns) — most of the F-4 ABI gap
  was the two CALLS + ctx refresh, not the spill traffic itself;
  (3) mutable fill arrays (vs F-3's baked const literals) cost ~nothing
  measurable at these sizes; (4) even UNFUSED, esnc NUTS is ~70%
  bookkeeping — the sampler overhead finding is not new to fusion,
  fusion just sharpens it to 93%.
