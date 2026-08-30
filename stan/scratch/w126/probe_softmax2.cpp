// W-126 probe 6: verify the manual SCALAR spelling == stock's view-instantiated
// softmax, bitwise, across K=3..9, and vs the dense instantiation (expected diff).
#include <stan/math/rev.hpp>
#include <stan/math/prim/fun/softmax.hpp>
#include <iostream>
#include <iomanip>
#include <random>

using namespace stan;
using namespace stan::math;

int main() {
  std::mt19937 rng(7);
  std::uniform_real_distribution<double> U(-3.0, 3.0);
  int view_vs_manual = 0, view_vs_dense = 0, total = 0;
  for (int trial = 0; trial < 2000; ++trial) {
    int K = 3 + (trial % 7);
    Eigen::VectorXd c(K);
    for (int k = 0; k < K; ++k) c[k] = U(rng);
    Eigen::VectorXd p_dense = softmax(c);
    Eigen::Matrix<var, -1, 1> cvar(K);
    for (int k = 0; k < K; ++k) cvar[k] = var(c[k]);
    Eigen::VectorXd p_view = softmax(cvar.val());
    // manual SCALAR spelling of the stock (view) path
    double mx = c[0];
    for (int k = 1; k < K; ++k) mx = std::max(mx, c[k]);
    double S = 0.0;
    for (int k = 0; k < K; ++k) S = S + std::exp(c[k] - mx);
    Eigen::VectorXd p_man(K);
    for (int k = 0; k < K; ++k) p_man[k] = std::exp(c[k] - mx) / S;
    ++total;
    for (int k = 0; k < K; ++k) {
      if (p_view[k] != p_man[k]) ++view_vs_manual;
      if (p_view[k] != p_dense[k]) ++view_vs_dense;
    }
    stan::math::recover_memory();
  }
  std::cout << "trials=" << total << "  view-vs-manual diffs=" << view_vs_manual
            << "  view-vs-dense diffs=" << view_vs_dense << std::endl;
  return view_vs_manual != 0;
}
