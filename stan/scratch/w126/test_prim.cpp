// W-126 gate (a): pcm_lpdf_gathered vs the composed stock path (the EXACT
// generated loop: rvalue/index_uni, segment, the user-fn body), bitwise on
// lp + every gradient component, both flag levels, all operand layouts,
// the real gpcm shape, priors-before-likelihood, and the throw set.
#include <stan/math/rev.hpp>
#include <stan/math/rev/prob/pcm_lpdf_gathered.hpp>
#include <stan/math/rev/fun/softmax.hpp>
#include <stan/math/rev/fun/cumulative_sum.hpp>
#include <stan/math/rev/fun/append_row.hpp>
#include <stan/math/rev/core/operator_subtraction.hpp>
#include <stan/math/prim/fun/segment.hpp>
#include <stan/model/indexing/index.hpp>
#include <stan/model/indexing/rvalue.hpp>
#include <stan/model/indexing/assign.hpp>
#include <stan/model/indexing/access_helpers.hpp>
#include <stan/math/rev/fun/accumulator.hpp>
#include <Eigen/Dense>
#include <cmath>
#include <iostream>
#include <random>
#include <string>
#include <vector>

#include "gpcm_data.inc"

using namespace stan;
using namespace stan::math;

static long g_checks = 0;
static long g_comps = 0;
static long g_fails = 0;

static Eigen::VectorXd to_vec(const std::vector<double>& v) {
  return Eigen::VectorXd::Map(v.data(), v.size());
}

template <typename VecT>
static inline double adj_at(const VecT& v, int k) {
  if constexpr (std::is_same_v<std::decay_t<VecT>,
                               var_value<Eigen::VectorXd>>) {
    return v.vi_->adj_.coeff(k);
  } else {
    return adjoint_of(v.coeff(k));
  }
}

// ---------------------------------------------------------------- stock arm
template <typename VecT, typename VecA, typename VecB>
static void run_stock(const std::vector<int>& y, const VecT& theta,
                      const std::vector<int>& jj, const VecA& alpha,
                      const std::vector<int>& ii, const VecB& beta,
                      const std::vector<int>& pos, const std::vector<int>& m,
                      bool with_priors, double& lp_out,
                      Eigen::VectorXd& g_out) {
  start_nested();
  accumulator<var> lp_accum;
  if (with_priors) {
    lp_accum.add(lognormal_lpdf<false>(alpha, 1.0, 1.0));
    lp_accum.add(normal_lpdf<false>(beta, 0.0, 3.0));
    lp_accum.add(normal_lpdf<false>(theta, 0.0, 1.0));
  }
  const int N = y.size();
  for (int n = 0; n < N; ++n) {
    var th = stan::model::rvalue(theta, "theta",
                                 stan::model::index_uni(jj[n]));
    var al = stan::model::rvalue(alpha, "alpha",
                                 stan::model::index_uni(ii[n]));
    auto seg = stan::math::segment(beta, pos[ii[n] - 1], m[ii[n] - 1]);
    var t = th * al;
    Eigen::Matrix<var, -1, 1> unsummed =
        append_row(rep_vector(0.0, 1), subtract(t, to_ref(seg)));
    Eigen::Matrix<var, -1, 1> cs = cumulative_sum(unsummed);
    auto p = softmax(cs);
    Eigen::Matrix<var, -1, 1> probs(p.rows());
    stan::model::assign(probs, p, "assigning variable probs");
    lp_accum.add(categorical_lpmf<false>(y[n] + 1, probs));
  }
  var lp = lp_accum.sum();
  grad(lp.vi_);
  lp_out = lp.val();
  const int J = theta.size(), I = alpha.size(), B = beta.size();
  g_out.resize(J + I + B);
  for (int j = 0; j < J; ++j) g_out[j] = adj_at(theta, j);
  for (int i = 0; i < I; ++i) g_out[J + i] = adj_at(alpha, i);
  for (int k = 0; k < B; ++k) g_out[J + I + k] = adj_at(beta, k);
  recover_memory_nested();
}

