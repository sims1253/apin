// W-40: dump the eigenvalue spectra + adjacent-gap structure of the W-35
// cluster matrices (Sigma1/Lambda at failing points pt1/pt2/pt7/pt14) and the
// well-conditioned control, to ground the cluster threshold kappa choice.
// Pure value-level Eigen; no stan-math rev needed.
#include <cstdio>
#include <Eigen/Dense>
#include <limits>
#include <algorithm>
#include "../w35/common.hpp"

int main(int argc, char** argv) {
  Inputs in(argc > 1 ? argv[1] : "../w35/inputs.txt");
  const double eps = std::numeric_limits<double>::epsilon();
  for (const char* nm : {"A_wellcond", "Sigma1_1", "Sigma1_2", "Sigma1_7",
                         "Sigma1_14", "Lambda_1", "Lambda_2", "Lambda_7",
                         "Lambda_14"}) {
    Eigen::MatrixXd A = in.mat(nm, 30, 30);
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es(A);
    Eigen::VectorXd w = es.eigenvalues();
    double scale = std::max(1.0, w.cwiseAbs().maxCoeff());
    printf("== %s == w in [%.6g, %.6g]  scale %.6g\n", nm, w[0], w[w.size()-1], scale);
    // adjacent gaps (ascending order)
    Eigen::VectorXd d(w.size() - 1);
    for (int i = 0; i + 1 < w.size(); ++i) d[i] = w[i+1] - w[i];
    printf("min gap %.3e  max gap %.3e  median gap %.3e\n",
           d.minCoeff(), d.maxCoeff(), (d.size() ? d[d.size()/2] : 0.0));
    for (double kappa : {1e2, 1e3, 1e4}) {
      double tau = kappa * scale * eps;
      int masked = (d.array() < tau).count();
      // largest retained (>= tau) adjacent gap structure: report the smallest
      // RETAINED adjacent gap (drives residual conditioning after masking)
      double dmin_ret = 1.0 / 0.0;
      for (int i = 0; i < d.size(); ++i)
        if (d[i] >= tau && d[i] < dmin_ret) dmin_ret = d[i];
      printf("  kappa %.0e: tau %.3e  masked adjacent pairs %d/%zu"
             "  smallest retained gap %.3e (cond 1/d %.3e)\n",
             kappa, tau, masked, (size_t)d.size(),
             dmin_ret == 1.0/0.0 ? -1.0 : dmin_ret,
             dmin_ret == 1.0/0.0 ? -1.0 : 1.0/dmin_ret);
    }
    // bottom-10 eigenvalues + first 12 gaps in full precision (the cluster)
    printf("  w[0..9]:");
    for (int i = 0; i < 10; ++i) printf(" %.6e", w[i]);
    printf("\n  gaps[0..11]:");
    for (int i = 0; i < 12 && i < d.size(); ++i) printf(" %.3e", d[i]);
    printf("\n");
  }
  return 0;
}
