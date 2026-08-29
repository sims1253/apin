# F-13: eigh-fusion stanc3 pass on fortk kronecker-class models

GOAL: measure what halving the eigendecomposition work does to kronecker_gp
(and accel_gp if time permits) through stanli's whole stack (interpreted eigh
ops + fused regions around them), using the fusion stanc3 @ b5f600a6 as a
drop-in `deps/stanc3/stanc` swap for the pinned tool
(/tmp/stanli-b7a3fd5/build-f8/fortk_t1r, read-only).

OUTCOME IN ONE LINE: stanc toolchain built well inside the timebox and the
fusion fires on kronecker_gp (4 -> 2 decompositions), BUT the pinned stanli
tool cannot lower the fused tmir (no STuple/UTuple/TupleProjection/
eigendecompose_sym support) -> fused arm = hard REJECT; profile-grounded
PROJECTION (not measurement) of the win is ~1.26-1.27x, above the 1.15x bar.

## 1. Toolchain (timebox 45 min; used ~13 min)

- No opam on machine. opam 2.5.2 binary -> ~/bin/opam (direct release
  download, no sudo).
- `opam init --disable-sandboxing --bare --no-setup` (fast, squashfs repo).
- `opam switch create f13 ocaml-base-compiler.5.5.0 -j 4`: 2:56 (4 cores,
  235% cpu).
- `opam install --deps-only ./stanc.opam -y -j 4` (menhir 20260209, fmt
  0.11.0, yojson 3.0.0, cmdliner 2.1.1, ppx_deriving 6.1.1, ppx_compare,
  ppx_sexp_conv, ppx_expect_nobase): 1:25.
- `dune build src/stanc/stanc.exe -j 4`: 6.1 s.
- Binary: external/stanc3/_build/default/src/stanc/stanc.exe (12.0 MB;
  --version prints `%%NAME%%3 %%VERSION%%` placeholders — dune subst not run,
  cosmetic only). Copied to /tmp/f13-stage/deps/stanc3/stanc.
- external/stanc3 checkout state untouched: HEAD still b5f600a6, no tracked
  diffs, _build/ gitignored. Nothing committed. Ubuntu 22.04 apt ocaml (4.13)
  is far too old for the pinned menhir/ppx suite — the opam switch is
  mandatory.

## 2. Fusion-fired confirmation (tmir level)

stanc --O1 --debug-optimized-mir kronecker_gp.stan (n1=n2=30; two adjacent
pairs at model lines 63-66: Q1/R1 from Sigma1, Q2/R2 from Lambda):

- STOCK stanc (pinned tool's, v4d440ee): 4 eigen FunApps
  (eigenvectors_sym x2 + eigenvalues_sym x2), 0 eigendecompose_sym.
- FUSED stanc (mine, @b5f600a6): 2 `FunApp (StanLib eigendecompose_sym ...)`
  + 4 TupleProjection on `eigh_fusedsym28__/29__`, 0 two-call remnants.
  UTuple(UMatrix UVector) decls present.
- Decomposition count: 4 solver-runs/gradient -> 2 (at both the stan-math and
  interpreter level: in grad mode BOTH interpreter kernels run a full
  SelfAdjointEigenSolver — see 4 below).

## 3. Pinned-tool outcome on the fused tmir: HARD REJECT (rc 134)

From /tmp/f13-stage (deps/stanc3/stanc = fused binary):
`fortk_t1r kronecker_gp.stan kronecker_gp.json out/fused --name kronecker_gp
--inspect` ->
`terminate called after throwing an instance of 'stanli::CompileError'
  what():  stanli compile: unsupported sized type STuple | in: (STuple
  ((SMatrix ...`
(rc 134, uncaught CompileError abort.)

Root cause (verified in /tmp/stanli-b7a3fd5/runtime/src — and identical to
external/stanli main): mir_reader.cpp handles NO tuple nodes (expr grammar =
Var/Lit/FunApp/Promotion/TernaryIf/EOr/EAnd/Indexed only; everything else ->
Expr::Unsupported); read_unsized/read_sized know no UTuple/STuple; lower.cpp
has no eigendecompose_sym (only eigenvalues_sym/eigenvectors_sym at
lower.cpp:3667-3677); optable.hpp has no OP_EIGENDECOMPOSE_SYM. The fused
tmir therefore cannot be lowered, executed, verified, or timed by the pinned
tool. This holds for ANY model the fusion fires on.

Consequence for step 3 (bit-identity stock-vs-fused-stanc): NOT MEASURABLE —
the fused arm produces no logp/gradient points at all. For the record the
STOCK arm's internal gate is bitwise: VERIFY points=64 seed=20260826
grad_relL2_max=0.000e+00 logp_rel_max=0.000e+00 GATE_CORRECTNESS=PASS (all 3
runs) — matching F-6's kronecker BITWISE row. (Region re-carving was also
moot: carve never ran.)

accel_gp: skipped as moot — models/accel_gp.stan contains NO
eigenvalues_sym/eigenvectors_sym/eigendecompose call at all; the pass cannot
fire there.

## 4. Timing: stock arm measured; fused arm projected from per-op profile

Protocol: taskset -c 2, pinned tool from its own cwd (original
deps/stanc3/stanc), 3 tool-runs, each = tool-internal 3-rep medians
(BENCH_EXEC iters=2000). Background: an F-12-agent clang build ran during
runs 1-2 (<=84% cpu, 1 core); run2 unfused rep spread 7.5% -> re-ran per
protocol (run3 spread 3.7%). Full raw: /tmp/f13-stage/out/stock{,2,3}.run.txt
(+ .fusedrun for the REJECT).

