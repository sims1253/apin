# F-4 log — T1 integration: region emission + runtime install (fortk/t1-regions)

Started: 2026-08-26. Binding scope: WORKLOG "F-4 pre-registered BEFORE building".

## Session 1 start

- Read: WORKLOG fortk lane (F-3 verdict + F-4 pre-reg), stanli-arch.md, fortk-f3.md.
- Inherited: external/stanli branch fortk/t1-emitter @ a2e8615 (3687e52, f23a9ab, a2e8615), not pushed.
- Branch: child branch **fortk/t1-regions** created off fortk/t1-emitter @ a2e8615.
- Coordinator context (F-2b landed): hier_2pl fused ceiling ~1.21x vs unfused executor
  (hand-fused 430.4 vs exec 521) — >=1.3x gate expected to MISS (pre-declared
  informative); deliver ranked breakdown. Optional non-gate arm: radon_pp
  (its dump needs only GATHER+FMA beyond my set — covered, will include).

## Design (pinned before coding)

hier_2pl dump (97 ops): ops 0-1 supported (CONSTRAIN_LOWER, CONSTRAIN_CHOL_CORR
K=2), op 2 ISLAND, ops 3-96 supported (SLICE/INDEX/GATHER/MUL/SUB/DIAG_MATRIX/
GEMM/MVN_CHOL×32/LKJ/EXPONENTIAL/BERNOULLI_LOGIT/NORMAL_LPDF/ADD_N tree).
Region A live-outs: 2 values + 2 CL-jacobian scalars (=4 live-outs!) → markers
needed beyond out/out2. Region B live-out: result only.

- Opcode: OP_FORTK_REGION appended at END of STANLI_ALL_OPCODES (after
  SCALAR_UNARY) via `PLAIN(OP_FORTK_REGION)` — no existing opcode value shifts,
  no trait, no lowering entry, no kernel unless the tool registers → inert.
  Diff to document (1 line + comment in optable.hpp).
- Region op: n_in=0; ALL boundary I/O in udata RegionArtifact (value-arena
  offsets, adjoint-arena offsets, lens). Arena bases reconstructed in the
  kernel: arena = ctx.out.data - out0_val_off; adj = ctx.out_adj_vec.data -
  out0_adj_off (make_ctx_ sets out_adj_vec unconditionally). Slots vector of
  the rewritten graph is UNCHANGED → bind_'s value layout identical to the
  unmodified graph.
- Live-outs: op.out = live_out[0], op.out2 = live_out[1] (marks written[]);
  live-outs 3+ marked by MARKER ops (same opcode, artifact->marker=true:
  forward no-op, backward early-return) whose out = the extra live-out slot.
  Markers give the slot an adjoint cell so external consumers accumulate;
  region bwd reads the accumulated cells directly (reverse order guarantees
  consumers ran first — topological op list).
- Rewritten-graph adjoint layout mirrored exactly from executor.cpp bind_
  (params first, then written[] non-params, computed over the REWRITTEN op
  list). Adjoint accumulations for boundary inputs = += into arena cells
  (multiple consumers may exist outside the region).
- Region-internal slots: values + internal adjoints live in the op's scratch
  window (island doctrine: fwd snapshot; scratch survives fwd→bwd within one
  gradient()). Boundary inputs that are op-written slots (e.g. ISLAND outs)
  are SNAPSHOTTED into scratch in fwd (in-place overwrite hazard, island.hpp
  warning); params/fills are never op-written (carver asserts) → read from
  arena in both sweeps (zero snapshot cost on esnc/blr/diamonds whole-graph
  regions).
- Emitted fns: `void fwd(double* arena, double* scratch)` /
  `void bwd(const double* arena, double* adj, double* scratch)`. Fills read
  from arena (no giant .c data blocks); idata baked as static const arrays.
- Transcriptions (RAW reads, F-3 lesson): MVN_CHOL single-y overload with
  L-var path (inv_L, half, scaled_diff, dL = scaled_diff*half - inv_L^T,
  log-diag term UNCONDITIONAL when L active — include_summand block); LKJ
  (values(k) = (Km1-k-1)*logdiag + (2eta-2)*logdiag, diag-only partials,
  eta==1 shortcut = same value); CONSTRAIN_CHOL_CORR K=2 (z=tanh(y), lp +=
  log1m(z^2) — NOTE it's log(1-tanh^2) NOT log(1-y^2), caught by raw read;
  analytic pullback mirroring the tanh/square/log1m vari chain);
  exponential (dy=-beta, dbeta=inv(beta)-y, log-beta term mask-gated);
  bernoulli_logit vector path (ntheta cutoff 20, select tree, per-elem
  partials, 4-lane sum since Eigen sum reassociates); GEMM/DIAG/SLICE/INDEX/
  GATHER/MUL/SUB/ADD from kernels directly. K>2 CHOL_CORR and MVN m>1
  rejected loudly (not needed by targets).
