// W-40 unit driver: gradients of eigendecomposition functionals on the W-35
// cluster matrices + FD self-checks + well-separated random matrices.
// Modes:
//   cluster           — 9 W-35 matrices (Sigma1/Lambda pts 1,2,7,14 + control):
//                        phi_noninv = sum(W.*V) + c'w   (two-call pattern; basis-dependent)
//                        phi_inv    = u'V diag(1/w) V'u + sum(log w)  (cluster-invariant)
//                        phi_ed     = sum(W.*V) + c'w   (via eigendecompose_sym)
//                       prints phi + full gA (%.17g) for each; Richardson FD
//                       checks (h=1e-5, 5e-6) for phi_inv on fixed directions.
//   wellsep <seed0> <n> — n well-separated random symmetric 30x30 (LCG,
//                       deterministic across builds); prints gradients of all
//                       three functionals; SKIPS any matrix whose min adjacent
//                       gap < 1e-6*scale (gate (c) requires well-separated).
// All output %.17g so cross-build comparison is byte-exact.
#include <cmath>
#include <cstdio>
#include <vector>
#include <stan/math/rev.hpp>
#include "../w35/common.hpp"
using namespace stan::math;
using Eigen::MatrixXd; using Eigen::VectorXd;

// ---- functionals (double + var share code) ----
template <typename Mat>
auto phi_noninv(const Mat& A, const MatrixXd& W, const VectorXd& c) {
  using T = typename Mat::Scalar;
  Eigen::Matrix<T,-1,-1> V = eigenvectors_sym(A);
  Eigen::Matrix<T,-1,1> w = eigenvalues_sym(A);
  return (W.template cast<T>().array() * V.array()).sum()
         + c.template cast<T>().dot(w);
}

template <typename Mat>
auto phi_inv(const Mat& A, const VectorXd& u) {
  using T = typename Mat::Scalar;
  Eigen::Matrix<T,-1,-1> V = eigenvectors_sym(A);
  Eigen::Matrix<T,-1,1> w = eigenvalues_sym(A);
  Eigen::Matrix<T,-1,1> f = w.array().inverse();          // S^-1 = V diag(1/w) V'
  Eigen::Matrix<T,-1,1> Vu = V.transpose() * u.template cast<T>();
  return (Vu.array() * f.array() * Vu.array()).sum() + w.array().log().sum();
}

template <typename Mat>
auto phi_ed(const Mat& A, const MatrixXd& W, const VectorXd& c) {
  using T = typename Mat::Scalar;
  auto [V, w] = eigendecompose_sym(A);
  return (W.template cast<T>().array() * V.array()).sum()
         + c.template cast<T>().dot(w);
}

// ---- AD gradient of a functional over a full symmetric matrix ----
template <typename F>
VectorXd ad_grad(const MatrixXd& A0, F phi) {
  std::vector<var> av(A0.data(), A0.data() + A0.size());
  Eigen::Map<Eigen::Matrix<var,-1,-1>> Am(av.data(), A0.rows(), A0.cols());
  var f = phi(Am);
  f.grad();
  VectorXd g(A0.size());
  for (int i = 0; i < A0.size(); ++i) g[i] = av[i].adj();
  recover_memory();
  return g;
}

static int run_one(const char* nm, const MatrixXd& A, const MatrixXd& W,
                   const VectorXd& c, const VectorXd& u, bool with_fd) {
  const int n = A.rows();
  VectorXd g;
  g = ad_grad(A, [&](const auto& Am) { return phi_noninv(Am, W, c); });
  printf("== %s phi_noninv ==\n", nm); prv("gA_ni", g);
  g = ad_grad(A, [&](const auto& Am) { return phi_inv(Am, u); });
  printf("== %s phi_inv ==\n", nm); prv("gA_inv", g);
  g = ad_grad(A, [&](const auto& Am) { return phi_ed(Am, W, c); });
  printf("== %s phi_ed ==\n", nm); prv("gA_ed", g);
  if (with_fd) {
    // Richardson central FD of the double-mode phi_inv along symmetric dirs;
    // h sweep shows where FD itself converges (on cluster matrices the
    // curvature ~1/w^3 makes small-h FD truncation-dominated).
    VectorXd gad = ad_grad(A, [&](const auto& Am) { return phi_inv(Am, u); });
    for (auto [i, j] : std::vector<std::pair<int,int>>{{0,1},{5,5},{3,17},{10,29},{2,7}}) {
      auto ev = [&](double h) {
        MatrixXd P = A, Q = A;
        P(i,j) += h; if (i != j) P(j,i) += h;
        Q(i,j) -= h; if (i != j) Q(j,i) -= h;
        return (phi_inv(P, u) - phi_inv(Q, u)) / (2*h);
      };
      double ad = gad[i*n+j] + (i != j ? gad[j*n+i] : 0.0);
      for (double h0 : {1e-3, 1e-4, 1e-5}) {
        double d1 = ev(h0), d2 = ev(h0/2), rich = (4*d2 - d1) / 3;
        printf("fd_inv(%d,%d) h=%.0e rich %.12g ad %.12g reldiff %.3e\n", i, j, h0, rich, ad,
               std::abs(rich - ad) / std::max(1.0, std::abs(ad)));
      }
    }
  }
  return 0;
}

