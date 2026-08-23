// W-46 micro-bench: kernels for the bernoulli_logit_lpmf interior on hier_2pl's
// real ntheta distribution. Pure C++; no model builds. See WORKLOG W-46.
#include <stan/math/prim/fun/log1p.hpp>   // K0: the faithful stan wrapper path
#include <Eigen/Core>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <random>
#include <string>
#include <vector>

#include "log1p_poly.h"

using Eigen::ArrayXd;
using Eigen::Map;
namespace EIN = Eigen::internal;
using Pkt = EIN::packet_traits<double>::type;
constexpr int PK = EIN::unpacket_traits<Pkt>::size;
constexpr double CUT = 20.0;

// ---------------- helpers ----------------
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

// ---------------- log1p primitives (reduced range w in [e^-20, 1]) ----------
static inline double log1p_kahan_s(double w) {  // scalar, glibc log + Kahan corr
  double y = 1.0 + w;
  double m = (y - 1.0) - w;      // exact (Dekker FastTwoSum, |1|>=|w|)
  return std::log(y) - m / y;    // log(y) ~ log1p(w) + m/y  => subtract
}
template <int D>
static inline double log1p_poly_s(double w) {   // peeled Chebyshev, split at 0.5
  double a = (w >= 0.5) ? 0.5 : 0.0;
  double u = (w - a) * ((a == 0.0) ? 1.0 : (2.0 / 3.0));
  double z = (u - 0.25) * 4.0;
  const double* C = D == 16 ? w46::LOG1P_S16 : (D == 13 ? w46::LOG1P_S13 : w46::LOG1P_S10);
  double zz = 2.0 * z, b1 = 0.0, b2 = 0.0;
  for (int k = D; k >= 1; --k) { double t = C[k] + zz * b1 - b2; b2 = b1; b1 = t; }
  double S = C[0] + z * b1 - b2;
  double u2 = u * u;
  double r = (a == 0.5) ? w46::LN1P_HALF : 0.0;
  r += u - 0.5 * u2;
  r += u * u2 * S;
  return r;
}
// packet kahan: log1p(w) = plog(1+w) + ((1+w)-1-w)/(1+w)
static inline Pkt log1p_kahan_p(Pkt w) {
  Pkt one = EIN::pset1<Pkt>(1.0);
  Pkt y = EIN::padd(w, one);
  Pkt m = EIN::psub(EIN::psub(y, one), w);
  return EIN::padd(EIN::plog(y), EIN::pdiv(m, y));
}
template <int D>
static inline Pkt log1p_poly_p(Pkt w) {
  Pkt half = EIN::pset1<Pkt>(0.5);
  Pkt zero = EIN::pset1<Pkt>(0.0);
  Pkt one = EIN::pset1<Pkt>(1.0);
  Pkt two3 = EIN::pset1<Pkt>(2.0 / 3.0);
  Pkt quar = EIN::pset1<Pkt>(0.25);
  Pkt four = EIN::pset1<Pkt>(4.0);
  Pkt anchor = EIN::pset1<Pkt>(w46::LN1P_HALF);
  Pkt small = EIN::pcmp_lt(w, half);              // w < 0.5
  Pkt a = EIN::pselect(small, zero, half);
  Pkt inv = EIN::pselect(small, one, two3);
  Pkt anc = EIN::pselect(small, zero, anchor);
  Pkt u = EIN::pmul(EIN::psub(w, a), inv);
  Pkt z = EIN::pmul(EIN::psub(u, quar), four);
  const double* C = D == 16 ? w46::LOG1P_S16 : (D == 13 ? w46::LOG1P_S13 : w46::LOG1P_S10);
  Pkt zz = EIN::pmul(EIN::pset1<Pkt>(2.0), z);
  Pkt b1 = zero, b2 = zero;
  for (int k = D; k >= 1; --k) {
    Pkt t = EIN::psub(EIN::padd(EIN::pset1<Pkt>(C[k]), EIN::pmul(zz, b1)), b2);
    b2 = b1; b1 = t;
  }
  Pkt S = EIN::padd(EIN::pset1<Pkt>(C[0]), EIN::psub(EIN::pmul(z, b1), b2));
  Pkt u2 = EIN::pmul(u, u);
  Pkt r = EIN::padd(anc, EIN::psub(u, EIN::pmul(EIN::pset1<Pkt>(0.5), u2)));
  return EIN::padd(r, EIN::pmul(EIN::pmul(u, u2), S));
}

