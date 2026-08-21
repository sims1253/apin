// Hypothesis: var arena alloc/reset policy cost in a gradient-heavy loop.
// Time: N scalar var ops chain (depth-D expression) vs doubles; plus arena reset cost.
#include <stan/math.hpp>
#include <chrono>
#include <cstdio>
namespace sm = stan::math;

static double now_s(){ static auto t0 = std::chrono::steady_clock::now();
  return std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count(); }

int main(){
  const int n = 1000, reps = 2000, depth = 20;   // chain of depth ops on vector of n
  Eigen::VectorXd x0 = Eigen::VectorXd::Constant(n, 0.3);
  // doubles
  { double t0 = now_s(); double acc=0;
    for (int r=0;r<reps;r++){ Eigen::VectorXd x = x0;
      for (int d=0; d<depth; d++) x = (x.array() * 1.0001 + 0.5).matrix();
      acc += x.sum(); }
    printf("double chain d=%d n=%d     : %8.1f ns/rep\n", depth, n, (now_s()-t0)/reps*1e9); }
  // var chain + grad
  { double t0 = now_s(); double acc=0;
    for (int r=0;r<reps;r++){
      Eigen::Matrix<sm::var,-1,1> x = x0.cast<sm::var>();
      for (int d=0; d<depth; d++) x = (x.array() * 1.0001 + 0.5).matrix();
      sm::var s = x.sum(); s.grad(); acc += s.val();
      sm::recover_memory(); }
    printf("var chain +grad +arena reset: %8.1f ns/rep\n", (now_s()-t0)/reps*1e9); }
  return 0;
}
