// W-126 probe 8: same c through four softmax paths; find which matches the
// rev softmax (smoke says rev == dense, probe5 said prim-view == manual).
#include <stan/math/rev.hpp>
#include <stan/math/prim/fun/softmax.hpp>
#include <stan/math/rev/fun/softmax.hpp>
#include <stan/math/rev/fun/cumulative_sum.hpp>
#include <stan/math/rev/fun/append_row.hpp>
#include <stan/math/rev/core/operator_subtraction.hpp>
#include <iostream>

using namespace stan;
using namespace stan::math;

int main() {
  // the failing obs 1 c vector (from smoke_diag)
  Eigen::VectorXd c(5);
  c << 0.0, 0.95904659396029357, -0.86871720078685277, -1.5597403778588137,
      -1.7171484285464214;

  // (a) direct prim softmax on a val-view of Matrix<var>
  Eigen::Matrix<var, -1, 1> cvar(5);
  for (int k = 0; k < 5; ++k) cvar[k] = var(c[k]);
  Eigen::VectorXd p_view = softmax(cvar.val());

  // (b) the FULL rev softmax on the same Matrix<var> values
  Eigen::Matrix<var, -1, 1> cs2 = cvar;
  auto ps = softmax(cs2);  // arena_matrix<Matrix<var>>
  Eigen::VectorXd p_rev(5);
  for (int k = 0; k < 5; ++k) p_rev[k] = ps.coeff(k).val();

  // (c) dense instantiation
  Eigen::VectorXd c3 = c;
  Eigen::VectorXd p_dense = softmax(c3);

  // (d) manual scalar
  double mx = c[0];
  for (int k = 1; k < 5; ++k) mx = std::max(mx, c[k]);
  double S = 0.0;
  for (int k = 0; k < 5; ++k) S = S + std::exp(c[k] - mx);
  Eigen::VectorXd p_man(5);
  for (int k = 0; k < 5; ++k) p_man[k] = std::exp(c[k] - mx) / S;

  std::cout << std::setprecision(17);
  for (int k = 0; k < 5; ++k)
    std::cout << "k=" << k << " view=" << p_view[k] << " rev=" << p_rev[k]
              << " dense=" << p_dense[k] << " man=" << p_man[k] << std::endl;
  return 0;
}
