# Upstream-worthy improvements — consolidated before/after summary
(2026-08-23; every number = medians of 3 reps, protocol gates in WORKLOG)

## A. Ready to file (kits + patches + dry-run green vs real tips)

| # | improvement | repo | before → after | tradeoffs |
|---|---|---|---|---|
| 1 | Cluster-aware eigh adjoint (W-40) | stan-math | gradient-vs-FD error 30–52% → ~1e-6; cross-build divergence 1.156 → 3.1e-8 rel; **kronecker_gp bulk-ESS-min 29 → 411, R-hat 1.13 → 1.02** | +1% per-call; not bit-identical on degenerate clusters (gauge choice, defensible); well-separated path byte-identical (200/200). Patch+dry-run vs develop@46a3133 (Eigen 5): tests green, PR test fails 2/4 on stock by design |
| 2 | stanc3 eigh pair-fusion (W-39) | stanc3 | kronecker_gp 393.0 → 337.0 µs/call (−15.6% .so-measured; −19.4% Ir/grad) with NO model rewrite | none — bit-identical vs the language rewrite; peephole scoped to adjacent structurally-equal pure pairs |
| 3 | square() pow→mul (W-33) | stan-math | gp_regr 6.681 → 5.820/5.640 µs/call (−13/−15%), Ir/grad 66,950 → 60,864 (−9.1%) | bit-identical (glibc); widened-to-double form covers int overflow + float double-rounding (dry-run adapted patch green vs develop) |
| 4 | bridgestan cache + threads signals (W-27/W-31) | bridgestan | correctness footguns: silent stale .so regardless of make_args; silent double-free/SEGV when default .so used from threads (3/3 repro) | issue-only (draft texts ready) |
| 5 | walnutpie silent-failure trio (W-41/W-42/W-43) | walnutpie | −inf init: 8.2s pinned zero-ESS run → 0.16s loud fail (~98% budget saved); blr-class w100 pin: bulk-ESS 5–9 → 779 (find_reasonable_step 3-way bug fixed, 0/48 pinned after); freeze NaN abort → auditable fallback | opt-in/explicit where behavior changes; default paths bit-identity-gated 12/12 each |
| 6 | safe adapt defaults (W-31) | walnutpie | destructive default early-exit (ESS 519 → 24–61) eliminated; default = full budget, bit-identical to baseline 24/24 | old behavior preserved behind explicit opt-in |

## B. Model-level adoptions (our benchmark; available today)

| improvement | before → after | tradeoffs |
|---|---|---|
| kronecker_gp via eigendecompose_sym (W-32) | 393 → 337 µs/call (−14.3%), −19.4% Ir/grad | none — bit-identical (draws md5, call counts) |
| hier_2pl GEMM formulation (W-34) | 793.5 → 595.3 µs/call (−25%), −28.2% Ir, wall 0.739× | last-ulp drift; ESS-min 519→447 (unstable min-statistic; distributions identical); complete-design IRT only |
| cmdstan scratch-hoist (W-24; fork PR sims1253/stan#1) | wall geomean ×0.931; memcpy/alloc Ir 9.9% → 6.7% | none — bit-identical 24/24 |

## C. In flight (W-45/W-46: subsampled warmup, log1p kernel; W-47/48/49: research tier)

## D. Sampler-side wins already validated (fork exp stack, W-36 end-to-end)
2.93× geomean wall (10 models, defaults, 28/28 cells bit-identical): parallel
multi-chain 2.77× + endpoint threading ×1.056. Tradeoffs: +10–25% per-call
under 4-way concurrency; STAN_THREADS=1 builds required; ~parity vs 4
processes (0.86×–1.13× by model size).
