// march_native_repro.cpp — W-35 minimized reproducer (kronecker_gp -march=native
// gradient divergence), self-contained stan-math + Eigen, no model, no data file.
//
// A = var1 * exp(-((xi-xj)^2) * bw1) + 1e-5 * I   (n = 30; the model's Sigma1
// at a posterior point). The RBF saturation pins a cluster of bottom
// eigenvalues at exactly the 1e-5 jitter floor -> eigenvalue gaps at rounding
// level inside the cluster.
//
// Compile twice (same source, same input bits):
//   baseline: g++ -std=c++17 -O2  <incs> march_native_repro.cpp -o repro_base
//   native:   g++ -std=c++17 -O2 -march=native <incs> march_native_repro.cpp -o repro_native
//
// Observed (gcc 16.2.1, Zen 3; also clang 22 with -march=native):
//   * A is bit-identical in both binaries; eigenvalues agree to ~1e-14
//   * eigenvectors WITHIN the cluster differ by up to ~0.96 with sign flips
//     (both results satisfy A*V = V*diag(w) to ~1e-14: both valid decompositions)
//   * the stan-math rev eigenvector adjoint (F_ij = 1/(w_j - w_i)) then yields
//     AD gradients that differ between the binaries by O(1)-O(1e3) rel AND are
//     inconsistent with Richardson finite differences IN BOTH binaries.
// NOT a compiler bug: ASan/UBSan clean under both flag sets; well-conditioned
// controls are bit-identical across compilers/flags; -ffp-contract=off and
// -fno-tree-vectorize do NOT remove the divergence (Eigen's explicitly
// vectorized AVX GEMM kernel changes FP summation order, which is all it takes).
#include <cmath>
#include <cstdio>
#include <stan/math/rev.hpp>

int main() {
  const int n = 30;
  const double var1 = 2.2259362831331342, bw1 = 0.62234081376409707;  // posterior pt
  // x grid = linspace(-2, 2, 30) (data); W/c from an integer LCG -> identical
  // in every binary (no FP in generation).
  double x[30];
  for (int i = 0; i < n; ++i) x[i] = -2.0 + 4.0 * i / 29.0;
  Eigen::MatrixXd W(n, n);
  Eigen::VectorXd c(n);
  unsigned long long s = 88172645463325252ULL;
  auto rnd = [&]() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return (int)(s >> 33); };
  for (int j = 0; j < n; ++j)
    for (int i = 0; i < n; ++i) W(i, j) = rnd() / 1073741824.0 - 1.0;
  for (int i = 0; i < n; ++i) c[i] = rnd() / 1073741824.0 - 1.0;

  // A: the model's Sigma1 (double; elementwise exp, identical across builds)
  Eigen::MatrixXd A(n, n);
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j) A(i, j) = var1 * std::exp(-(x[i] - x[j]) * (x[i] - x[j]) * bw1);
  for (int i = 0; i < n; ++i) A(i, i) += 1e-5;
  printf("A(0,1) %.17g  A(15,15) %.17g\n", A(0, 1), A(15, 15));

  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es(A);  // what eigenvectors_sym uses
  printf("w[0..4]:");
  for (int i = 0; i < 5; ++i) printf(" %.17g", es.eigenvalues()[i]);
  printf("\nV col0 [0..5]:");
  for (int i = 0; i < 6; ++i) printf(" %.10g", es.eigenvectors()(i, 0));
  printf("\nresid %.3e\n",
         (A * es.eigenvectors() - es.eigenvectors() * es.eigenvalues().asDiagonal())
             .cwiseAbs().maxCoeff());

  // AD objective through the eigen complex (model-like: depends on V and w)
  auto phi = [&](const auto& Am) {
    auto V = stan::math::eigenvectors_sym(Am);
    auto w = stan::math::eigenvalues_sym(Am);
    return (W.array() * V.array()).sum() + c.dot(w);
  };
  std::vector<stan::math::var> av(A.data(), A.data() + n * n);
  Eigen::Matrix<stan::math::var, -1, -1> Am =
      Eigen::Map<Eigen::Matrix<stan::math::var, -1, -1>>(av.data(), n, n);
  stan::math::var f = phi(Am);
  f.grad();
  printf("phi %.17g  gA(0,1) %.17g  gA(5,5) %.17g  gA(29,28) %.17g\n", f.val(),
         av[0 * n + 1].adj(), av[5 * n + 5].adj(), av[29 * n + 28].adj());
  // Richardson central FD self-check at the same entries (double mode)
  auto phid = [&](const Eigen::MatrixXd& M) { return phi(M); };
  for (auto [i, j] : std::vector<std::pair<int, int>>{{0, 1}, {5, 5}, {29, 28}}) {
    auto ev = [&](double h) {
      Eigen::MatrixXd P = A, Q = A;
      P(i, j) += h; if (i != j) P(j, i) += h;
      Q(i, j) -= h; if (i != j) Q(j, i) -= h;
      return (phid(P) - phid(Q)) / (2 * h);
    };
    double d1 = ev(1e-5), d2 = ev(5e-6), rich = (4 * d2 - d1) / 3;
    double ad = av[i * n + j].adj() + (i != j ? av[j * n + i].adj() : 0.0);
    printf("fd(%d,%d) rich %.10g  ad %.10g  reldiff %.2e\n", i, j, rich, ad,
           std::abs(rich - ad) / std::max(1.0, std::abs(ad)));
  }
  return 0;
}
