# F-3 log — T1 deterministic emitter prototype (branch fortk/t1-emitter)

Pre-registration: WORKLOG.md "F-3 pre-registered BEFORE building" (binding).
Scope: additive tool in external/stanli fork; emit ONE fused C99 file per model
from the post-pass Graph (compile_model output), forward+reverse, variant byte
honored per op instance; verify vs stanli Executor (T0 oracle) at 64 seeded
points (seed 20260826); gate grad rel-L2 < 1e-9 AND logp rel < 1e-9; perf gate
emitted >= 1.3x vs executor kernel-only on >= 2 of 3 target models
(8schools_nc, blr, diamonds). Opcodes: loud rejection on anything outside v1.

## Session log

- [start] Workspace verified: fork clean @ 85a8f11 on main, build-rel present
  (bench_grad, dump_ops, libstanli.a all built). No bench/cc1plus running,
  load 0.3. Branch fortk/t1-emitter created off main.
- Op dumps for the 3 targets (deps/stanc3/stanc --O1 --debug-optimized-mir +
  build-rel/dump_ops): esnc 7 ops, blr 5, diamonds 7. Post-pass graphs need
  exactly: CONSTRAIN_LOWER, FMA (eltwise std::fma form), SUB, ADD_N,
  NORMAL_LPDF, CAUCHY_LPDF, STUDENT_T_LPDF, NORMAL_ID_GLM_LPDF. NO
  GATHER/SLICE/INDEX survive the passes on these models. v1 whitelist = that
  set; everything else rejects loudly (name + position).
- Read sources: executor.cpp bind_ (layout mirror), graph.hpp, compile.hpp,
  elementwise.cpp, eltwise_expr.cpp, constrain.cpp, densities_impl.hpp,
  matrix_fns.cpp nid_glm kernel, bench_grad.cpp, capi.cpp, CMakeLists.
  Transcribed density math from vendored stan-math prim sources
  (deps/math/stan/math/prim/prob/{normal,cauchy,student_t,normal_id_glm}_lpdf.hpp).
- KEY semantics pinned (the nastiest bug classes):
  - include_summand<propto> == !propto; include_summand<propto,T_scale> ==
    (!propto || arg bound as var). Recorder densities bind arg as var iff
    variant mask bit set => log(sigma) term included iff (!propto || mask bit).
  - nid_glm kernel (matrix_fns.cpp:600+) binds alpha/beta/sigma as var
    UNCONDITIONALLY => its -N*log(sigma) value term is present even under
    propto (differs from recorder densities!). Only NEG_LOG_SQRT_TWO_PI*N is
    propto-gated there.
  - Variant bit 6 (elementwise-lp) rejected v1; student_t with ACTIVE nu
    (digamma partial) rejected v1 (not needed by the 3 models).
- Implementation: tools/fortk/emit.cpp (one binary: emit -> clang -> dlopen ->
  verify vs Executor -> bench, bench_grad-matched theta/loop). Value storage =
  one C variable per non-fill slot (v{offset}; whitelist has no in-place ops,
  offsets asserted disjoint); fills = static const arrays (%a literals) or
  inline literals for len-1; adjoints = one compact array mirroring the
  executor's adjoint arena (params first, then written slots — memset 25..33
  doubles, NOT the full value arena). CMake target fortk_t1 + ctest smoke on
  tests/fixtures/glmy (single normal_id_glm with PARAMETER outcome = y-active
  path; bit-exact, PASS).
- Two transcription bugs found via the gate + fixed (would have been silent
  drift):
  1. normal_id_glm y_scaled lacks my initial `* inv_sigma` — my first read of
     the prim source was through a comment filter that dropped the expression
     continuation line. Caught by verify: blr lp off by 527x relative. Re-read
     raw source; also re-checked cauchy/student_t raw and found...
  2. cauchy dsigma partial missing the `* inv_sigma` factor (same
     continuation-line class): correct form ((y-mu)^2 - sigma^2)*inv_sigma /
     (sigma^2 + (y-mu)^2). Not exercised by 8schools (sigma data there) —
     found by source re-read, fixed pre-verification.
  Lesson recorded: never transcribe stan-math expressions through grep
  filters; continuation lines carry factors.
