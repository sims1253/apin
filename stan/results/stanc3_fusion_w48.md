# W-48 — stanc3 expression fusion for indexed elementwise likelihood arguments: the compiler transform works, and it buys nothing (a measured negative with the mechanism)

Date: 2026-08-22/23. Pre-registration: WORKLOG.md W-48. Continuation of a
predecessor session (died on infra rate limits at 14:11 after ~70 min; all
state salvaged — see §2). Clone `external/stanc3` branch **w48-fusion**
@ commit **4b07a23** (off develop master `90c6532`); patch:
`scratch/w48/stanc3_fusion.patch` (2629 lines, applies to 90c6532).
Model under test: `models/hier_2pl.stan` (unmodified), N=19,200.

**Headline: candidate A (the narrow peephole) was implemented, is
CORRECT (bit-identical gradients and bit-identical same-seed draws vs
stock at the same -O level), fires ONLY on the intended pattern, and is
performance-NEUTRAL: +0.59% Ir/grad, +0.8% per-call wall vs stock at
--Oexperimental — nowhere near the −28.2% Ir / −25% wall gates from
W-34. Attribution shows why, and it refutes the W-34 §7.2(a)(b)
hypothesis: on current stan-math (5.3.0), stock eltwise ops over
gathered containers already cost only one arena matrix + one callback
vari per OP (not per element); what remains is per-element value-gather
and adjoint-scatter, which an eltwise-shape fusion cannot remove — it
can only re-arrange it (and the AoS `value_of` gather + vari** pointer
collection re-add as much as the removed op boundaries save). The
−28.2% ceiling belongs to eliminating per-element work entirely — the
complete-grid GEMM identity (W-34 arm B) — reachable in the compiler
only by grid-pattern recognition, or in stan-math by a gathered-GLM
primitive (W-34 §7.3). The GLM-codegen study (degradation item i) is
confirmed and recorded in §4.**

## 1. The transform (what shipped on the branch)

- **MIR pass** `Optimize.fuse_indexed_eltwise` (runs LAST in the suite,
  `--Oexperimental` only; O0/O1 explicitly off): matches
  `target += bernoulli_logit_lpmf(...)` in the REVERSE-mode log prob
  only, where some argument is a pure tree of elementwise
  `+ - .* ./` over containers indexed once by a multi-index whose index
  expression is a data variable (≤ 8 distinct leaves). Wraps the chain
  in an internal `fused_eltwise_eta` marker. Nothing else is touched.
- **Backend** `Lower_expr.Fused_eltwise` + a new `Cpp.IIFE` expression
  (immediately-invoked lambda in expression position): the marker lowers
  to code that (1) gathers each leaf's VALUES once in double space
  (`rvalue(value_of(x), "x", index_multi(idx))`, arena materialized),
  (2) records each leaf's adjoint route — plain `Matrix<var>` containers
  get an arena `vari**` array of per-element `vi_` pointers filled
  forward; `var_value<VectorXd>` (SoA) containers keep just `x.vi_` —
  chosen at compile time via `if constexpr (stan::is_var_v<...>)` on the
  container type, so one lowering serves both layouts; (3) computes the
  chain value with Eigen double expressions (identical per-element
  arithmetic/order to stock); (4) creates ONE
  `vari_value<Eigen::VectorXd>` for the whole vector; (5) registers ONE
  `reverse_pass_callback` whose body applies the symbolic batched chain
  rule per leaf with the partials evaluated inline per element
  (`p[n]->adj_ += d.coeff(n) * t0.coeff(n)` / SoA
  `s->adj_.coeffRef(i[n]-1) += ...`). `check_matching_dims` guards are
  emitted per node. This is the partials-in-forward structure of the GLM
  lpmfs, synthesized by the compiler — the exact machinery route W-39
  proved with `fuse_eigendecompose`.
