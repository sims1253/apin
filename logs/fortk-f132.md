# F-13.2: eigh-fusion interpreter adoption (OP_EIGENDECOMPOSE_SYM)

Pre-registered in WORKLOG.md "F-13.2 pre-registered". Charter: teach stanli
the fused eigendecompose_sym op so F-13's stanc3 eigh-fusion
(4 solver-runs/grad -> 2 on kronecker_gp) lands through the whole stack.

Worktree: external/stanli-f132, branch fortk/f132-eigh off 9b2bf80.
deps/{math,stan,stanc3} symlinked to the shared main-worktree deps
(pattern proven in /tmp/stanli-b7a3fd5). F-10 owns deps/stan atomically; it
does not touch deps/math.

## Design (fixed before coding)

- mir_reader: parse STuple (sized), UTuple (unsized tag), TupleAD decl
  adtypes, TupleProjection exprs (1-based index; index 1 = matrix =
  eigenvectors, 2 = vector = eigenvalues, matching math's
  tuple(vectors, values)). Anything else tuple-shaped stays Unsupported.
- mir.hpp: Expr::TupleProjection kind (index rides lit_i); SizedType
  carries tuple components (additive field).
- lower.cpp: Decl of STuple skips slot creation; Assignment whose rhs is
  StanLib eigendecompose_sym(A) emits OP_EIGENDECOMPOSE_SYM with
  out = fresh n*n vectors slot, out2 = fresh n values slot; the tuple name
  binds in a side map; TupleProjection returns the component Val (NO copy
  op, NO extra slot) so Q1/R1 alias the op outputs directly.
- optable.hpp: X(OP_EIGENDECOMPOSE_SYM) after OP_EIGENVECTORS_SYM. No
  rewrite traits (default: not rerollable, backward reads values) and it
  is automatically a fortk carve blocker (regions.cpp op_supported default
  false). All graph passes already refuse out2>=0 ops (cse candidate rule,
  reroll/partition/inplace guards).
- graph.hpp/executor.cpp: KernelCtx gains Desc out2_adj_vec (out2_adj is
  scalar-only, built for constrain jacobians); make_ctx_ fills it when
  op.out2 >= 0 from the existing adjoint arena (written[] already covers
  out2, so the cells exist).
- Kernel (matrix_fns.cpp): ONE SelfAdjointEigenSolver (full mode; vectors
  are a real output so values_only() may not shortcut). check_symmetric
  spelling "eigendecompose_sym" per math rev/fun/eigendecompose_sym.hpp.
  vectors -> out, values -> out2, no scratch needed (V lives in out,
  eigenvalues in out2; the backward rereads them exactly like
  eigvecs_bwd reads ctx.out).

### Bit-identity argument (the load-bearing one)

Stock two-call graph (source order Q=eigenvectors_sym(A); R=eigenvalues_sym(A)):
ops [EIGENVECTORS(out=Qslot), EIGENVALUES(out=Rslot)] adjacent; reverse
sweep fires eigvals_bwd then eigvecs_bwd, back to back, accumulating into
the same zero-initialized A adjoint cells:
  A_adj += V * diag(R_adj) * V^T          (eigvals_bwd)
  A_adj += V * f o (V^T * Qslot_adj) * V^T (eigvecs_bwd)
Each stock op runs its own SelfAdjointEigenSolver on the SAME input slot,
deterministically -> identical V and eigenvalues in both runs.

Fused op: one solver; same V in out, same values in out2; backward computes
the SAME two expressions with the SAME Eigen spellings and accumulates with
two += into the same cells. The fused op's position in the graph is the
tuple assignment's position, i.e. where the FIRST stock op sat; in the
reverse sweep the pair of contributions still lands consecutively (nothing
fires between the two stock backwards; the two statements were adjacent).
Order within the pair does not matter bitwise: IEEE addition is commutative
and the cells start at 0 (0 + c1 = c1 exactly), so
fl(fl(0+c1)+c2) = fl(c1+c2) = fl(c2+c1) either way. This is also why math's
single-callback form `A_adj += (value_adj + vector_adj)` (one fl(c1+c2))
is bitwise equal to stanli's two-op stock form. Same GEMM expression text
in all three (stan-math rev spellings transcribed operand-for-operand,
-ffp-contract=off pinned).

Adjoint seeding: consumers of Q1/R1 accumulate into the out/out2 adjoint
cells (they are ordinary written slots); the fused backward reads
out_adj_vec (vectors) and out2_adj_vec (values) after all consumers fired,
exactly as the stock backwards read Qslot/Rslot adjoints.

## Gates (pre-registered, never loosened)

