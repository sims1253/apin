# F-6 log — corpus census of the fortk T1 region tier (all 21 bs_models)

Started: 2026-08-26. Binding scope: WORKLOG "F-6 pre-registered BEFORE running".
Census only — NO perf gate. Honest table incl. every reject and every FAIL.

Fork: external/stanli @ branch fortk/t1-regions (d1f234d, build-rel current;
binary build-rel/fortk_t1r). READ-ONLY on the fork: run the existing tool,
no source modification, no git state changes. stanc = external/stanli/deps/
stanc3/stanc (the tool shells out to `stanc`; put on PATH).

Protocol per model:
1. `stanc --O1 --debug-optimized-mir models/M.stan > bench/fortk_f6/M.tmir.sexp`
2. `build-rel/dump_ops M.tmir.sexp data/M.json -1` -> slots/ops/opcode histogram
3. `taskset -c 2 build-rel/fortk_t1r M.tmir.sexp data/M.json bench/fortk_f6/M
   --name M --inspect` (verify = 64 pts seed 20260826 vs UNFUSED executor,
   grad rel-L2 AND logp rel < 1e-9; bench = in-C loop, 3 reps, medians,
   unfused vs fused executor; per-rep arrays printed for spread check).
   Rejects/crashes recorded verbatim (exit 3 = tool's loud REJECT; other rc
   = crash, also census data).
Timing hygiene: taskset core 2, pgrep coordination with other bench agents,
re-run on >5% rep spread.

## Pairing check (21 models)

All 21 .stan in models/ + .json in data/ verified present (ls, both dirs)
— accel_gp, arma11, blr, bym2_offset_only, diamonds, dogs_hierarchical,
eight_schools_centered, eight_schools_noncentered, garch11, gp_regr,
hier_2pl, kidscore_momiq, kronecker_gp, logmesquite_logvash,
lotka_volterra, low_dim_gauss_mix, lsat_model, pilots,
radon_partially_pooled_noncentered,
radon_variable_intercept_slope_noncentered, wells_dist100_model.
None skipped.

## Runs

Batch 1 (all 21, sequential, taskset -c 2, pgrep-checked quiet, load 0.31):
18 rc=0, 2 rc=3 (REJECT), 1 rc=134 (lotka crash). Raw outputs:
bench/fortk_f6/<model>.run.txt (+.run2/.run3/.run4 re-runs, .dumpops.txt
summary, .fullops.txt full listing, .tmir.sexp).

### Non-accepted, verbatim

- dogs_hierarchical rc=3: `fortk_t1r: REJECT: no carveable region (all ops
  unsupported?)`. Ops (7): CONSTRAIN_LU x2, POW x2, BERNOULLI_LPMF x1
  unsupported; MUL x1, ADD_N x1 supported but NON-ADJACENT (BERNOULLI_LPMF
  op5 sits between MUL op4 and ADD_N op6) → no >=2-op supported run.
  Blockers: CONSTRAIN_LU, POW, BERNOULLI_LPMF.
- wells_dist100_model rc=3: same REJECT line. Graph is a SINGLE op
  (BERNOULLI_LOGIT_GLM_LPMF v=86, N=3020 obs) — unsupported opcode AND
  below the >=2-op region minimum regardless.
- lotka_volterra rc=134 (SIGABRT, core dumped), stdout empty (block-buffered,
  lost on abort):
  `terminate called after throwing an instance of 'std::domain_error'`
  `  what():  lognormal_lpdf: Location parameter[1] is -nan, but must be finite!`
  Pinpointed by follow-up probe (--no-verify --no-bench, rc=0): the tool
  CARVES 3 regions fine (ops[0,3) + [4,8) + [24,27), 10/27 ops = 37%
  coverage); the abort is in the VERIFY phase — the interpreted ODE op at
  seeded random N(0,1) points yields nan solution → LOGNORMAL_LPDF domain
  check throws → uncaught. Both arms share the interpreted ODE→LOGNORMAL
  path (neither op is emitter-supported), i.e. model-level, not
  fused-code-level. Crash documented, NOT retried.

### Accepted (18): verify + bench

