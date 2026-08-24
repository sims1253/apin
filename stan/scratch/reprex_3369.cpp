#include <stan/math.hpp>
#include <iostream>
int main() {
  using stan::math::var;
  const int N = 100000;
  Eigen::VectorXi y(N); y.setConstant(1);
  Eigen::MatrixXd x = Eigen::MatrixXd::Ones(N, 1);
  Eigen::Matrix<var, -1, 1> alpha = Eigen::Matrix<var, -1, 1>::Zero(N);
  Eigen::Matrix<var, -1, 1> beta(1);  beta(0) = 25.0;
  var lp = stan::math::bernoulli_logit_glm_lpmf(y, x, alpha, beta);
  lp.grad();
  std::cout.precision(17);
  std::cout << "lp            = " << lp.val() << "\n"
            << "beta adjoint  = " << beta(0).adj() << "\n"
            << "expected sign = +" << N * std::exp(-25.0) << " (N * exp(-25))\n"
            << "alpha adjoint = " << alpha(0).adj() << " (expected +" << std::exp(-25.0) << ", one observation per intercept)\n";
  return 0;
}