// ---------------- fused lpmf-interior kernels ----------------
// signs = +1 (bench); stock formulas with branch cuts at +-20.
// K0: faithful stock shape (packet exp; per-element stan::math::log1p wrapper;
// Eigen Select redux for the value; Eigen Select partials expression).
static void k0_stock(const double* x, int n, double* val, double* p) {
  Map<const ArrayXd> xm(x, n);
  ArrayXd e = (-xm).exp();
  ArrayXd l(n);
  for (int i = 0; i < n; ++i) l[i] = stan::math::log1p(e[i]);
  double s = ((xm > CUT).select(-e, (xm < -CUT).select(xm, -l))).sum();
  *val = s;  // val slot holds the redux sum for K0 (array variant below)
  Map<ArrayXd> pm(p, n);
  pm = (xm > CUT).select(-e, (xm >= -CUT).select(e / (e + 1.0),
                                                 ArrayXd::Constant(n, 1.0)));
}
static void k0_val_array(const double* x, int n, double* val) {
  Map<const ArrayXd> xm(x, n);
  ArrayXd e = (-xm).exp();
  ArrayXd l(n);
  for (int i = 0; i < n; ++i) l[i] = stan::math::log1p(e[i]);
  Map<ArrayXd> vm(val, n);
  vm = (xm > CUT).select(-e, (xm < -CUT).select(xm, -l));
}
// K1: std::log1p direct (no stan wrapper)
static void k1_std(const double* x, int n, double* val, double* p) {
  Map<const ArrayXd> xm(x, n);
  ArrayXd e = (-xm).exp();
  ArrayXd l(n);
  for (int i = 0; i < n; ++i) l[i] = std::log1p(e[i]);
  double s = ((xm > CUT).select(-e, (xm < -CUT).select(xm, -l))).sum();
  *val = s;
  Map<ArrayXd> pm(p, n);
  pm = (xm > CUT).select(-e, (xm >= -CUT).select(e / (e + 1.0),
                                                 ArrayXd::Constant(n, 1.0)));
}
// K2: branch-cut, glibc log1p only in-band, bit-identical outputs to K0
static void k2_skip(const double* x, int n, double* val, double* p) {
  Map<const ArrayXd> xm(x, n);
  ArrayXd e = (-xm).exp();
  double s = 0;
  for (int i = 0; i < n; ++i) {
    double xi = x[i], ei = e[i], v;
    if (xi > CUT) { v = -ei; p[i] = -ei; }
    else if (xi < -CUT) { v = xi; p[i] = 1.0; }
    else { v = -std::log1p(ei); p[i] = ei / (1.0 + ei); }
    val[i] = v; s += v;
  }
  (void)s;
}
// K3: fused scalar, min-form (argument confined to [e^-20,1]); packet exp kept
static void k3_fused(const double* x, int n, double* val, double* p) {
  Map<const ArrayXd> xm(x, n);
  ArrayXd w = (-xm.abs()).exp();
  for (int i = 0; i < n; ++i) {
    double xi = x[i], wi = w[i], v, pi;
    if (xi > CUT) { v = -wi; pi = -wi; }
    else if (xi < -CUT) { v = xi; pi = 1.0; }
    else {
      double l = std::log1p(wi);
      v = (xi < 0.0) ? (xi - l) : -l;
      pi = (xi < 0.0) ? 1.0 / (1.0 + wi) : wi / (1.0 + wi);
    }
    val[i] = v; p[i] = pi;
  }
}
// packet fused kernel factory: LOGL = lambda (Pkt w)->Pkt
template <typename LOGL>
static void kern_packet(const double* x, int n, double* val, double* p, LOGL logl) {
  Pkt c20 = EIN::pset1<Pkt>(CUT), nm20 = EIN::pset1<Pkt>(-CUT);
  Pkt one = EIN::pset1<Pkt>(1.0), zero = EIN::pset1<Pkt>(0.0);
  int i = 0;
  for (; i + PK <= n; i += PK) {
    Pkt px = EIN::ploadu<Pkt>(x + i);
    Pkt w = EIN::pexp(EIN::pnegate(EIN::pabs(px)));      // e^{-|x|}
    Pkt y = EIN::padd(w, one);
    Pkt l = logl(w, y);                               // log1p(w), y = 1+w
    Pkt vm = EIN::psub(EIN::pmin(px, zero), l);       // min(x,0) - log1p(w)
    Pkt gt = EIN::pcmp_lt(c20, px), lt = EIN::pcmp_lt(px, nm20);
    Pkt v = EIN::pselect(gt, EIN::pnegate(w), EIN::pselect(lt, px, vm));
    Pkt q = EIN::pdiv(w, y);                          // w/(1+w)
    Pkt negm = EIN::pcmp_lt(px, zero);
    Pkt pmid = EIN::pselect(negm, EIN::psub(one, q), q);
    Pkt pv = EIN::pselect(gt, EIN::pnegate(w), EIN::pselect(lt, one, pmid));
    EIN::pstoreu(val + i, v);
    EIN::pstoreu(p + i, pv);
  }
  for (; i < n; ++i) {  // scalar tail = k3 math
    double xi = x[i], wi = std::exp(-std::fabs(xi)), v, pi;
    if (xi > CUT) { v = -wi; pi = -wi; }
    else if (xi < -CUT) { v = xi; pi = 1.0; }
    else {
      double l = std::log1p(wi);
      v = (xi < 0.0) ? (xi - l) : -l;
      pi = (xi < 0.0) ? 1.0 / (1.0 + wi) : wi / (1.0 + wi);
    }
    val[i] = v; p[i] = pi;
  }
}
static void k4_kahan_pkt(const double* x, int n, double* val, double* p) {
  kern_packet(x, n, val, p, [](Pkt w, Pkt y) {
    Pkt one = EIN::pset1<Pkt>(1.0);
    Pkt m = EIN::psub(EIN::psub(y, one), w);
    return EIN::psub(EIN::plog(y), EIN::pdiv(m, y));
  });
}
template <int D>
static void k_poly_pkt(const double* x, int n, double* val, double* p) {
  kern_packet(x, n, val, p, [](Pkt w, Pkt) { return log1p_poly_p<D>(w); });
}
static void k7_eigen_plog1p(const double* x, int n, double* val, double* p) {
  kern_packet(x, n, val, p, [](Pkt w, Pkt) { return EIN::generic_plog1p<Pkt>(w); });
}

