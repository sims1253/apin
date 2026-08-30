# W-129 — family 4 increment 2 (the stanc3 additive emission + TP-LOOP resolution): STOPPED at the pre-registered build-first gate — the mission's central bit-identity claim is REFUTED by a measured mechanism (the scatter fold-order is structural for tp-built predictors in priors-first models); the transformation itself is validated as OUTPUT-INVISIBLE, lp-EXACT, and −56.7% total Ir (the 55.2% prize is real and fully harvested by the rewrite — only bit-identity fails)

Executed 2026-08-30 per the WORKLOG "W-129 PRE-REGISTRATION". Deliverable
intent: stanc3 branch `gathered-additive-emit` in `external/stanc3_w129`
(worktree created off the registry tip `50e8c9d`, verified). **The compiler
pass was NOT built: the pre-registration orders the increment-2 hand-edit
built FIRST and gated bit-identity as the precondition (gate (b)); the
hand-edit fails that gate by a precisely-diagnosed structural mechanism, so
per the campaign's pre-registration discipline the OCaml work does not
proceed.** The branch stays clean at `50e8c9d` (nothing to commit; the
campaign's scratch artifacts carry the evidence). Artifacts under
`scratch/w129/`.

**Headline: the pre-registered design — tp loop rewritten to value-only
double-space writes + likelihood rewritten to the scatter overload —
reproduces, digit-for-digit, the INCREMENT-1 DIRECT-SCATTER arm's known
divergent draws md5 `295549186964b50693df3cff63ddbbe4` (not the stock
reference `d2e2f896e81dc03aff55e0f2a54f6065`). The mission's claim that
"after the tp-loop rewrite, the tp chains no longer exist, so the
sweep-order interleaving problem disappears" is FALSE, and the W-127
record's own mechanism section, read carefully, predicts exactly this: the
1-ulp-class divergence is not the chains' EXISTENCE but the DELIVERY
POSITION of the likelihood's increments. Stock delivers Σw to the
coefficients through varis created in the TRANSFORMED-PARAMETERS block (the
earliest stack frames, swept LAST, i.e. AFTER every prior edge); any
scatter callback is created at the likelihood call (swept BEFORE the priors
that precede it). Eliminating the chains eliminates stock's delivery
vehicle, not the reorder. A three-arm causal triangle (§3) proves this
experimentally: a PURE-STOCK arm with the likelihood statement moved before
the priors has gradients BITWISE-IDENTICAL to stock (0/100) — statement
order among model-block statements is irrelevant to stock's fold — while
the increment-2 arm diverges from both with the same ~32/90-component,
last-ulp signature (grad rel-L2 median 9.4e-17; lp EXACT 100/100).**

**What IS validated (and is not nothing): (1) the value-only tp rewrite is
OUTPUT-INVISIBLE — the constrained output including all 11,566 `y_hat`
columns is bitwise-identical at 100/100 points (the pre-registration's
stop-clause constraint HOLDS); (2) lp is bitwise-exact 100/100; (3) the
rewrite harvests MORE than the pre-registered −40..−50% band: total run
54.76e9 → 23.73e9 Ir = −56.7% (wall 5.73 s → 1.70 s), with the tp complex
going to ~0 EXACTLY as pre-registered (vari pushes 4.898e9 → 1.3e6; the
var operator+/operator* forward overloads and their chain callbacks simply
cease to exist as symbols; `__log1p` identical to the digit). The prize is
real, measured, and one math-side increment away from bit-identity (§6).**

---

## 1. What was built (the gated hand-edit reference — gate (b), step 1)

Bundle `scratch/w129/bs_w129` = `cp -al` of `scratch/w127/bs_w127` (header
md5 `7367df51…` = the branch-tip state of `gathered-additive` @
`5267fb4858` — the TU commit touched only tests; `bridgestan.o` = the
canonical model-flags rebuild `e4b6077b…`). Build: `gxx_fixed`,
`env -u LD_LIBRARY_PATH`, `/usr/bin/make -j2`, nice 19, model flags
(`-O3 -mavx2 -mfma`; FMA-count provenance: stock .so 341 fused ops, i2 .so
384). The stock reference .so and its parity/draws artifacts are W-127's,
reused read-only.

The hand-edit (`scratch/w129/model_election88_i2/election88_full.hpp`,
51-line diff vs pristine `d0557507…`; md5 `2b5d816e…`), REV-mode
instantiation only (the base/double template and `write_array` untouched):

- **(a) tp loop → value-only writes**: `y_hat` declared
  `Eigen::Matrix<double,-1,1>` (write_array's exact spelling); the loop body
  is the SAME left-associated 10-term expression with the AutoDiffable
  operands wrapped `stan::math::rvalue(stan::math::value_of(<coef>), …)`
  (10 wraps: beta×5, a, b, c, d, e); data operands unchanged. The loop is
  retained (its `rvalue` range checks preserve stock's throw order — bad
  gathered indices still throw at statement 13, before the priors), but its
  result is dead in rev mode (the scatter recomputes eta from the leaves).
- **(b) likelihood → the scatter overload**:
  `bernoulli_logit_lpmf_gathered_additive<propto__>(y, rvalue(beta,…,1),
  slope_term(β₂, black), slope_term(β₃, female), slope2_term(β₅, female,
  black), slope_term(β₄, v_prev_full), gather_term("a", a, age), …,
  gather_term("e", e, region_full))` — the increment-1 `_tp` call's exact
  spelling minus the `y_hat` argument.
- The include after `model_header.hpp`.

## 2. Gate (b) — the hand-edit bit-identity gate: **FAIL** (the mechanism, §3)

`scratch/w129/gate_parity_w129.py` (ctypes C ABI, 100 pts, W-103 scheme,
one .so per process; also captures `bs_param_constrain(include_tp=true)` —
the 11,656-column constrained output):

| check | result | verdict |
|---|---|---|
| lp, 100 pts | **0/100 bitwise mismatches** | PASS |
| constrained output (params + all 11,566 `y_hat` cols), 100 pts | **0/100 bitwise mismatches** | PASS (output-invisible; the pre-reg stop-clause constraint HOLDS) |
| parameter adjoints, 100 pts | **100/100 points differ**: 83/90 components ever differ (~32/pt), grad rel-L2 median 9.4e-17, max 1.7e-16; max abs diff 4.5e-13 on a gradient of 3,944 | **FAIL** |
| component classes | sigmas (prior-only) NEVER differ; a/b/c/d/e ALWAYS-class; beta 21–42/100 | consistent with the fold mechanism |
| draws, W-29 protocol (w36exp CLI read-only, seed 20260819, w100/s50, mw50, w80 pf init rep0/chain_0) | md5 `295549186964b50693df3cff63ddbbe4` — **digit-for-digit the increment-1 DIRECT-SCATTER arm's recorded md5** (≠ the required `d2e2f896…`) | **FAIL** |

The md5 recurrence is the strongest possible statement: the increment-2
numerics (lp AND gradients) are bitwise-identical to increment-1's scatter
arm — literally the same trajectory. Removing the tp chains changed nothing
about the adjoint computation, exactly as the mechanism predicts (the
chains were stock's delivery vehicle, absent in both scatter arms).

## 3. The mechanism, and the causal triangle that proves it

`grad()` sweeps `var_stack_` top-down (reverse creation). For a tp-built
predictor, stock's stack is `[tp varis][model-block edges in program
order]`; the coefficient adjoint fold is therefore **[model-block edges,
last statement first] then Σw (tp chains, elements descending)** — and a
third arm proves the statement-order invariance:

- **stockRO** (`scratch/w129/model_election88_stockRO/`): PURE STOCK
  expressions everywhere; ONLY the likelihood statement moved before the
  six priors (in both `log_prob_impl` templates; gradients are invariant to
  the lp-fold reordering — each term's adjoint receives exactly w=1 through
  the accumulator tree).
- **grads stockRO vs stock: 0/100 bitwise IDENTICAL.** Wherever the
  likelihood sits among the model statements, the tp chains (created in the
  tp block) still deliver Σw AFTER every prior edge.
- **grads stockRO vs i2: 100/100 differ** — the same ~32-component
  signature as i2-vs-stock. The ONLY structural difference in i2 is WHERE
  the Σw-delivery callback is created (the likelihood call) — swept BEFORE
  the priors that precede it: each coefficient folds
  `RN(Σw_desc + prior)` vs stock's `RN(…(prior + w)…)`.
- **lp isolation**: i2 == stock 100/100 (exact); stockRO != stock 52/100
  (pure lp reassociation) — the gradient fold is i2's ONLY divergence.

**Corrected applicability condition** (a refinement of the W-127 header
doc, which says scatter is right "when the likelihood is the last statement
touching its operands" — true for COMPOSED predictors like hier_2pl, where
stock's delivery varis are created inside the likelihood call and priors
before it are fine): for TP-BUILT predictors the condition inverts — the
scatter matches stock only if every operand-touching edge is created AFTER
the likelihood (priors after it), because stock's tp-chain delivery always
comes last regardless of statement order. election88 (priors first) is the
maximally-unfavorable legal layout.

## 4. Gate (e) — cost: the prize is fully harvested by the rewrite (report; band exceeded favorably)

Callgrind (3.25.1; W-127's baseline ran 3.23.0 — Ir counting is
version-invariant; one run at a time, ps-checked; draws md5 `2955491…` under
tracing = untraced):

| metric | stock (W-127 baseline) | increment-2 arm | delta |
|---|---|---|---|
| PROGRAM TOTALS Ir | 54,761,167,358 | **23,725,199,672** | **−56.68%** |
| Ir/grad (2,999 both) | 18.26 M | 7.91 M | −56.7% |
| Ir/elem (N=11,566) | 1,578 | 684 | −56.7% |
| native wall | 5.73 s | 1.70 s | −70.4% |

Attribution (self Ir; stock column = the W-127 record's):

| complex | stock | increment-2 |
|---|---|---|
| tp-loop forward `operator+` / `operator*` (var) | 15.03e9 / 5.87e9 | **0 / 0 (symbols gone)** |
| add-varis / `multiply_vd_vari` chain() | 3.47e9 / 0.95e9 | **0 / 0 (gone)** |
| vari-stack pushes (`emplace_back`) | 4.898e9 | **1.3e6 (~0, as pre-registered)** |
| `__log1p` (shared interior) | 2,802,390,986 | **2,802,390,986 (identical to the digit)** |
| `bs_log_density_gradient` | 4.357e9 | 4.084e9 |
| `log_prob_impl` self | 11.34e9 | 6.13e9 |
| composed lpmf forward + edge machinery | 2.38e9 | **0** |
| primitive forward (`additive_impl`) | — | 4.022e9 |
| `resolved_gather` forward | — | **4,068,745,310 (identical to increment-1 to the digit)** |
| scatter callback `chain()` | — | 2.692e9 |
| memcpy | 0.041e9 | 0.383e9 (the primitive's arena copies, = increment-1) |

Two pre-registered cost expectations, honestly scored: (1) "the tp complex
→ ~0" — **EXACTLY MET** (the −31.0e9 total delta ≈ the 30.22e9 tp complex
plus the stack-sweep/zeroing frame); (2) "the increment-1 eta recompute → 0
(the likelihood consumes gathered values)" — **INFEASIBLE in-box**: the
scatter overload's certified bit-identical value path IS the recompute (no
header overload reads precomputed eta; the `_tp` variant's docs state its
values are not read either). The recompute (8.09e9 Ir) is the price of the
primitive's bit-exact value path and remains in the emitted arm.

## 5. Gates (a)/(c)/(d) — not run (moot by the stop)

Gate (a) pattern discipline and gate (c) end-to-end were pre-registered
AFTER gate (b)'s hand-edit reference passes; it did not, so no OCaml pass
exists to test (the pre-registration's own sequencing — "build FIRST, gate
it" — is what caught this). Gate (d) no-op/dune: nothing to be a no-op.
The gate-(a) "choose, disclose" fork (likelihood-only fallback when y_hat
has other reads) is moot at this increment; it transfers to whichever
follow-up shape proceeds.

## 6. The two ways forward (PI decision, both quantified by this W)

1. **Bit-identity lane (W-130 candidate, math-side increment):** a per-
   element custom vari CREATED AT THE TP LOOP — forward computes the
   element's value in double space (this W's validated value-only path);
   `chain()` replays the element's decoded backward (W-127's certified
   schedule: pure adds for gathered leaves, fused multiply-adds for slopes,
   the within-element order and elements-descending order stock uses); the
   likelihood line stays STOCK `bernoulli_logit_lpmf(y, y_hat)`. Delivery
   then sits at the tp stack position = stock's fold, with one vari instead
   of ~15 per element — the same −30e9-class elimination with bit-identity
   by construction. The stanc3 emission is then "tp loop → the new factory
   call" (the scatter/likelihood rewrite is NOT needed).
2. **Statistical-class lane (reclassify, W-34-ArmB gates):** accept the
   measured last-ulp divergence (grad rel-L2 ~1e-16, lp exact, draws in the
   composed-model equivalence class — the rewrite makes the program
   numerically the likelihood-composed form) and harvest the measured
   −56.7% now. Not this agent's call: W-129 was pre-registered
   bit-identity-class.

## 7. Deviations / disclosures (all owned)

- **The central pre-registered mechanism claim was wrong** (§3): owned at
  the top of this record. The W-127 record's §3b wording ("A callback at
  the likelihood's stack position scatters Σw FIRST, then the prior lands")
  already contained the refutation — the interleaving disappears with the
  chains, the REORDER does not.
- **Cost expectation (2) infeasible in-box** (§4): the eta recompute cannot
  go to 0 under any header-only emission; disclosed rather than silently
  dropped.
- The valgrind version differs from the W-127 baseline (3.25.1 vs 3.23.0);
  Ir totals are instruction-exact and version-invariant; disclosed.
- The rev-template value-only loop is dead code in rev mode; its (possibly
  fp-contracted) values are unobservable — output values come from
  `write_array` (stock, untouched), verified 0/100 via `bs_param_constrain`.
  The loop is retained deliberately for throw-set parity (its range checks
  fire at stock's statement position).
- `bs_w129` is a hardlink copy; every modified file lives outside the
  bundle (model dirs) or was never modified in-copy; `bs_w127`/`bs_prim_stock`
  untouched. No pushes; `stanc3_w129` left clean at `50e8c9d`; WORKLOG.md
  and comms.md not written by this agent (PI-owned).
- Machine: ≤2 cores for builds (nice 19, `gxx_fixed`, `/usr/bin/make`,
  `env -u LD_LIBRARY_PATH`); one callgrind at a time (0 running at launch,
  verified); sampler cells single-process nice 19 OMP_NUM_THREADS=1.

## 8. Artifacts

- `scratch/w129/`: `notes.md` (session state), `make_i2_edit.py` (the
  reproducible hand-edit), `model_election88_i2/` (the increment-2 arm:
  hpp `2b5d816e…`, .so `413354316e…`), `model_election88_stockRO/` (the
  causal-triangle reorder arm: hpp `cb72f228…`, .so `79cd944d…`),
  `gate_parity_w129.py` + `parity_ref|ro|i2.npz` (the 100-pt gates),
  `gate_triangle_w129.py`, `diag_components.py`, `runs/i2_w100s50.csv`
  (md5 `2955491…`), `profile_i2/` (callgrind.out + ann.txt + draws),
  `logs/` (builds, runs, callgrind).
- Reused read-only: `scratch/w127` (bs bundle, stock .so, pristine hpp,
  runs), `scratch/w80` (data.json + pf inits), `scratch/w46/gxx_fixed`,
  `external/walnutpie/build_w36exp/examples/stan_cli`,
  `external/math_dev_w127` (header source, read).
