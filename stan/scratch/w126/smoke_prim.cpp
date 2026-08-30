// W-126 smoke: primitive vs composed stock (the real generated expression),
// multi-observation, repeated indices, mixed layouts.
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
#include <stan/math/rev/fun/accumulator.hpp>
#include <iostream>
#include <random>

using namespace stan;
using namespace stan::math;

// stock composed path: EXACTLY the generated loop body
template <typename VecT, typename VecA, typename VecB>
double run_stock(const std::vector<int>& y, const VecT& theta,
                 const std::vector<int>& jj, const VecA& alpha,
                 const std::vector<int>& ii, const VecB& beta,
                 const std::vector<int>& pos, const std::vector<int>& m,
                 Eigen::VectorXd& g) {
  int N = y.size();
  // parameters packaged for gradient extraction
  // (theta/alpha/beta are passed as eigen var vectors; we record their varis)
  start_nested();
  accumulator<var> lp_accum;
  for (int n = 0; n < N; ++n) {
    var th = stan::model::rvalue(theta, "theta", stan::model::index_uni(jj[n]));
    var al = stan::model::rvalue(alpha, "alpha", stan::model::index_uni(ii[n]));
    auto seg = stan::math::segment(beta, pos[ii[n] - 1], m[ii[n] - 1]);
    lp_accum.add([&](var t_, const Eigen::Matrix<var, -1, 1>& b_) {
      Eigen::Matrix<var, -1, 1> unsummed =
          append_row(rep_vector(0.0, 1), subtract(t_, b_));
      Eigen::Matrix<var, -1, 1> probs =
          softmax(cumulative_sum(unsummed));
      return categorical_lpmf<false>(y[n] + 1, probs);
    }(th * al, to_ref(seg)));
  }
  var lp = lp_accum.sum();
  grad(lp.vi_);
  double lpv = lp.val();
  int J = theta.size(), I = alpha.size(), B = beta.size();
  g.resize(J + I + B);
  for (int j = 0; j < J; ++j) g[j] = theta.coeff(j).adj();
  for (int i = 0; i < I; ++i) g[J + i] = alpha.coeff(i).adj();
  for (int k = 0; k < B; ++k) g[J + I + k] = beta.coeff(k).adj();
  recover_memory_nested();
  return lpv;
}

template <typename VecT, typename VecA, typename VecB>
double run_prim(const std::vector<int>& y, const VecT& theta,
                const std::vector<int>& jj, const VecA& alpha,
                const std::vector<int>& ii, const VecB& beta,
                const std::vector<int>& pos, const std::vector<int>& m,
                Eigen::VectorXd& g) {
  int N = y.size();
  start_nested();
  accumulator<var> lp_accum;
  auto terms = pcm_lpdf_gathered<false>(y, theta, jj, alpha, ii, beta, pos, m);
  for (const auto& t : terms) lp_accum.add(t);
  var lp = lp_accum.sum();
  grad(lp.vi_);
  double lpv = lp.val();
  int J = theta.size(), I = alpha.size(), B = beta.size();
  g.resize(J + I + B);
  for (int j = 0; j < J; ++j) g[j] = theta.coeff(j).adj();
  for (int i = 0; i < I; ++i) g[J + i] = alpha.coeff(i).adj();
  for (int k = 0; k < B; ++k) g[J + I + k] = beta.coeff(k).adj();
  recover_memory_nested();
  return lpv;
}

int main() {
  std::mt19937 rng(42);
  std::uniform_real_distribution<double> U(-1.5, 1.5);
  int fails = 0, total = 0;
  for (int trial = 0; trial < 60; ++trial) {
    int I = 2 + (trial % 4), J = 2 + (trial % 5), N = 1 + (trial % 9);
    std::vector<int> m(I), pos(I);
    int tot = 0;
    for (int i = 0; i < I; ++i) {
      m[i] = 1 + (trial + i) % 5;  // K = 2..6
      pos[i] = tot + 1;
      tot += m[i];
    }
    std::vector<int> y(N), jj(N), ii(N);
    for (int n = 0; n < N; ++n) {
      jj[n] = 1 + (n * 7 + trial) % J;   // repeated indices
      ii[n] = 1 + (n * 3 + trial) % I;
      y[n] = (n + trial) % m[ii[n] - 1];  // 0..m-1
    }
    Eigen::Matrix<var, -1, 1> theta(J), alpha(I), beta(tot);
    for (int j = 0; j < J; ++j) theta[j] = var(U(rng));
    for (int i = 0; i < I; ++i) alpha[i] = var(U(rng));
    for (int k = 0; k < tot; ++k) beta[k] = var(U(rng));

    Eigen::VectorXd gs, gp;
    // NOTE: run both on identical parameter VALUES via separate nested scopes
    // -- rebuild the vars with the same RNG draws for each arm
    std::vector<double> th_v(J), al_v(I), b_v(tot);
    for (int j = 0; j < J; ++j) th_v[j] = U(rng);
    for (int i = 0; i < I; ++i) al_v[i] = U(rng);
    for (int k = 0; k < tot; ++k) b_v[k] = U(rng);

    Eigen::Matrix<var, -1, 1> th1(J), al1(I), b1(tot), th2(J), al2(I), b2(tot);
    for (int j = 0; j < J; ++j) { th1[j] = var(th_v[j]); th2[j] = var(th_v[j]); }
    for (int i = 0; i < I; ++i) { al1[i] = var(al_v[i]); al2[i] = var(al_v[i]); }
    for (int k = 0; k < tot; ++k) { b1[k] = var(b_v[k]); b2[k] = var(b_v[k]); }

    double lp1 = run_stock(y, th1, jj, al1, ii, b1, pos, m, gs);
    double lp2 = run_prim(y, th2, jj, al2, ii, b2, pos, m, gp);
    ++total;
    bool ok = (lp1 == lp2) && (gs.size() == gp.size());
    for (int k = 0; ok && k < gs.size(); ++k) ok = (gs[k] == gp[k]);
    if (!ok) {
      ++fails;
      if (fails <= 3) {
        std::cout << std::setprecision(17) << "FAIL trial " << trial
                  << " N=" << N << " I=" << I << " J=" << J << std::endl;
        std::cout << "  lp " << lp1 << " vs " << lp2 << std::endl;
        for (int k = 0; k < gs.size(); ++k)
          if (gs[k] != gp[k])
            std::cout << "  g[" << k << "] " << gs[k] << " vs " << gp[k]
                      << std::endl;
      }
    }
  }
  std::cout << (fails == 0 ? "SMOKE-PASS " : "SMOKE-FAIL ") << total
            << " trials, " << fails << " fails" << std::endl;
  return fails != 0;
}
