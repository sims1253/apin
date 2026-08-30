// W-126 STEP ZERO probe: pin the exact type resolution + adjoint mechanics of the
// generated pcm body on the family stack, BEFORE writing the primitive.
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

template <typename T>
struct TN;
template <typename T>
void tn(const char* label, const T&) {
  std::cout << label << ": " << __PRETTY_FUNCTION__ << std::endl;
}
// print the deduced type short-form
template <typename T>
const char* S();
template <>
const char* S<Eigen::Matrix<var, -1, 1, 0, -1, 1>>() { return "Matrix<var,-1,1>"; }

int main() {
  // one observation, m=3 categories -> K=4
  int m = 3;
  Eigen::Matrix<var, -1, 1> theta(1), alpha(1);
  theta[0] = var(0.7);
  alpha[0] = var(1.3);
  Eigen::Matrix<var, -1, 1> beta(m);
  beta.setConstant(var(0.0));
  std::vector<double> bv{0.11, -0.22, 0.33};
  for (int k = 0; k < m; ++k) beta[k] = var(bv[k]);

  var t = theta.coeff(0) * alpha.coeff(0);
  tn("var*var", t);
  auto u = subtract(t, beta);
  tn("subtract(var, Matrix<var>)", u);
  auto un = append_row(rep_vector(0.0, 1), u);
  tn("append_row(VectorXd, u)", un);
  auto cs = cumulative_sum(un);
  tn("cumulative_sum(un)", cs);
  auto p = softmax(cs);
  tn("softmax(cs)", p);
  Eigen::Matrix<var, -1, 1> probs(p.rows());
  stan::model::assign(probs, p, "assigning variable probs");
  tn("probs (assigned)", probs);
  var lp = categorical_lpmf<false>(2, probs);
  tn("lp", lp);
  std::cout << std::setprecision(17) << "lp val = " << lp.val() << std::endl;

  // ---- hand double-space reference of the VALUE path ----
  double tv = 0.7 * 1.3;
  Eigen::VectorXd c(m + 1);
  c[0] = 0.0;
  for (int k = 0; k < m; ++k) c[k + 1] = c[k] + (tv - bv[k]);
  Eigen::VectorXd pval = softmax(c);
  double lp_ref = std::log(pval[1]);  // y+1 = 2 -> index 1
  std::cout << "lp_ref      = " << lp_ref << std::endl;
  std::cout << (lp.val() == lp_ref ? "VALUE-PATH-MATCHES-HAND" : "VALUE-PATH-DIFFERS")
            << std::endl;

  // ---- hand backward reference (my planned primitive adjoint arithmetic) ----
  // e = 1 (seed adjoint), g = e / p_y (division per rev log)
  // dot = p.dot(res_adj) with res_adj = g at y else 0
  // adj_c = p.array() * (res_adj.array() - dot)
  // adj_u_k = adj_c_k ; adj_t = sum_k adj_u_k sequential ascending (subtract chain)
  // theta_j += adj_t * alpha_val ; alpha_i += adj_t * theta_val ; beta_k -= adj_u_k
  grad(lp.vi_);
  double e = 1.0;
  Eigen::VectorXd res_adj = Eigen::VectorXd::Zero(m + 1);
  res_adj[1] = e / pval[1];
  double dot = pval.dot(res_adj);
  Eigen::VectorXd adj_c = pval.array() * (res_adj.array() - dot);
  double adj_t = 0.0;
  for (int k = 0; k < m; ++k) adj_t += adj_c[k + 1];  // ascending sequential
  std::cout << std::setprecision(17);
  std::cout << "hand: adj_theta=" << adj_t * 1.3 << " adj_alpha=" << adj_t * 0.7 << std::endl;
  std::cout << "real: adj_theta=" << theta[0].adj() << " adj_alpha=" << alpha[0].adj()
            << std::endl;
  for (int k = 0; k < m; ++k)
    std::cout << "beta[" << k << "] real=" << beta[k].adj() << " hand=" << -adj_c[k + 1]
              << (beta[k].adj() == -adj_c[k + 1] ? "  OK" : "  DIFF") << std::endl;
  bool ok = (adj_t * 1.3 == theta[0].adj()) && (adj_t * 0.7 == alpha[0].adj());
  std::cout << (ok ? "ADJOINT-PATH-MATCHES-HAND" : "ADJOINT-PATH-DIFFERS") << std::endl;
  return 0;
}