(a) kronecker_gp 64-pt verification BITWISE vs the STOCK two-call arm
    (grad_relL2 = 0.0, logp_rel = 0.0). Cross-arm: same 64 seeded points
    (mt19937 20260826, same np), stock arm = pinned stanc two-call
    lowering, fused arm = F-13 stanc. Tool extension (this branch, additive,
    env-gated): FORTK_DUMP=<prefix> writes %.17g lp + grad per point for
    ex0 and ex1 during VERIFY; diff across arms.
(b) µs/call <= 240 on kronecker (F-13 projected 224-227; stock 284.5).
    3 tool runs, taskset-pinned, medians.
(c) ctest green.
(d) Non-fusion neutrality: stanc3's eigh-fusion.stan (fused pairs + reverse
    order + different-args + non-adjacent) lowers the non-fused parts to
    stock two-call ops and verifies.
(e) dump_ops on kronecker: 2 OP_EIGENDECOMPOSE_SYM in the log_prob graph
    (not 4 stock eigh ops).

## Log

- [setup] worktree + branch created at 9b2bf80; deps symlinks in.
  /tmp/f132-stage: deps/stanc3/stanc -> F-13 built
  external/stanc3/_build/default/src/stanc/stanc.exe; kronecker model/data
  + eigh-fusion fixture copies. Tool runs from that cwd.
  /tmp/f132-stockstage: same but deps/stanc3/stanc -> pinned nightly
  (4d440ee) for the stock arm. F-10's base_nuts.hpp patch is live in the
  shared deps/stan (sampler-only; disjoint from the graph/executor paths
  this task touches).
- [impl] mir.hpp/mir_reader: Expr::TupleProjection (1-based index in
  lit_i; 1 = matrix/vectors, 2 = vector/values), SizedType.tuple
  components, read_sized STuple, read_expr UTuple type tag, Decl
  TupleAD parsing (all-AutoDiffable log_prob form + all-DataOnly GQ
  re-declaration; MIXED adlevels are a loud reader error; initialized
  tuple Decls fail in the lowering). graph.hpp/executor: KernelCtx gained
  Desc out2_adj_vec (out2_adj is scalar-only; make_ctx_ fills it from the
  out2 slot's adjoint-arena region, which bind_ already allocates because
  written[] covers out2). optable: X(OP_EIGENDECOMPOSE_SYM). lower.cpp:
  STuple Decl skips slot creation (shadowing doctrine preserved);
  Assignment rhs = StanLib eigendecompose_sym (whole-variable form the
  pass emits only) emits the op via emit_value(..., out2=wslot) with
  out = n*n vectors slot, out2 = n values slot, idata {n}; tuple name
  recorded in eigh_tuples; TupleProjection lowers to the component Val
  with NO copy op (Q/R alias the op outputs; consumers' require_binding
  against the original declarations cross-checks shapes). Kernel in
  matrix_fns.cpp: one SelfAdjointEigenSolver (values_only may NOT
  shortcut -- vectors are a real output), check_symmetric spelling
  "eigendecompose_sym" per math rev, no scratch (V in out, values in
  out2; backward rereads like eigvecs_bwd does). All graph passes
  already refuse out2>=0 ops (cse candidate rule, reroll/partition/
  inplace guards) and fortk op_supported defaults false -> carve blocker,
  as pre-registered.
- [tool] regions.cpp: env-gated FORTK_DUMP=<prefix> writes %.17g lp +
  full grad per VERIFY point for ex0/ex1 (64 points are a pure function
  of seed 20260826 + np, so arms are comparable by byte diff).
  dump_ops prints out2 slots. Test: test_eigen.cpp gained the fused
  kernel vs math's eigendecompose_sym-on-var oracle AND vs the stock
  two-op pair as a second bitwise oracle (1x1, 2x2, 3x3 x2, 30x30).
- [build] first -j4 run killed by earlyoom (four other agents compiling;
  the 7.6GB-class density shards) -> -j2. One compile error (s2 scope in
  make_ctx_) fixed; TupleAD list shape fixed (components live in ONE
  list child); SizedType field order fixed (test uses aggregate init).

## Results

- GATE (a) BITWISE, kronecker_gp 64 pts, TWO ways:
  (i) cross-stanc: fused arm (F-13 stanc) vs stock arm (pinned nightly
  stanc), same tool build: FORTK_DUMP diffs EMPTY for BOTH ex0
  (interpreter) and ex1 (fortk regions) -> grad_relL2 = 0.0, logp_rel =
  0.0 exactly (28096 lines: 64 x (lp + 438 grads) each arm).
  (ii) same-stanc isolation: defuse_tmir.py (in /tmp/f132-stage)
  rewrites the fused tmir's tuple regions back to the two-call form
  (0 tuple nodes remain; byte-equivalent to an unfused stanc for the
  same program); fused-vs-defused tmir through the identical tool:
  diffs EMPTY both executors.
