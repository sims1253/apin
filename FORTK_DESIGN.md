# FORTK — per-model fused codegen tier for stanli (working design)

Status: DRAFT v1 (2026-08-26). Companion to the fortk pre-registration in
WORKLOG.md ("fortk lane opened"). Stanli internals sections are placeholders
until the architecture map lands (logs/stanli-arch.md). Evidence gates F-1..F-3
control what actually gets built.

## 1. Goal / non-goals

Goal: replace interpretation of a model's lowered op sequence with execution of
per-model COMPILED code in which chains of ops are fused into single kernels —
primal and adjoint both — with compile latency small enough to feel like JIT
(seconds, not the ~60s of stanc3+g++).

Non-goals: changing the Stan language or .stan format; touching samplers
(walnutpie/nuts stay as-is on the other side of logp_grad); GPU in this lane
(CPU/AVX2 Zen 3 first — GPU is a later lane); bit-identical draws (see §5).

## 1½. Refined thesis (evidence: F-2/F-2b/F-3, 2026-08-26)

The naive "fusion wins grow with model size" thesis is FALSIFIED. Measured
ceiling structure, kernel-only, single core (Zen 3):

- Dispatch/overhead-bound (tiny/small graphs, 5–100 ops): fused wins big —
  14.6x (esnc) / 4.3x (blr) over the interpreter; interpreter itself only
  1.6x over CmdStan here. T1's core value zone.
- Bandwidth-bound (diamonds-class, 960 KB streams/call): PARITY (1.01x) —
  both arms pinned at ~30 GB/s single-core; AD overhead hides under DRAM.
  Wins here need cross-pass fusion, cache blocking, or multi-core — not
  fusion alone.
- Transcendental-bound (hier_2pl-class, 22 ns/obs exp+log1p): 1.44x over
  CmdStan, ~1.21x over interpreter, floor hit by hand-fusion. Next lever is
  ulp-accurate vectorized exp/log1p (~2x more headroom, fits the 1e-9
  gate) — a T2 kernel-library item, not a T1 emitter item.

Implications: T1 integrates (F-4) with its win concentrated on small/
medium graphs — which is also where whole-workflow wall-clock becomes
sampler-bound (esnc at 19.4 ns/grad means NUTS bookkeeping dominates).
The system-level pitch matures into: fused logp_grad + lean sampler loop.
Scale-class wins are a T2/T-later story (vectorized libm, multi-core).

## 2. What exists, what's the delta

stanli (upstream 85a8f11): .stan → embedded stanc3 → MIR → lowering to a
linear op sequence over preallocated value/adjoint arenas → graph passes →
interpreted execution against PRECOMPILED kernel library. No JIT, no codegen.
~2.9x median grad win vs CmdStan, ~100x source-to-CSV.

Delta under construction: after the graph passes, instead of (only)
interpreting, PARTITION the op sequence into fused groups and emit one C
function per group (plus a paired adjoint), compile once per
(model, shape-signature), cache the .so, dispatch to it from the executor.
Interpreter stays as the universal fallback tier.

## 3. Tier architecture (who writes what)

The "age of agents" division of labor — each tier has a different author of
the machine code, but ALL tiers pass through the same deterministic verifier:

- T0 — Interpreter (exists). Universal fallback; correctness reference
  implementation for every op.
- T1 — Deterministic emitter (to build). Op sequence → flat C, fused per
  partition. Structure emission is mechanical: arenas become arrays, op
  groups become loops/calls. Compile: clang -O2 -march=native (measured in
  F-2); cache keyed (MIR hash, shape signature, emitter version, flags).
  Target compile latency: <1s warm-path feel via cache, ~100-500ms cold.
- T2 — Agent-authored kernel library (to build, grows incrementally). The op
  algebra is finite (~70 densities + arithmetic + linalg). For the hot ops:
  hand-quality fused kernels with symbolic adjoints, written by agents,
  verified ONCE against T0/CmdStan differentially, then immutable library
  entries. BLAS-model development at agent speed. Verification cost is
  amortized to zero over invocations.
