# Upstream candidates — consolidated list

**Date:** 2026-08-22 (W-31). Living list of findings from this project that
are worth proposing to the relevant UPSTREAM repos (walnutpie, stan-math /
stanc3, bridgestan, gcc). One paragraph per candidate: evidence, affected
repo, proposed change, status. Evidence pointers are all in this repo;
nothing here is pushed anywhere yet.

1. **Combined eigh primitive in stan-math / paired codegen in stanc3**
   (kronecker_gp class). Evidence: W-29 hotspot atlas
   (`results/hotspot_atlas_w29.md`, raw `results/profile/w29/`) — the
   generated model calls BOTH `eigenvectors_sym` and `eigenvalues_sym` on
   the same two matrices, so every gradient runs 4 full double-mode
   `SelfAdjointEigenSolver` decompositions where 2 suffice (each primitive
   internally computes values AND vectors and discards half); reverse-mode
   eigh costs 39.3% of total program Ir, the eigenvector adjoint callback
   alone 9.1%T, and Eigen's unblocked `computeFromTridiagonal` scalar loop
   20.6% of the gradient subtree. Affected repo: stan-math (primitive) and
   stanc3 (codegen that emits the two calls). Proposed change: a combined
   `eigh`-style primitive returning values+vectors with one solver run and
   one reverse callback producing both adjoints; stanc3 pattern-match the
   paired calls. Status: MEASURED by W-32 (`results/eigh_reuse_w32.md`) —
   the primitive ALREADY EXISTS upstream as `eigendecompose_sym`
   (stan-math 5.3.0 + stanc3 2.39 language support); rewriting the model
   to use it is bit-identical in gradients/draws and saves 19.4% of
   gradient Ir, 18.4% of total program Ir, ~14% of gradient wall on
   kronecker_gp. Remaining upstream ask narrowed to stanc3 CODEGEN: fuse
   the natural `eigenvectors_sym(A)` + `eigenvalues_sym(A)` pair (or
   flag it in pedantic mode) — see the W-32 close-out for full numbers.

2. **Elementwise var-mode plumbing tax on indexed likelihood lines**
   (hier_2pl class). Evidence: W-29 atlas — ONE program line
   (`y ~ bernoulli_logit(alpha[ii] .* (theta[jj] - beta[ii]))`) spends
   ~32% of the gradient subtree in plumbing (`subtract`/`elt_multiply`
   forward 23.9% + `rvalue<index_multi>` 8.1%) on top of ~39% in the
   likelihood math itself (bernoulli_logit_lpmf 18.5%, `libm log1p` 14.4%,
   `inv_logit` reverse lambda 6.3%). Affected repo: stan-math (expression
   templates / var arithmetic) and stanc3 (fused codegen). Proposed
   change: fused/overloaded elementwise expressions that keep operands in
   double until the likelihood boundary (or partial-evaluation of indexed
   elementwise chains), amortizing the per-element vari construction.
   Status: measured only (W-29); no prototype. Ceiling on hier_2pl is
   large (~1/3 of gradient Ir).

3. **cholesky_decompose<var> reverse pass + `pow` → `d*d` in covariance
   kernels** (gp_regr class). Evidence: W-29 atlas — the cholesky reverse
   lambda costs 17.0% of the gradient subtree vs 9.8% forward (adjoint
   sweep alone is 1.7x the factorization); `gp_exp_quad_cov` calls libm
   `pow` (8.9% of the subtree) where `d*d` would do for the ubiquitous
   square. Affected repo: stan-math. Proposed change: (a) cheaper adjoint
   for the Cholesky of a symmetric matrix (exploit the structure instead
   of the generic triangular reverse sweep), (b) specialize
   `square()`/integer exponents in the covariance kernels (and/or
   stanc3-emitted `d*d`). Status: measured only (W-29); the `pow` half is
   likely a small, easily-reviewable patch.