- **Tests**: new integration model
  `test/integration/good/compiler-optimizations/fused-eltwise.stan`
  (2 firing cases, 3 guarded non-firing cases: scalar non-indexed
  operand, non-data index expression, non-bernoulli_logit density);
  expectations regenerated for cpp/cppO0/cppO1. Fused code appears ONLY
  in the `--Oexperimental` expectations (22 `fused_elt__v` lines; 0 at
  O0/O1).

## 2. Salvage from the predecessor (timeline + what was reused)

The predecessor (13:03–14:11, died on rate limits) left: the full
implementation above as uncommitted edits on `w48-fusion`; five .so arms
(`stock_build` 13:11, `handfused_build` 13:20, `stock_oexp` 13:41,
`fused_build` 13:52, `fused_o1` 14:08); five callgrind profiles; gate
scripts; the no-transform artifacts; regenerated test expectations; and
one final unbuilt edit (14:11) that gated the pass to Oexperimental-only.
No written results survived. Everything was re-verified by me: current
tree builds green (`dune build`, opam switch w39), reproduces
`fused_build/hier_2pl.hpp` byte-identically (path comments aside) and
the three pattern-free hpps; the stale `fused_o1` arm (built when the
pass fired at O1) was replaced by the correct statement: patched stanc
`--O1` output is bit-identical to vanilla `--O1` (the pass is off).
**Confound identified**: `stock_build`/`handfused_build` were compiled
against a since-reverted W-46-patched stan-math (vectorized log1p) —
they carry `w46_kern::fwd_avx2`; `stock_oexp`/`fused_build` are pristine
math. Cross-arm comparisons use only the pristine pair.

## 3. Gates (W-34 protocol; arbiter)

Builds: bridgestan 2.9.0 (pristine stan-math 5.3.0), default CXXFLAGS,
`env -u LD_LIBRARY_PATH`, `/usr/bin/make -j2`, custom stanc via
`STANC=`, fresh scratch/w48 dirs. All four arms traced the IDENTICAL
2172 gradient calls (callgrind), so totals compare directly.