All 18: GATE_CORRECTNESS=PASS (64 pts, seed 20260826, grad rel-L2 and logp
rel both < 1e-9; 4 models BITWISE both metrics: bym2, kronecker,
low_dim_gauss_mix grad, accel_gp grad, esnc grad, pilots logp).

Timing hygiene: rep spreads <5% everywhere except bym2 (5.2%) and accel_gp
(5.05%) → re-run per protocol. bym2 run2 tight (1.6%/1.9%), ratio 1.266→1.280.
accel_gp 4 runs: ratio 1.329/1.190/1.132/1.249 (between-run drift under
residual background load; per-rep spreads <=5.5%) → quoted median 1.22,
table µs from run2.

| model | dim | ops | regions | regops(cov%) | grad rel-L2 / logp rel | unfused µs | fused µs | ratio |
|---|---|---|---|---|---|---|---|---|
| eight_schools_noncentered | 10 | 7 | 1 | 7 (100%) | 0.0 / 2.5e-16 | 0.273 | 0.034 | 8.04x |
| eight_schools_centered | 10 | 6 | 1 | 6 (100%) | 3.0e-16 / 4.0e-16 | 0.297 | 0.0415 | 7.16x |
| logmesquite_logvash | 7 | 14 | 1 | 14 (100%) | 6.5e-16 / 4.7e-16 | 0.931 | 0.214 | 4.36x |
| blr | 6 | 5 | 1 | 5 (100%) | 3.2e-16 / 2.4e-16 | 0.586 | 0.148 | 3.95x |
| pilots | 18 | 21 | 3 | 16 (76%) | 7.4e-16 / 0.0 | 0.754 | 0.263 | 2.87x |
| kidscore_momiq | 3 | 7 | 1 | 7 (100%) | 1.3e-15 / 1.9e-15 | 2.70 | 0.97 | 2.78x |
| radon_variable_intercept_slope_nc | 175 | 19 | 1 | 19 (100%) | 2.7e-15 / 2.6e-15 | 9.61 | 5.10 | 1.88x |
| radon_partially_pooled_nc | 389 | 11 | 1 | 11 (100%) | 2.0e-14 / 9.9e-15 | 63.2 | 40.1 | 1.58x |
| bym2_offset_only | 3845 | 25 | 4 | 15 (60%) | 0.0 / 0.0 (bitwise) | 52.7 | 41.2 | 1.28x |
| accel_gp | 66 | 68 | 10 | 29 (43%) | 0.0 / 9.8e-16 | 8.22 | 6.91 | 1.22x (1.13–1.33, 4 runs) |
| gp_regr | 3 | 14 | 3 | 10 (71%) | 1.0e-14 / 4.0e-16 | 5.21 | 4.62 | 1.13x |
| garch11 | 4 | 8 | 1 | 3 (38%) | 1.3e-15 / 8.6e-16 | 10.16 | 9.34 | 1.09x |
| lsat_model | 1006 | 28 | 1 | 28 (100%) | 1.7e-16 / 1.2e-15 | 74.7 | 70.8 | 1.06x |
| low_dim_gauss_mix | 5 | 16 | 4 | 8 (50%) | 0.0 / 0.0 (bitwise) | 71.5 | 70.8 | 1.01x |
| hier_2pl | 669 | 97 | 2 | 96 (99%) | 1.0e-15 / 1.2e-14 | 474.0 | 474.0 | 1.00x |
| kronecker_gp | 438 | 223 | 63 | 131 (59%) | 0.0 / 0.0 (bitwise) | 274.6 | 278.1 | 0.99x |
| arma11 | 4 | 806 | 201 | 606 (75%) | 7.8e-16 / 4.0e-15 | 6.91 | 7.16 | 0.97x |
| diamonds | 26 | 7 | 1 | 7 (100%) | 3.9e-16 / 2.5e-16 | 35.6 | 38.6 | 0.92x |

Consistency with F-4 (same protocol): esnc 8.04 vs 8.32, blr 3.95 vs
3.6–4.2, diamonds 0.92 vs 0.85, hier_2pl 1.00 vs 0.99, radon_pp 1.58 vs
1.52. All within run-to-run variation. (radon_pp here dim 389 = the
radon_all N=12573 data via bs_models; F-4 used the same.)

### Aggregates