// ---------------------------------------------------------------- prim arm
template <typename VecT, typename VecA, typename VecB>
static void run_prim(const std::vector<int>& y, const VecT& theta,
                     const std::vector<int>& jj, const VecA& alpha,
                     const std::vector<int>& ii, const VecB& beta,
                     const std::vector<int>& pos, const std::vector<int>& m,
                     bool with_priors, double& lp_out,
                     Eigen::VectorXd& g_out) {
  start_nested();
  accumulator<var> lp_accum;
  if (with_priors) {
    lp_accum.add(lognormal_lpdf<false>(alpha, 1.0, 1.0));
    lp_accum.add(normal_lpdf<false>(beta, 0.0, 3.0));
    lp_accum.add(normal_lpdf<false>(theta, 0.0, 1.0));
  }
  auto terms = pcm_lpdf_gathered<false>(y, theta, jj, alpha, ii, beta, pos, m);
  for (const auto& t : terms) {
    lp_accum.add(t);
  }
  var lp = lp_accum.sum();
  grad(lp.vi_);
  lp_out = lp.val();
  const int J = theta.size(), I = alpha.size(), B = beta.size();
  g_out.resize(J + I + B);
  for (int j = 0; j < J; ++j) g_out[j] = adj_at(theta, j);
  for (int i = 0; i < I; ++i) g_out[J + i] = adj_at(alpha, i);
  for (int k = 0; k < B; ++k) g_out[J + I + k] = adj_at(beta, k);
  recover_memory_nested();
}

// run one comparison with all three operands at given layouts
template <int LT, int LA, int LB>
void compare_case(const std::vector<double>& th_v,
                  const std::vector<double>& al_v,
                  const std::vector<double>& b_v,
                  const std::vector<int>& y, const std::vector<int>& jj,
                  const std::vector<int>& ii, const std::vector<int>& pos,
                  const std::vector<int>& m, bool with_priors,
                  const char* tag) {
  const int J = th_v.size(), I = al_v.size(), B = b_v.size();
  double lp1, lp2;
  Eigen::VectorXd g1, g2;
  auto arm = [&](auto which, double& lp_out, Eigen::VectorXd& g_out) {
    start_nested();
    Eigen::Matrix<var, -1, 1> th_a(J), al_a(I), b_a(B);
    for (int j = 0; j < J; ++j) th_a[j] = var(th_v[j]);
    for (int i = 0; i < I; ++i) al_a[i] = var(al_v[i]);
    for (int k = 0; k < B; ++k) b_a[k] = var(b_v[k]);
    std::vector<var> th_buf(J), al_buf(I), b_buf(B);
    for (int j = 0; j < J; ++j) th_buf[j] = var(th_v[j]);
    for (int i = 0; i < I; ++i) al_buf[i] = var(al_v[i]);
    for (int k = 0; k < B; ++k) b_buf[k] = var(b_v[k]);
    auto th_map = Eigen::Map<const Eigen::Matrix<var, -1, 1>>(th_buf.data(), J);
    auto al_map = Eigen::Map<const Eigen::Matrix<var, -1, 1>>(al_buf.data(), I);
    auto b_map = Eigen::Map<const Eigen::Matrix<var, -1, 1>>(b_buf.data(), B);
    var_value<Eigen::VectorXd> th_soa(to_vec(th_v)), al_soa(to_vec(al_v)),
        b_soa(to_vec(b_v));
    auto th = [&]() -> decltype(auto) {
      if constexpr (LT == 0) return (th_a);
      else if constexpr (LT == 1) return (th_map);
      else return (th_soa);
    }();
    auto al = [&]() -> decltype(auto) {
      if constexpr (LA == 0) return (al_a);
      else if constexpr (LA == 1) return (al_map);
      else return (al_soa);
    }();
    auto b = [&]() -> decltype(auto) {
      if constexpr (LB == 0) return (b_a);
      else return (b_map);
    }();
    if constexpr (which == 0) {
      run_stock(y, th, jj, al, ii, b, pos, m, with_priors, lp_out, g_out);
    } else {
      run_prim(y, th, jj, al, ii, b, pos, m, with_priors, lp_out, g_out);
    }
    recover_memory_nested();
  };
  arm(std::integral_constant<int, 0>{}, lp1, g1);
  arm(std::integral_constant<int, 1>{}, lp2, g2);
  ++g_checks;
  g_comps += 1 + g1.size();  // lp + every gradient component
  bool ok = (lp1 == lp2) && (g1.size() == g2.size());
  for (int k = 0; ok && k < g1.size(); ++k) ok = (g1[k] == g2[k]);
  if (!ok) {
    ++g_fails;
    if (g_fails <= 5) {
      std::cout << "FAIL " << tag << " lp " << lp1 << " vs " << lp2 << "\n";
      for (int k = 0; k < g1.size(); ++k)
        if (g1[k] != g2[k])
          std::cout << "  g[" << k << "] " << g1[k] << " vs " << g2[k] << "\n";
    }
  }
}