Stock-stanc arm (executor µs/call, medians-of-3-runs in parens):
| run | unfused exec | fused exec | ratio |
|---|---|---|---|
| 1 | 279.9 (279.2/279.9/285.1) | 287.2 (283.6/287.2/289.7) | 0.975 |
| 2 | 284.5 (275.6/284.5/296.3) | 284.9 (284.6/284.9/288.7) | 0.999 |
| 3 | 291.2 (283.1/291.2/293.5) | 297.4 (295.4/297.4/298.7) | 0.979 |
| median | 284.5 | 287.2 | 0.991 |
Consistent with F-6 (274.6/278.1, 0.99x): region fusion alone = parity on
this linalg-bound model. CARVE regions=63 ops=223->157 (matches F-6).

Where the time sits (tool --profile, 500 gradients, unfused executor, run 1;
total 146.47M ns = 292.9 µs/grad incl ~4.6% instrumentation vs bench):
| opcode | calls | fwd ns | bwd ns | % |
|---|---|---|---|---|
| OP_EIGENVECTORS_SYM | 1000 | 30,491,189 | 10,735,761 | 28.1% |
| OP_EIGENVALUES_SYM | 1000 | 30,106,182 | 3,823,854 | 23.2% |
| OP_CONSTRAIN_CHOL_CORR | 500 | 3,595,548 | 24,647,213 | 19.3% |
| OP_GEMM | 2500 | 8,503,353 | 15,299,482 | 16.3% |
| OP_LKJ_CORR_CHOL_LPDF | 500 | 1,468,654 | 1,901,151 | 2.3% |
| next 14 opcodes | — | ~8.9M | ~4.5M | ~9.2% |

eigh = 51.3% of interpreter op time. Key kernel fact (matrix_fns.cpp
eigvals_fwd/eigvecs_fwd, identical in pinned + main): in gradient mode BOTH
run `Eigen::SelfAdjointEigenSolver` in full (vectors) mode — eigvals keeps
the vectors in scratch for its pullback. Measured fwd cost per call is
statistically identical: 30.49 vs 30.11 µs (1.3% apart). EIGENVALUES_SYM fwd
is therefore a pure duplicated 30x30 solve, exactly what the fused
eigendecompose_sym op eliminates; the combined pullback keeps the same GEMM
FLOPs (V(gw + f o (V'gV))V'), so bwd saving ~ 0.

PROJECTION (clearly labeled: NOT executed — tool cannot lower fused tmir):
saving = EIGENVALUES_SYM fwd = 30,106,182 ns / 500 grads = 60.2 µs/call
(21.2% of 284.5) on EITHER executor arm (eigh ops are carve blockers, stay
interpreted in both):
- unfused exec: 284.5 -> ~224.3 µs => ~1.27x
- fused exec:   287.2 -> ~227.0 µs => ~1.27x
Above the >1.15x bar — and a bigger relative win than the PR's stan-math
level (-15.6%) because eigh is a larger share of interpreter time. Remaining
time after the hypothetical fusion: CONSTRAIN_CHOL_CORR bwd 16.8%, GEMM
16.3%, EIGENVECTORS bwd 7.3%, LKJ 2.3% — the next blockers in this class.

## 5. Verdict + adoption note

- Toolbox: BUILT (13 min, well inside 45). Fusion: FIRES (4 -> 2
  decompositions, tmir-verified).
- Through-the-stack measurement: BLOCKED by the pinned tool (CompileError:
  unsupported sized type STuple, rc 134). Fused arm has no verify/bench
  numbers; bit-identity comparison impossible (no fused-arm logp exists).
- Verdict vs >1.15x bar: PROJECTION ~1.27x clears it, but per the gate's
  spirit this is NOT a measured win — treat as "projected pass, unmeasured
  pending interpreter support".
- Adoption path (NOT implemented — post-F-12 branch decision, per scope):
  the deps/stanc3 pin swap alone is INSUFFICIENT. Needs, in the fork:
  (a) mir_reader: parse UTuple/STuple decl types + TupleProjection exprs;
  (b) lower.cpp: eigendecompose_sym -> one new op;
  (c) optable + matrix_fns kernel OP_EIGENDECOMPOSE_SYM: one full solver,
      vectors->out + values->out, vectors retained in scratch; pullback =
      V(ḡ_w + f∘(Vᵀḡ_V V))Vᵀ (the two existing pullbacks share V from one
      scratch — bit-identity argument carries over structurally, same as the
      PR's stan-math proof);
  (d) region carver: keep it a blocker (or support later).
  Expected landing gain per 4: ~60 µs/call on kronecker_gp (~1.27x), plus
  removal of 2 interpreted ops/grad. Also fixes the same idiom corpus-wide
  (any pre-2.34 GP/latent-factor model compiled at --O1+).

## Provenance / hygiene
- /tmp/stanli-b7a3fd5 used read-only (runs from its cwd; nothing written).
- external/stanc3: build artifacts in gitignored _build/ only; no commits.
- opam artifacts: ~/.opam (switch f13), ~/bin/opam.
- Staging + raw outputs: /tmp/f13-stage/ (kronecker_gp.{stan,json},
  kronecker_stock.tmir.sexp, kronecker_fused.tmir.sexp, out/*.run.txt).
- Zero changes to external/stanli, external/stanli-f7, WORKLOG.md, other logs.