**(a) SEMANTICS — PASS, bit-identical (stronger than the pre-registered
last-ulp).** 100 random N(0,1) + 100 posterior-cloud points
(`scratch/w48/w48_gatea_oexp.py`): max rel logp **0.0**, worst grad
rel-L2 **0.0**, cosine 1.0 (12 dp) — stock-Oexp vs fused-Oexp. Expected
mechanistically: the fusion evaluates the same per-element expressions
in the same order (Eigen cwise ops on gathered values), so no
reordering occurs (W-34's GEMM arm reordered and showed 2.3e-15). A
comparison against the w46-math stock arm shows 3.0e-10 rel-L2 — that
is the W-46 log1p kernel, not the fusion (isolated and explained).

**(b) COST — FAIL (neutral).** Callgrind W-29 protocol (valgrind 3.23,
stan_cli, warmup 50 + samples 20, seed 20260819, pf init, one job at a
time; `scratch/w48/prof/`):

| arm (pristine math) | Ir/grad | vs stock |
|---|---|---|
| stock `--Oexperimental` | 5,644,934 | — |
| fused `--Oexperimental` (final lowering) | 5,678,304 | **+0.59%** |
| fused (intermediate 13:38 lowering, hoisted w-temps) | 5,809,906 | +2.92% |
| *(confounded, w46 math)* stock `--O1` | 3,732,725 | — |
| *(confounded, w46 math)* hand-coded same fusion | 4,030,099 | +7.97% |

Wall (200 posterior-cloud pts, 7 interleaved reps, medians, taskset
0-3): stock 665.8 → fused 671.1 µs/call = **+0.80%**
(`scratch/w48/w48_wall_final.py`). Gates asked: approach −25% wall,
−28.2% Ir ceiling. The hand-coded reference (a careful manual version
of the same shape, `handfused_build/`) ALSO loses to its stock — the
negative is structural, not an artifact of compiler-generated code.

**(c) SAMPLER — PASS by bit-identity.** Same-seed short runs (stan_cli,
seed 20260822, warmup 50 + samples 20): draws CSVs **bit-identical**
(`cmp` clean; `scratch/w48/gatec/`). Identical draws ⇒ identical ESS/rhat
by construction; no separate ESS computation needed.

**(d) NO-TRANSFORM — PASS.** `arma11`, `gp_regr`, `lotka_volterra`
compiled at `--Oexperimental` with patched vs vanilla stanc: hpp diff is
exactly ONE line each (the embedded `stancflags` comment). Reproduced
fresh from the current tree.

**(e) SUITE — PASS.** `dune runtest -j2` exit 0 on the full tree (twice;
silent-on-success dune). Uncached confirmation: cppO0/cppO1 outputs
regenerated and byte-equal to expectations; a manual `--Oexperimental
--print-cpp` sweep over all 47 models in the directory matches
`cpp.expected` in content (only the harness's `[exit 0]` formatting
differs). Fused code present only at Oexperimental.

## 4. GLM-codegen study (degradation item i — confirmed upstream fact)

How `bernoulli_logit_glm_lpmf` / `normal_id_glm_lpdf` get their special
treatment: **entirely in stan-math, none in stanc3.**

- All 8 GLM densities live in single headers
  `stan/math/prim/prob/{bernoulli_logit,binomial_logit,categorical_logit,neg_binomial_2_log,normal_id,ordered_logistic,poisson_log}*_glm_*.hpp`
  (bridgestan 2.9.0 / stan-math 5.3.0). There is NO `rev/prob`
  counterpart (`stan/math/rev/prob/` contains only
  `std_normal_log_qf.hpp`, `student_t_qf.hpp`): the prim templates
  handle `var` arguments through `operands_and_partials` /
  `partials_propagator` — value AND partials computed in one forward
  pass, one edge per operand, reverse pass is the edge application. That
  is the whole trick (W-34 called it the diamonds pattern).
- stanc3 contributes ONLY: signature tables
  (`src/stan_math_signatures/`), OpenCL dispatch restrictions +
  `opencl_supported_functions` in `src/stan_math_backend/Transform_Mir.ml`
  (~line 125–170), and pedantic warnings
  (`Pedantic_dist_warnings.ml`). No codegen special-casing whatsoever —
  a GLM call is emitted as a plain `stan::math::*_glm_lpmf(...>` call.
- Consequence for a general fusion mechanism: there are exactly two
  reusable routes. (1) Math-side: put the fusion inside a distribution
  (the GLM route) — requires new prim functions. (2) Compiler-side:
  synthesize the partials-in-forward code at the call site — exactly
  what W-39 (eigh pair) and this W-48 patch do with MIR markers +
  backend lowering + `reverse_pass_callback`. Route (2) is now proven
  end-to-end twice; this experiment measures its ceiling on the
  eltwise-argument pattern: ~zero.

## 5. Why neutral — attribution (exclusive Ir, per run of 2172 grads)

Stock eltwise+gather complex at `--Oexperimental`, pristine math
(`scratch/w48/prof/cg_stock_oexp.out`):

| complex | stock | fused |
|---|---|---|
| gathers fwd (`rvalue<index_multi>`: AoS 0.889G + SoA 0.869G) | 1.758 G | ~2.34 G (value_of-expr gather 0.890G + arena ctors 0.647G/0.445G/0.364G) |
| eltwise op fwd (`subtract` + `elt_multiply`) | 1.314 G | 0.788 G (IIFE lambda: eta, checks, vari** fills) + 0.293 G (t0/eta arena + vari ctor) |
| reverse callbacks | 1.212 G (elt_mult 0.485G + sub 0.444G + rvalue 0.283G) | 1.091 G (single fused callback) |
| **complex total** | **4.284 G (34.9% of G)** | **4.517 G (36.7% of G)** |

The transform removes the op-boundary objects (2 output arena matrices +
2–3 callback varis per gradient — the things W-34's "per-element vari"
framing predicted were the tax) and finds ~0.3G/2172 ≈ 138k Ir/grad of
savings in the reverse pass, then re-spends it forward: gathering values
through a `value_of(Eigen-expr)` materialization is MORE expensive than
stock's direct var gather for AoS (`Matrix<var>`) containers, and the
fused reverse needs per-element adjoint routes (`vari**` arrays filled
forward, 2×19,200 pointer writes/grad for alpha+beta) that stock simply
reads from its lazy Holder operands in reverse. The lowering iteration
history (hoisted-w-temps variant +2.9% → inline-partials +0.6%)
shows the residual gap is structural slack, not implementation slack.

Root cause: on stan-math 5.3.0 the eltwise rev ops over these types
(`subtract(var_value, Holder<AoS-gather>)`, `elt_multiply(Holder<...>,
var_value)`) are ALREADY one-callback-per-op with arena value matrices —
the per-element cost is value-gather + adjoint-scatter, inherent to
indexed AoS arguments. (W-34's measurements quoted a per-element vari
plumbing tax of ~32%G on stanc 2.39-era codegen; on current develop
math + this profile the same line's complex is ~35% of G but
op-boundary overhead inside it is small — the 3.15M Ir/grad the GEMM
removed was mostly per-element work.)

Secondary observation: alpha/beta are `Matrix<var>` (AoS) only because
the transformed-parameters block assigns them per-element in a loop
(`alpha[i] = exp(xi[i,1])`). A vectorized tp assignment would keep them
`var_value<VectorXd>` (SoA), making both stock and fused gathers cheap
`.val()` block reads — an orthogonal stanc3 codegen/layout lever worth
recording.

## 6. What WOULD reach the ceiling (design sketch, replaces candidate B)

Candidate B (general middle-end fusion of elementwise chains) is MOOT:
fusion at the eltwise level cannot beat ~0 (§5). The −28.2% is
grid-structure exploitation:

1. **stanc3 grid-detection pass** (the direct compiler fix): recognize
   complete-design IRT likelihoods — `y ~ d( a[ii] .* (t[jj] − b[ii]) )`
   where (ii, jj) is the complete item-major J×I grid — and rewrite to
   the W-34 arm-B form (`eta = [theta, −1] · [alpha; alpha.*beta]`,
   `to_vector`, same lpmf). Grid completeness is checkable at run time
   once per call (O(N) int pass) or from data constraints. Wins only
   complete-grid datasets (hier_2pl/lsat class), but there it removes
   per-element work entirely. Difficulty: moderate (pattern + rewrite
   + the runtime guard); payoff: the full −28%.
2. **stan-math gathered-GLM primitive** (W-34 §7.3(i)):
   `bernoulli_logit_glm_lpmf(y | theta, jj, alpha, beta, ii)` taking
   index vectors — partials-in-forward for the gathered/bilinear
   predictor class, generalizes to Rasch/ordinal/rating. This is the
   math-side route and the strongest upstream story.
3. Not worth pursuing: further eltwise-fusion lowering polish (bounded
   by §5 at roughly −6..−11% Ir even if perfect, with wall gains smaller).

## 7. Verdict + artifacts

- The W-34 §7.2(a)(b) hypothesis ("peephole + one fused vari ≈ measured
  ~28% ceiling") is **REFUTED for the eltwise shape** on current math;
  recorded here and to be reflected in the upstream pack (the
  hier2pl-plumbing candidate becomes: grid-GEMM detection or
  gathered-GLM, not eltwise fusion).
- The transform itself is a validated, tested, default-off experimental
  pass — kept on the branch as the reference implementation of
  compiler-synthesized custom varis (second successful use of the W-39
  mechanism), with honest numbers attached.
- Artifacts: `external/stanc3` branch `w48-fusion` @ 4b07a23 (base
  90c6532; `w39-eigh` and `stanc3_pr` untouched); patch
  `scratch/w48/stanc3_fusion.patch`; profiles + scripts
  `scratch/w48/prof/`, `scratch/w48/*.py`; gate-c draws
  `scratch/w48/gatec/`. Reproduction: §3 commands (gatea_oexp /
  wall_final scripts; callgrind cmds recorded in `prof/cg_*.out`
  headers).
