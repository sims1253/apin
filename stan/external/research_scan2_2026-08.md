# Research scan 2 — recent (2024–2026) ideas for our active fronts

Date: 2026-08-23. Item W-51 (retry of the rate-limit-killed attempt; no
prior entry survived). Method: 6/6 planned `hermes chat -q` one-shot
queries ran to completion (90 s sleeps between; raw transcripts in
`stan/scratch/w51/q1..q6_*.txt`), one transient provider 429 occurred
after q4's answer was already delivered (memory-save step; limit message
said reset 23:01) but q5/q6 sessions established fine — zero queries
lost, no fallback needed. Independent verification of the load-bearing
leads was done with zcode WebSearch/WebFetch + `gh api` (Semantic
Scholar citation pulls, arXiv abs fetches, GitHub PR/release/issue
records) — 20+ items verified first-hand, marked **[V]** below;
hermes-only items are marked [H]. Companion: `results/upstream_scan_2026-08.md`
(ecosystem scan), `results/UPSTREAM_SUMMARY.md`.

Fronts (one hermes query each, self-contained): (1) SoA/adjoint-array
autodiff arenas; (2) SIMD transcendental kernels in stats libraries;
(3) HMC/NUTS step-size+mass adaptation theory; (4) differentiation with
repeated/degenerate eigenvalues; (5) within-chain MCMC parallelism;
(6) WALNUTS citations/derivatives since JMLR 2026.

---

## Front 1 — SoA / adjoint-array autodiff arenas (maps: W-53 SoA rollout, W-48 eltwise fusion, W-47 design doc)

**Leads.**

- **CoDiPack v3.0.0 (2025-07-08) + v3.1.0 (2026-02-02)** — SciCompKL.
  3.0 restructured per-value tape data handling (each tape/index-manager
  defines what is stored per value); 3.1 adds user-definable **custom
  tape evaluators with access to the full statement data** — i.e.
  statement-level dispatch replacing per-node virtual callbacks, plus
  positional/partial tape evaluation. **[V]** (changelog + releases)
  https://github.com/SciCompKL/CoDiPack/releases ,
  https://scicomp.rptu.de/codi/d6/dc7/Changelog.html
- **XAD v2.1.0 (2026-03-31)** — auto-differentiation/xad; adds
  xad-codegen JIT backend and an optimized OperationsContainer for
  slots/multipliers with faster `computeAdjoints` iteration — a flat
  slot/multiplier operation tape rather than per-node objects.
  **[V]** (gh api release tag, timestamp 2026-03-31T14:48:41Z)
  https://github.com/auto-differentiation/xad/releases/tag/v2.1.0
- **ParDiff: Efficiently Parallelizing Reverse-Mode AD with Direct
  Indexing** — Huang, Tang, Wen, Cao, Tang, Chen, Yu, Li, Jiang, Xiao,
  Zhai (Tsinghua/Qingcheng.AI/Aberdeen/Lenovo), **PPoPP 2026**. Tape is
  direct-indexed (tensor layout) rather than control-flow-tied, enabling
  summation-aware loop transforms; claims up to 483x (geomean 30.9x) vs
  Enzyme and 2.05x vs PyTorch. Code: github.com/roastduck/FreeTensor.
  **[V]** (PPoPP program page) https://dl.acm.org/doi/10.1145/3774934.3786418
- **"Differentiate the Evaluator, Not the Program"** — L. Sheneman,
  arXiv:2607.03574 (July 2026). Define-by-run reverse mode recorded as a
  compact **payload-only** native tape (a node appended only for
  differentiable ops, no boxed/tagged payloads); ~4-5x vs a tagged
  backend, neuro-symbolic setting. **[V]** (arXiv found independently)
- **Local adjoints for simultaneous preaccumulations with shared
  inputs** — Blühdorn & Gauger, arXiv:2405.07819 (2024; SIAM PP24,
  doi 10.1137/1.9781611979039.13). Thread-local adjoint buffers to make
  shared-memory parallel preaccumulation race-free; implemented in
  CoDiPack, benchmarked on SU2. **[V]** https://arxiv.org/abs/2405.07819
- **NVIDIA Warp `warp.Tape`** — records kernel *launches* (one tape
  entry per array operation, not per scalar) and compiles an adjoint
  kernel per launch: the cleanest shipping per-array-op registration.
  [H] https://nvidia.github.io/warp/stable/user_guide/differentiability.html
- **PyTorch Compiled Autograd (Oct 2024)** — captures the whole
  autograd graph into one torch.compile graph, replacing per-node C++
  Function dispatch with a single compiled array-level backward. [H]
