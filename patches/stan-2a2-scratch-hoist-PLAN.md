# Patch plan: stan-2a2 scratch-hoist (base_nuts.hpp) — implement fresh-session

Target file: src/stan/mcmc/hmc/nuts/base_nuts.hpp (stan submodule @ d13c50c0f)

## Hunks

### H1: class members (scratch stack), after `bool divergent_;`
```cpp
  // Phase-2a scratch: build_tree-internal vectors hoisted out of the
  // recursion. Indexed by depth; sized on first transition (num_params).
  std::vector<Eigen::VectorXd> scratch_p_init_end_;
  std::vector<Eigen::VectorXd> scratch_p_sharp_init_end_;
  std::vector<Eigen::VectorXd> scratch_rho_init_;
  std::vector<Eigen::VectorXd> scratch_p_final_beg_;
  std::vector<Eigen::VectorXd> scratch_p_sharp_final_beg_;
  std::vector<Eigen::VectorXd> scratch_rho_final_;
  std::vector<Eigen::VectorXd> scratch_rho_subtree_;
  ps_point z_propose_final_scratch_{0};  // resized + reused
```
Initializer: `z_propose_final_scratch_{0}` OK; on first transition() entry,
resize all stacks to max_depth_ and each vector to z_.p.size(), and
`z_propose_final_scratch_ = ps_point(z_.p.size())` (or per-depth stack of
ps_points if cleanest).

### H2: build_tree body — replace locals with refs into the stacks
- `Eigen::VectorXd p_init_end(...)` -> `Eigen::VectorXd& p_init_end = scratch_p_init_end_[depth];`
- same for p_sharp_init_end, rho_init (setZero instead of Zero), p_final_beg,
  p_sharp_final_beg, rho_final.
- `ps_point z_propose_final(this->z_)` -> ref to per-depth scratch ps_point,
  `z_propose_final = this->z_;` after ref.
- `Eigen::VectorXd rho_subtree = rho_init + rho_final;` ->
  `Eigen::VectorXd& rho_subtree = scratch_rho_subtree_[depth]; rho_subtree = rho_init + rho_final;`
  (the 2 extended reuses keep the same buffer, no new temps).
- NOTE the depth-indexed refs are recursion-SAFE only because a parent's
  depth d scratch is not touched while children (d-1) run; verify no aliasing
  between a node's own scratch and its children's (different indices — OK).

### H3: transition() rho_extended
`Eigen::VectorXd rho_extended = rho_bck + p_fwd_bck;` -> hoist one member,
  two reuses stay.

## Gates (all required, in order)
1. Builds: `./bin/stanc --version` + compile 3 probe models (blr, pilots, lsat).
2. BIT-IDENTITY: same seed, same model, csv diff vs stock binary == 0.
   (3 models x 2 seeds. rho-hoist history says do NOT assume this.)
3. callgrind on pilots: memcpy/alloc share 21% -> target <8%.
4. Wall-clock paired, small-model class (pilots, arma11, blr, 8schools):
   report per-model + geomean.
5. If gate 2 fails: bisect hunks H1/H2/H3 individually; ship only what passes.

## Never touch in this patch
- leaf `z_propose = this->z_`, transition-scope 12 vectors,
  compute_criterion, integrator/hamiltonian internals, RNG call order.
