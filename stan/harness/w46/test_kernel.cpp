// W-46 unit test: the patched lpmf kernel (dispatcher: baseline Packet2d or
// AVX2 island) vs stock expressions + glibc, on grids and the real x sets.
#include "/home/m0hawk/Documents/apin/stan/scratch/w46/bernoulli_logit_lpmf.hpp.patched"
#include <Eigen/Core>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <random>
#include <string>
#include <vector>

using ArrayXd = Eigen::Array<double, Eigen::Dynamic, 1>;
using Map = Eigen::Map<const ArrayXd>;
constexpr double CUT = 20.0;

static double ulp_of(double r) {
  r = std::fabs(r);
  double nx = std::nextafter(r, INFINITY);
  double d = nx - r;
  return d > 0 ? d : 4.9406564584124654e-324;
}
static double ulps(double a, double ref) {
  if (a == ref) return 0.0;
  return std::fabs(a - ref) / ulp_of(ref);
}

// stock reference (exact lpmf interior, signs = +1)
static void stock_ref(const double* x, int n, double* val, double* p) {
  Map xm(x, n);
  ArrayXd e = (-xm).exp();
  ArrayXd l(n);
  for (int i = 0; i < n; ++i) l[i] = std::log1p(e[i]);
  Eigen::Map<ArrayXd> vm(val, n), pm(p, n);
  vm = (xm > CUT).select(-e, (xm < -CUT).select(xm, -l));
  pm = (xm > CUT).select(-e, (xm >= -CUT).select(e / (e + 1.0),
                                                 ArrayXd::Constant(n, 1.0)));
}

int main() {
  // ---- primitive accuracy through the kernel: x = -log(w) in [0,20] ----
  double mu = 0;
  long cnt = 0;
  const long M = 1500000;
  for (long j = 0; j <= M; ++j) {
    double w = std::exp(-20.0 * (double)j / M);
    double x = -std::log(w);
    double p;
    double v = ::w46_kern::dispatch(&x, 1, &p);
    mu = std::max(mu, ulps(-v, std::log1p(w)));
    ++cnt;
  }
  std::mt19937_64 rng(20260823);
  std::uniform_real_distribution<double> U(0.0, 1.0);
  for (long j = 0; j < 1000000; ++j) {
    double w = U(rng);
    double x = -std::log(w);
    double p;
    double v = ::w46_kern::dispatch(&x, 1, &p);
    mu = std::max(mu, ulps(-v, std::log1p(w)));
    ++cnt;
  }
  printf("UNIT prim (kernel -val vs glibc log1p(w)): max_ulp=%.3f over %ld pts\n", mu, cnt);

  // ---- fused vs stock on the real x sets ----
  const char* sets[] = {"draws", "cloud", "random", "pfinit"};
  for (auto nm : sets) {
    FILE* f = fopen((std::string("/home/m0hawk/Documents/apin/stan/scratch/w46/x_") + nm + ".f64").c_str(), "rb");
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    int n = sz / 8;
    std::vector<double> x(n), val0(n), p0(n), pk(n);
    if (fread(x.data(), 1, sz, f) != (size_t)sz) return 1;
    fclose(f);
    stock_ref(x.data(), n, val0.data(), p0.data());
    double s = ::w46_kern::dispatch(x.data(), n, pk.data());
    (void)s;
    double vu = 0, pr = 0, s0 = 0, sk = 0;
    for (int i = 0; i < n; ++i) {
      double pp;
      double v = ::w46_kern::elem(x[i], &pp);  // scalar = kernel semantics
      vu = std::max(vu, ulps(v, val0[i]));
      pr = std::max(pr, std::fabs(pp - p0[i]) / std::max(1e-300, std::fabs(p0[i])));
      s0 += val0[i];
      sk += v;
    }
    double sum_rel = std::fabs(sk - s0) / std::fabs(s0);
    printf("UNIT set=%-7s n=%d  val_max_ulp=%.3f  p_max_rel=%.3e  sum_rel=%.3e\n",
           nm, n, vu, pr, sum_rel);
  }

  // ---- dispatch + speed on 19200 elements ----
  std::vector<double> x(19200), p(19200);
  for (int i = 0; i < 19200; ++i) x[i] = std::sin(0.001 * i) * 8.0;
  auto t0 = std::chrono::steady_clock::now();
  double acc = 0;
  for (int r = 0; r < 2000; ++r) acc += ::w46_kern::fwd_scalar(x.data(), 19200, p.data());
  auto t1 = std::chrono::steady_clock::now();
  double nsb = std::chrono::duration<double, std::nano>(t1 - t0).count() / (2000.0 * 19200);
  t0 = std::chrono::steady_clock::now();
  for (int r = 0; r < 2000; ++r) acc += ::w46_kern::fwd_avx2(x.data(), 19200, p.data());
  t1 = std::chrono::steady_clock::now();
  double nsa = std::chrono::duration<double, std::nano>(t1 - t0).count() / (2000.0 * 19200);
  printf("UNIT speed: fwd_base %.3f ns/elem, fwd_avx2 %.3f ns/elem (%.2fx) [acc=%g]\n",
         nsb, nsa, nsb / nsa, acc * 1e-300);
  return 0;
}