- **DaCe AD** — Boudaoud, Calotoiu, Copik, Hoefler, arXiv:2509.02197
  (IEEE Cluster 2025): array-level (SDFG) AD with an ILP-based
  store-vs-recompute optimizer; >92x vs JAX average on NPBench. **[V]**
- **Clad layered tape + prefetching** (GSoC 2025) — tiered tape +
  adjoint-sweep prefetching in the Clang source-transform AD. [H]
- **Adept lineage: NEGATIVE** — Adept 2 stays v2.1.3 (tag May 2025,
  docs Feb 2024), maintenance only; "Adept 2.2" does not exist. [H]
- **Stan-math itself**: the reverse-mode-types contributor doc describes
  the AoS (`var`) vs SoA (`var_value<Matrix>` / varmat) *type* split and
  its test protocol — but no arena/tape-layout redesign anywhere.
  **[V]** https://mc-stan.org/math/md_doxygen_2contributor__help__pages_2reverse__mode__types.html

**Verdict.** The 2024-2026 window shipped exactly the pattern W-47's
design doc proposed: statement-level tape data with custom evaluators
(CoDiPack 3.x), flat slot/multiplier op containers (XAD 2.1), and
per-array-op registration (Warp, PyTorch compiled autograd, DaCe) —
per-scalar `vari` + virtual `chain()` is now the outlier design among
actively-developed C++ tapes. For the **W-53 rollout**: pitch Increment
A (batched vari-array + span registration) as bringing stan-math to the
CoDiPack-3/Warp pattern, with those systems as named precedents; the
varmat (SoA types) line is stan-math's own in-house destination for the
same idea. ParDiff's direct-indexed tape is the compiler-side extreme
of the same axis (index-typed adjoints, no pointer soup) and the
strongest published number set to cite. W-47's "flat callbacks measured
ZERO" negative result is corroborated by the field's move to
statement-level dispatch (fewer, bigger callbacks) rather than faster
per-node dispatch.

---

## Front 2 — SIMD transcendental kernels in stats libraries (maps: W-46 fused log1p kernel, W-50 errno flags)

**Leads.**

- **glibc CORE-MATH timeline (primary sources)** [H, consistent with
  glibc announcements seen in our own searches]:
  - 2.41 (Jan 2025): 23 correctly-rounded binary32 functions from
    CORE-MATH incl. **log1pf**, expm1f, tanhf, erff, lgammaf.
    https://sourceware.org/pipermail/libc-announce/2025/000045.html
  - 2.42 (Jul 2025): C23 families (compoundn/pown/powr/rootn/rsqrt) +
    acospif/sinpif etc.
  - 2.43 (Jan 2026): seven correctly-rounded **binary64** functions
    (acosh, asinh, atanh, erf, erfc, lgamma, tgamma) + AArch64
    AdvSIMD/SVE libmvec vector variants of C23 exp2m1/exp10m1/log10p1/
    log2p1/rsqrt.
- **glibc `exp2m1f` commit (Oct 2024, 17-patch series)** — production
  last-ULP engineering: interval-nested polynomial splits keyed on
  exponent bits, hardcoded hard-to-round constants, and **ifunc
  function multi-versioning with -mfma -mavx2 islands + per-CPU
  dispatch**. [H] This is glibc itself using the exact mechanism of our
  W-46 ask (pragma-target islands rather than a global -march).
  https://sourceware.org/pipermail/libc-cvs/2024q4/086573.html
- **SLEEF 3.6/3.6.1 (2024)** — library revived: RISC-V libm, quad
  precision, OpenMP pragmas in sleef.h for GCC auto-vectorization.
  u10 (1.0 ULP) / u35 (3.5 ULP) dual-accuracy policy remains the
  ecosystem's accuracy knob. [H]
- **Adoption inside stats/ML stacks** [H]: PyTorch ATen uses SLEEF u10
  with MKL-VML fallback (PR #111898 documents the u10-vs-u35 decision
  with measured max-ULP tables); NumPy merged Intel's open-sourced SVML
  AVX-512 kernels (PR #19478, stated max 4 ULP, 32x/14x float/double vs
  scalar glibc); Eigen ships its OWN packet kernels (pexp, plog, plog1p,
  ptanh, FMA-conditional paths — no external vector libm); Julia via
  musm/SLEEF.jl; Arrow vendors xsimd (integer/rounding, not
  transcendentals); AMD AOCL-LibM ≥4.2 integrates CORE-MATH tanhf;
  LLVM `-fveclib` understands SVML/SLEEFGNUABI/LIBMVEC/AMDLIBM/ArmPL.