- T3 — Agent-authored whole-model artifacts (optional, later). For a user's
  hot model: agent writes the whole fused logp+grad (the F-2 experiment),
  verified at >=50 random points (grad rel-L2 < 1e-9), cached AOT. Compile
  latency = agent minutes; quality = ceiling. Justified only for models
  sampled much longer than they are written.
- T-LT — Long tail (to build): ops/programs T1 can't emit or fuse (ODEs,
  algebra solver, exotic linalg) → Enzyme on the emitted flat C (PITCH 2f's
  idea, with the Eigen risk removed by construction since we emit the C), or
  straight to T0 interpreter.

Dispatch: executor tries T3 → T1(+T2 kernels) → T-LT → T0, per fused group,
all cached per (model, shapes).

## 4. The AD question (fusing the reverse sweep)

NUTS pays for grad, not logp; a primal-only JIT is half a system. Principles:

- The op sequence IS the tape (stanli's insight — value/adjoint arenas).
  Codegen must produce a paired adjoint sweep with the same fusion
  boundaries as the primal.
- Pointwise chains: adjoint of a fused pointwise group is the mirrored
  pointwise chain (chain rule composes elementwise). No cross-element
  interaction => trivially fusable both directions.
- Reductions (lpdf accumulation, target +=): adjoint is broadcast of the
  upstream cotangent. Reduction boundaries are fusion boundaries in the
  primal; the adjoint sweep crosses them in reverse order.
- GEMM/linalg: do not fuse — call BLAS/LAPACK (or stanli's existing kernels);
  fuse only epilogues (the Inductor "epilogue on GEMM" pattern).
- Symbolic partials per op (T2) vs Enzyme on the whole function (T-LT):
  T2 is faster and predictable; Enzyme covers arbitrary control flow we
  don't want to hand-lower. Both gated by the same verifier.

## 5. Verification doctrine — the harness is the compiler

Inherited from stanli's differential-testing culture, one deliberate change:

- Gradient correctness is HARD-gated: vs bridgestan .so at >=50 seeded
  random unconstrained points, rel-L2 < 1e-9, logp rel < 1e-12 (F-2 gates).
  This gate applies to every tier, every cache entry, no exceptions.
- Bit-identical draws are NOT a blanket goal (fusion reorders summation;
  NUTS is chaotic) — but with a precision the arch map makes concrete:
  OPTIMIZATIONS.md:910–955 ("deferred reduction reassociation") is exactly
  the list of fusions that break the bitwise band. Pointwise fusion and
  epilogue fusion that preserve accumulation ORDER (compile with
  -ffp-contract=off, transcribe descending accumulations like the kernels
  do) can stay bitwise vs the interpreter. Reduction reassociation is the
  opt-in tier: documented drift, statistical draw comparison (3 reps,
  ESS-aware), per the -march=native precedent and PITCH.md Phase 2 rule.
  T1 v1 should aim for order-preserving fusion only — bitwise vs T0 by
  construction, verified by stanli's own test_cross_path machinery.
- Cache entries carry their verification proof (points, residuals, version).
  A failed re-verification invalidates the entry and deopts to T0.

## 6. Fusion partition (sketch, to refine against the arch map)

Color ops: POINTWISE / REDUCTION / GEMM / SOLVE / OPAQUE.
- Maximal pointwise runs between materialization-forcing ops fuse into one
  kernel (primal) + one mirrored kernel (adjoint).
- Reductions terminate a pointwise run; a fused group = pointwise-run +
  terminal reduction; adjoint = reverse pointwise + broadcast.
- GEMM/SOLVE/OPAQUE are their own groups (library call), with epilogue
  fusion into an adjacent pointwise run where shapes allow.
- stanli's existing passes (reroll = vectorization, cse, constfold, inplace)
  run BEFORE partitioning; partition.cpp may already do part of this
  (placeholder — fill from arch map).

## 7. Hook points in stanli (from logs/stanli-arch.md — full map there)

- **The seam**: `compile_model()` (lower.cpp:5029) returns `CompiledModel`
  whose `Graph` is post-pass, fully resolved (opcodes, slot lengths, variants,
  scratch sizes all load-time final). `capi.cpp:71–72` constructs the
  `Executor` from it. A codegen backend is a second consumer of that Graph —
  the Executor deliberately exposes `graph()` / `param_ptr()` /
  `value_ptr()` (graph.hpp:169–178) for exactly this.
- **Install path**: the `Kernel` function-pointer triple (forward/backward/
  scratch_size) resolved into `fwd_fn_`/`bwd_` dispatch vectors at bind
  (executor.cpp:232–242). Two options: replace dispatch-vector entries for a
  fused region, or emit a fused `OP_ISLAND`-style op replacing the region
  (the island carver + `compact_program` are the existing region-extraction
  machinery; `Program::CALL` shows kernel invocation out of a register file).
- **Precedent = reusable infra**: islands + `gen_adjoint` (adjoint.cpp) are
  ALREADY a load-time source-transforming compiler over a region IR with
  checkpoint analysis, cost model, and an adjoint generator. T1 should look
  like "islands, but emitting C instead of register programs, and over
  elementwise/density regions instead of scalar residue."
- **Legality facts exist**: `op_trait::kBackwardValueFree` (what may precede
  destructive writes), `kReroll*` traits, `is_effectful_op`, variant byte
  (per-arg activity bits 0–5, elementwise bit 6, propto bit 7 — MUST be
  preserved or lp__ drifts by a constant while gradients stay perfect; the
  nastiest bug class, hacking.md:226–229).
- **Tools**: `dump_ops` / `dump_islands` print exactly what codegen would
  consume; `STANLI_NO_*` kill switches + `test_cross_path` give the A/B
  oracle; `docs/corpus-refs.json.gz` (129 models, 387 points, CmdStan-recorded
  lp+grad) + `stanli_check` + `verify_refs.py` are the verification harness
  our tiers must pass — reuse it instead of building a new one.
- **Cache keying**: mirror the `__stanli` manifest pattern —
  `STANLI_BUILD_ID` (exists precisely "for callers that cache artifacts next
  to the library", CMakeLists.txt:226–239) + a graph hash.
- **No LLVM anywhere today**; no on-disk cache of lowered graphs. The
  `STANLI_PACKET_MATH` experiment (varmat kernels, measured neutral, OFF by
  default) is the cautionary precedent for kernel tiers that cost parity.

## 8. Cache & specialization

Key: (MIR hash, data shape signature, emitter+kernel-lib versions, flags).
Shape signature = the data-dependent sizes that enter the op sequence
(stanli already specializes/unrolls on them at lowering). Cold compile once
per key; warm dispatch is a dlopen + function pointer. Cache dir under
~/.cache/fortk (never the repo; see git-hygiene standing rule).

## 9. Gate mapping

- F-1 (stanli vs bridgestan baseline, 5 models): must reproduce ~2-3x
  before anything is built on the interpreter.
- F-2 (hand-fused C ceiling, 2 models): >=1.5x over the F-1 stanli number
  opens T1; a miss writes the negative result and the lane stops.
- F-3 (T1 prototype on top of the op sequence): gradient parity gate §5,
  then CORE_SET-class timing vs both baselines.

## 10. Risks / open questions

- Summation-order drift in reductions: logp rel < 1e-12 gate may need
  relaxing to ~1e-10 for genuinely reordered sums (document if so; never
  silently).
- Executor dispatch overhead may already be small post-reroll (radon_pooled
  = 8 ops) — the T1 win then concentrates in small models and per-op kernel
  call overhead; F-2's blr arm measures exactly this class.
- Compile-latency budget: clang -O2 on a few hundred lines is fast, but
  -march=native + many fused groups could exceed the 1s feel; measure in F-3.
- Fork divergence: keep fortk rebased on upstream stanli main; prefer
  upstreaming generally-useful pieces (the harness especially).
