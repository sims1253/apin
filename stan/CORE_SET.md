# CORE_SET — frozen benchmark set

**FROZEN 2026-08-19, before any optimization work. Do not edit.**

- posteriordb clone: `external/posteriordb` @ `28f8d3d6e975315f42aa274a8399f21e07a43b30` (github.com/stan-dev/posteriordb, master)
- CmdStan pin: **2.39.0** (cmdstan @ bd4aeedb8c09e4d214a9bb4728edeb734bf5fb28,
  stan submodule @ 44be14e28e8a677719eb821447d37765b3295f7a), stanc3 v2.39.0
- Protocol: 4 chains × (1000 warmup + 1000 draws), default NUTS, fixed seeds
  (rep r: seed = 20260819 + 1000·r, chain seeds offset by chain id), median of 3 reps.
- Machine: Ryzen 9 5900X (Zen 3, AVX2 only — no AVX-512), ≤4 cores per run, 1 thread/chain.

| # | model | family | posterior | data |
|---|-------|--------|-----------|------|
| 1 | eight_schools_noncentered | easy/small | eight_schools-eight_schools_noncentered | eight_schools |
| 2 | blr | easy/small | sblrc-blr | sblrc |
| 3 | kidscore_momiq | easy/small | kidiq-kidscore_momiq | kidiq |
| 4 | lsat_model | easy/small | lsat_data-lsat_model | lsat_data |
| 5 | logmesquite_logvash | GLM | mesquite-logmesquite_logvash | mesquite |
| 6 | wells_dist100_model | GLM | wells_data-wells_dist100_model | wells_data |
| 7 | diamonds | GLM | diamonds-diamonds | diamonds |
| 8 | radon_partially_pooled_noncentered | hierarchical | radon_all-radon_partially_pooled_noncentered | radon_all |
| 9 | radon_variable_intercept_slope_noncentered | hierarchical | radon_mn-radon_variable_intercept_slope_noncentered | radon_mn |
| 10 | dogs_hierarchical | hierarchical | dogs-dogs_hierarchical | dogs |
| 11 | pilots | hierarchical | pilots-pilots | pilots |
| 12 | hier_2pl | hierarchical | sat-hier_2pl | sat |
| 13 | gp_regr | GP/spatial | gp_pois_regr-gp_regr | gp_pois_regr |
| 14 | kronecker_gp | GP/spatial | synthetic_grid_RBF_kernels-kronecker_gp | synthetic_grid_RBF_kernels |
| 15 | accel_gp | GP/spatial | mcycle_gp-accel_gp | mcycle_gp |
| 16 | bym2_offset_only | GP/spatial | traffic_accident_nyc-bym2_offset_only | traffic_accident_nyc |
| 17 | eight_schools_centered | stiff/funnel | eight_schools-eight_schools_centered | eight_schools |
| 18 | garch11 | stiff/funnel | garch-garch11 | garch |
| 19 | lotka_volterra | stiff/funnel | hudson_lynx_hare-lotka_volterra | hudson_lynx_hare |
| 20 | low_dim_gauss_mix | stiff/funnel | low_dim_gauss_mix-low_dim_gauss_mix | low_dim_gauss_mix |
| 21 | arma11 | stiff/funnel | arma-arma11 | arma |
