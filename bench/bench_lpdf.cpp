// Hypotheses: (a) validity-check share in hot lpdf; (b) operands_and_partials /
// make_partials_propagator construction cost; (c) vectorized sm::normal_lpdf vs
// sm::normal_id_glm_lpdf vs hand-written gradient (checks+partials stripped).
#include <stan/math.hpp>
#include <chrono>
#include <cstdio>
#include <vector>
#include <random>

namespace sm = stan::math;
using sm::var;
using std::chrono::steady_clock;
static double now_s(steady_clock::time_point t0) {
  return std::chrono::duration<double>(steady_clock::now() - t0).count();
}

int main() {
  std::mt19937 rng(42);
  const int N = 12573;                       // radon_all-sized likelihood
  Eigen::VectorXd y(N), mu_v(N);
  for (int i = 0; i < N; i++) { y(i) = std::normal_distribution<>(0,1)(rng); mu_v(i) = 0.01*i; }
  double sigma = 1.3, mu0 = 0.7;
  const int REPS = 2000;

  // ---- (1) double-mode: sm::normal_lpdf value (checks on) ----
  { double s = 0; auto t0 = steady_clock::now();
    for (int r = 0; r < REPS; r++) s += sm::normal_lpdf(y, mu_v, sigma);
    printf("sm::normal_lpdf<double>            : %8.1f ns/call\n", now_s(t0)/REPS*1e9); (void)s; }

  // ---- (2) var-mode: sm::normal_lpdf value+grad via stan::math ----
  { double s = 0; auto t0 = steady_clock::now();
    for (int r = 0; r < REPS; r++) {
      var mu_vv(mu0); var sig_v(sigma);
      Eigen::Matrix<var, -1, 1> mu_vv2 = mu_v.cast<var>();
      // scalar shift param: emulate radon: mu[n]=alpha; here constant vector + sigma param
      var lp = sm::normal_lpdf(y, mu_vv2, sig_v);
      lp.grad();
      s += lp.val();
      sm::recover_memory();
    }
    printf("sm::normal_lpdf<var>+grad (vec mu) : %8.1f ns/call\n", now_s(t0)/REPS*1e9); (void)s; }

  // ---- (3) hand-written no-check gradient of same density ----
  { double s = 0; auto t0 = steady_clock::now();
    for (int r = 0; r < REPS; r++) {
      double sigma = 1.3 + 1e-9 * r;   // defeat loop-invariant elimination
      // lp = -N/2 log(2 pi s^2) - sum((y-mu)^2)/(2 s^2); d/ds only (mu const)
      double inv2 = 1.0/(2*sigma*sigma);
      double ss = (y - mu_v).squaredNorm();
      double lp = -0.5*N*std::log(2*M_PI*sigma*sigma) - ss*inv2;
      double dlp_dsigma = -N/sigma + ss/(sigma*sigma*sigma);
      s += lp + dlp_dsigma;
    }
    printf("hand no-check d/dsigma         : %8.1f ns/call (s=%.6g)\n", now_s(t0)/REPS*1e9, s); }

  // ---- (4) sm::normal_id_glm_lpdf (diamonds likelihood), var mode ----
  const int K = 25;                          // diamonds X cols
  Eigen::MatrixXd X(N, K);
  for (int i = 0; i < N; i++) for (int k = 0; k < K; k++) X(i,k) = std::normal_distribution<>(0,1)(rng);
  Eigen::VectorXd beta_d(K); for (int k = 0; k < K; k++) beta_d(k) = 0.1*k;
  { double s = 0; auto t0 = steady_clock::now();
    const int R2 = REPS/2;
    for (int r = 0; r < R2; r++) {
      Eigen::Matrix<var, -1, 1> beta = beta_d.cast<var>();
      var alpha(0.5), sig(sigma);
      var lp = sm::normal_id_glm_lpdf(y, X, alpha, beta, sig);
      lp.grad();
      s += lp.val();
      sm::recover_memory();
    }
    printf("sm::normal_id_glm_lpdf<var>+grad   : %8.1f ns/call\n", now_s(t0)/(REPS/2)*1e9); (void)s; }

  // ---- (5) same GLM, plain double ----
  { double s = 0; auto t0 = steady_clock::now();
    for (int r = 0; r < REPS; r++) s += sm::normal_id_glm_lpdf(y, X, 0.5, beta_d, sigma);
    printf("sm::normal_id_glm_lpdf<double>     : %8.1f ns/call\n", now_s(t0)/REPS*1e9); (void)s; }
  return 0;
}
