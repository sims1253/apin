// Hypothesis: ps_point copies in the NUTS loop. Measures raw cost of copying
// an N-dim ps_point (q, p, g, i.e. 3 vectors) as done by build_tree per node.
#include <chrono>
#include <cstdio>
#include <vector>
#include <Eigen/Dense>
struct ps_point {
  Eigen::VectorXd q, p, g;
  ps_point(int n): q(n), p(n), g(n) {}
  ps_point(const ps_point& o) = default;
};
static double now_s(){ static auto t0=std::chrono::steady_clock::now();
  return std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count(); }
int main(){
  for (int n : {18, 100, 1000, 7000}) {
    ps_point z(n); volatile double sink=0;
    const int reps = 200000;
    double t0 = now_s();
    for (int r=0;r<reps;r++){ ps_point z2 = z; sink += z2.q[0]; }  // copy ctor
    printf("ps_point copy n=%4d          : %7.1f ns/copy\n", n, (now_s()-t0)/reps*1e9);
  }
}