template <int LT, int LA, int LB>
void dispatch(const std::vector<double>& th, const std::vector<double>& al,
              const std::vector<double>& b, const std::vector<int>& y,
              const std::vector<int>& jj, const std::vector<int>& ii,
              const std::vector<int>& pos, const std::vector<int>& m,
              bool priors, const char* tag) {
  compare_case<LT, LA, LB>(th, al, b, y, jj, ii, pos, m, priors, tag);
}

static void run_layout_combo(int LT, int LA, int LB,
                             const std::vector<double>& th,
                             const std::vector<double>& al,
                             const std::vector<double>& b,
                             const std::vector<int>& y,
                             const std::vector<int>& jj,
                             const std::vector<int>& ii,
                             const std::vector<int>& pos,
                             const std::vector<int>& m, bool priors,
                             const char* tag) {
  switch (LT * 9 + LA * 3 + LB) {
    case 0: dispatch<0, 0, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 1: dispatch<0, 0, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 3: dispatch<0, 1, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 4: dispatch<0, 1, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 6: dispatch<0, 2, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 7: dispatch<0, 2, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 9: dispatch<1, 0, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 10: dispatch<1, 0, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 12: dispatch<1, 1, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 13: dispatch<1, 1, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 15: dispatch<1, 2, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 16: dispatch<1, 2, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 18: dispatch<2, 0, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 19: dispatch<2, 0, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 21: dispatch<2, 1, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 22: dispatch<2, 1, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 24: dispatch<2, 2, 0>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
    case 25: dispatch<2, 2, 1>(th, al, b, y, jj, ii, pos, m, priors, tag); break;
  }
}



// run_* equivalents WITHOUT the nested guard (throw tests recover globally)
template <typename VecT, typename VecA, typename VecB>
static void run_stock_norecover(const std::vector<int>& y, const VecT& theta,
                                const std::vector<int>& jj, const VecA& alpha,
                                const std::vector<int>& ii, const VecB& beta,
                                const std::vector<int>& pos,
                                const std::vector<int>& m, double& lp_out,
                                Eigen::VectorXd& g_out) {
  accumulator<var> lp_accum;
  const int N = y.size();
  for (int n = 0; n < N; ++n) {
    var th = stan::model::rvalue(theta, "theta", stan::model::index_uni(jj[n]));
    var al = stan::model::rvalue(alpha, "alpha", stan::model::index_uni(ii[n]));
    auto seg = stan::math::segment(beta, pos[ii[n] - 1], m[ii[n] - 1]);
    var t = th * al;
    Eigen::Matrix<var, -1, 1> unsummed =
        append_row(rep_vector(0.0, 1), subtract(t, to_ref(seg)));
    Eigen::Matrix<var, -1, 1> cs = cumulative_sum(unsummed);
    auto p = softmax(cs);
    Eigen::Matrix<var, -1, 1> probs(p.rows());
    stan::model::assign(probs, p, "assigning variable probs");
    lp_accum.add(categorical_lpmf<false>(y[n] + 1, probs));
  }
  var lp = lp_accum.sum();
  grad(lp.vi_);
  lp_out = lp.val();
}

