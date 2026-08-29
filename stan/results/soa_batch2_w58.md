# W-58 — SoA arena batch rollout, BATCH 2: all 21 broadcast/one-autodiff sites shipped; one develop-only regression caught by gate (c) and fixed substrate-level; bit-exact everywhere; hier_2pl unchanged (as pre-registered)

Date: 2026-08-24. Pre-registration: WORKLOG.md W-58 (+ the gate-failure
entry). Inputs: W-57 (results/soa_batch1_w57.md), migration plan
results/soa_var_w53.md §2. Cumulative state after this batch: **batches
0+1+2 = the complete code-changing migration of the four eltwise op
families; hier_2pl −15.9%T / −17.1%G Ir, −6..−7% in-sampler wall,
bit-exact at every level probed.**

## 1. Scope + implementation

21 sites: subtract ×6 (VarMat−Arith, Arith−VarMat, Var−EigMat,
EigMat−Var, Var−VarMat, VarMat−Var), add ×3 (the non-delegating
overloads), divide ×6 (m/c, c/m, m1/m2 × one-autodiff variants),
multiply ×4 (GEMM arith×var + var×arith via the W-57 arena-temp
pattern; scalar×matrix both one-autodiff variants), elt_multiply ×2
(the mixed branches). Guards `is_eigen_v<ret_type>` (or
`promote_scalar_t<var, Mat>` for divide's scalar shapes); stock else
arms verbatim. Bundle GEMM arms use `val_op()` (Eigen 3.4
CwiseUnaryView const-qualifier — matches bundle stock), develop
`val()`. Trees stay byte-identical except those stock-spelling lines.

## 2. The caught regression (the batch's headline lesson)

Gate (c) on develop/Eigen-5 compile-FAILED add_test/subtract_test:
`make_nochain_vari_array`'s linear `expr.coeff(i)` walk static-asserts
on 2D CwiseBinaryOps without `LinearAccessBit` (scalar-var vs
Eigen-block operands). Bundle/Eigen-3.4 compiles — gates (a)/(b) were
green — so ONLY the second toolchain saw it. Fix (substrate,
both trees): compile-time branch on `(Eig::Flags & Eigen::LinearAccessBit)`
— linear walk unchanged for the hot (gated) path; 2D col-major
`coeff(i,j)` walk otherwise (identical per-element arithmetic; also
correct for RowMajor arith operands). Verified by
linear_access_probe (block/RowMajor/adjoint closed forms, all PASS)
and the full battery. Upstream-PR lesson: encode the Eigen-5
linear-access constraint in the helper, never at call sites.

## 3. Gates (all PASS on the fixed substrate, fresh binaries)

| gate | result |
|---|---|
| (a) parity 4 models ×100 pts | 0/400 values, 0/400 gradients |
| (b) draws md5 | stock = patched = fe7c57c99a7a6530ce2dcc408d6e9c65 |
| (c) unit tests (19 targets) | **392/0** — incl. add 18, subtract 18, operator_addition 84, operator_subtraction 84, operator_division 48, operator_multiplication 108, multiply1/2, diag_pre/post, lmultiply family, matrix_exp_multiply, scale_matrix_exp_multiply |
| (d) callgrind (fresh both arms) | patched T 31,194,060,751 / G 28,767,198,065 vs W-57 patched 31,207,289,278 / 28,780,442,093 — NO-REGRESS (−0.04%/−0.046%, marginally better); stock T 37,130,444,615 (+0.005% continuity); 4,493 gradient calls identical; md5 exact under valgrind |
| (e) wall in-sampler (5 interleaved rounds) | clean rounds (stock r3–5): warmup −6.2%, sampling −6.9%; patched bands [934..958]/[957..972] indistinguishable from W-57 patched — as pre-registered for cold branches (hier_2pl does not exercise them materially) |

## 4. Measurement notes + incidents

- Stock rounds r1–2 of the wall gate were spiked by concurrent agents
  (1997/1258 µs); medians are robust but the honest headline uses
  clean rounds. Coordinator-driven re-gate after the first re-gate
  agent died on model-infra error (filesystem-state reconstruction;
  no gate result depends on agent memory).
- Wall harness: v1 w58 script displayed W-57's data (hardcoded
  analysis path + missing bc). Caught because numbers matched W-57
  EXACTLY — identical-to-previous results are a red flag. v2 script
  (awk, $OUT-relative analysis) is durable; W-57's copy keeps the
  bugs — do not reuse unfixed.

## 5. Verdict + what remains

**BATCH 2: GO — shipped and gated. The migration plan's code-changing
batches (0, 1, 2) are COMPLETE.** Remaining before an upstream PR:
(i) record-loop restructure (raw vptr-store + memcpy'd val block;
removes the +9 Ir/record placement-new term; wall-gated per
toolchain — W-53 §5.3); (ii) one demonstrator model that exercises
the mixed branches (blr/diamonds class) to show batch-2 value where
it bites; (iii) batches 3/4 lifetime audits (audit-only, no code
change expected). Increment-B (record shrinking) deprioritized by
W-57's flat model-level LLd finding.

Artifacts: scratch/w57/ — w58_soa_batch012_{develop,bundle}.patch
(cumulative 14-file artifact), w58_batch2_{bundle.patch,develop.diff},
linear_access_probe.cpp, instantiate_probe.cpp, draws_w58_final/,
profile_w58/, wall_w58/ (raw.txt + v2 script), stock_so_md5_w58.txt.