- Carver: maximal contiguous runs of supported ops; region needs >=2 ops,
  all out/out2 slots within the run distinct; no SET_*_INPLACE in run; every
  run with >=1 live-out carved; unsupported ops (ISLAND etc.) survive as-is.
- Cache: key = FNV over (emitter version, flags, per-region structure:
  opcode/variant/in-lens/out-lens/idata arrays + boundary offset layout +
  scratch layout). Fill VALUES excluded (code reads arena → dataset-
  independent). bench/fortk_emitted/cache/<key>.so (+.c on miss).
- Gates mapping: (a) fused Executor.gradient vs oracle Executor.gradient
  64 pts seed 20260826 < 1e-9 both metrics; (b) kernel-only direct region-fn
  loop w/ per-iter memset of region adj cells (F-3-comparable) AND
  executor-level ratio; (c) run_nuts both arms same seed, bitwise or
  3-seed statistical; (d) wall: stanc/compile_model/emit/clang/dlopen,
  cold + cached.
- New tool: tools/fortk/regions.cpp (fortk_t1r); ctest smoke on `es` fixture
  (8 ops, 1 region, exercises MUL/ADD broadcast + CONSTRAIN_LOWER + densities
  + ADD_N). OP_ADD added to whitelist (es needs it; trivial).

## Build session log (bugs found by the 1e-9 gate + fixed; never loosened)

1. Scalar (len-1) density partials accumulate lane-wise in scratch, which
   persists across evaluations: first gradient call was correct (bind-time
   zeros), later calls inherited garbage → pt0 bitwise, pt1 off. Fix: zero
   scalar partial temps at each op's fwd start.
2. MVN transcription had half/scaled_diff TRANSPOSED (computed invLᵀ·d
   instead of invL·d; found numerically by matching an algebraic variant to
   16 digits); the L-data branch's substitution indices likewise addressed
   the zero upper triangle. Raw-source re-read fixed both.
3. `lp0` accumulator was function-scoped: 32 MVN instances in hier_2pl's
   region B accumulated into ONE variable (MVN0 correct, MVN1+ wrong).
   Fix: per-op declaration.
4. log1m is stan-math, not C99: log1m(x) == log1p(-x) (raw prim source).
5. Temp-array element refs emitted S[off][i] instead of S[off+i] (compile
   errors, no silent wrongness).
6. Perf path: scratch-pointer stores cost 2.6x vs F-3's locals (esnc 51ns);
   C99 restrict (→31ns) + fwd-local values/temps with end-spill to scratch
   (→23ns) recovered most of the F-3 single-function SSA advantage.

## FINAL RESULTS (F-4 gates; taskset core 2, 3-rep medians, reps <5% spread
except where noted; background load from another agent's job caused up to
16% between-run wobble on blr — re-ran per protocol, quoted the tight set)

### Gate (a) correctness — PASS all 4 (vs Executor over UNMODIFIED graph,
64 pts seed 20260826, limits 1e-9/1e-9):

| model | grad rel-L2 max | logp rel max |
|---|---|---|
| eight_schools_nc | 0.0 (bitwise) | 2.5e-16 |
| blr | 3.2e-16 | 2.4e-16 |
| diamonds | 3.9e-16 | 2.5e-16 |
| hier_2pl | 1.0e-15 | 1.2e-14 |

Suite 63/63 green (62 inherited + fortk_t1r_smoke). radon_pp (non-gate):
2.0e-14 / 9.9e-15 PASS.

### Gate (b) perf — kernel-only (direct region fwd+bwd, per-iter adj-span
memset) vs F-3 emitted; executor-level = fused Executor.gradient vs
unfused Executor.gradient:

| model | unfused exec | fused exec | exec ratio | region fns | F-3 emitted |
|---|---|---|---|---|---|
| esnc | 274.7 ns | 33.0 ns | 8.32x | 22.7–25.3 ns | 19.4 ns |
| blr | 582.6 ns | 139–162 ns | 3.6–4.2x | 127.7–144.6 ns | 134.2 ns |
| diamonds | 33.8 µs | 39.6 µs | 0.85x | 38.0–40.6 µs | 40.1 µs |
| hier_2pl | 486.8 µs | 492.8 µs | 0.99x | 484.5 µs | (F-2b hand-fused 430) |
| radon_pp* | 62.9 µs | 41.3 µs | 1.52x | 40.9 µs | — |

- esnc/blr "within noise of F-3": blr YES (127.7–144.6 straddles 134.2);
  esnc PARTIAL (+17–30%: 22.7 vs 19.4). Mechanism: the region ABI splits
  fwd/bwd into two executor calls, forcing the partial round-trip through
  scratch + a second call; F-3's single function kept everything in
  registers. esnc is overhead-bound (≈10 transcendentals total) so the ABI
  cost is visible; blr is arithmetic-bound so it hides.
