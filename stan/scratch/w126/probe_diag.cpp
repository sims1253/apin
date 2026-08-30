// W-126 probe 4: one failing case, full forensic dump of stock vs hand chain.
#include <stan/math/rev.hpp>
#include <stan/math/prim/fun/softmax.hpp>
#include <stan/math/rev/fun/softmax.hpp>
#include <stan/math/rev/fun/cumulative_sum.hpp>
#include <stan/math/rev/fun/append_row.hpp>
#include <stan/math/rev/core/operator_subtraction.hpp>
#include <stan/model/indexing/index.hpp>
#include <stan/model/indexing/rvalue.hpp>
#include <stan/model/indexing/assign.hpp>
#include <stan/model/indexing/access_helpers.hpp>
#include <iostream>
#include <iomanip>
#include <random>

using namespace stan;
using namespace stan::math;

int main() {
  std::mt19937 rng(20260829);
  std::uniform_real_distribution<double> U(-2.0, 2.0);
  for (int trial = 0; trial <= 3; ++trial) {
    int m = 2 + (trial % 7);
    double th = U(rng), al = U(rng);
    std::vector<double> bv(m);
    for (auto& b : bv) b = U(rng);
    if (trial != 3) continue;
    int y = trial % m;
    std::cout << "case m=" << m << " y=" << y << " th=" << th << " al=" << al << std::endl;
    for (int k = 0; k < m; ++k) std::cout << "bv[" << k << "]=" << bv[k] << std::endl;

    var theta = var(th), alpha = var(al);
    Eigen::Matrix<var, -1, 1> beta(m);
    for (int k = 0; k < m; ++k) beta[k] = var(bv[k]);
    var t = theta * alpha;
    Eigen::Matrix<var, -1, 1> u = subtract(t, beta);
    Eigen::Matrix<var, -1, 1> un = append_row(rep_vector(0.0, 1), u);
    Eigen::Matrix<var, -1, 1> cs = cumulative_sum(un);
    auto p = softmax(cs);
    Eigen::Matrix<var, -1, 1> probs(p.rows());
    stan::model::assign(probs, p, "assigning variable probs");
    var lp = categorical_lpmf<false>(y + 1, probs);
    grad(lp.vi_);

    int K = m + 1;
    double tv = th * al;
    Eigen::VectorXd c(K);
    c[0] = 0.0;
    for (int k = 0; k < m; ++k) c[k + 1] = c[k] + (tv - bv[k]);
    Eigen::VectorXd pv = softmax(c);
    std::cout << std::setprecision(17);
    for (int k = 0; k < K; ++k)
      std::cout << "p[" << k << "] stock_val=" << probs[k].val() << " hand=" << pv[k]
                << (probs[k].val() == pv[k] ? " OK" : " DIFF") << "  adj=" << probs[k].adj()
                << std::endl;
    std::cout << "t adj=" << t.adj() << std::endl;
    for (int k = 0; k < m; ++k)
      std::cout << "u[" << k << "] adj=" << u[k].adj() << "  un[" << k + 1
                << "]=" << un[k + 1].adj() << "  cs[" << k + 1 << "]=" << cs[k + 1].adj()
                << std::endl;
    std::cout << "cs[0]=" << cs[0].adj() << " un[0]=" << un[0].adj() << std::endl;

    // hand chain pieces
    double e = 1.0;
    Eigen::VectorXd r = Eigen::VectorXd::Zero(K);
    r[y] = e / pv[y];
    double dot = pv.dot(r);
    double dot_seq = 0;
    for (int k = 0; k < K; ++k) dot_seq = dot_seq + pv[k] * r[k];
    std::cout << "dot=" << dot << " dot_seq=" << dot_seq << std::endl;
    Eigen::VectorXd A = pv.array() * (r.array() - dot);
    for (int k = 0; k < K; ++k)
      std::cout << "A[" << k << "]=" << A[k] << "  -cs_adj_suffix_diff="
                << (cs[k].adj() - (k + 1 < K ? cs[k + 1].adj() : 0.0)) << std::endl;
    return 0;
  }
  return 0;
}
