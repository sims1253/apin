// W-45 harness tool: data-subsampled warmup transplant. NOT part of
// walnutpie — a standalone consumer of the walnutpie HEADERS (header-only
// library), compiled with the same include set as
// external/walnutpie/build_w36exp/examples/stan_cli (read-only binary,
// @43b6435). The FULL/WARMUP modes replicate stan_cli's single-chain path
// exactly (same seeding, same StanHandler, same CSV writer, same timing
// stanzas); SAMPLE mode injects a previously dumped frozen state into the
// FULL-data model with warmup=0 (V1) or with a find_reasonable_step
// re-tune first (V2 — the library's own --step-init-heuristic code path).
//
// Usage:
//   w45_run full   <model.so> <data.json> --seed S --init-file F \
//                   --warmup N --samples N --output out.csv \
//                   --dump-state state.txt
//   w45_run warmup <model.so> <data.json> --seed S --init-file F \
//                   --warmup N --dump-state state.txt
//   w45_run sample <model.so> <data.json> --seed S --load-state state.txt \
//                   [--retune-step] --samples N --output out.csv
//
// State file (text, %.17g round-trip):
//   dim D / step S / min_micro M / lp L
//   inv_mass D values / position D values
#include <walnutpie.hpp>
#include <walnutpie/load_stan.hpp>
#include <walnutpie/warmup_heuristics.hpp>

#include <chrono>
#include <cmath>
#include <cstddef>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <Eigen/Dense>

using walnutpie::DynamicStanModel;
using walnutpie::unique_bs_rng;

// ---- verbatim from stan_cli.cpp (FULL-mode CSVs are byte-identical) ----
static void write_draws(std::string& output_file,
                        const std::vector<std::string>& names,
                        const Eigen::MatrixXd& draws) {
  std::ofstream out(output_file);
  for (std::size_t i = 0; i < names.size(); ++i) {
    out << (i > 0 ? "," : "") << names[i];
  }
  out << "\n";
  auto EigenCommaFormat =
      Eigen::IOFormat(12, Eigen::DontAlignCols, ",", "\n", "", "", "", "");
  out << draws.transpose().format(EigenCommaFormat);
  out.close();
}

class StanHandler {
 public:
  StanHandler(DynamicStanModel& model, unsigned int seed,
              std::size_t num_warmup, std::size_t num_draws, bool save_warmup)
      : model_(model),
        rng_(model.make_rng(seed + 1)),
        draws_(model.constrained_dimensions(),
               num_draws + static_cast<std::size_t>(save_warmup) * num_warmup),
        save_warmup_(save_warmup) {}

  void on_sample(const Eigen::VectorXd& position, double lp) {
    model_.constrain_draw(position, draws_.col(n_), rng_);
    n_++;
  }

  void on_warmup(const Eigen::VectorXd& position, double lp, double step_size,
                 const Eigen::VectorXd& diag_inv_mass) {
    // W-45: record the final warmup state verbatim (position is theta_
    // after the last transition — exactly what sampler() freezes).
    last_position_ = position;
    last_lp_ = lp;
    last_step_ = step_size;
    last_invm_ = diag_inv_mass;
    if (!save_warmup_) {
      return;
    }
    model_.constrain_draw(position, draws_.col(n_), rng_);
    n_++;
  }

  void on_warmup_complete(double step_size,
                          const Eigen::VectorXd& diag_inv_mass) {}

  void on_logp_exception(const Eigen::VectorXd& position,
                         const std::exception& exn) const noexcept {
    std::cout << "Logp failed with exception " << exn.what() << " at "
              << position.transpose() << "\n";
  }

  void write_csv(std::string& output_file) {
    auto names = model_.param_names();
    ::write_draws(output_file, names, draws_);
  }

  const Eigen::VectorXd& last_position() const { return last_position_; }
  double last_lp() const { return last_lp_; }
  double last_step() const { return last_step_; }
  const Eigen::VectorXd& last_invm() const { return last_invm_; }