- GATE (e): dump_ops kronecker log_prob graph: exactly 2
  EIGENDECOMPOSE_SYM (out len900 vectors, out2 len30 values, idata 30),
  0 stock eigh ops (stock arm: 4 stock ops, 223 vs 221 total ops).
- GATE (d) neutrality, stanc3's eigh-fusion.stan (fused + reversed +
  different-args + non-adjacent + GQ nested block), F-13 stanc: lowers to
  2 EIGENDECOMPOSE_SYM + 4 STOCK ops (EIGENVECTORS/EIGENVALUES for the
  different-args AND non-adjacent pairs -- pass correctly declines);
  VERIFY 2.1e-15 / 0.0 PASS; GQ (DataOnly tuple decls) lowers and runs.
- FINDING (CSE interaction, outside the gates, documented not fixed):
  on models where the SAME symmetric argument feeds a FUSED pair AND a
  stray unfused eigenvectors_sym (the fixture's Q3), stock's CSE merges
  the duplicate eigenvectors_sym ops into one pullback of the combined
  adjoint, while the fused op (out2) is not CSE-mergeable with a plain
  EIGENVECTORS_SYM -- the stray op survives, and its separate pullback
  reassociates the operand adjoint accumulation. Effect: last-ulp
  gradient differences (rel ~1e-14..1e-15; every VERIFY passes; lp
  identical). Kronecker-class models (argument feeds only the pair) are
  unaffected -- byte-identical as measured above. This is the same
  reassociation class OPTIMIZATIONS.md defers; fixing it would teach cse
  the two subsumption rules (EIGENVECTORS/EIGENVALUES <= earlier
  EIGENDECOMPOSE_SYM on the same input version); declined as
  out-of-scope gold-plating, noted here for the record.
- GATE (b) PERF, kronecker_gp, taskset -c 2, 3 interleaved tool runs per
  arm (each = tool-internal 3-rep median), both arms ONE fortk_t1r build:
  - GATE round (load ~2.9, one sibling agent benching):
    fused interpreter arm (unfused_ns): 232.3 / 226.2 / 234.0 -> 232.3
    us/call MEDIAN <= 240 PASS; fused region arm 229.2 us.
    stock interpreter arm: 287.7 us (F-13 baseline 284.5, matched);
    stock region arm 291.9 (F-13: 287.2).
    speedup (interpreter arms): 287.7 / 232.3 = 1.239x (F-13 projected
    1.27x => 224-227; measured 232.3 under residual sibling load).
  - noisy round 1 kept for the record (4 sibling compilers): fused
    247.2 vs stock 316.1 = same ~1.28x matched-noise ratio.
- GATE (c) SUITE: build-f132 ctest 63/63 PASS; test_eigen OK (the fused
  kernel bitwise-equals math's eigendecompose_sym-on-var AND the stock
  two-op pair at 1x1/2x2/3x3x2/30x30).

## Verdict

All five pre-registered gates PASS on the first complete run:
(a) kronecker 64-pt BITWISE vs the stock two-call arm, proven two ways
    (cross-stanc and same-stanc tmir surgery; one md5 across all five
    dump files); (b) 232.3 us/call <= 240; (c) ctest 63/63; (d) the
    non-adjacent/different-args idiom still lowers to stock two-call ops
    and the mixed model verifies; (e) dump_ops shows 2 EIGENDECOMPOSE_SYM.
F-13's projected ~1.27x is realized as 1.24x measured under a loaded
box (stock baseline re-matched at 287.7). One finding recorded (CSE
interaction above, outside the gates). The eigh fusion is now
end-to-end: stanc (F-13) -> mir reader -> lowering -> one-solver kernel
-> executor, with the fortk carver still treating it as an interpreted
blocker by default.

## Artifacts

- bench/fortk_f132/: bench_summary.txt (both rounds, medians), dump
  files + bitwise_md5.txt (all one hash), op dumps (kronecker fused/
  defused, fixture), fixture + probe models, defuse_tmir.py.
- /tmp/f132-stage (fused arm), /tmp/f132-stockstage (stock arm): full
  run outputs, FORTK_DUMP files, probe models.
- Branch fortk/f132-eigh @ external/stanli-f132: 3 commits
  (53db89a reader grammar, 844ad46 op+lowering+kernel, 08db4b6
  tests+tooling). No push, per rules.