4. **walnutpie: controller's cross-chain early exit must be opt-in (safe
   adaptation defaults)** (this item, W-31). Evidence: W-25 side finding 3
   + W-26 gate c — with the DEFAULT WarmupConfig the multi-chain
   controller's cross-chain tols (mass 1.0 / step 0.1) stop warmup at
   iteration 50–80 with good inits and destroy post-warmup quality
   (hier_2pl bulk-ESS-min 519 → 61); W-25/W-28 further showed no
   tolerance-based gate preserves quality (temporal 2-window gate:
   519 → 126; pilot gate: safe only by never exiting). Any embedder
   calling `adapt()`/`adapt_with_stats()` with defaults is exposed.
   Affected repo: walnutpie (dev branch lineage; not yet `origin/main` —
   `origin/main` has the same controller semantics, so the issue applies
   upstream too). Proposed change: `WarmupConfig::allow_early_exit`
   default FALSE (fixed-budget warmup out of the box, diagnostics still
   computed); old behavior via explicit opt-in. Status: IMPLEMENTED on
   walnutpie branch `exp/safe-adapt-defaults` (W-31; gates: single-chain
   canary 12/12 bit-identical, default `--chains 4` now runs to budget
   with draws bit-identical to the full-warmup baseline 24/24,
   `--early-exit` still reproduces the destructive exit). Full entry:
   WORKLOG W-31.

5. **bridgestan: `compile_model` silently reuses a cached `.so`
   regardless of `make_args`** (W-27). Evidence: W-27 setup note —
   `compile_model` checks/returns `<stem>_model.so` next to the `.stan`
   if it exists, so requesting e.g. `CXXFLAGS=-O3` or
   `STAN_THREADS=True` against an already-built pair silently ships the
   OLD binary (W-27's first build attempt shipped default binaries; had
   to copy `.stan` files into per-variant scratch dirs). The Makefile
   does not encode build-mode in the `.so` name for models (only the
   bridge object gets a `_threads` suffix), so the two concerns compound
   (see also the STAN_THREADS addendum in
   `external/upstream_audit_walnutpie.md` §4). Affected repo: bridgestan.
   Proposed change: stamp the build flags (at minimum the STAN_* mode
   variables) into the `.so` name or a sidecar, and/or have
   `compile_model` verify the requested `make_args` against the cached
   build before returning it. Status: measured/reproduced (W-27); no
   patch written. Repro: `bridgestan.compile_model(x.stan)` then again
   with `make_args=["STAN_THREADS=True"]` — returns the same mtime/.so.

