// W-53: exact hier_2pl eltwise line at N=19200, 50 wild points (same RNG
// scheme as gate_parity), wall per call + grad/sum check. Stock vs patched
// via include-tree swap by the build script.
#include <stan/math/rev.hpp>
#include <Eigen/Dense>
#include <cstdio>
#include <chrono>
#include <random>

using namespace stan::math;
using Eigen::Matrix;
using Eigen::VectorXd;

int main() {
  const int J = 600, I = 32, N = J * I;
  std::mt19937_64 rng(20260822);
  std::normal_distribution<double> norm(0.0, 1.0);
  VectorXd alpha_d = VectorXd::NullaryExpr(I, [&](int){ return 0.5 * norm(rng); });
  VectorXd theta_d = VectorXd::NullaryExpr(J, [&](int){ return 0.5 * norm(rng); });
  VectorXd beta_d  = VectorXd::NullaryExpr(I, [&](int){ return 0.5 * norm(rng); });
  Matrix<var, -1, 1> alpha = alpha_d, theta = theta_d, beta = beta_d;
  // gathered expressions exactly like the model line:
  Eigen::ArrayXi ii(N), jj(N);
  for (int j = 0; j < J; ++j)
    for (int i = 0; i < I; ++i) { ii(j * I + i) = i; jj(j * I + i) = j; }
  Matrix<var, -1, 1> a_g(N), t_g(N), b_g(N);
  for (int n = 0; n < N; ++n) { a_g[n] = alpha[ii[n]]; t_g[n] = theta[jj[n]]; b_g[n] = beta[ii[n]]; }
  double sink = 0;
  for (int rep = 0; rep < 3; ++rep) {
    auto t0 = std::chrono::steady_clock::now();
    for (int it = 0; it < 50; ++it) {
      var lp = elt_multiply(a_g, subtract(t_g, b_g)).sum();
      grad(lp.vi_);
      sink += lp.val();
      recover_memory();
    }
    auto t1 = std::chrono::steady_clock::now();
    printf("rep %d: %.1f us/call (sink %.6f)\n", rep,
           std::chrono::duration<double, std::micro>(t1 - t0).count() / 50, sink);
  }
  return 0;
}
