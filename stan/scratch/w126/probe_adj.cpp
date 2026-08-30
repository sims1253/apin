// W-126 STEP ZERO probe 2: dump every intermediate adjoint of the pcm graph +
// finite-difference reference, to pin the adjoint arithmetic exactly.
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

using namespace stan;
using namespace stan::math;

int main() {
  int m = 3;
  double th_v = 0.7, al_v = 1.3;
  std::vector<double> bv{0.11, -0.22, 0.33};
  auto build = [&](auto f) {
    var theta = var(th_v), alpha = var(al_v);
    Eigen::Matrix<var, -1, 1> beta(m);
    for (int k = 0; k < m; ++k) beta[k] = var(bv[k]);
    var t = theta * alpha;
    Eigen::Matrix<var, -1, 1> u = subtract(t, beta);
    Eigen::Matrix<var, -1, 1> un = append_row(rep_vector(0.0, 1), u);
    Eigen::Matrix<var, -1, 1> cs = cumulative_sum(un);
    auto p = softmax(cs);
    Eigen::Matrix<var, -1, 1> probs(p.rows());
    stan::model::assign(probs, p, "assigning variable probs");
    var lp = categorical_lpmf<false>(2, probs);
    return f(lp, theta, alpha, beta, t, u, un, cs, probs);
  };

  // 1) dump adjoints
  build([&](var lp, var theta, var alpha, Eigen::Matrix<var, -1, 1>& beta, var t,
            Eigen::Matrix<var, -1, 1>& u, Eigen::Matrix<var, -1, 1>& un,
            Eigen::Matrix<var, -1, 1>& cs, Eigen::Matrix<var, -1, 1>& probs) {
    grad(lp.vi_);
    std::cout << std::setprecision(17);
    std::cout << "adj: theta=" << theta.adj() << " alpha=" << alpha.adj()
              << " t=" << t.adj() << std::endl;
    for (int k = 0; k < m; ++k)
      std::cout << "  beta[" << k << "]=" << beta[k].adj() << "  u[" << k << "]=" << u[k].adj()
                << "  un[" << k + 1 << "]=" << un[k + 1].adj() << "  cs[" << k + 1 << "]="
                << cs[k + 1].adj() << "  p[" << k + 1 << "]=" << probs[k + 1].adj() << std::endl;
    std::cout << "  un[0]=" << un[0].adj() << " cs[0]=" << cs[0].adj() << " p[0]=" << probs[0].adj()
              << std::endl;
    return 0;
  });

  // 2) finite-difference reference (central, h=1e-6, on theta and beta[0])
  auto lpval = [&](double th, double al, std::vector<double> b) {
    double tv = th * al;
    Eigen::VectorXd c(m + 1);
    c[0] = 0.0;
    for (int k = 0; k < m; ++k) c[k + 1] = c[k] + (tv - b[k]);
    Eigen::VectorXd p = softmax(c);
    return std::log(p[1]);
  };
  double h = 1e-6;
  std::cout << "FD d/dtheta = " << (lpval(th_v + h, al_v, bv) - lpval(th_v - h, al_v, bv)) / (2 * h)
            << std::endl;
  std::cout << "FD d/dbeta0 = "
            << (lpval(th_v, al_v, {bv[0] + h, bv[1], bv[2]}) -
                lpval(th_v, al_v, {bv[0] - h, bv[1], bv[2]})) / (2 * h)
            << std::endl;
  return 0;
}
