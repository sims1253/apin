# W-102 scan: post-SoA math-side lever ranking beyond hier_2pl (callgrind, multi-model)

Mission: generalize the W-57-era lever mining (hier_2pl-only: #1 bernoulli_logit_lpmf
48.8% G, #2 rvalue/gather 13.5% G) to 4 other model classes on the patched-SoA
.so lineage: kronecker_gp, accel_gp, blr, diamonds.

## Protocol (W-29, verbatim)

- CLI: `external/walnutpie/build_w36exp/examples/stan_cli` (read-only), valgrind 3.23
  `~/vginstall`, callgrind Ir, one job at a time, nice 19, `env -u LD_LIBRARY_PATH
  OMP_NUM_THREADS=1`.
- warmup 100, samples 50, seed 20260819, `--metric-window 50`, model data + pf init.
- Models / .so (all patched-SoA lineage) / inits:
  - kronecker_gp: `scratch/w53/model_kronecker_gp_patched/kronecker_gp_model.so`
    (md5 229cfeb4… identical to w81 copy), init `inits_w27/kronecker_gp/rep0/chain_1.txt`
    (chain_0 avoided — dead init).
  - accel_gp: `scratch/w53/model_accel_gp_patched/accel_gp_model.so` (md5 2c0ac8c1… =
    w81 copy), init `inits_w36/accel_gp/rep0/chain_0.txt` (per w63 manifest).
  - blr: `scratch/w57/model_blr_patched/blr_model.so` (md5 61b05e4f…), init
    `inits_w25/blr/rep0/chain_0.txt` (w63 manifest / w60 gate posture).
  - diamonds: `scratch/w81/model_diamonds/diamonds_model.so` (md5 1bb9d1b7…), init
    `inits_w36/diamonds/rep0/chain_0.txt` (w63 manifest).
- Outputs: `scratch/w102scan/profile_<model>/{callgrind.out,ann.txt,incl_ann.txt,draws.csv,cli.log}`.
  All runs rc=0, 50 draws each (md5: kron ad40da16…, accel 49f00689…, blr 11fb5b6f…,
  diamonds 7dad75d3…). Runner: `scratch/w102scan/run_callgrind_w102.sh`.
- hier_2pl column uses the current patched .so reference `scratch/w57/profile_w59/patched`
  (same w53 patched .so, same protocol), i.e. the W-102 pre-reg reference era.

## Method + validation

G = inclusive Ir of `bs_log_density_gradient` (the logp_grad subtree). Complexes =
disjoint self-Ir buckets over model-.so + shared-lib functions (CLI/JSON separated),
normalized %G. Inclusive-entry view added for the W-102 lever style. Validation on
hier_2pl: strict rvalue+vector-copies = rvalue 9.99% + 3.33% + std::vector copies
3.64% = **13.63% G** (W-102 anchor 13.5% ✓); bernoulli_logit_lpmf inclusive =
**52.98% G** (W-57 anchor 48.8% = same subtree minus the elt_multiply<IndexedView>
carve ✓). blr fresh run reproduces the w60 gate profile exactly (rethrow 49.84%G,
G within 0.0005%). Scripts: `scratch/w102scan/parse_ann.py`, `complex_table.py`,
table dump `complex_table.out`.

## Deliverable table: model x complex -> %G (self Ir, disjoint)

G per model: hier_2pl 28.09e9, kronecker_gp 22.26e9, accel_gp 0.625e9, blr 0.450e9,
diamonds 2.79e9.

| complex                     | hier_2pl | kronecker_gp | accel_gp |  blr  | diamonds |
|-----------------------------|---------:|-------------:|---------:|------:|---------:|
| lpmf/lpdf-interior          |    23.1  |    (0.0)     |    8.9   |  4.4  |   9.8    |
| rvalue-gather/IndexedView/copies | 41.2 (13.6 strict) | 3.3 | 0.8 | 0.9 | 7.3 |
| eltwise-forwards            |    25.7  |     6.9      |   14.0   |  1.5  |   2.1    |
| reverse-callbacks           |     4.7  |     2.2      |    8.9   |  1.1  |   0.2    |
| decompositions (eigh/chol)  |     0.6  |    36.6      |    0.0   |  0.0  |   0.0    |
| GEMM/BLAS (gemv/gebp)       |     0.3  |    31.6      |   22.0   |  2.5  |  80.5    |
| alloc/emplace remnants      |     0.8  |     7.8      |   19.4   |  1.7  |   0.6    |
| exception/check-throw       |     0.0  |     0.0      |    0.0   | 78.7* |   0.0    |
| model-glue / checks         |     0.4  |     4.2      |    8.0   |  0.6  |   0.2    |
| other (math .so)            |     2.9  |     7.4      |   14.0   |  2.9  |   1.1    |
| libc-other                  |     0.2  |     2.8      |    3.1   |  7.0  |   2.9    |
| *(outside G)* CLI/sampler   |     7.5  |     6.7      |   43.2   | 13.9  |   6.4    |
| *(outside G)* construct/JSON|     0.1  |     0.0      |    1.8   |  0.2  |   5.9    |

*blr 78.7 is whole-program throw-machinery self Ir in G-units; the provably in-G
part is `stan::lang::rethrow_located` inclusive = **49.84% G** (of which
`elementwise_throw_domain_error` message formatting 24.38% + libstdc++/libgcc
unwinding). Present identically on stock blr (w60: 49.25% G) — posture, not patch.

### Inclusive-entry lever view (W-102 style, >=2%G)

- hier_2pl: bernoulli_logit_lpmf 52.98%G; rvalue+copies 13.63%G (anchors above).
- kronecker_gp: `Eigen::SelfAdjointEigenSolver` 39.05%G; `gebp_kernel` 22.16%G;
  `stan::math::eigenvectors_sym` 21.79%G; `computeFromTridiagonal_impl` 21.56%G;
  `eigenvalues_sym` 20.13%G; `tridiagonalization_inplace` 17.08%G.
- accel_gp: var-value matrix materialization ctor path 33.16%G; `stan::math::multiply`
  (gemv) 14.68%G; `normal_lpdf` 14.65%G; `plog_impl_double` packets 5.94%G.
- blr: `rethrow_located` 49.84%G; `normal_lpdf` 34.68%G (includes throw paths);
  `elementwise_check` 24.30%G.
- diamonds: `normal_id_glm_lpdf` 98.93%G — interior is two gemv instantiations
  (40.43%G + 40.09%G, Xc*b and Xc^T*alpha), i.e. the glm lpdf IS the GEMM complex.

## RANKING: cross-model vs hier_2pl-specific

Cross-model (candidates for the next math work), by breadth x size:

1. **GEMM/BLAS (dense gemv/gebp kernels)** — 80.5% G (diamonds), 31.6% (kronecker_gp),
   22.0% (accel_gp); range 22–80% G over 3 of 4 scanned classes; cold on hier_2pl (0.3%).
   On diamonds the kernels live inside `normal_id_glm_lpdf`; on accel inside
   `multiply(Xgp, …)`; on kronecker inside the eigh blocked tridiagonalization. This is
   the single largest math-side lever outside the hier_2pl class (Eigen gemv path,
   not BLAS-library calls — all kernels are Eigen-internal in these builds).
2. **Decompositions (symmetric eigensolver family)** — 36.6% G self / 39.05% G incl on
   kronecker_gp (`eigenvectors_sym`+`eigenvalues_sym` per grad: Q1/R1, Q2/R2). Not hot
   on the other three, but it is THE complex of the Kronecker/GP model class
   (kronecker G = 22.3e9 Ir/eval-set — heavier per-grad than hier_2pl's 28.1e9 run).
3. **lpdf forward interiors** — an lpdf entry is top-2 on every model, but the
   composition splits: hier_2pl's scalar-packet Select/log1p redux (the W-103 log1p
   lever) does NOT transfer — on glm-style models (diamonds, blr, accel: normal/
   normal_id_glm) the interior is gemv + a few scalar checks. The W-103 lever stays
   hier_2pl/IRT-scoped.

hier_2pl-specific:

- **rvalue/gather + IndexedView + vector-copies** (W-102's target): 41.2% G broad /
  13.6% strict on hier_2pl, but <=7.3% everywhere else scanned (kronecker 3.3,
  diamonds 7.3, accel 0.8, blr 0.9). It needs the ragged multi-index (index_multi)
  structure; expect it only in the IRT/hierarchical-ragged family (lsat_model would
  be the sibling case, not scanned here). W-102 stays justified on hier_2pl but is
  NOT a cross-model lever.
- eltwise-forwards redux on hier_2pl (25.7%) is part of the lpmf interior above.

Post-SoA hygiene confirmed: reverse-callbacks small everywhere (0.2–8.9% G);
alloc/emplace remnants modest except accel_gp (19.4% — var-value Matrix
materialization of the gpa() products, 33.2% incl; a "fused gpa output" candidate).

## Surprises

1. **blr: the #1 complex is exception/check-throw machinery, not math** — 49.84% of G
   inside the gradient subtree is `rethrow_located` (24.4% `elementwise_throw_domain_error`
   message formatting + unwinding in libstdc++/libgcc/ld), and another ~14% G-units of
   throw Ir sits CLI-side. `normal_lpdf`'s `elementwise_check` fires on a large fraction
   of evaluations (sigma underflow at metric-window/warmup probe points — the pf init
   itself is sane, sigma(0)=1.035), and each throw costs ~1e5 Ir in formatting+unwind.
   Identical on stock blr (49.25% G, w60) — a walnutpie/sampler-posture or cheap-reject
   check lever, not a SoA-math one. blr's real math is ~35% of its tiny G (0.45e9).
2. **diamonds' "lpdf" is GEMM** — normal_id_glm_lpdf inclusive 98.93% G with the two
   gemv instantiations at 80.5% G self: any lpdf-side work there must actually be
   kernel work.
3. **accel_gp is sampler-dominated**: 43.2% G-units of program Ir is CLI-side
   (metric-window) machinery; its math-side top item is var-matrix materialization
   (33.2% incl), a tape-side lever in the brms-gpa pattern.

## Paths

- Profiles: `/home/m0hawk/Documents/apin/stan/scratch/w102scan/profile_{kronecker_gp,accel_gp,blr,diamonds}/`
- Runner + analysis: `/home/m0hawk/Documents/apin/stan/scratch/w102scan/run_callgrind_w102.sh`,
  `parse_ann.py`, `complex_table.py`, `complex_table.out`
- hier_2pl reference: `/home/m0hawk/Documents/apin/stan/scratch/w57/profile_w59/patched/`
  (w60 blr gate: `scratch/w57/profile_w60/`)