 private:
  DynamicStanModel& model_;
  unique_bs_rng rng_;
  Eigen::MatrixXd draws_;
  bool save_warmup_;
  Eigen::Index n_ = 0;
  Eigen::VectorXd last_position_;
  Eigen::VectorXd last_invm_;
  double last_lp_ = std::numeric_limits<double>::quiet_NaN();
  double last_step_ = std::numeric_limits<double>::quiet_NaN();
};

struct DumpedState {
  Eigen::Index dim;
  double step;
  std::size_t min_micro;
  double lp;
  Eigen::VectorXd inv_mass;
  Eigen::VectorXd position;
};

static void dump_state(const std::string& path, double step,
                       std::size_t min_micro, double lp,
                       const Eigen::VectorXd& inv_mass,
                       const Eigen::VectorXd& position) {
  std::ofstream out(path);
  out << std::setprecision(17);
  out << "dim " << inv_mass.size() << "\n";
  out << "step " << step << "\n";
  out << "min_micro " << min_micro << "\n";
  out << "lp " << lp << "\n";
  out << "inv_mass";
  for (Eigen::Index i = 0; i < inv_mass.size(); ++i) {
    out << " " << inv_mass[i];
  }
  out << "\n";
  out << "position";
  for (Eigen::Index i = 0; i < position.size(); ++i) {
    out << " " << position[i];
  }
  out << "\n";
}

static DumpedState load_state(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    throw std::invalid_argument("cannot open state file: " + path);
  }
  DumpedState s;
  std::string tag;
  in >> tag >> s.dim >> tag >> s.step >> tag >> s.min_micro >> tag >> s.lp;
  s.inv_mass.resize(s.dim);
  s.position.resize(s.dim);
  in >> tag;
  for (Eigen::Index i = 0; i < s.dim; ++i) {
    in >> s.inv_mass[i];
  }
  in >> tag;
  for (Eigen::Index i = 0; i < s.dim; ++i) {
    in >> s.position[i];
  }
  if (!in) {
    throw std::invalid_argument("malformed state file: " + path);
  }
  return s;
}

static Eigen::VectorXd read_init_file(const std::string& init_file,
                                      Eigen::Index dims) {
  std::ifstream in(init_file);
  if (!in) {
    throw std::invalid_argument("cannot open --init-file: " + init_file);
  }
  std::vector<double> vals;
  double v;
  while (in >> v) {
    vals.push_back(v);
  }
  if (static_cast<Eigen::Index>(vals.size()) != dims) {
    throw std::invalid_argument("--init-file dimension mismatch: file has " +
                                std::to_string(vals.size()) +
                                ", model has " + std::to_string(dims));
  }
  return Eigen::VectorXd(Eigen::VectorXd::Map(vals.data(), vals.size()));
}

// ---- the CLI's timing stanza, verbatim structure ----
using Clock = std::chrono::high_resolution_clock;
struct Timers {
  double logp_time = 0.0;
  std::size_t logp_count = 0;
  Clock::time_point global_start;
  void reset() {
    logp_time = 0.0;
    logp_count = 0;
    global_start = Clock::now();
  }
  void end() const {
    auto total = std::chrono::duration<double>(Clock::now() - global_start)
                     .count();
    std::cout << "    total time: " << total << "s" << std::endl;
    std::cout << "logp_grad time: " << logp_time << "s" << std::endl;
    std::cout << "logp_grad fraction: " << logp_time / total << std::endl;
    std::cout << "        logp_grad calls: " << logp_count << std::endl;
    std::cout << "        time per call: " << logp_time / logp_count << "s"
              << std::endl;
    std::cout << std::endl;
  }
};