- diamonds 0.85x: same memory-bound negative as F-3 (2×960KB X streams).
- hier_2pl 1.3x target MISSED (pre-declared informative): 0.99x. Ranked
  breakdown (executor profile, 500 grads): fused side — OP_FORTK_REGION
  99.6% (fwd 360 µs/call + bwd 133 µs/call), OP_ISLAND 0.4% (2.1 µs/call);
  unfused decomposition — BERNOULLI_LOGIT fwd 64.7% (307 µs/call), GATHER
  fwd+bwd 24.9% (3×19200-element scatters), MVN 3.3%, MUL 3.2%, SUB 2.3%.
  Interpretation: transcendental-bound (~22 ns/obs floor, matching F-2b's
  verdict); my region bernoulli loop beats Eigen's select-array (region
  fwd total 360 µs < unfused bernoulli fwd alone 307 µs + everything else)
  but the gather/adjoint traffic and MVN work balance the win to parity.
  Island share negligible; region dispatch overhead negligible.

### Gate (c) sampling smoke (NUTS via run_nuts, same seed both arms):

No model bitwise: last-bit lp differences (esnc logp 2.5e-16 rel) amplify
chaotically through trajectories — expected when the rewrite is not
order-preserving at the bit level. 3-seed statistical equivalence
(per-coordinate z of mean difference, ess=n — conservative):

| model | draws | worst z (3 seeds) | divergences unfused/fused |
|---|---|---|---|
| esnc | 500 | 2.78 / 1.21 / 2.09 | 0/0 |
| blr | 500 | 1.27 / 2.26 / 1.77 | 0/0 |
| diamonds | 1000 | 2.47 / 2.05 / 3.05 | 0/0 |
| hier_2pl | 150 | 2.83 / 2.71 / 2.70 | 0/0 |

Max-z over 30–2000 comparisons per model at these levels is consistent
with noise (and the true ess < n makes the real z smaller). lp__
trajectories track (max |Δlp| per draw 1.2–80 in step with the chaotic
divergence; no systematic drift).

### Gate (d) compile budget (wall, cold → cached):

| model | stanc | lower | clang (cold) | dlopen+exec | COLD total | CACHED total |
|---|---|---|---|---|---|---|
| esnc | 0.02 | 0.001 | 0.148 | ~0.001 | ~0.15 s | ~0.002 s |
| blr | 0.01 | 0.001 | 0.170 | ~0.001 | ~0.17 s | ~0.002 s |
| diamonds | 0.02 | 0.034 | 0.390 | ~0.001 | ~0.43 s | ~0.035 s |
| hier_2pl | 0.02 | 0.008 | 2.008 (2 regions: 0.14 + 1.87) | ~0.001 | ~2.02 s | ~0.011 s |

Cache: content-keyed (emitter version, flags, region structure incl.
idata + boundary offsets); fill values NOT in the key (code reads the
arena → dataset-independent artifacts). Hit path re-verifies (64-pt gate
re-run on cached .so: PASS).

## Deliverables

- Branch fortk/t1-regions (child of fortk/t1-emitter), commits:
  e55ea85 (optable: inert OP_FORTK_REGION, appended after all lists — no
  opcode value shifts, no trait, no lowering entry, no kernel unless the
  tool registers it; the ONLY runtime diff, 8 lines incl. comment),
  d1f234d (tools/fortk/regions.cpp + CMake fortk_t1r + fortk_t1r_smoke).
  Not pushed.
- Artifacts: bench/fortk_emitted/regions/ (*.c + *.so per region).
- Everything else lives in tool TUs; executor/lowering untouched.

## Surprises / notes for F-5

- The graph rewrite is value-exact and gradient-exact to 1e-15, but NOT
  bitwise on lp at every point (2.5e-16 rel on esnc) → NUTS draws are
  never bitwise. Any future "bitwise sampling" claim needs the emitted
  code to preserve the executor's exact summation order per op (possible
  but restrictive; the 1e-9 gate is the right arbiter).
- The separate fwd/bwd call ABI costs ~15% on overhead-bound regions
  (esnc) vs F-3's single-function emission. A combined fwd+bwd region fn
  is impossible under the executor's two-sweep model without executor
  changes (out of F-4 scope by design).
- radon_pp (the interpreter's strongest class in F-1) is where the region
  tier pays most among our models: 1.52x.
- hier_2pl region .c is 290KB (32 MVN instances + 3×19200 gather idata);
  clang -O2 takes 1.9s of the 2s cold budget. The idata arrays dominate
  source size, not complexity.
- Coordinator context absorbed: F-2b ceiling ~1.21x explained the hier
  miss in advance; the ranked breakdown above is the deliverable.