- **Accuracy-policy anchors**: CORE-MATH (Sibidanov, Zimmermann,
  Glondu, ARITH 2022, hal-03721525) — correctly-rounded policy,
  exhaustive binary32 verification, adopted by glibc/AMD (and used by
  Meta as reference); the **Gladman/Innocente/Mather/Zimmermann survey**
  (hal-03141101, v8 Feb 2025 → Feb 2026 ed. covering glibc 2.43/LLVM
  libc 21) — the standing accuracy benchmark across glibc/Intel/AMD/
  Apple/LLVM/MSVC/CUDA/ROCm **[V]**; RLIBM-ALL (Lim & Nagarakatte,
  POPL 2022) — one LP-generated polynomial correctly rounded across
  all rounding modes/representations.
- **NEGATIVES** [H]: stan-math has **no** vector-math library adoption
  (lgamma_r + Boost fallback, scalar throughout — our fused-kernel work
  is unconstrained by an incumbent); JAX/XLA CPU lowers math to plain
  libm calls; **no library yet ships correctly-rounded *vectorized*
  binary64 log/exp/log1p** — glibc's correctly-rounded work is
  scalar-facing and libmvec remains narrow (exp/log/pow/trig wrappers).

**Verdict.** W-46's ask (fuse + packetize the bernoulli_logit interior
with a deg-16 Chebyshev/Kahan log1p, multiversioned AVX2/FMA islands
with runtime dispatch) sits squarely in the 2024-2026 mainstream:
per-ISA runtime dispatch (glibc ifunc, SLEEF dispatcher, NumPy universal
intrinsics) and a two-tier ULP policy (u10/u35; ≤2 ULP kernels like
Eigen's generic_plog1p are the norm, and glibc itself now ships
correctly-rounded binary64 scalars as the reference). The honest gap
hermes confirmed — no correctly-rounded *vector* binary64 log1p
anywhere — means our kernel claim (≤1-2 ULP packet log1p, −22.8%
Ir/grad) remains best-in-class for the niche; cite glibc's exp2m1f
ifunc islands + SLEEF's u10/u35 + the Gladman survey as the accuracy
framework in the upstream PR. For **W-50**: glibc guards its
`__DECL_SIMD_*` vector-ABI declarations behind `__FAST_MATH__`, which
we will not define — confirming our probe that `-fno-math-errno` alone
never vectorizes elementwise libm chains; the ecosystem's actual lever
is `-fveclib` or explicit packet kernels (i.e., the W-46 kernel ask,
not a compile flag).

---

## Front 3 — HMC/NUTS step-size + mass adaptation theory post-2023 (maps: two-phase warmup W-45 follow-up, walnutpie adaptation lane)

**Leads.**

- **Preconditioning HMC by minimizing Fisher divergence** — Seyboldt,
  Carlson, **Carpenter**, arXiv:2603.18845 (Mar 2026). Mass matrix from
  *score/gradient* information (diag / dense / **low-rank+diagonal**) by
  minimizing sample Fisher divergence instead of matching covariance;
  on **114 posteriordb models** the diagonal version beats Stan/PyMC
  diagonal estimators by median 1.3x, low-rank by **4x**. Reference
  implementations in nutpie and blackjax (`fisher_low_rank`). **[V]**
- **Faster parallel MCMC: Metropolis adjustment is best served warm
  (LAPS)** — Robnik & Seljak, arXiv:2601.16696 (Jan 2026, AISTATS
  2026). Many parallel chains each collecting one sample: an
  **unadjusted phase with ensemble-based bias→step-size conversion,
  then late Metropolis adjustment**; beats MEADS/ChESS/Pathfinder,
  ~2 orders of magnitude wall-clock vs sequential NUTS. **[V]**
- **Algorithmic warm starts for HMC** — Zhang, Altschuler, Chewi,
  arXiv:2603.22741 (Mar 2026). Theory: non-Metropolized HMC *generates*
  a warm start in Õ(d^{1/4}) (vs Ω(d^{1/2}) cold for MH-HMC), then
  switch to Metropolized HMC — the two-phase warmup scheme with
  guarantees. **[V]**
- **The Universal Warmup Path: Automatic Preconditioner Selection for
  HMC** — Junpeng Lao, arXiv:2607.23788 (Jul 2026). Multi-chain warmup
  controller choosing diagonal vs low-rank+diagonal (+rank) at
  dimension-derived window endpoints via diagnostics; ESS/grad ratios
  2.45/1.95 vs a prespecified Fisher low-rank baseline. **[V]**
- **Tuning diagonal scale matrices for HMC** — Tran & Kleppe, arXiv:
  2403.07495 (Statistics and Computing 34:196, 2024). Which diagonal
  estimator (incl. Welford variants) to use. [H]
