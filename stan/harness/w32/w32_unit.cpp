// W-32 unit validation of the fused combined eigendecomposition adjoint.
//
// phi(V, w) = sum(R . V) + c^T w  (R random matrix, c random vector)
// Compare d phi/d A from:
//   (1) stock two-call composition: eigenvectors_sym + eigenvalues_sym
//   (2) w32_eigh combined helper
//   (3) central finite differences on the double phi
// on well-conditioned symmetric A (distinct, well-separated eigenvalues).
#include <stan/model/model_header.hpp>
#include "w32_eigh.hpp"
#include <iomanip>
#include <iostream>
#include <random>

using Eigen::MatrixXd;
using Eigen::VectorXd;

static MatrixXd random_symmetric_wellcond(std::mt19937_64& rng, int n) {
  std::normal_distribution<double> nd(0.0, 1.0);
  MatrixXd M(n, n);
  for (int i = 0; i < n; i++)
    for (int j = 0; j < n; j++) M(i, j) = nd(rng);
  Eigen::HouseholderQR<MatrixXd> qr(M);
  MatrixXd Q = qr.householderQ();
  VectorXd w(n);
  for (int i = 0; i < n; i++) w(i) = 1.0 + 0.7 * i + 0.1 * nd(rng);  // gaps >= ~0.6
  return Q * w.asDiagonal() * Q.transpose();
}

static double phi_dbl(const MatrixXd& A, const MatrixXd& R, const VectorXd& c) {
  Eigen::SelfAdjointEigenSolver<MatrixXd> es(A);
  return (R.array() * es.eigenvectors().array()).sum() + c.dot(es.eigenvalues());
}

int main() {
  std::mt19937_64 rng(20260822);
  std::normal_distribution<double> nd(0.0, 1.0);
  int failures = 0;

  for (int trial = 0; trial < 5; trial++) {
    int n = 30;
    MatrixXd A = random_symmetric_wellcond(rng, n);
    MatrixXd R(n, n);
    for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) R(i, j) = nd(rng);
    VectorXd c(n);
    for (int i = 0; i < n; i++) c(i) = nd(rng);

    // (1) stock two-call
    MatrixXd g_stock = MatrixXd::Zero(n, n);
    {
      Eigen::Matrix<stan::math::var, -1, -1> Av(A);
      auto Vs = stan::math::eigenvectors_sym(Av);
      auto ws = stan::math::eigenvalues_sym(Av);
      stan::math::var phi = (R.cast<stan::math::var>().array() * Vs.array()).sum()
                            + c.cast<stan::math::var>().dot(ws);
      phi.grad();
      for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) g_stock(i, j) = Av(i, j).adj();
      stan::math::recover_memory();
    }

    // (2) combined w32_eigh
    MatrixXd g_comb = MatrixXd::Zero(n, n);
    {
      Eigen::Matrix<stan::math::var, -1, -1> Av(A);
      auto res = stan::math::w32_eigh(Av);
      stan::math::var phi = (R.cast<stan::math::var>().array() * res.vectors.array()).sum()
                            + c.cast<stan::math::var>().dot(res.values);
      phi.grad();
      for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) g_comb(i, j) = Av(i, j).adj();
      stan::math::recover_memory();
    }

    // (3) central FD along symmetric directions S = E_ij + E_ji:
    // dphi/dt = g_ij + g_ji (t perturbs BOTH entries by t). For i == j the
    // code below adds h twice to the same entry (S = 2 E_ii), so scale by 2.
    MatrixXd g_fd = MatrixXd::Zero(n, n);
    for (int i = 0; i < n; i++) {
      for (int j = i; j < n; j++) {
        double h = 1e-6;
        MatrixXd Ap = A, Am = A;
        Ap(i, j) += h; Ap(j, i) += h;
        Am(i, j) -= h; Am(j, i) -= h;
        double d = (phi_dbl(Ap, R, c) - phi_dbl(Am, R, c)) / (2 * h);
        g_fd(i, j) = g_fd(j, i) = (i == j) ? d / 2 : d / 2;  // symmetrized adjoint
      }
    }

    // stan's eigenvector adjoint V (F.(V^T G)) V^T is NOT symmetric (F is
    // antisymmetric); its antisymmetric part is inert for symmetric dA, so
    // the honest FD comparison is against the symmetrized adjoint.
    MatrixXd g_stock_sym = 0.5 * (g_stock + g_stock.transpose());
    MatrixXd g_comb_sym = 0.5 * (g_comb + g_comb.transpose());

    double s_vs_c = (g_stock - g_comb).cwiseAbs().maxCoeff();
    double ss_vs_f = (g_stock_sym - g_fd).cwiseAbs().maxCoeff();
    double cs_vs_f = (g_comb_sym - g_fd).cwiseAbs().maxCoeff();
    double asym = (g_stock - g_stock_sym).cwiseAbs().maxCoeff();
    double scale = g_stock.cwiseAbs().maxCoeff();
    std::cout << std::scientific << std::setprecision(3)
              << "trial " << trial << ": |g|max=" << scale
              << "  stock-vs-comb " << s_vs_c << " (rel " << s_vs_c / scale << ")"
              << "  sym(stock)-vs-fd " << ss_vs_f << " (rel " << ss_vs_f / scale << ")"
              << "  sym(comb)-vs-fd " << cs_vs_f << " (rel " << cs_vs_f / scale << ")"
              << "  [asym part " << asym << "]\n";
    if (s_vs_c / scale > 1e-12 || ss_vs_f / scale > 1e-6 || cs_vs_f / scale > 1e-6)
      failures++;
  }
  std::cout << (failures ? "UNIT TEST: FAIL" : "UNIT TEST: PASS")
            << " (" << failures << " failures)\n";
  return failures ? 1 : 0;
}
