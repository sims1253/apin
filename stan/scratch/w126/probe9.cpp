// W-126 probe 9 (CORRECT include discipline: bundle math + ONLY our header via inc/):
// does prim softmax over a val-view of a var matrix == the full rev softmax path,
// on both stacks, vs manual-scalar and dense?
#include <stan/math/rev.hpp>
#include <stan/math/rev/prob/pcm_lpdf_gathered.hpp>
#include <stan/math/rev/fun/softmax.hpp>
#include <stan/math/rev/fun/cumulative_sum.hpp>
#include <stan/math/rev/fun/append_row.hpp>
#include <stan/math/rev/core/operator_subtraction.hpp>
#include <iostream>
#include <random>

using namespace stan;
using namespace stan::math;

int main() {
  std::mt19937 rng(11);
  std::uniform_real_distribution<double> U(-3.0, 3.0);
  int rev_vs_mview = 0, rev_vs_arena = 0, rev_vs_man = 0, rev_vs_dense = 0;
  int total = 0;
  for (int trial = 0; trial < 500; ++trial) {
    int K = 3 + (trial % 7);
    Eigen::VectorXd c(K);
    for (int k = 0; k < K; ++k) c[k] = U(rng);
    // (a) full rev softmax path (what the model runs)
    Eigen::Matrix<var, -1, 1> cs(K);
    for (int k = 0; k < K; ++k) cs[k] = var(c[k]);
    auto ps = softmax(cs);
    Eigen::VectorXd p_rev(K);
    for (int k = 0; k < K; ++k) p_rev[k] = ps.coeff(k).val();
    // (b) prim softmax over val-view of a Matrix<var> lvalue
    Eigen::Matrix<var, -1, 1> cm(K);
    for (int k = 0; k < K; ++k) cm[k] = var(c[k]);
    Eigen::VectorXd p_mview = softmax(cm.val());
    // (c) prim softmax over val-view of an arena_matrix<Matrix<var>>
    arena_matrix<Eigen::Matrix<var, -1, 1>> ca(K);
    for (int k = 0; k < K; ++k) ca.coeffRef(k) = var(c[k]);
    Eigen::VectorXd p_arena = softmax(ca.val());
    // (d) dense
    Eigen::VectorXd cd = c;
    Eigen::VectorXd p_dense = softmax(cd);
    // (e) manual scalar
    double mx = c[0];
    for (int k = 1; k < K; ++k) mx = std::max(mx, c[k]);
    double S = 0.0;
    for (int k = 0; k < K; ++k) S = S + std::exp(c[k] - mx);
    Eigen::VectorXd p_man(K);
    for (int k = 0; k < K; ++k) p_man[k] = std::exp(c[k] - mx) / S;
    ++total;
    for (int k = 0; k < K; ++k) {
      if (p_rev[k] != p_mview[k]) ++rev_vs_mview;
      if (p_rev[k] != p_arena[k]) ++rev_vs_arena;
      if (p_rev[k] != p_man[k]) ++rev_vs_man;
      if (p_rev[k] != p_dense[k]) ++rev_vs_dense;
    }
    stan::math::recover_memory();
  }
  std::cout << "trials=" << total << "  rev-vs-MatrixView=" << rev_vs_mview
            << "  rev-vs-ArenaView=" << rev_vs_arena << "  rev-vs-manual="
            << rev_vs_man << "  rev-vs-dense=" << rev_vs_dense << std::endl;
  return 0;
}