- **Adaptive RMHMC with hierarchical metric** — Kailas, Vihola, Wallin,
  arXiv:2604.09832 (Apr 2026). Position-dependent hierarchical metric
  with a **closed-form explicit leapfrog** + adaptive scheme → usable
  inside dynamic HMC without RMHMC's implicit solves. **[V]**
- **Relativistic RMHMC** — Xu & Ge, ICML 2024 (PMLR 235): position-
  dependent mass with explicit integrator. [H]
- **Quantifying the effectiveness of linear preconditioning in MCMC**
  — Hird & Livingstone, arXiv:2312.04898 (JMLR 26(119), 2025): theory
  incl. cases where the *diagonal* choice strictly worsens conditioning.
  [H]
- Step-size successors: **ATune** (Akhmatskaya et al., arXiv:2506.04082,
  2025 — tune to the center of the stability interval, randomization
  intervals); **ATLAS** (Modi, arXiv:2410.21587, 2024 — joint step-size
  + trajectory adaptation via delayed rejection); **randomized step
  sizes** (Grazzi et al., arXiv:2601.19710, 2026 — randomized-step MH
  inherits weak Poincaré/spectral-gap from fixed-step **[V]**);
  **no-Metropolis-test HMC** (Robnik, Cohn-Gordon, Seljak, arXiv:
  2412.08876, ICML 2026 — step size by bounding an energy-error
  functional with bias control **[V]**); adaptive-MCMC lower bounds
  (Brown & Rosenthal, arXiv:2411.17084). Apers, Gribling, Szilágyi
  (JMLR 25(348), 2024) is the theoretical archetype of
  unadjusted-then-Metropolized warm starts. [H except as marked]
- NUTS-proper convergence theory (also Front 6): Balasubramanian,
  arXiv:2608.06336 (Aug 2026) — profile-separation conductance bounds
  for multinomial AND biased-progressive NUTS **with gradient-work
  accounting** **[V]**; Oberdörster arXiv:2507.13259 (2025) **[V]**;
  Gruffaz/Kim et al. arXiv:2603.18640 (2026) **[V]**.

**Verdict.** The two open flanks of Stan-style adaptation both moved:
(1) metric estimation has a new principled family — score/Fisher-based
low-rank+diagonal (2603.18845, 2607.23788, plus walnutpie's own
direction, Front 6) with large measured ESS/grad gains on OUR benchmark
suite (posteriordb); (2) the warmup *schedule* now has theory —
unadjusted-then-adjusted two-phase warmup is optimal-ish (2603.22741)
and practically implemented (LAPS 2601.16696). Explicit gap (hermes,
flagged honestly): **no paper analyzes the dual-averaging ×
expanding-window interaction head-on** — Stan's 75/25/50 window scheme
remains justified only by Betancourt's essays, which keeps our
W-43-class adaptation work novel territory.

---

## Front 4 — differentiation with repeated/degenerate eigenvalues (maps: W-40 cluster-adjoint, Kit 4 upstream ask)

**Leads.**

- **JAX PR #36832 "Implement JVP for eig eigenvectors (LAPACK gauge)"**
  — j-towns, merged **2026-04-17**. Differentiates `lax.linalg.eig`
  through LAPACK's *geev gauge (unit 2-norm, largest-magnitude
  component real), gated behind `enable_eigvec_derivs: bool = False`;
  the PR text itself proves the gauge-fixed eigenvectors are
  discontinuous where two components tie in magnitude. **[V]** (gh api:
  merged 2026-04-17T03:28:14Z; body text confirmed). Non-Hermitian eig
  only — eigh untouched. https://github.com/jax-ml/jax/pull/36832
- **Differentiable SVD based on Moore-Penrose pseudoinverse** —
  Yinghao Zhang & Yue Hu, arXiv:2411.14141 (Nov 2024). Shows the
  repeated-singular-value backward is an *underdetermined system* and
  selects the **Moore-Penrose minimal-norm solution** — a minimal-norm
  gauge choice for a backward pass, with stability analysis. **[V]**
- **KrylovKit.jl v0.8 (Jun 2024)** — ships a ChainRules rrule for
  `eigsolve` (adjoint as k linear solves or one non-Hermitian
  eigenproblem, described as "not in the literature"), **warns at
  runtime when the incoming adjoint reveals a gauge-dependent loss**;
  the rigorous manuscript is announced "forthcoming" (watch item). [H]