// exact-degeneracy mode: block-diagonal A with an EXACTLY k-fold repeated
// eigenvalue mu (the masked adjoint is then the exact derivative of any
// cluster-invariant composite; the stock adjoint divides by exact zeros).
static void run_exact(double mu, const VectorXd& u) {
  const int n = 30, k = 4;
  MatrixXd A = MatrixXd::Zero(n, n);
  for (int i = 0; i < k; ++i) A(i, i) = mu;            // exactly mu, k-fold
  for (int i = k; i < n; ++i) A(i, i) = 1.0 + 2.0 * i; // well separated
  const char* nm = mu == 1.0 ? "exact_mu1" : "exact_mu1e-5";
  VectorXd g;
  g = ad_grad(A, [&](const auto& Am) { return phi_inv(Am, u); });
  printf("== %s phi_inv ==\n", nm); prv("gA_inv", g);
  // FD of the invariant functional (well-conditioned when mu=1)
  for (auto [i, j] : std::vector<std::pair<int,int>>{{0,1},{2,3},{5,5},{0,7}}) {
    auto ev = [&](double h) {
      MatrixXd P = A, Q = A;
      P(i,j) += h; if (i != j) P(j,i) += h;
      Q(i,j) -= h; if (i != j) Q(j,i) -= h;
      return (phi_inv(P, u) - phi_inv(Q, u)) / (2*h);
    };
    double d1 = ev(1e-4), d2 = ev(5e-5), rich = (4*d2 - d1) / 3;
    double ad = g[i*n+j] + (i != j ? g[j*n+i] : 0.0);
    printf("fd_inv(%d,%d) rich %.12g ad %.12g reldiff %.3e\n", i, j, rich, ad,
           std::abs(rich - ad) / std::max(1.0, std::abs(ad)));
  }
}

// LCG identical across builds/compilers (integer arithmetic only)
static unsigned long long lcg_s = 88172645463325252ULL;
static double lcgu() {  // uniform-ish in (-1, 1)
  lcg_s ^= lcg_s << 13; lcg_s ^= lcg_s >> 7; lcg_s ^= lcg_s << 17;
  return (int)(lcg_s >> 33) / 1073741824.0 - 1.0;
}

int main(int argc, char** argv) {
  const std::string mode = argc > 1 ? argv[1] : "cluster";
  if (mode == "cluster") {
    Inputs in(argc > 2 ? argv[2] : "../w35/inputs.txt");
    MatrixXd W = in.mat("W30", 30, 30);
    VectorXd c = in.vec("c30");
    // u for the invariant functional: use column 0 of W (deterministic, O(1))
    VectorXd u = W.col(0);
    for (const char* nm : {"A_wellcond", "Sigma1_1", "Sigma1_2", "Sigma1_7",
                           "Sigma1_14", "Lambda_1", "Lambda_2", "Lambda_7",
                           "Lambda_14"})
      run_one(nm, in.mat(nm, 30, 30), W, c, u, true);
    run_exact(1.0, W.col(0));
    run_exact(1e-5, W.col(0));
    return 0;
  }
  if (mode == "wellsep") {
    unsigned long long seed = argc > 2 ? strtoull(argv[2], nullptr, 10) : 1;
    int n_mats = argc > 3 ? atoi(argv[3]) : 200;
    lcg_s = seed * 6364136223846793005ULL + 1442695040888963407ULL;
    int tested = 0, skipped = 0;
    for (int m = 0; m < n_mats; ++m) {
      MatrixXd A(30, 30);
      for (int j = 0; j < 30; ++j)
        for (int i = 0; i < 30; ++i) A(i, j) = lcgu();
      A = (A + A.transpose()).eval() * 0.5;
      for (int i = 0; i < 30; ++i) A(i, i) += 40.0;   // keep gaps O(1)
      Eigen::SelfAdjointEigenSolver<MatrixXd> es(A);
      VectorXd w = es.eigenvalues();
      double scale = std::max(1.0, w.cwiseAbs().maxCoeff());
      double mingap = (w.tail(29) - w.head(29)).minCoeff();
      if (mingap < 1e-6 * scale) { ++skipped; continue; }
      ++tested;
      MatrixXd W(30, 30); VectorXd c(30), u(30);
      for (int j = 0; j < 30; ++j)
        for (int i = 0; i < 30; ++i) W(i, j) = lcgu();
      for (int i = 0; i < 30; ++i) c[i] = lcgu();
      for (int i = 0; i < 30; ++i) u[i] = lcgu();
      printf("== wellsep %d mingap %.6e ==\n", m, mingap);
      VectorXd g;
      g = ad_grad(A, [&](const auto& Am) { return phi_noninv(Am, W, c); });
      prv("gA_ni", g);
      g = ad_grad(A, [&](const auto& Am) { return phi_inv(Am, u); });
      prv("gA_inv", g);
      g = ad_grad(A, [&](const auto& Am) { return phi_ed(Am, W, c); });
      prv("gA_ed", g);
      // eigenvalues_sym-only functional (file unpatched; must be identical)
      g = ad_grad(A, [&](const auto& Am) {
        Eigen::Matrix<var,-1,1> wv = eigenvalues_sym(Am);
        return var(wv.sum());
      });
      prv("gA_ev", g);
    }
    printf("wellsep tested %d skipped %d\n", tested, skipped);
    return 0;
  }
  fprintf(stderr, "unknown mode %s\n", mode.c_str());
  return 1;
}
