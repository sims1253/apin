All verified. Here's the report.

---

# Q1 — Aurora

**Disambiguation.** Exactly one optimizer named Aurora exists (2025–2026): **arXiv:2606.27715, "Aurora: A Leverage-Aware Spectral Optimizer"** (Dewulf, Pai, Yang, Zhang, Keigwin — Tilde Research, Jun 2026; blog 2026-05-05; code `github.com/tilde-research/aurora-release`). No second optimizer named Aurora found. Name collisions elsewhere: Aurora the atmospheric-foundation-model (Microsoft, Nature 2025, Bodnar et al. — e.g. analyzed in arXiv:2603.06516, arXiv:2606.26361) — unrelated, not an optimizer.

**Mechanism.** Muon updates W ← W − η·polar(M) = −η·UV^⊤ (spectral-norm steepest descent). For **tall** matrices (m > n, i.e. MLP up/gate projections), the polar factor's row norms are non-uniform (avg row norm² = n/m; leverage-score concentration), creating a feedback loop → neuron death in MLPs. Post-hoc row normalization (NorMuon, arXiv:2510.05491) fixes it but destroys column-orthogonality — their Claim 1: a tall matrix cannot be simultaneously column-orthogonal and unit-row-norm (trace argument: n ≠ m). **Aurora = alternating projections between the Stiefel manifold (semi-orthogonality) and the equal-row-norm ("row oblique") manifold**, i.e. it approximates the projection onto the intersection while preserving polar geometry (~6% overhead, `pp_iterations`≈2 extra polar calls). Riemannian-Aurora = exact tangent-space solver on that intersection (reference/expensive). Gains scale with MLP expansion factor; 1.1B model +9.1 MMLU over Muon; modded-nanoGPT optimizer-track SoTA at time of writing.

**Scalar/diagonal-vector applicability: none.** Aurora is defined only for 2-D tall matrices (paper: "specifically for the up and gate projection matrices"; square matrices reduce to plain Muon). RMSNorm scales/embeddings stay on Adam(W), as in standard Muon practice (stated explicitly in 2606.27715 §2.1). For a vector parameter the whole polar machinery degenerates: polar(v) = v/‖v‖₂, and the row-uniformity constraint is vacuous.

---

# Q2 — Does it need 2-D matrix parameters to be meaningful?

| Optimizer | arXiv / source | Needs 2-D? | One line |
|---|---|---|---|
| Muon | Jordan blog 2024; scalable in 2502.16982 | **Yes** | NS orthogonalization → polar(M)=UV^⊤; on vectors degenerates to normalized momentum, scalars to sign(m); scalars/1-D routed to AdamW. |
| Aurora | 2606.27715 | **Yes — tall 2-D specifically** | Alternating projection Stiefel ∩ equal-row-norm; square → Muon; undefined/trivial for vectors, scalars. |
| Muon2 (Muon²) | 2604.09967 | **Yes** | Adam-style elementwise second-moment preconditioning *before* NS to fix ill-conditioned momentum; orthogonalization core unchanged. |
| NAMO (+NAMO-D) | 2602.17080 ("Adam Improves Muon") | Direction yes; adaptation no | Orthogonalized momentum scaled by a **single scalar** adaptive step (shape-free); NAMO-D right-multiplies by clamped **diagonal** matrix (neuron-wise). |
| MALT (+MALTER) | 2608.05088 | Yes (for the core) | Two-sided **diagonal** preconditioners DˡMDʳ around NS + norm grafting; MALTER adds scalar adaptive stepsize rescaling. |
| SOAP | 2409.11321 | **Yes** | Adam run in the eigenbasis of Shampoo's L=GGᵀ, R=GᵀG factors; per-dimension preconditioner pairs need matrices. |
| Shampoo | 1802.09568 | **Yes** | Full per-mode preconditioners from gradient second moments; 1-D case collapses to diagonal/Adam. |
| Purifying Shampoo | 2506.03595 | **Yes** | Same Kronecker/eigencorrected preconditioner, heuristics (grafting, staleness) removed + update clipping. |
| Schedule-Free | 2405.15682 | **No** | Parameter-space interpolation (x,y,z averaging); shape-agnostic, works on scalars/vectors unchanged. |
| OptMuon | 2606.08783 | Direction yes; magnitude no | Polar-factor direction + **closed-loop scalar** AdaGrad-norm coefficient from realized trajectory; paper notes vector params handled by reshape/blocks. |
| AdaGO | 2509.02981 | Direction yes; magnitude no | Norm-based AdaGrad **scalar** (one accumulated ‖g‖² accumulator) scaling orthogonalized updates; preserves orthogonality. |
| AdaMuon | 2507.11005 | Yes | Elementwise second moment applied *after* orthogonalization (breaks orthogonality). |