// CLI-default configs, copied verbatim from stan_cli.cpp (every value is
// initialized FROM WarmupConfigBuilder()/SamplingConfigBuilder() defaults).
static walnutpie::WarmupConfig default_warmup_cfg() {
  walnutpie::WarmupConfig d = walnutpie::WarmupConfigBuilder().build();
  return walnutpie::WarmupConfigBuilder()
      .mass_init_count(d.mass_init_count())
      .mass_additive_smoothing(d.mass_additive_smoothing())
      .max_macro_steps_target(d.max_macro_steps_target())
      .step_accept_rate_target(d.step_accept_rate_target())
      .step_learning_rate(d.step_learning_rate())
      .step_gradient_decay(d.step_gradient_decay())
      .step_sq_gradient_decay(d.step_sq_gradient_decay())
      .step_stabilization(d.step_stabilization())
      .step_learn_rate_decay(d.step_learn_rate_decay())
      .da_gamma(d.da_gamma())
      .da_t0(d.da_t0())
      .da_kappa(d.da_kappa())
      .step_opt_batch_stride(1)
      .step_grad_clip(0.0)
      .da_freeze_average(false)
      .mass_shrink_kappa(0.0)
      .mass_var_floor(0.0)
      .mass_init_clamp(0.0)
      .metric_drift_guard(false)
      .mass_combine_power(0.0)
      .metric_collapse_reset(0.0)
      .metric_stall_reset(0.0)
      .anti_windup_pass_rate(0)
      .drift_iters(0)
      .max_error_schedule(0.0, 0)
      .metric_window(0)
      .metric_rank(0)
      .metric_basis(0)
      .metric_full(false)
      .metric_auto(0.0)
      .temporal_step_drift_tol(0.0)
      .temporal_window(50)
      .temporal_min_iter(200)
      .build();
}

static walnutpie::SamplingConfig default_sample_cfg() {
  walnutpie::SamplingConfig d = walnutpie::SamplingConfigBuilder().build();
  return walnutpie::SamplingConfigBuilder()
      .max_trajectory_doublings(d.max_trajectory_doublings())
      .max_step_halvings(d.max_step_halvings())
      .max_hamiltonian_error(d.max_hamiltonian_error())
      .min_micro_steps(d.min_micro_steps())
      .build();
}

