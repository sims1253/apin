#ifndef W32_EIGH_COMBINED_HPP
#define W32_EIGH_COMBINED_HPP

// W-32 prototype (measurement, not a shippable patch): combined values+vectors
// symmetric eigendecomposition for reverse-mode var matrices.
//
// Problem (W-29 atlas candidate #1): a model that uses BOTH eigenvectors_sym(A)
// and eigenvalues_sym(A) pays TWO full Eigen::SelfAdjointEigenSolver runs per
// matrix per gradient, because each stan-math rev overload constructs its own
// solver on the .val() matrix (stan/math/rev/fun/eigenvectors_sym.hpp and
// eigenvalues_sym.hpp — both default ComputeEigenvectors mode; the rev
// eigenvalues overload cannot use EigenvaluesOnly because its adjoint needs
// the eigenvectors).
//
// This helper runs ONE solver and registers ONE reverse callback that computes
// BOTH adjoints. Adjoint math for A = V diag(w) V^T (V orthogonal), with
// downstream adjoints G_V (eigenvector matrix) and g_w (eigenvalue vector):
//
//   via values :  dA += V diag(g_w) V^T                     [stan eigenvalues_sym]
//   via vectors:  dA += V ( F . (V^T G_V) ) V^T,            [stan eigenvectors_sym]
//                 F_ij = 1/(w_j - w_i),  F_ii = 0
//   combined   :  dA += V ( F . (V^T G_V) + diag(g_w) ) V^T
//
// (first-order perturbation theory: dw_i = v_i^T dA v_i;
//  dv_i = sum_{j!=i} v_j (v_j^T dA v_i)/(w_i - w_j); . = elementwise product)
//
// Derivation cross-checked against stan-math's own two implementations; see
// results/eigh_reuse_w32.md for finite-difference + stock-model validation.
//
// NOTE: defined inside namespace stan::math with UNQUALIFIED trait names
// (require_rev_matrix_t, arena_t, ...) so the same header compiles against
// both cmdstan-2.39's stan-math (traits in stan::math) and bridgestan 2.9's
// newer stan-math (traits hoisted to stan::).

#include <stan/model/model_header.hpp>

namespace stan {
namespace math {

// var-input result: plain var matrices (the types stanc3-generated code uses
// for Matrix<var> locals; element var copies share varis with the arena
// copies, so downstream adjoints reach the callback exactly as in stock).
struct w32_eigh_result_var {
  Eigen::Matrix<var, -1, -1> vectors;
  Eigen::Matrix<var, -1, 1> values;
};

// double-input result (log_prob values-only / write_array paths).
struct w32_eigh_result_dbl {
  Eigen::MatrixXd vectors;
  Eigen::VectorXd values;
};

// ---- reverse-mode (var) input: ONE solver + ONE fused callback ----
template <typename T, require_rev_matrix_t<T>* = nullptr>
inline w32_eigh_result_var w32_eigh(const T& m) {
  if (m.size() == 0) {
    return w32_eigh_result_var{};
  }
  check_symmetric("w32_eigh", "m", m);

  auto arena_m = to_arena(m);
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> solver(arena_m.val());
  arena_t<Eigen::Matrix<var, -1, -1>> eigenvecs = solver.eigenvectors();
  auto eigenvals_dbl = to_arena(solver.eigenvalues());
  arena_t<Eigen::Matrix<var, -1, 1>> eigenvals = solver.eigenvalues();

  reverse_pass_callback([arena_m, eigenvecs, eigenvals, eigenvals_dbl]() mutable {
    const auto p = arena_m.val().cols();
    Eigen::MatrixXd f = (1
                         / (eigenvals_dbl.rowwise().replicate(p).transpose()
                            - eigenvals_dbl.rowwise().replicate(p))
                               .array());
    f.diagonal().setZero();
    // fused inner matrix: eigenvector term (elementwise) + eigenvalue term
    // (diagonal)
    Eigen::MatrixXd inner = f.cwiseProduct(
        eigenvecs.val_op().transpose() * eigenvecs.adj_op());
    inner.diagonal() += eigenvals.adj_op();
    arena_m.adj() += eigenvecs.val_op() * inner * eigenvecs.val_op().transpose();
  });

  w32_eigh_result_var out;
  out.vectors = eigenvecs;  // Matrix<var> copies sharing varis
  out.values = eigenvals;
  return out;
}

// ---- double input: ONE solver for both outputs ----
// (stock prim path: eigenvectors_sym runs a full solver, eigenvalues_sym runs
//  an EigenvaluesOnly solver; here one full solver serves both)
template <typename T, require_not_st_var<T>* = nullptr,
          require_eigen_t<T>* = nullptr>
inline w32_eigh_result_dbl w32_eigh(const T& m) {
  if (m.size() == 0) {
    return w32_eigh_result_dbl{};
  }
  check_symmetric("w32_eigh", "m", m);
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> solver(m);
  w32_eigh_result_dbl out;
  out.vectors = solver.eigenvectors();
  out.values = solver.eigenvalues();
  return out;
}

}  // namespace math
}  // namespace stan

#endif  // W32_EIGH_COMBINED_HPP