- Carve coverage: 19/21 (90.5%) carve >=1 region (18 complete + lotka
  carves 3 regions but crashes in verify); zero-region rejects 2/21
  (dogs_hierarchical, wells_dist100_model). Fully-processed accept: 18/21
  (85.7%).
- Verification pass rate among completed accepted: 18/18 (100%); worst
  grad rel-L2 2.0e-14 (radon_pp), worst logp rel 1.2e-14 (hier_2pl) —
  both 5 decades inside the 1e-9 gate. 1 verify crash (lotka, documented
  above — nan ODE solution at random points, not an emitter defect).
- Speedup among verified (n=18): median 1.25x, geomean 1.81x, range
  0.92x–8.04x. Wins >=1.1x: 11; parity 0.95–1.1x: 6; loss <0.95x: 1
  (diamonds 0.92x).
- Opcode-blocker histogram (unsupported opcodes present, #models / #ops):
  CONSTRAIN_LU 5/9, SET_INDEX 4/10, ISLAND 3/3, SUM_VEC 3/4, CHECK_LOWER
  2/5, POW 2/4, EXPV 2/5, SET_SLICE_INPLACE 2/3, SQRT 2/4,
  SET_INDEX_INPLACE 2/228, DIV 2/2, BETA_LPDF 2/2, LOGNORMAL_LPDF 2/8,
  LOGV 2/5, then 1-model tail: SQUARE, MATVEC, INV_GAMMA_LPDF,
  POISSON_LOG_LPMF, DOT, BERNOULLI_LPMF, GP_EXP_QUAD_COV, REP_VEC,
  CHOLESKY, GAMMA_LPDF, TRANSPOSE(7 ops kronecker), EIGENVALUES_SYM,
  EIGENVECTORS_SYM, SET_SLICE_STRIDED_INPLACE(30 ops kronecker), ODE,
  SLICE_STRIDED, CONSTRAIN_ORDERED, LOG_MIX, BERNOULLI_LOGIT_GLM_LPMF.
  Reject-causing blockers: dogs = CONSTRAIN_LU+POW+BERNOULLI_LPMF
  (isolate the 2 supported ops); wells = BERNOULLI_LOGIT_GLM_LPMF
  (single-op graph). Lotka crash path: ODE → LOGNORMAL_LPDF nan.
- Cold clang cost of many-region graphs: arma11 201 regions → 26.6 s,
  kronecker 63 → 8.5 s, accel 10 → 1.4 s (cache hits ~0; per-region file
  splitting already noted in F-4 as the fix).

### Concurrent-agent note (timing + provenance)

A concurrent F-4b agent is editing tools/fortk/regions.cpp in this same
checkout ("F-4b direct path" per the diff; source mtime 17:59:13, binary
relink 17:59:25 — both AFTER my last census run 17:53:55). Provenance that
the census ran entirely on the unmodified F-4 binary: every re-run
(accel_gp run2/3/4, bym2 run2) reported cache miss/hit=0/N hitting the
SAME region keys as run1's fresh emission — keys include the emitter
version, so any emitter change would have forced misses. pgrep showed no
competing bench processes during my timed runs (load 0.31); accel_gp's
between-run drift (1.13–1.33) is residual background wobble, median
quoted. The F-4b working-tree edit is theirs — left untouched (this task
made zero fork changes).

### Prior check (pre-registered expectations vs measured)

- "ODE models reject via ode ops": PARTIAL. lotka does NOT reject — it
  carves 3 regions (ODE stays interpreted) and instead CRASHES in verify
  on nan from the ODE solve at random points. sir not in this corpus.
- "gp/kronecker linalg-heavy → slow or parity": CONFIRMED (gp_regr 1.13x,
  accel_gp 1.22x, kronecker 0.99x).
- "hierarchical + GLM families → wins": MOSTLY. Strong: kidscore 2.78x,
  radon_vis 1.88x, radon_pp 1.58x, bym2 1.28x. But hier_2pl 1.00x
  (transcendental-bound, F-4 known) and the biggest wins are actually the
  small dispatch-bound models (8schools 7–8x, logmesquite 4.4x, blr 4.0x)
  — consistent with the F-2b refined thesis (T1 pays where dispatch/
  overhead dominates, vanishes at bandwidth/libm bound).