int main(int argc, char** argv) {
  if (argc < 4) {
    std::cerr << "usage: w45_run {full|warmup|sample} model.so data.json "
                 "[--seed S] [--init-file F] [--warmup N] [--samples N] "
                 "[--output out.csv] [--dump-state s.txt] "
                 "[--load-state s.txt] [--retune-step]\n";
    return 2;
  }
  std::string mode = argv[1];
  std::string lib = argv[2];
  std::string data = argv[3];
  unsigned long seed = 0;
  bool have_seed = false;
  std::string init_file, output_file, dump_path, load_path;
  std::size_t num_warmup = 1000, num_draws = 1000;
  bool retune = false;
  for (int i = 4; i < argc; ++i) {
    std::string a = argv[i];
    auto next = [&]() -> std::string {
      if (i + 1 >= argc) {
        throw std::invalid_argument("missing value for " + a);
      }
      return argv[++i];
    };
    if (a == "--seed") {
      seed = std::stoul(next());
      have_seed = true;
    } else if (a == "--init-file") {
      init_file = next();
    } else if (a == "--warmup") {
      num_warmup = std::stoul(next());
    } else if (a == "--samples") {
      num_draws = std::stoul(next());
    } else if (a == "--output") {
      output_file = next();
    } else if (a == "--dump-state") {
      dump_path = next();
    } else if (a == "--load-state") {
      load_path = next();
    } else if (a == "--retune-step") {
      retune = true;
    } else {
      throw std::invalid_argument("unknown argument " + a);
    }
  }
  if (!have_seed) {
    throw std::invalid_argument("--seed is required (reproducibility)");
  }

  auto warmup_cfg = default_warmup_cfg();
  auto sample_cfg = default_sample_cfg();

  DynamicStanModel model(lib.c_str(), data.c_str(), seed);
  unique_bs_rng model_rng = model.make_rng(seed);  // CLI parity (unused)

  Timers t;  // one counter pair, reset between phases — CLI structure

  if (mode == "full" || mode == "warmup") {
    if (init_file.empty()) {
      throw std::invalid_argument("full/warmup modes require --init-file");
    }
    if (mode == "warmup") {
      num_draws = 0;
      output_file.clear();
    }
    auto logp = [&](auto&&... args) {
      auto start = Clock::now();
      model.logp_grad(args...);
      t.logp_time +=
          std::chrono::duration<double>(Clock::now() - start).count();
      ++t.logp_count;
    };

    StanHandler storage(model, seed, num_warmup, num_draws, false);
    auto init_positions =
        read_init_file(init_file, model.unconstrained_dimensions());
    auto init_cfg =
        walnutpie::InitConfigBuilder{1, model.unconstrained_dimensions()}
            .step_sizes(1.0)
            .positions(init_positions)
            .masses(logp, warmup_cfg.mass_additive_smoothing(), false, 0.0)
            .build();
    auto inits = init_cfg.init_chain_config(0);
    std::mt19937_64 rng{seed};

    walnutpie::AdaptiveWalnuts<decltype(logp), decltype(rng), StanHandler,
                               walnutpie::detail::Adam>
        walnuts(rng, storage, logp, inits, warmup_cfg, sample_cfg);
    t.reset();
    for (std::size_t w = 0; w < num_warmup; ++w) {
      walnuts();
    }
    t.end();

    auto sampler = walnuts.sampler();  // freeze tuning
    std::cout << "Macro time = " << sampler.macro_time() << std::endl;
    double frozen_step = walnuts.step_size();
    std::size_t frozen_min_micro = walnuts.min_micro_steps();
    Eigen::VectorXd frozen_invm = walnuts.inv_mass();

    if (num_draws > 0) {
      t.reset();
      for (std::size_t n = 0; n < num_draws; ++n) {
        sampler();
      }
      t.end();
      storage.write_csv(output_file);
    }
    if (!dump_path.empty()) {
      dump_state(dump_path, frozen_step, frozen_min_micro,
                 storage.last_lp(), frozen_invm, storage.last_position());
    }
    return 0;
  }

  if (mode == "sample") {
    if (load_path.empty() || output_file.empty()) {
      throw std::invalid_argument(
          "sample mode requires --load-state and --output");
    }
    DumpedState st = load_state(load_path);
    if (st.dim != static_cast<Eigen::Index>(model.unconstrained_dimensions())) {
      throw std::invalid_argument(
          "state/model dimension mismatch: state has " +
          std::to_string(st.dim) + ", model has " +
          std::to_string(model.unconstrained_dimensions()));
    }
    auto logp = [&](auto&&... args) {
      auto start = Clock::now();
      model.logp_grad(args...);
      t.logp_time +=
          std::chrono::duration<double>(Clock::now() - start).count();
      ++t.logp_count;
    };

    StanHandler storage(model, seed, 0, num_draws, false);
    std::mt19937_64 rng{seed};

    // W-42 lesson: never start a chain at a non-finite-logp position.
    // One explicit full-data evaluation both guards this and seeds the
    // frozen sampler's endpoint cache (freeze-boundary semantics).
    Eigen::VectorXd grad0;
    double lp0;
    logp(st.position, lp0, grad0);
    if (!std::isfinite(lp0)) {
      std::cerr << "W45 ABORT: transplanted position has non-finite logp ("
                << lp0 << ") on the full-data model" << std::endl;
      return 3;
    }

    double step = st.step;
    if (retune) {
      // V2: the CLI's --step-init-heuristic code path, verbatim, with the
      // transplanted inv_mass on the FULL-data model.
      walnutpie::detail::Random heur_rand(rng);
      step = walnutpie::detail::find_reasonable_step(
          heur_rand, logp, st.position, st.inv_mass, 1.0);
      std::cout << "Heuristic retuned step size: " << step << std::endl;
    }

    t.reset();
    walnutpie::WalnutsSampler<decltype(logp), std::mt19937_64, StanHandler>
        sampler(rng, storage, logp, st.position, st.inv_mass, step,
                sample_cfg.max_trajectory_doublings(),
                sample_cfg.max_step_halvings(), st.min_micro,
                sample_cfg.max_hamiltonian_error());
    sampler.seed_endpoint_cache(grad0, lp0);
    for (std::size_t n = 0; n < num_draws; ++n) {
      sampler();
    }
    t.end();
    storage.write_csv(output_file);
    return 0;
  }

  std::cerr << "unknown mode " << mode << std::endl;
  return 2;
}
