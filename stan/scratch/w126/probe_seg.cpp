// W-126 probe 7: the segment path's types and the failing term isolated.
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
#include <iostream>

using namespace stan;
using namespace stan::math;

template <typename T>
void tn(const char* label, const T&) {
  std::cout << label << ": " << __PRETTY_FUNCTION__ << std::endl;
}

int main() {
  // failing obs: y=3 (0-based), K=5, item beta slice of a big vector
  const int tot = 13, start1 = 5, mlen = 4;  // 1-based segment (5,4)
  std::vector<double> bv(tot);
  for (int k = 0; k < tot; ++k) bv[k] = 0.1 * (k + 1) - 0.7;
  double th = 0.31, al = -0.47;
  // regenerate the smoke RNG values for th/al of obs1? -- use fixed values;
  // the mechanism is layout-dependent, not value-dependent.
  Eigen::Matrix<var, -1, 1> b1(tot);
  for (int k = 0; k < tot; ++k) b1[k] = var(bv[k]);
  var t = var(th) * var(al);
  auto seg = stan::math::segment(b1, start1, mlen);
  tn("segment(b1,...)", seg);
  auto seg_ref = to_ref(seg);
  tn("to_ref(seg)", seg_ref);
  auto u = subtract(t, seg_ref);
  tn("subtract(t, seg_ref)", u);
  auto un = append_row(rep_vector(0.0, 1), u);
  tn("append_row", un);
  auto cs = cumulative_sum(un);
  tn("cumulative_sum", cs);
  auto p = softmax(cs);
  tn("softmax", p);
  Eigen::Matrix<var, -1, 1> probs(p.rows());
  stan::model::assign(probs, p, "assign");
  var lp = categorical_lpmf<false>(3 + 1, probs);
  std::cout << std::setprecision(17) << "stock lp = " << lp.val() << std::endl;

  // manual scalar replica
  int K = mlen + 1;
  Eigen::VectorXd c(K);
  c[0] = 0.0;
  for (int k = 1; k < K; ++k) c[k] = c[k - 1] + (th * al - bv[start1 - 1 + k - 1]);
  double mx = c[0];
  for (int k = 1; k < K; ++k) mx = std::max(mx, c[k]);
  double S = 0.0;
  for (int k = 0; k < K; ++k) S = S + std::exp(c[k] - mx);
  Eigen::VectorXd pm(K);
  for (int k = 0; k < K; ++k) pm[k] = std::exp(c[k] - mx) / S;
  std::cout << "manual lp = " << std::log(pm[3]) << std::endl;
  // dense-instantiation softmax for comparison
  Eigen::VectorXd pd = softmax(c);
  std::cout << "dense-softmax lp = " << std::log(pd[3]) << std::endl;
  return 0;
}
