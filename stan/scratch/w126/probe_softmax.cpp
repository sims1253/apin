// W-126 probe 5: does softmax<VectorXd> differ bitwise from softmax<val-view>?
// Also: does the exp path (packet pexp vs scalar std::exp) explain it?
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
  int diffs = 0, total = 0;
  for (int trial = 0; trial < 200; ++trial) {
    int K = 3 + (trial % 7);
    Eigen::VectorXd c(K);
    for (int k = 0; k < K; ++k) c[k] = U(rng);
    Eigen::VectorXd p_dense = softmax(c);                 // my hand instantiation
    Eigen::Matrix<var, -1, 1> cvar(K);
    for (int k = 0; k < K; ++k) cvar[k] = var(c[k]);
    Eigen::VectorXd p_view = softmax(cvar.val());         // stock instantiation
    ++total;
    for (int k = 0; k < K; ++k) {
      if (p_dense[k] != p_view[k]) {
        ++diffs;
        if (diffs <= 5)
          std::cout << std::setprecision(17) << "K=" << K << " k=" << k
                    << " dense=" << p_dense[k] << " view=" << p_view[k] << std::endl;
      }
    }
    // also compare against a manual glibc-exp + sequential-sum spelling
    double mx = c.maxCoeff();
    double S = 0;
    for (int k = 0; k < K; ++k) S += std::exp(c[k] - mx);
    for (int k = 0; k < K; ++k) {
      if (p_view[k] != std::exp(c[k] - mx) / S && diffs <= 8)
        std::cout << "  manual-glibc differs from view at k=" << k << std::endl;
    }
    stan::math::recover_memory();
  }
  std::cout << "softmax dense-vs-view: " << diffs << " differing elements / " << total
            << " trials" << std::endl;
  return 0;
}