// ---------------- accuracy harness ----------------
struct PrimResult { std::string name; double max_ulp; long npts; double max_abs; };
template <typename F>
static PrimResult check_prim(const std::string& name, const std::vector<double>& g, F f) {
  double mu = 0, ma = 0;
  for (double w : g) {
    double ref = std::log1p(w);
    double a = f(w);
    mu = std::max(mu, ulps(a, ref));
    ma = std::max(ma, std::fabs(a - ref));
  }
  return {name, mu, (long)g.size(), ma};
}
static std::vector<double> make_grid() {
  std::vector<double> g;
  const double W0 = std::exp(-20.0);
  const long M = 1200000;
  for (long j = 0; j <= M; ++j) g.push_back(std::exp(-20.0 * (double)j / M)); // [1, e^-20]
  std::mt19937_64 rng(20260822);
  std::uniform_real_distribution<double> U(0.0, 1.0);
  for (long j = 0; j < 1000000; ++j) g.push_back(U(rng));                     // uniform [0,1]
  // exact boundary/special points
  for (int k = 0; k <= 20; ++k) { g.push_back(std::exp(-(double)k)); g.push_back(-std::expm1(-(double)k)); }
  g.push_back(W0); g.push_back(1.0); g.push_back(0.5); g.push_back(0.0);
  g.push_back(std::nextafter(1.0, 0.0)); g.push_back(std::nextafter(0.5, 1.0));
  g.push_back(std::nextafter(0.5, 0.0)); g.push_back(1e-300); g.push_back(5e-324);
  return g;
}

// ---------------- timing ----------------
using KFn = void (*)(const double*, int, double*, double*);
struct Kern { std::string name; KFn fn; };
static double now_ns() {
  return std::chrono::duration<double, std::nano>(
             std::chrono::steady_clock::now().time_since_epoch()).count();
}

