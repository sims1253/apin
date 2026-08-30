// W-126 smoke diag: per-observation term values, stock vs prim, one failing case.
#include <stan/math/rev.hpp>
#include <stan/math/rev/prob/pcm_lpdf_gathered.hpp>
#include <stan/math/rev/fun/softmax.hpp>
#include <stan/math/rev/fun/cumulative_sum.hpp>
#include <stan/math/rev/fun/append_row.hpp>
#include <stan/math/rev/core/operator_subtraction.hpp>
#include <stan/math/prim/fun/segment.hpp>
#include <stan/model/indexing/index.hpp>
#include <stan/model/indexing/rvalue.hpp>
#include <stan/model/indexing/assign.hpp>
#include <stan/model/indexing/access_helpers.hpp>
#include <iostream>
#include <random>

using namespace stan;
using namespace stan::math;

template <typename T>
void tn(const char* label, const T&) {
  std::cout << label << ": " << __PRETTY_FUNCTION__ << std::endl;
}

int main() {
  // reproduce smoke trial 2 exactly
  std::mt19937 rng(42);
  std::uniform_real_distribution<double> U(-1.5, 1.5);
  int trial = 2;
  int I = 2 + (trial % 4), J = 2 + (trial % 5), N = 1 + (trial % 9);
  std::vector<int> m(I), pos(I);
  int tot = 0;
  for (int i = 0; i < I; ++i) {
    m[i] = 1 + (trial + i) % 5;
    pos[i] = tot + 1;
    tot += m[i];
  }
  std::vector<int> y(N), jj(N), ii(N);
  for (int n = 0; n < N; ++n) {
    jj[n] = 1 + (n * 7 + trial) % J;
    ii[n] = 1 + (n * 3 + trial) % I;
    y[n] = (n + trial) % m[ii[n] - 1];
  }
  Eigen::Matrix<var, -1, 1> theta(J), alpha(I), beta(tot);
  for (int j = 0; j < J; ++j) theta[j] = var(U(rng));
  for (int i = 0; i < I; ++i) alpha[i] = var(U(rng));
  for (int k = 0; k < tot; ++k) beta[k] = var(U(rng));
  std::vector<double> th_v(J), al_v(I), b_v(tot);
  for (int j = 0; j < J; ++j) th_v[j] = U(rng);
  for (int i = 0; i < I; ++i) al_v[i] = U(rng);
  for (int k = 0; k < tot; ++k) b_v[k] = U(rng);
  std::cout << "N=" << N << " I=" << I << " J=" << J << " tot=" << tot << std::endl;
  for (int n = 0; n < N; ++n)
    std::cout << "obs " << n << ": y=" << y[n] << " jj=" << jj[n] << " ii=" << ii[n]
              << " m=" << m[ii[n] - 1] << std::endl;

  // stock terms
  start_nested();
  Eigen::Matrix<var, -1, 1> th1(J), al1(I), b1(tot);
  for (int j = 0; j < J; ++j) th1[j] = var(th_v[j]);
  for (int i = 0; i < I; ++i) al1[i] = var(al_v[i]);
  for (int k = 0; k < tot; ++k) b1[k] = var(b_v[k]);
  std::vector<double> stock_terms;
  for (int n = 0; n < N; ++n) {
    var th = stan::model::rvalue(th1, "theta", stan::model::index_uni(jj[n]));
    var al = stan::model::rvalue(al1, "alpha", stan::model::index_uni(ii[n]));
    auto seg = stan::math::segment(b1, pos[ii[n] - 1], m[ii[n] - 1]);
    var t = th * al;
    Eigen::Matrix<var, -1, 1> unsummed =
        append_row(rep_vector(0.0, 1), subtract(t, to_ref(seg)));
    auto cs_ = cumulative_sum(unsummed);
    if (n == 1) tn("cumsum(unsummed)", cs_);
    auto p_ = softmax(cs_);
    if (n == 1) tn("softmax(cs)", p_);
    Eigen::Matrix<var, -1, 1> probs = p_;
    var lp = categorical_lpmf<false>(y[n] + 1, probs);
    stock_terms.push_back(lp.val());
  }
  recover_memory_nested();

  // prim terms
  start_nested();
  Eigen::Matrix<var, -1, 1> th2(J), al2(I), b2(tot);
  for (int j = 0; j < J; ++j) th2[j] = var(th_v[j]);
  for (int i = 0; i < I; ++i) al2[i] = var(al_v[i]);
  for (int k = 0; k < tot; ++k) b2[k] = var(b_v[k]);
  auto terms = pcm_lpdf_gathered<false>(y, th2, jj, al2, ii, b2, pos, m);
  recover_memory_nested();

  std::cout << std::setprecision(17);
  for (int n = 0; n < N; ++n) {
    std::cout << "term " << n << ": stock=" << stock_terms[n]
              << " prim=" << terms[n].val()
              << (stock_terms[n] == terms[n].val() ? " OK" : " DIFF") << std::endl;
    if (stock_terms[n] != terms[n].val()) {
      int item = ii[n] - 1;
      int K = m[item] + 1;
      double tv = th_v[jj[n] - 1] * al_v[item];
      Eigen::VectorXd c(K);
      c[0] = 0.0;
      for (int k = 1; k < K; ++k)
        c[k] = c[k - 1] + (tv - b_v[pos[item] + k - 2]);
      double mx = c[0];
      for (int k = 1; k < K; ++k) mx = std::max(mx, c[k]);
      double S = 0.0;
      for (int k = 0; k < K; ++k) S = S + std::exp(c[k] - mx);
      Eigen::VectorXd pm(K), pd = softmax(c);
      for (int k = 0; k < K; ++k) pm[k] = std::exp(c[k] - mx) / S;
      std::cout << "  manual lp = " << std::log(pm[y[n]])
                << "  dense lp = " << std::log(pd[y[n]]) << std::endl;
      std::cout << "  th=" << th_v[jj[n] - 1] << " al=" << al_v[item]
                << " t=" << tv << std::endl;
      for (int k = 0; k < K; ++k)
        std::cout << "  c[" << k << "]=" << c[k] << "  p_man=" << pm[k]
                  << "  p_dense=" << pd[k] << std::endl;
    }
  }
  return 0;
}
