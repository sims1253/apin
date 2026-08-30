// W-126 STEP ZERO probe 3: corrected hand adjoint chain vs stock, bitwise,
// across m (K = m+1 in 3..9), y positions, and randomized values.
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

// hand replica of stock's per-observation value+adjoint arithmetic
struct Hand {
  double lp;
  double adj_theta, adj_alpha;
  std::vector<double> adj_beta;
};

Hand hand_pcm(int y, double th, double al, const std::vector<double>& bv, double e) {
  int m = bv.size();
  int K = m + 1;
  double t = th * al;
  Eigen::VectorXd c(K);
  c[0] = 0.0;
  for (int k = 0; k < m; ++k) c[k + 1] = c[k] + (t - bv[k]);  // u then cumsum
  // manual SCALAR spelling == stock's view-instantiated softmax (probe6-verified)
  double mx = c[0];
  for (int k = 1; k < K; ++k) mx = std::max(mx, c[k]);
  double S = 0.0;
  for (int k = 0; k < K; ++k) S = S + std::exp(c[k] - mx);
  Eigen::VectorXd p(K);
  for (int k = 0; k < K; ++k) p[k] = std::exp(c[k] - mx) / S;
  Hand h;
  h.lp = std::log(p[y]);   // categorical_lpmf(n=y+1) logs coeff(n-1) = p[y]
  // adjoint
  Eigen::VectorXd r = Eigen::VectorXd::Zero(K);
  r[y] = e / p[y];                          // division (rev log chain)
  double dot = p.dot(r);                   // dense dot
  Eigen::VectorXd A = p.array() * (r.array() - dot);
  std::vector<double> suf(K);
  suf[K - 1] = A[K - 1];
  for (int k = K - 2; k >= 0; --k) suf[k] = A[k] + suf[k + 1];  // right-nested relay
  double adj_t = suf[1];
  for (int k = 2; k < K; ++k) adj_t = adj_t + suf[k];  // ascending left-assoc
  h.adj_theta = th;  // placeholder, computed below
  h.adj_theta = adj_t * al;
  h.adj_alpha = adj_t * th;
  h.adj_beta.resize(m);
  for (int k = 0; k < m; ++k) h.adj_beta[k] = -suf[k + 1];
  return h;
}

int main() {
  std::mt19937 rng(20260829);
  std::uniform_real_distribution<double> U(-2.0, 2.0);
  int fails = 0, total = 0;
  for (int trial = 0; trial < 400; ++trial) {
    int m = 2 + (trial % 7);  // K = 3..9
    double th = U(rng), al = U(rng);
    std::vector<double> bv(m);
    for (auto& b : bv) b = U(rng);
    int y = trial % m;  // 0..m-1 (valid)
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
    Hand h = hand_pcm(y, th, al, bv, 1.0);
    ++total;
    bool ok = (lp.val() == h.lp) && (theta.adj() == h.adj_theta)
              && (alpha.adj() == h.adj_alpha);
    for (int k = 0; k < m && ok; ++k) ok = (beta[k].adj() == h.adj_beta[k]);
    if (!ok) {
      if (++fails <= 3) {
        std::cout << std::setprecision(17) << "FAIL m=" << m << " y=" << y
                  << " th=" << th << " al=" << al << " bv0=" << bv[0] << std::endl;
        std::cout << "  lp " << lp.val() << " vs " << h.lp << std::endl;
        std::cout << "  th " << theta.adj() << " vs " << h.adj_theta << std::endl;
        std::cout << "  al " << alpha.adj() << " vs " << h.adj_alpha << std::endl;
        for (int k = 0; k < m; ++k)
          std::cout << "  b" << k << " " << beta[k].adj() << " vs " << h.adj_beta[k]
                    << std::endl;
      }
    }
    stan::math::recover_memory();
  }
  std::cout << (fails == 0 ? "HAND-CHAIN-BITWISE-MATCH " : "MISMATCH ") << total
            << " trials, " << fails << " fails" << std::endl;
  return fails != 0;
}