- Diamonds perf forensics (honest, in order):
  1. First build: emitted 118.5 us vs executor 37.4 us (0.32x). Split
     fwd-only: fwd 20.5 us / rev 98 us. Cause: reverse per-column dot products
     are 5000-long scalar add chains (clang -O2 cannot vectorize FP
     reductions without reassociation); forward matvec was row-major strided
     (40KB stride, cache-hostile).
  2. Loop-order fix (bitwise-identical per element): forward matvec as
     column-at-a-time axpy (exactly what Eigen col-major GEMV computes —
     ascending-c per element, starting from 0). 98 -> ... still slow.
  3. 4-lane unrolled accumulators for the three GLM reductions (q sum,
     dalpha, per-column dbeta dots; threshold N>=32). Justification: the
     executor's own nid_glm computes these SAME reductions through Eigen
     redux/GEMV, which reassociates — there was no ascending-order band to
     preserve for this op in the first place; the 1e-9 gate is the arbiter
     (actual drift 3.9e-16 grad, 2.5e-16 lp on diamonds). Result: blr 331->134
     ns, diamonds 118->40 us.
  4. Final diamonds: fwd 17.4 us / rev 22.3 us = memory-bound on the same
     2 x 960KB X streams the executor does (its kernel = Eigen GEMV in fwd +
     reassociated transpose GEMV partials + var tape contraction). 0.87x =
     honest negative on this model; gate needs 2 of 3.

## FINAL RESULTS (quiet run, taskset core 2, 3 reps medians, reps within 5%)

| model | verify grad rel-L2 (max 64 pts) | verify logp rel | exec ns/call | emitted ns/call | ratio | clang s |
|---|---|---|---|---|---|---|
| eight_schools_nc | 0.0 (bitwise) | 2.5e-16 | 282.9 | 19.4 | 14.58x | 0.134 |
| blr (N=100,D=5) | 3.2e-16 | 2.4e-16 | 571.5 | 134.2 | 4.26x | 0.167 |
| diamonds (N=5000,D=24) | 3.9e-16 | 2.5e-16 | 34958 | 40133 | 0.871x | 0.404 |

- Executor cross-check vs F-1 bench_grad: 0.283 us esnc / 0.597 blr — mine
  0.283/0.572 — consistent.
- F-3 CORRECTNESS GATE: PASS all 3 (limits 1e-9; worst 3.9e-16, 6+ orders
  margin). Gates never loosened.
- F-3 PERF GATE (>=1.3x on >=2 of 3): PASS (esnc 14.6x, blr 4.3x; diamonds
  0.87x negative, profiled above).
- Secondary oracle (F-2 bridgestan npz, tools/fortk/check_npz.py): grad
  rel-L2 max esnc 1.1e-16, blr 4.0e-16, diamonds 8.2e-14; logp also matches
  at 4.1e-16/2.2e-16/1.1e-14 (F-2 refs evidently generated with matching
  propto semantics, so no constant offset appears).
- -ffp-contract=fast datapoint (not gated): drift <= 6.0e-16 grad / 4.4e-16
  lp on all 3 — no measurable contraction opportunity in these graphs.
- Compile times: 0.13-0.40 s per model (informational target <2s: met;
  diamonds .c = 2.75 MB dominated by 120k %a X literals).
- Artifacts: bench/fortk_emitted/{esnc,blr,diamonds}.c (+_t1.so, _fast.so).
  Fork branch fortk/t1-emitter, not pushed. Full stanli ctest suite green
  after the additive change (incl. new fortk_t1_smoke).

## Notes for F-4+ (not pre-registered, just recorded)

- esnc 19.4 ns/call puts T1 ABOVE the F-2 hand-fused kernel-only estimates
  (~0.2 us for 8schools) — the fused no-dispatch floor is real on tiny
  graphs: executor dispatch+recorder tax is ~14x of the arithmetic there.
- diamonds shows where T1 v1 loses: GEMM-shaped work is memory-bandwidth-bound
  and the executor's Eigen GEMV path is already good. A T1 that wants the GLM
  class must either beat Eigen's blocking or fuse the two X passes (compute
  dbeta in the forward when adjoint-of-out is known to be 1 at the result —
  only valid for single-consumer densities at the root).
- Opcode whitelist growth path: ADD/MUL/DOT/SUM_VEC/INDEX/SLICE/GATHER are
  all trivial to add from the same kernel sources; ISLAND/GEMM = v2.