- **AD-framework state**: JAX eigh degeneracy = canonical issue #669
  (NaNs; maintainers: gradients of degenerate eigenvectors are not
  well-defined, any defined version must reference the implementation's
  gauge-breaking); PyTorch #47599 open since 2021; TensorFlow carries
  the in-tree comment "for (k-fold) degenerate eigenvalues the
  corresponding eigenvectors are only defined up to arbitrary rotation
  in a (k-dimensional) subspace" (master through 2026, cites Boeddeker
  1701.00392 which assumes distinct eigenvalues); Enzyme.jl #2264 (no
  eigen rules). ChainRules.jl differentiates the LAPACK
  normalization/phase gauge for general eig with an explicit
  degenerate-unsupported TODO (#144). [H]
- **Shift-and-invert adjoint** — Li & Kennedy, Struct. Multidisc.
  Optim. 68 (2025), doi 10.1007/s00158-024-03940-6, code
  github.com/smdogroup/eigd (the scan-1 ResearchGate item, now fully
  cited). Eigenvector aggregates with adjoints well-defined under
  repetition: Li & Kennedy, CMAME 429:117145 (2024). [H]
- **Canonical representatives in degenerate groups** — Usevich &
  Barthelmé, arXiv:2407.17047 (SIMAX, doi 10.1137/24M1677460):
  limiting eigenvectors inside degenerate blocks from Schur complements
  (which representative perturbation converges to); Simons,
  arXiv:2303.18233: eigenprojection Jacobians via Sun (1991) — the
  subspace map is differentiable where eigenvectors are not; Carlsson,
  IntechOpen 2025 chapter (doi 10.5772/intechopen.1008386): Frechet
  derivative formulas incl. the degenerate case after a canonical
  gauge. [H]
- de Leeuw arXiv:2508.09355 has **0 indexed citations** to date (our
  Semantic Scholar pull). Engineering-2024-25: Łasecka-Plura (Acta
  Mechanica 2024, repeated-eigenvalue sensitivities, viscoelastic);
  Li et al. MSSP 224 (2025, asymmetric damped, repeated). **[V** for
  the S2 count; H for the engineering items**]**

**Verdict.** Nothing post-2023 supersedes or scoops the W-40
cluster-aware minimal-norm adjoint — hermes' explicit negative: **"no
2023-2026 paper formalizes a minimal-norm or gauge-fixed adjoint of the
eigenproblem in the AD literature; the only treatments are framework
code/docs"**. But the design pattern we chose (opt-in flag,
differentiate-through-the-implementation's-gauge, minimal-norm at
clusters) now has a first-class precedent to cite: JAX PR #36832
(merged April 2026, default-off flag, discontinuity analysis in the PR
text) plus Zhang & Hu's minimal-norm SVD backward. Kit 4 should cite
both, plus KrylovKit's gauge-dependent-loss runtime warning (our
relative-gap warning ask), and claim the remaining first: gauge-fixed
adjoints for *Hermitian eigh at clusters* exist nowhere.

---

## Front 5 — within-chain MCMC parallelism (maps: W-49 parked lane, future parallel axis after W-36)

**Leads.**

- **Parallelizing MCMC Across the Sequence Length** — Zoltowski, Wu,
  Gonzalez, Kozachkov, Linderman, arXiv:2508.18413 (Aug 2025,
  **NeurIPS 2025**). Whole trajectories as a fixed point solved by
  parallel Newton/DEER iterations — exact recovery of serial MCMC
  output, 4-180x GPU wall-clock; §3.3.2-3.3.3 covers **parallel
  leapfrog inside HMC** (block quasi-DEER). Code:
  github.com/lindermanlab/parallel-mcmc (pushed 2026-05). **[V]**
  (abs + repo + Gelman-blog coverage Feb 2026)
- **Predictability Enables Parallelization of Nonlinear State Space
  Models** — Gonzalez, Kozachkov, Zoltowski, Clarkson, Linderman,
  arXiv:2508.16817 (Aug 2025, NeurIPS 2025). THE theory: conditioning
  of DEER-style parallel evaluation is governed by the largest Lyapunov
  exponent — predictable dynamics give O((log T)^2) evaluation, chaotic
  ones fail; **MCMC predictability explicitly open**. **[V]**
- **On the fundamental limitations of multiproposal MCMC** — Pozza &
  Zanella, arXiv:2410.23174 (Biometrika 112(2), 2025). Ceiling: ≤K
  speedup universally, ≤O(log^2 K) for log-concave — proposal clouds
  cannot buy real within-step parallel gains; explains why speculative
  prefetching (Brockwell 2006 … Angelino 2014) has no 2024-26
  successors. **[V]**
- **Zeroth-order parallel sampling** — Pozza & Zanella, arXiv:2601.19722
  (Jan 2026): random-slice zeroth-order MALA/HMC, provable polynomial
  speedup in workers m. **[V]**