int main(int argc, char** argv) {
  const bool fast = (argc > 1 && std::string(argv[1]) == "ir");
  // load raw x sets
  const std::string dir = "/home/m0hawk/Documents/apin/stan/scratch/w46/";
  std::vector<std::vector<double>> xs;
  std::vector<std::string> xnames = {"draws", "cloud", "random", "pfinit"};
  for (auto& nm : xnames) {
    FILE* f = fopen((dir + "x_" + nm + ".f64").c_str(), "rb");
    if (!f) { fprintf(stderr, "missing %s\n", nm.c_str()); return 1; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    std::vector<double> v(sz / 8);
    if (fread(v.data(), 1, sz, f) != (size_t)sz) return 1;
    fclose(f);
    xs.push_back(std::move(v));
  }
  printf("packet lanes = %d (Eigen default for double at current flags)\n", PK);

  // ---------- accuracy: primitives ----------
  if (!fast) {
  auto grid = make_grid();
  auto r_kahan = check_prim("log1p_kahan_plog", grid, [](double w) { return log1p_kahan_s(w); });
  auto r_p16 = check_prim("log1p_poly16", grid, [](double w) { return log1p_poly_s<16>(w); });
  auto r_p13 = check_prim("log1p_poly13", grid, [](double w) { return log1p_poly_s<13>(w); });
  auto r_p10 = check_prim("log1p_poly10(APPROX)", grid, [](double w) { return log1p_poly_s<10>(w); });
  auto r_eig = check_prim("eigen_generic_plog1p", grid, [](double w) {
    Pkt pv = EIN::pset1<Pkt>(w); return EIN::pfirst(EIN::generic_plog1p<Pkt>(pv));
  });
  for (auto& r : {r_kahan, r_p16, r_p13, r_p10, r_eig})
    printf("PRIM %-22s max_ulp=%9.3f  max_abs=%.3e  npts=%ld\n",
           r.name.c_str(), r.max_ulp, r.max_abs, r.npts);
  }

  // ---------- accuracy: fused kernels vs K0 on the real sets ----------
  int n = (int)xs[0].size();
  std::vector<double> val0(n), p0(n), valk(n), pk(n);
  struct FusedAcc { std::string name; double val_ulp = 0, p_rel = 0, p_abs = 0; long nbad = 0; };
  std::vector<std::pair<std::string, KFn>> fused = {
      {"k2_skip", k2_skip}, {"k3_fused", k3_fused}, {"k4_kahan_pkt", k4_kahan_pkt},
      {"k5_poly16_pkt", k_poly_pkt<16>}, {"k5b_poly13_pkt", k_poly_pkt<13>},
      {"k7_eigen_plog1p", k7_eigen_plog1p}, {"k8_poly10_pkt(APPROX)", k_poly_pkt<10>}};
  for (size_t s = 0; s < xs.size() && !fast; ++s) {
    const int ns = (int)xs[s].size();
    k0_val_array(xs[s].data(), ns, val0.data());
    Map<const ArrayXd> pm0(p0.data(), n);
    (void)pm0;
    // K0 partials
    {
      Map<const ArrayXd> xm(xs[s].data(), ns);
      ArrayXd e = (-xm).exp();
      Map<ArrayXd> pp(p0.data(), ns);
      pp = (xm > CUT).select(-e, (xm >= -CUT).select(e / (e + 1.0),
                                                     ArrayXd::Constant(ns, 1.0)));
    }
    printf("SET %s:\n", xnames[s].c_str());
    for (auto& kf : fused) {
      kf.second(xs[s].data(), ns, valk.data(), pk.data());
      double vu = 0, pr = 0, pa = 0; long nb = 0;
      for (int i = 0; i < ns; ++i) {
        vu = std::max(vu, ulps(valk[i], val0[i]));
        double d = std::fabs(pk[i] - p0[i]);
        pr = std::max(pr, d / std::max(1e-300, std::fabs(p0[i])));
        pa = std::max(pa, d);
        if (std::isnan(valk[i]) || std::isnan(pk[i])) ++nb;
      }
      printf("  ACC %-24s val_max_ulp=%10.3f  p_max_rel=%.3e  p_max_abs=%.3e  nan=%ld\n",
             kf.first.c_str(), vu, pr, pa, nb);
    }
  }

  // ---------- timing (interleaved, medians) ----------
  std::vector<Kern> kernels = {
      {"k0_stock", k0_stock}, {"k1_std", k1_std}, {"k2_skip", k2_skip},
      {"k3_fused", k3_fused}, {"k4_kahan_pkt", k4_kahan_pkt},
      {"k5_poly16_pkt", k_poly_pkt<16>}, {"k5b_poly13_pkt", k_poly_pkt<13>},
      {"k7_eigen_plog1p", k7_eigen_plog1p}, {"k8_poly10_pkt", k_poly_pkt<10>}};
  const int R = fast ? 3 : 9, INNER = fast ? 1 : 3;
  // cache-resident regime: the model evaluates N=19,200 elements per gradient
  // call (a few hundred KB working set). Time on the first 19,200 elements.
  const int NT = std::min(n, 19200);
  const int PASSES = fast ? 2 : (n / NT);
  std::vector<std::vector<double>> t(kernels.size(), std::vector<double>(R));
  // warmup
  for (auto& k : kernels) k.fn(xs[0].data(), NT, valk.data(), pk.data());
  for (auto& k : kernels) k.fn(xs[0].data(), NT, valk.data(), pk.data());
  volatile double sink = 0;
  for (int rep = 0; rep < R; ++rep) {
    for (size_t ki = 0; ki < kernels.size(); ++ki) {
      double t0 = now_ns();
      for (int it = 0; it < INNER; ++it)
        for (int q = 0; q < PASSES; ++q)
          kernels[ki].fn(xs[0].data() + (size_t)q * NT, NT, valk.data(), pk.data());
      double t1 = now_ns();
      t[ki][rep] += (t1 - t0) / (INNER * n);
      double cs = 0, cp = 0;
      for (int i = 0; i < n; ++i) { cs += valk[i]; cp += pk[i]; }
      sink += cs * 1e-300 + cp * 1e-300;
    }
  }
  printf("TIMING (set=draws, n=%d, median of %d reps x %d passes):\n", n, R, INNER);
  double base = 0;
  for (size_t ki = 0; ki < kernels.size(); ++ki) {
    std::vector<double> v = t[ki];
    std::sort(v.begin(), v.end());
    double ns = v[R / 2];
    if (ki == 0) base = ns;
    printf("  TIME %-24s %8.4f ns/elem   (%5.2fx vs k0)\n", kernels[ki].name.c_str(), ns, base / ns);
  }
  // secondary set: cloud
  const int nc = (int)xs[1].size();
  const int NTC = std::min(nc, 19200), PASSES_C = fast ? 2 : (nc / NTC);
  for (auto& k : kernels) k.fn(xs[1].data(), NTC, valk.data(), pk.data());
  std::vector<std::vector<double>> t2(kernels.size(), std::vector<double>(R));
  for (int rep = 0; rep < R; ++rep) {
    for (size_t ki = 0; ki < kernels.size(); ++ki) {
      double t0 = now_ns();
      for (int it = 0; it < INNER; ++it)
        for (int q = 0; q < PASSES_C; ++q)
          kernels[ki].fn(xs[1].data() + (size_t)q * NTC, NTC, valk.data(), pk.data());
      double t1 = now_ns();
      t2[ki][rep] += (t1 - t0) / (INNER * nc);
      double cs = 0, cp = 0;
      for (int i = 0; i < NTC; ++i) { cs += valk[i]; cp += pk[i]; }
      sink += cs * 1e-300 + cp * 1e-300;
    }
  }
  printf("TIMING (set=cloud):\n");
  base = 0;
  for (size_t ki = 0; ki < kernels.size(); ++ki) {
    std::vector<double> v = t2[ki];
    std::sort(v.begin(), v.end());
    double ns = v[R / 2];
    if (ki == 0) base = ns;
    printf("  TIME %-24s %8.4f ns/elem   (%5.2fx vs k0)\n", kernels[ki].name.c_str(), ns, base / ns);
  }
  // pure-primitive scale: bare std::log1p loop on w in [e^-20,1], L1-resident
  if (!fast) {
    const int NP = 4096;
    std::vector<double> wv(NP), lv(NP);
    for (int i = 0; i < NP; ++i) wv[i] = std::exp(-20.0 * (i + 0.5) / NP);
    for (int i = 0; i < NP; ++i) lv[i] = std::log1p(wv[i]);
    double best = 1e300;
    for (int rep = 0; rep < 5; ++rep) {
      double t0 = now_ns();
      for (int g = 0; g < 200; ++g)
        for (int i = 0; i < NP; ++i) lv[i] = std::log1p(wv[i]);
      double t1 = now_ns();
      best = std::min(best, (t1 - t0) / (200.0 * NP));
      sink += lv[0];
    }
    printf("PRIMTIME std::log1p alone: %.4f ns/call\n", best);
  }
  printf("sink=%g\n", (double)sink);
  return 0;
}
