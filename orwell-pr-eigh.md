# eigendecompose_sym: tuple MIR grammar + one-solver kernel

## Problem

The natural two-call idiom (eigenvectors_sym then eigenvalues_sym on the same matrix) runs two full SelfAdjointEigenSolvers per gradient where one suffices — on kronecker_gp, eigh is 51.3% of op time and the eigenvalues forward pass (21.2% of grad) is pure duplication. The combined primitive (eigendecompose_sym, CmdStan 2.34) was never expressible in stanli's MIR reader and never lowered.

## Evidence

- mir reader: STuple sized types, TupleAD decls, 1-based TupleProjection (anything else tuple-shaped stays a loud error); lowering emits one OP_EIGENDECOMPOSE_SYM (out=vectors, out2=values, projections alias with no copy op); kernel = one solver + the combined pullback V(g_w + f o (V^T g_Q))V^T transcribed in stock order.
- kronecker_gp 64-pt verification BITWISE vs the stock two-call arm: 0.0/0.0, proven two ways (cross-stanc fused-vs-nightly, and same-stanc tmir surgery defusing the tuple back to two calls — one md5 across all dump files).
- kronecker_gp interpreter arm: 4.840M -> 3.810M callgrind Ir per gradient eval = 1.27x, the load-stable instrument (busy-box wall 1.24x at the 85a8f11 base, 1.32x re-measured at the rebased tip; region arm 1.27x Ir likewise); kronecker ops 221 -> 94; draws through NUTS bit-identical to the unfused arm (the fusion's bit-identity realized end-to-end).
- Non-fusion neutrality: reversed-order / different-args / non-adjacent / GQ-nested variants still lower to stock two-call ops (verify 2.1e-15); models without the idiom verify unchanged.

## Validation

ctest green incl. test_eigen (fused kernel bitwise-equals math's eigendecompose_sym-on-var AND the stock two-op pair at 1x1..30x30); esnc verify unchanged (bitwise) — the reader change is inert without tuple nodes. Rebase note: portable-MIR v2 expression tags are Expr::Kind ordinals, so the new kind sits after Unsupported (tag 10 stays the last decodable; v2 wire never carries tuples).

## References

CROSS-PROJECT: requires the fused tmir from sims1253/stanc3 (eigendecompose_sym fusion pass, --O1+) to fire; with stock stanc nothing changes. apin WORKLOG F-13/F-13.2/F-19/F-20; logs/fortk-f13{,2}.md + f19/f20 (Ir instrument mirrors the stanc3 PR's own callgrind protocol). Known limitation: a fused pair sharing its argument with a stray unfused eigenvectors_sym reassociates the operand adjoint at <=1e-14 rel (lp identical, gates pass); kronecker-class unaffected.

Rebased onto 33f79dea; all measurements taken at the 85a8f11 base (pre-rebase); re-gated at the rebased tip.