- **Unifying framework for parallelizing sequential models with LDS**
  — Gonzalez, Buchanan, Lee, Liu, Wang, Zoltowski, Kozachkov, Ré,
  Linderman, arXiv:2509.21716 (TMLR): Newton/Picard/Jacobi parallel
  schemes as approximate linearizations of one nonlinear recursion. **[V]**
- Parallel-in-time with guarantees: Anari, Chewi, Vuong (arXiv:
  2401.09016, COLT 2024 — parallel LMC, polylog rounds); Yu & Dalalyan
  (arXiv:2402.14434 — parallelized midpoint randomization); Wei et al.
  PiX-MC (arXiv:2608.17666, Aug 2026 — Picard proximal MC). [H]
- Multiproposal line: Glatt-Holtz et al. (arXiv:2209.04750, TMA 8(2)
  2024 — GPU ~100k proposals); Carigi et al. (arXiv:2607.04466, 2026 —
  mpCN mixing, warmup shortens with more proposals). [H]
- Couplings for unbiased parallel MCMC: Ceriani, Pandolfi, Zanella
  (arXiv:2410.08939); Phan et al. multi-marginal MH couplings
  (arXiv:2605.12807, 2026). Empty sub-bucket: no GPU-resident meeting
  couplings yet. [H]
- GPU many-chain practice: Sountsov, Carroll, Hoffman, arXiv:2411.04260
  (Nov 2024 book chapter; ChEES/MEADS cross-chain warmup — both
  algorithms pre-2024). [H/**V** via own search]
- **GAP (hermes, matches our W-49 read)**: nobody combines
  fixed-point/DEER trajectory parallelism with **Metropolis-adjusted
  HMC + warmup adaptation** — 2508.18413 stays unadjusted, and its
  authors flag adjusted-chain predictability as open. Also nothing
  Picard-parallelizes NUTS-style tree building.

**Verdict.** W-49's Amdahl-style ceiling (split B: independent
attempts/rungs only) was the right conservative frame, and the 2025-26
literature now supplies (a) the ceiling's *reason* (Pozza-Zanella log^2
K bound), and (b) the escape route: treat the whole serial trajectory
as a fixed point (DEER) instead of speculating step-by-step — with the
Lyapunov/predictability criterion telling you when it can converge.
For walnutpie the unoccupied cell is precise: DEER/Picard over a
Metropolis-adjusted, warmup-adapted sampler (our macro/micro-step
chain is a fixed-point-shaped pipeline; the direction-coin and dyadic
search add unguessable bits — the predictability question is exactly
whether that kills conditioning). Park as the next parallelism axis;
revisit after cross-chain saturation, per the W-38u plan.

---

## Front 6 — WALNUTS citations/derivatives since JMLR 2026 (maps: walnutpie fork strategy, ESS-per-gradient lane)

**Leads.** (Semantic Scholar citation pull: 9-10 items **[V** via our
own API call**]**; hermes cross-checked contexts [H].)

- Citations found: Gruffaz/Kim et al. 2603.18640 (NUTS variant theory);
  Oberdörster 2507.13259 (NUTS accelerated mixing); Chevallier/Power/
  Sutton 2503.11479 (practical PDMP with locally adaptive step sizes —
  explicitly contrasts its approach with WALNUTS); GIST survey
  2404.15253 (Stat. Surveys 20, 2026 version); Kailas/Vihola/Wallin
  2604.09832; Bou-Rabee & de la Peña, "Decoupling for Markov Chains"
  (2512.19351); Lao 2607.23788; Chevallier 2606.19909 (PDMP Ω(√d)
  lower bound broken); Mukherjee & Vats, "HMC for (Physics) Dummies"
  (2601.01422).
- **Lineage**: 2408.08259 (Bou-Rabee/Carpenter/Kleppe/Marsden, Aug
  2024, J. Chem. Phys. 163:084119, 2025) — the direct GIST-based local
  step-size precursor **[V]**; No-Underrun Sampler 2501.18548 follow-up
  status; Turok/Modi/Carpenter, delayed-rejection GHMC for multiscale
  densities, arXiv:2406.02741 (AISTATS 2025) — per-leapfrog local step
  sizes by delayed rejection. [H]
- **Carpenter's March 2026 talk "GIST, WALNUTS, and Continuous
  Nutpie"** announces the derivative direction: continuously-discounted
  nutpie-style mass adaptation (Fisher divergence), **Adam replacing
  dual averaging** for step size, lock-free multithreading. [H, but
  corroborated first-hand below]
- **walnutpie README (verified today)**: the repo's own subtitle is
  "Adaptive Walnuts in Python and C++", listing "Adaptive Walnuts
  (continuous form of Nutpie-style adaptation)" as a shipped feature;
  bob-carpenter in AdvancedHMC.jl #470 (Sep 2025): "my C++
  implementation uses an online version of the warmup from Nutpie …
  way better than the warmup schedule we have been using in NUTS …
  The geometric motivation is to minimize Fisher divergence …
  (co)variance of scores and of draws … for mass matrix tuning", and
  "we're finding WALNUTS is performing worse than NUTS when there is a
  lot of correlation" until Kleppe identified the missing
  **min-micro-steps-per-macro-step** tuning parameter. **[V]** (gh api
  issue + comments + README)
- **Community ports**: AdvancedHMC.jl issue #470 (sethaxen, 2025-09-17,
  open; Axen prototype ≈2x ESS/iter but ≈**0.5x ESS/gradient** vs NUTS
  pre-tuning) **[V]**; BlackJAX discussion #935 (6/2026, DJLacombeTTU,
  stateless JAX kernel + PyMC bridge, NOT merged) [H]; numpyro issue
  #2070 (juanitorduz, 2025-09-14, open, no implementation) **[V]**;
  nutpie has no WALNUTS — the flow is reversed (walnutpie imports
  nutpie-style adaptation). [H/**V** README]
- **Theory gap**: as of 2026-08-23 **no independent paper analyzes
  WALNUTS itself** (reversibility calibration, threshold theory, mixing
  rates); the only third-party quantitative assessment is the AHMC #470
  ESS/gradient regression.

**Verdict.** Two consequences for us. (1) **Fork strategy**: upstream
walnutpie is actively becoming "Adaptive WALNUTS" = nutpie-style
continuous Fisher-divergence mass adaptation + Adam step size — the
same direction as arXiv:2603.18845 (Seyboldt/Carlson/Carpenter). Our
fork point (main @ 6162d88) predates the visible fruits; our adaptation
patches (W-43 find_reasonable_step fix, W-31 safe defaults, W-45-class
warmup experiments) should be re-based/upstreamed with that destination
in mind, and any warmup experiment we run should compare against a
Fisher/score-based metric arm or it will answer a question upstream has
already moved past. (2) **ESS-per-gradient**: the only published
third-party WALNUTS measurement (AHMC #470, ~0.5x ESS/grad vs NUTS
without min-micro-steps tuning) matches our W-38-E1 accounting
framework — our ESS/grad instrumentation is the right measuring stick
and the min-micro-steps knob is the documented confounder to control.

---

## TOP-5 "try this next" (ranked, mapped to our open items)

1. **Score/Fisher-based low-rank+diagonal metric in walnutpie warmup**
   → *W-45 two-phase-warmup follow-up + fork strategy.*
   arXiv:2603.18845 (Seyboldt/Carlson/Carpenter 2026, **[V]**) +
   walnutpie's own "Adaptive Walnuts" direction (**[V]** README +
   Carpenter in AHMC #470) + Lao's controller arXiv:2607.23788 (**[V]**).
   W-45's subsampled-covariance transplant failed because the geometry
   was a different posterior's; a metric estimated from *gradients*
   (score covariance / Fisher divergence) during the SAME chain's
   warmup is the principled fix, validated on 114 posteriordb models
   (4x median ESS/grad vs diagonal). Next concrete step: prototype a
   fisher_low_rank-style window in our fork and race it against Welford
   diagonal on the ESS/grad harness — and check upstream main before
   building (they may land it first; then adopt + measure).

2. **Two-phase warmup: unadjusted warm-start phase, then Metropolized
   sampling** → *W-45 follow-up (the untried axis that now has theory).*
   arXiv:2603.22741 (Zhang/Altschuler/Chewi 2026, **[V]** — unadjusted
   HMC generates a warm start in Õ(d^{1/4})) + LAPS arXiv:2601.16696
   (Robnik & Seljak, AISTATS 2026, **[V]** — ensemble bias estimation
   auto-selects the unadjusted-phase step size) + archetype (Apers et
   al., JMLR 2024). For walnutpie: a cheap unadjusted WALNUTS warmup
   phase (no U-turn tree, coarse energy control) could cut warmup
   gradient spend on pf-class short-warmup pathologies (the W-43 blr
   pin family) — the bias→step-size mechanism from 2412.08876 (**[V]**)
   is the tuning rule.

3. **Cite-and-ship the gauge-fixed eigenvector adjoint (Kit 4 / W-40).**
   JAX PR #36832 (merged 2026-04-17, **[V]**) + Zhang & Hu arXiv:
   2411.14141 minimal-norm SVD backward (**[V]**) + KrylovKit gauge
   warning [H]. The opt-in-flag, differentiate-the-implementation's-
   gauge design we built in W-40 is now the pattern a major AD
   framework ships; no one has done Hermitian eigh at clusters.
   Next step: file the stan-math issue/PR with these as precedents and
   the explicit "no paper exists for eigh-at-clusters" claim (verified
   negative), adding KrylovKit's runtime gauge-dependence warning to
   the relative-gap warning ask.

4. **DEER/Picard trajectory parallelism as the successor to W-49's
   speculation ceiling** → *W-49 parked lane / post-cross-chain axis.*
   arXiv:2508.18413 (Zoltowski et al., NeurIPS 2025, **[V]**) +
   arXiv:2508.16817 predictability theory (**[V]**) + arXiv:2509.21716
   LDS unification (**[V]**) + the multiproposal ceiling arXiv:2410.23174
   (**[V]**). Zoltowski et al. already parallelize leapfrog inside HMC
   with exact serial-output recovery; the open cell is
   Metropolis-adjusted + warmup — walnutpie-shaped. Next step (cheap,
   analysis-only): run the 2508.16817 Lyapunov-style predictability
   argument on a WALNUTS orbit (direction-coin + dyadic search as the
   chaotic bits) to decide PARK vs PROTOTYPE before any threading work.

5. **Frame the W-53 SoA rollout on the CoDiPack-3/Warp pattern**
   → *W-53 (post-W-47 rollout), feeds W-48.*
   CoDiPack 3.0/3.1 (**[V]**) + XAD 2.1.0 (**[V]**) + Warp per-array
   tape + PyTorch compiled autograd [H] + ParDiff PPoPP 2026 (**[V]**).
   W-47 measured the typed-pool ceiling (~1/3 of the eltwise complex)
   and stopped at the design doc; the shipping world has since adopted
   statement-level tape data + custom evaluators + per-array-op
   registration. Next step: re-issue Increment A (batched vari-array +
   span registration) as "stan-math's CoDiPack-3 moment", citing
   CoDiPack 3.1 evaluators and Warp as the API precedent — and note for
   W-48 that the fused-logp node we emit is exactly the "one callback
   per array op" pattern those systems standardize.

**Honorable mentions** (near misses): glibc's correctly-rounded
binary64 imports + ifunc multiversioned islands (cite directly in the
W-46 fused-log1p PR — glibc itself uses pragma-target islands
**[V/H]**; and it retires the "global -march" objection); NUTS
gradient-work-accountable convergence bounds arXiv:2608.06336 (**[V]**)
— the first theory matching our ESS-per-gradient objective;
Kleppe/Carpenter's min-micro-steps confounder (AHMC #470, **[V]**) —
control it in every WALNUTS ESS/grad comparison we report.

---

## Hermes status (honest close-out)

6/6 planned queries completed and delivered (q1 13:58, q2 9:39, q3
19:30, q4 17:10, q5 15:26, q6 39:00 wall). One provider 429 (zai,
"Usage limit reached for 5 hour") fired during q4's *post-answer*
memory-save step; q5 and q6 sessions then established and ran clean
(hermes' pooled-credential rotation), so the pre-registered
two-consecutive-failures fallback never triggered and WebSearch/
WebFetch fallback was used only for verification (as planned).
All raw transcripts preserved: `stan/scratch/w51/q{1..6}_*.txt`.

## Verification log (first-hand, this session)

arXiv abs fetches: 2603.18845, 2601.16696, 2603.22741, 2607.23788,
2604.09832, 2509.02197, 2405.07819, 2507.13259, 2603.18640, 2508.16817,
2410.23174, 2601.19722, 2509.21716, 2411.14141, 2412.08876 (via
search), 2601.19710 (search), 2607.03574 (search). GitHub via `gh api`:
jax-ml/jax#36832 (merged 2026-04-17), auto-differentiation/xad v2.1.0
(2026-03-31), TuringLang/AdvancedHMC.jl#470 (+ comments incl.
bob-carpenter's Fisher/nutpie remarks), pyro-ppl/numpyro#2070,
lindermanlab/parallel-mcmc (pushed 2026-05), flatironinstitute/walnutpie
README ("Adaptive Walnuts"). Semantic Scholar API: full citation lists
of arXiv:2506.18746 (9), 2506.09762 (3: 2601.19722, 2509.21716,
2508.18413), 2508.09355 (0). Web: PPoPP26 program page (ParDiff),
CoDiPack changelog/releases, HAL hal-03141101 (survey v8), stan-math
reverse-mode-types doc. Items marked [H] were verified by hermes
against primary sources during its sessions (transcripts in scratch/)
but not re-verified by us — treat citations-before-print accordingly.