template <typename VecT, typename VecA, typename VecB>
static void run_prim_norecover(const std::vector<int>& y, const VecT& theta,
                               const std::vector<int>& jj, const VecA& alpha,
                               const std::vector<int>& ii, const VecB& beta,
                               const std::vector<int>& pos,
                               const std::vector<int>& m, double& lp_out,
                               Eigen::VectorXd& g_out) {
  accumulator<var> lp_accum;
  auto terms = pcm_lpdf_gathered<false>(y, theta, jj, alpha, ii, beta, pos, m);
  for (const auto& t : terms) lp_accum.add(t);
  var lp = lp_accum.sum();
  grad(lp.vi_);
  lp_out = lp.val();
}

// ------------------------------------------------------------ throw set
static long g_throw_checks = 0;
static long g_throw_fails = 0;

template <typename VecT, typename VecA, typename VecB>
static void try_stock(const std::vector<int>& y, const VecT& theta,
                      const std::vector<int>& jj, const VecA& alpha,
                      const std::vector<int>& ii, const VecB& beta,
                      const std::vector<int>& pos, const std::vector<int>& m,
                      std::string& msg) {
  try {
    double lp;
    Eigen::VectorXd g;
    run_stock_norecover(y, theta, jj, alpha, ii, beta, pos, m, lp, g);
    msg = "(no throw)";
  } catch (const std::exception& e) {
    msg = e.what();
  }
  recover_memory();
}

template <typename VecT, typename VecA, typename VecB>
static void try_prim(const std::vector<int>& y, const VecT& theta,
                     const std::vector<int>& jj, const VecA& alpha,
                     const std::vector<int>& ii, const VecB& beta,
                     const std::vector<int>& pos, const std::vector<int>& m,
                     std::string& msg) {
  try {
    double lp;
    Eigen::VectorXd g;
    run_prim_norecover(y, theta, jj, alpha, ii, beta, pos, m, lp, g);
    msg = "(no throw)";
  } catch (const std::exception& e) {
    msg = e.what();
  }
  recover_memory();
}

static void throw_case(const std::vector<double>& th_v,
                       const std::vector<double>& al_v,
                       const std::vector<double>& b_v,
                       const std::vector<int>& y, const std::vector<int>& jj,
                       const std::vector<int>& ii, const std::vector<int>& pos,
                       const std::vector<int>& m, const char* tag) {
  const int J = th_v.size(), I = al_v.size(), B = b_v.size();
  auto arm_throw = [&](int which, std::string& msg) {
    Eigen::Matrix<var, -1, 1> th_a(J), al_a(I), b_a(B);
    for (int j = 0; j < J; ++j) th_a[j] = var(th_v[j]);
    for (int i = 0; i < I; ++i) al_a[i] = var(al_v[i]);
    for (int k = 0; k < B; ++k) b_a[k] = var(b_v[k]);
    if (which == 0)
      try_stock(y, th_a, jj, al_a, ii, b_a, pos, m, msg);
    else
      try_prim(y, th_a, jj, al_a, ii, b_a, pos, m, msg);
  };
  std::string m1, m2;
  arm_throw(0, m1);
  arm_throw(1, m2);
  ++g_throw_checks;
  if (m1 != m2) {
    ++g_throw_fails;
    std::cout << "THROW-FAIL " << tag << "\n  stock: " << m1 << "\n  prim: "
              << m2 << "\n";
  }
}