**2026-era successors (found):** all matrix-bound: NorMuon 2510.05491 (row RMS rescale), MuonEq 2603.28254 (lightweight two-sided **diagonal equilibration before** orthogonalization — the most "diagonal-adjacent"), Dion 2504.05295 / Dion2 2512.16928 / Dion3 2608.11612 (distributed orthogonalization), Nora 2605.03769 (row alignment), FOGO 2606.10406, Newton-Muon 2604.01472, Turbo-Muon 2512.04632 (near-orthogonal preconditioner replacing NS), Polar Express 2505.16932 (optimal matrix-sign/NS iteration), Modular Duality 2410.21265 + On MUON non-convergence 2608.04607 (theory), Spectral Flattening 2605.13079 (theory: orthogonalization ≈ spectral flattening controlling tolerable LR). **Diagonal-only, no-orthogonalization lineage:** OLion 2602.01105 (Lion-style sign + few NS steps; sign part shape-free), SCALE 2506.16659 (column-wise normalization + last-layer-only momentum; zero matrix factorization, vector ops only).

Pattern: nobody makes the *direction* work below 2-D. The 2025–26 innovation surface is exactly (i) diagonal preconditioning around the orthogonalization (MALT, MuonEq, Muon2) and (ii) scalar closed-loop step-size loops on top (NAMO, OptMuon, AdaGO, MALTER).

---

# Q3 — Orthogonalized/preconditioned updates for (a) scalar step-size adaptation, (b) MCMC mass matrices

**(a) Scalar LR/step-size adaptation.** Orthogonalizing the scalar itself is vacuous (polar factor of a 1×1 = ±1), and no published work does "orthogonalized step size." What exists is the exact structural dual of your WALNUTS loop — a **single scalar adapted from trajectory statistics wrapping an orthogonalized direction**:
- NAMO (arXiv:2602.17080): one adaptive scalar scales polar(M).
- OptMuon (arXiv:2606.08783): "closed-loop **scalar adaptation** can be combined with Muon-style momentum orthogonalization" (their abstract, verbatim) — AdaGrad-norm-type coefficient, running-max corrected.
- AdaGO (arXiv:2509.02981): accumulated ‖g‖² scalar stepsize on orthogonal updates.
- MALTER (inside arXiv:2608.05088): adaptive scalar rescaling of the preconditioned Muon step.
- Pure scalar-loop lineage (no orthogonalization, same adaptation logic): AdaGrad-norm (arXiv:1806.01811, Ward/Wu/Bottou), hypergradient descent (arXiv:1703.04782), D-Adaptation (arXiv:2301.07733), Prodigy (arXiv:2306.06101), DADA (arXiv:2501.10258).

**(b) MCMC/HMC.** **No published use of Newton-Schulz/polar orthogonalization for mass-matrix estimation or scalar step-size adaptation in samplers was found.** Your two WALNUTS ingredients map to established, non-orthogonal statistics:
- Scalar log-step-size from acceptance statistics = dual averaging, exactly NUTS (Hoffman & Gelman, arXiv:1111.4246; JMLR 15(47):1593–1623, 2014, §3.2/primal-dual averaging). WALNUTS itself (arXiv:2506.18746; Bou-Rabee, Carpenter, Kleppe, Liu, JMLR 2026) adapts step size *within orbit* from an energy-error threshold against a dyadic schedule — a different scalar statistic (energy error, not acceptance), and it does not touch the mass matrix.
- Diagonal mass matrix from online draw variances = standard Stan warmup (windowed adaptation, Welford accumulators on draws; Stan Reference Manual §14.2, mc-stan.org/docs). The **score-side** variant exists for full matrices: Titsias, "Optimal Preconditioning and Fisher Adaptive Langevin" (arXiv:2305.14442) — preconditioner = inverse of averaged outer products of ∇log p (score), optimized for expected squared jump distance; your "score variance" diagonal is the diagonal restriction of exactly this. Older diagonal preconditioning in sampling: pSGLD (arXiv:1512.07666). Full-matrix-whitening-by-transport: NeuTra (arXiv:1903.03704) — learned bijection's Jacobian as preconditioner; AdamMCMC (arXiv:2312.14027) grafts Adam moments onto MALA. "Orthogonal parallel MCMC" (arXiv:1507.08577) is orthogonal-array enrichment across parallel chains — unrelated to orthogonalized updates.

**Bottom line for your WALNUTS setting:** adapting one scalar log-ε per chain via dual averaging and a diagonal mass matrix via online draw variances is the NUTS/Stan-standard recipe (1111.4246 + Stan §14.2); the score-outer-product mass estimate is Fisher-adaptive Langevin (2305.14442) restricted to the diagonal. There is no precedent applying Muon-style orthogonalization to either — and mathematically there can't be one at 1-D (degenerate to sign), while on the diagonal-vector mass matrix polar(·) collapses to per-coordinate normalization, i.e. the standard variance-normalized whitening already in use. The genuinely adjacent published ideas are OptMuon/AdaGO/NAMO's scalar closed-loop calibration and MALT/MuonEq's two-sided diagonal preconditioning — all optimizer-side, none sampler-side.