6. **`-march=native` changes Stan model gradients O(1) on eigen-degenerate
   models — NOT a compiler miscompile (W-27 characterized; W-35 reclassified)**
   (W-27 initially read this as a gcc miscompile; W-35 minimized + classified
   and REFUTED the miscompile reading — see results/march_native_w35.md and
   the retraction note in WORKLOG W-35.) Evidence: W-27 G1 — self-contained
   single-make builds of kronecker_gp with `-O3 -march=native -mtune=native`
   produce gradients wrong at up to 1.7 REL with SIGN FLIPS on 99/99 random
   points (250–305 of 438 components, the `lkj_corr_cholesky` L block and
   var1/bw1) while logp matches to 1e-16; default and `-O3`-only builds are
   bit-identical. W-35 root cause: any AVX-or-wider ISA (even `-mavx` alone;
   `-ffp-contract=off`, `-fno-tree-vectorize`, `-O2` vs `-O3` all do NOT
   prevent it) switches Eigen's GEMM to 256-bit packets → rounding-level
   (1e-15) summation-order change → Eigen SelfAdjointEigenSolver returns a
   DIFFERENT BUT EQUALLY VALID eigenbasis inside the model's rounding-
   degenerate eigenvalue clusters (Sigma1's 1e-5 jitter-floor cluster;
   Lambda's 1e-16 near-null cluster) → stan-math's rev eigenvector adjoint
   F_ij = 1/(w_j−w_i) amplifies the basis flip to O(1)–O(1e3) in the
   gradient. Critically, the DEFAULT build's own gradients are equally
   Richardson-FD-INCONSISTENT at those points (var1 30–47% off FD; native
   sometimes CLOSER to FD), sanitizers (ASan+UBSan) are clean under both
   flag sets, and clang 22 reproduces the phenomenon with `-march=native`
   while clang baseline is bit-identical to gcc baseline. Affected repo:
   stan-math (eigenvector adjoints assume separated eigenvalues — docs/
   warning ask; ready-to-file issue draft in results/march_native_w35.md
   §7a) and cmdstan/bridgestan docs (`-march=native` gradient-reproducibility
   caveat, §7c). gcc bug deliberately NOT filed (§7b records the rationale).
   Status: DONE (W-35): minimized self-contained reproducer committed at
   scratch/w35/repro/march_native_repro.cpp (no model, no data file; 4-
   compiler output table in the report); operational guidance unchanged —
   never build Stan models with `-march=native` (≤ ~10% upside, O(1)
   gradient instability downside), `-O3` is safe/bit-identical.

7. **walnutpie: three silent-failure modes in warmup startup/freeze**
   (W-38-E1/W-41/W-42, Aug 2026). Evidence: (a) non-finite-logp init draws
   pin the chain silently — acceptance statistic NaNs the step adapter at
   iteration 0, chain never moves, run ends in a freeze-time
   `macro_time must be in (0, inf)` abort (kronecker_gp/lotka_volterra
   repro in WORKLOG W-41) or a garbage completing chain; (b) blr-class pin
   at warmup ≤400 — every transition burns 31 evals with all 5 halvings
   failing (|ΔH|≈8e6), zero ESS, escapes only between 400–1000 iters;
   error-discipline caps 10× above the measured |ΔH| change nothing
   (W-38-E2 probe) so it is NOT tolerance-gated; (c) the frozen sampler is
   constructed with the (possibly degenerate) adapted step as macro_time
   with no fallback. Affected repo: walnutpie. Proposed changes (all
   implemented on exp branches, gated): init-protocol guard (fail fast on
   -inf file inits; 100-draw rejection loop for random inits — Stan
   convention), freeze clamp with auditable fallback + warning
   (exp/freeze-clamp), and the pin itself remains open (W-41 lineage).
   Status: fixes done in fork (branches exp/init-guard, exp/freeze-clamp);
   the pin's mechanism is documented but unresolved.

8. **stan-math: wrong-sign gradient in bernoulli_logit partials + packetized
   log1p ceiling** (W-46, Aug 2026). (a) BUG (one-line): in
   bernoulli_logit_lpmf's partials, the `(ntheta > cutoff)` branch computes
   `-exp_m_ntheta` WITHOUT the `signs` factor — wrong-SIGN gradient for
   y=1 observations with logit > 20 (per-element error ≤ 4e-9 in practice
   but structurally a sign error; present in develop). Fix: `signs *
   exp_m_ntheta`. Found by a tight parity harness, not by luck. (b) PERF:
   the lpmf eagerly evaluates glibc log1p for ALL N elements and discards
   results for |ntheta|>20 via nested Selects (verified: 84.7M log1p calls
   = N per log_prob on hier_2pl). A function-multiversioned fused
   value+partials kernel (pragma-target avx2,fma island with
   __builtin_cpu_supports dispatch — sidesteps the global -march question)
   with a ≤1–2 ulp polynomial/plog1p on the confined [e^-20,1] range:
   measured on hier_2pl −22.8% Ir/grad (7.77M→6.00M), −15.3% µs/call,
   parity 2.4e-16. At SSE2 baseline packetization is latency-bound (no win)
   — AVX2+FMA required. Evidence + kernel benches (Chebyshev vs Kahan-Eigen
   vs generic_plog1p, 2.2M-point ulp grids): results/log1p_ceiling_w46.md;
   patched headers + island implementation: scratch/w46/. Status: measured;
   (a) is a ready one-line PR, (b) is a design proposal with a working
   reference implementation.

9. **stan-math: tape/arena record machinery — typed-pool ceiling + design
   doc** (W-47, Aug 2026). Tax decomposition (exact, from W-29/W-34 dumps):
   stack_alloc::alloc 6.4%T + chainstack emplace_back 4.5%T on hier_2pl
   (172M + 173M calls; 98% from two eltwise ops; one nochain vari/element +
   one reverse_pass_callback per op — virtual dispatch is O(#ops), NOT
   O(N)). Microbench ceilings: typed SoA pool = −32% of the tape complex
   (≈ −10–16% of gradient Ir on hier_2pl stock); flat/index-based callbacks
   = 0.00 gain (the vtable-dispatch fear is obsolete — worth stating
   upstream to focus effort); ~2/3 of the eltwise complex is Eigen/Holder
   glue (the stanc3-fusion lane, W-34/W-48), ~1/3 tape. Full SoA var =
   rewrite (pointer type across 400+ files + codegen); shippable increments
   designed: (A) batch make_vari_array + span registration, (B) typed pools
   keeping var a pointer. A span-chainstack prototype was bitwise-correct
   but not model-level profitable under per-record checks (needs the batch
   API). Design doc: results/sota_arena_w47.md; patch (reference):
   scratch/w47/w47_span_chainstack.patch. ALSO bridgestan-relevant:
   prebuilt src/bridgestan.o embeds pristine stan-math headers into every
   model .so — any layout-touching stan-math patch must rebuild it or the
   .so segfaults (add to the bridgestan issues context).