int main() {
  std::mt19937 rng(20260829);
  std::uniform_real_distribution<double> U(-2.0, 2.0);

  // ---- P1: randomized shapes, all 27 layouts, N grid ----
  const int Ns[] = {1, 2, 3, 5, 8, 17, 100};
  for (int seed = 0; seed < 6; ++seed) {
    for (int N : Ns) {
      int I = 1 + (seed * 3 + N) % 6;
      int J = 1 + (seed * 5 + N) % 7;
      std::vector<int> m(I), pos(I);
      int tot = 0;
      for (int i = 0; i < I; ++i) {
        m[i] = 1 + (seed * 7 + i * 3 + N) % 7;  // K = 2..8
        pos[i] = tot + 1;
        tot += m[i];
      }
      std::vector<int> y(N), jj(N), ii(N);
      for (int n = 0; n < N; ++n) {
        jj[n] = 1 + (n * 7 + seed * 3) % J;
        ii[n] = 1 + (n * 5 + seed) % I;
        y[n] = (n * 11 + seed * 7) % (m[ii[n] - 1] + 1);  // 0..m
      }
      std::vector<double> th(J), al(I), b(tot);
      for (auto& x : th) x = U(rng);
      for (auto& x : al) x = U(rng) + 0.5;  // positive-ish
      for (auto& x : b) x = U(rng);
      char tag[64];
      std::snprintf(tag, 64, "P1 s%d N%d", seed, N);
      for (int LT = 0; LT < 3; ++LT)
        for (int LA = 0; LA < 3; ++LA)
          for (int LB = 0; LB < 2; ++LB)
            run_layout_combo(LT, LA, LB, th, al, b, y, jj, ii, pos, m, false,
                             tag);
    }
  }

  // ---- P1b: large N + y boundary values (all-min / all-max), 18 layouts ----
  for (int N : {919, 2000}) {
    int I = 5, J = 9;
    std::vector<int> m{1, 2, 3, 4, 7}, pos{1, 2, 4, 7, 11};
    std::vector<int> jj(N), ii(N), y(N);
    for (int n = 0; n < N; ++n) {
      jj[n] = 1 + (n * 7) % J;
      ii[n] = 1 + (n * 3) % I;
      y[n] = (N == 919) ? 0 : m[ii[n] - 1];  // all-min / all-max
    }
    std::vector<double> th(J), al(I), b(17);
    for (auto& x : th) x = U(rng);
    for (auto& x : al) x = U(rng) + 0.5;
    for (auto& x : b) x = U(rng);
    char tag[64];
    std::snprintf(tag, 64, "P1b N%d", N);
    for (int LT = 0; LT < 3; ++LT)
      for (int LA = 0; LA < 3; ++LA)
        for (int LB = 0; LB < 2; ++LB)
          run_layout_combo(LT, LA, LB, th, al, b, y, jj, ii, pos, m, false,
                           tag);
  }

  // ---- P2: the REAL gpcm shape (N=5500), the model's layout (Map/AoS mix)
  //          plus all-27 on a subsample ----
  {
    std::vector<int> y(gy, gy + gN), ii(gii, gii + gN), jj(gjj, gjj + gN);
    std::vector<int> m(gm, gm + gI), pos(gpos, gpos + gI);
    std::vector<double> th(gJ), al(gI), b(gB);
    for (auto& x : th) x = U(rng);
    for (auto& x : al) x = U(rng) * 0.5 + 1.0;
    for (auto& x : b) x = U(rng);
    run_layout_combo(1, 1, 0, th, al, b, y, jj, ii, pos, m, false, "P2 real");
    run_layout_combo(0, 0, 0, th, al, b, y, jj, ii, pos, m, false, "P2 real");
    run_layout_combo(2, 2, 2, th, al, b, y, jj, ii, pos, m, false, "P2 real");
  }

  // ---- P3: priors BEFORE the likelihood (the model's statement order),
  //          AoS/Map combos (this math's normal_lpdf takes AoS/Map) ----
  {
    int I = 4, J = 5, N = 40;
    std::vector<int> m{2, 1, 3, 2}, pos{1, 3, 4, 7};
    std::vector<int> y(N), jj(N), ii(N);
    for (int n = 0; n < N; ++n) {
      jj[n] = 1 + (n * 7) % J;
      ii[n] = 1 + (n * 3) % I;
      y[n] = n % (m[ii[n] - 1] + 1);
    }
    std::vector<double> th(J), al(I), b(8);
    for (auto& x : th) x = U(rng);
    for (auto& x : al) x = std::abs(U(rng)) + 0.5;  // positive: lognormal prior
    for (auto& x : b) x = U(rng);
    for (int LT = 0; LT < 2; ++LT)
      for (int LA = 0; LA < 2; ++LA)
        for (int LB = 0; LB < 2; ++LB)
          run_layout_combo(LT, LA, LB, th, al, b, y, jj, ii, pos, m, true,
                           "P3 priors");
  }

  // ---- throw set ----
  {
    int I = 3, J = 3;
    std::vector<int> m{2, 1, 3}, pos{1, 3, 4};
    std::vector<double> th{0.5, -0.8, 1.1}, al{1.2, 0.9, 1.5},
        b{0.1, -0.2, 0.3, -0.4, 0.5, 0.6};
    std::vector<int> jj{1, 2, 3}, ii{1, 2, 3};
    std::vector<int> yOK{0, 1, 2};
    // baseline: no throw
    throw_case(th, al, b, yOK, jj, ii, pos, m, "TS-baseline");
    // y out of range (low/high per item)
    {
      auto y = yOK; y[0] = -1;
      throw_case(th, al, b, y, jj, ii, pos, m, "TS-y-low");
    }
    {
      auto y = yOK; y[0] = 3;  // item 0 has K=3 (m=2): y+1=4 > 3
      throw_case(th, al, b, y, jj, ii, pos, m, "TS-y-high");
    }
    {
      auto y = yOK; y[2] = 4;  // item 2 has K=4 (m=3)
      throw_case(th, al, b, y, jj, ii, pos, m, "TS-y-high2");
    }
    // non-finite parameters -> non-simplex p
    {
      auto th2 = th; th2[1] = std::nan("");
      throw_case(th2, al, b, yOK, jj, ii, pos, m, "TS-theta-nan");
    }
    {
      auto th3 = th; th3[2] = INFINITY;
      throw_case(th3, al, b, yOK, jj, ii, pos, m, "TS-theta-inf");
    }
    {
      auto al2 = al; al2[0] = std::nan("");
      throw_case(th, al2, b, yOK, jj, ii, pos, m, "TS-alpha-nan");
    }
    {
      auto b2 = b; b2[2] = std::nan("");
      throw_case(th, al, b2, yOK, jj, ii, pos, m, "TS-beta-nan");
    }
    // out-of-range indices
    {
      auto jj2 = jj; jj2[1] = 0;
      throw_case(th, al, b, yOK, jj2, ii, pos, m, "TS-jj-0");
    }
    {
      auto jj3 = jj; jj3[2] = 4;
      throw_case(th, al, b, yOK, jj3, ii, pos, m, "TS-jj-hi");
    }
    {
      auto ii2 = ii; ii2[0] = 0;
      throw_case(th, al, b, yOK, jj, ii2, pos, m, "TS-ii-0");
    }
    {
      auto ii3 = ii; ii3[1] = 4;
      throw_case(th, al, b, yOK, jj, ii3, pos, m, "TS-ii-hi");
    }
    // N = 0
    throw_case(th, al, b, {}, {}, {}, pos, m, "TS-N0");
  }

  std::cout << "==== GATE (a): " << g_checks << " cases / " << g_comps
            << " bitwise component checks, " << g_fails
            << " mismatches + " << g_throw_checks << " throw checks, "
            << g_throw_fails << " throw mismatches => "
            << ((g_fails + g_throw_fails) == 0 ? "PASS" : "FAIL")
            << " ====" << std::endl;
  return (g_fails + g_throw_fails) != 0;
}
