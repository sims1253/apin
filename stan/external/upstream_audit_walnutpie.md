# Upstream audit — walnutpie dev branches vs `origin/main`

**Date:** 2026-08-21 (audit session)
**Repo:** `/home/m0hawk/Documents/apin/stan/external/walnutpie`
**Upstream:** `origin/main` = `6162d88` ("Merge pull request #93 from flatironinstitute/update-eigen").
Note: upstream history is a single squashed root — `git blame origin/main` attributes every upstream line to `^6162d88` (Bob Carpenter, 2026-08-14), so "present in origin/main" is proven by tree content + `-S` searches returning only `6162d88`.

**Branch inventory** (all dev branches are linear descendants of `6162d88`):

| branch | tip | relation to `dev/init-robustness` |
|---|---|---|
| `dev/pluggable-step-optimizers` | `250e5b3` | ancestor |
| `dev/adaptation-hardening` | `980c249` | ancestor |
| `dev/mass-matrix-shrinkage` | `9337fa9` | ancestor |
| `nindan-stepopt` | `0e2df0c` | ancestor |
| `dev/init-robustness` | `52051c9` | audited here (17 commits) |
| `dev/research-optimizer-notes` | `1edf39b` | **2 extra commits** (`134b194`, `1edf39b`), docs only |
| `upstream/adapt-with-stats` | `9361710` | **1 extra commit** on top of `origin/main` directly (parent = `6162d88`) |

Method: read-only git (`show`/`log -S`/`blame`/`grep`/`diff`). No builds, no test runs.

---

## 1. Bug provenance: B1, B1b, B2

### B1 — "sampler() drops the low-rank metric at freeze" (fix commit `5e56ff2`)

**Verdict: OURS (dev-branch bug). Not present in `origin/main` in any form.**

Evidence:

1. **The pre-fix lines exist upstream, but are not a bug upstream.** The fix's pre-image,
   `include/walnutpie/walnuts.hpp` (upstream lines 686–689):
   ```cpp
   theta_ = transition_w(rand_, logp_grad_, inv_mass_, cholesky_mass_,
                         macro_time_, max_nuts_depth_, max_step_halvings_,
                         min_micro_steps_, max_error_, std::move(theta_),
                         depth, grad_next, logp_pos, no_op_step_size_adapter_);
   ```
   is verbatim `origin/main` content (`git blame origin/main -L 683,700 -- include/walnutpie/walnuts.hpp` → `^6162d88`; `git log origin/main -S"theta_ = transition_w(rand_, logp_grad_, inv_mass_, cholesky_mass_,"` → only `6162d88`). Upstream has **only** a diagonal metric; a diagonal-only frozen sampler is exactly correct there.
2. **The bug requires our low-rank machinery, which does not exist upstream.** `git log origin/main -S"low_rank"` / `-S"LowRankMass"` / `-S"metric_full"` / `-S"transition_w_lr"` → all empty. `include/walnutpie/low_rank_mass.hpp` and `low_rank_metric.hpp` first appear in our `cc98377`/`5302ed8`.
3. **The exact buggy state (warmup under full operator, sampler diagonal) was never committed.** At the fix's parent `cc98377` the full operator was *not wired in at all* (commit message: "Integration into transition_w intentionally NOT wired yet … reverted cleanly"). `metric_full` and `transition_w_lr` were introduced and fixed **inside** `5e56ff2` itself.
4. **But a committed instance of the same mismatch exists in *fold* mode since `5302ed8`:** warmup `operator()()` used `rank_folded_estimate()` (folded diagonal) while `inv_mass()` (used by `sampler()` to freeze) returned the **unfolded** `inv_mass_estimate()` — compare `adaptive_walnuts.hpp` at `5302ed8`/`cc98377` line 638–640 vs the `operator()()` body. That is a silent warmup-vs-freeze metric mismatch introduced on our dev branch (`5302ed8`, "low-rank Fisher metric (first integration)").
5. **Residual at HEAD (`52051c9`):** the fold-mode mismatch is *still there*. `adaptive_walnuts.hpp:749–751` (`inv_mass()` returns `mass_estimator_.inv_mass_estimate()`) vs the `rank_active` branch of `operator()()` which transitions under `rank_folded_estimate()`. `5e56ff2` only forwarded factors for `metric_full` mode.

### B1b — "reversible()/uturn() evaluated under a different Hamiltonian than the one integrated" (fix commit `5e56ff2`)

**Verdict: OURS (dev-branch bug, never even committed in buggy form). Upstream is self-consistent.**

Evidence:

1. `reversible()` and `uturn()` are upstream functions (`origin/main` `walnuts.hpp:255` and `:193`; `git log origin/main -S"return reversible(logp_grad, inv_mass, step, num_steps, min_micro_steps,"` → only `6162d88`). Upstream calls them with the **same** `inv_mass` used for integration (`macro_step` passes the identical `inv_mass` to the leapfrog and to `reversible()`, `walnuts.hpp:340`; `transition_w`'s combined check uses the same `inv_mass`, `walnuts.hpp:546`). No metric mismatch exists upstream.
2. The mismatch is only possible under the full low-rank operator (`transition_w_lr`), which first exists in `5e56ff2` — already together with the corrected `reversible_lr`/`uturn_lr`/`within_tolerance_lr`. No commit in any ref contains `reversible(logp_grad, lrm.D` or the buggy `uturn`-with-`lrm.D`-in-`build_span_lr` form (scanned every commit in `refs/heads` + `refs/remotes`). The buggy state was an intra-commit working-tree state only.
3. **Residual at HEAD:** `walnuts.hpp:780` (dev) — inside `transition_w_lr`, the *combined-span* termination check is still the diagonal `uturn<D>(span_accum, *maybe_next_span, lrm.D)` while the trajectory is integrated under the full operator. Same bug class as B1b, one call site missed by the fix (the within-`build_span_lr` check was converted to `uturn_lr`, this one was not).

### B2 — "anti-windup adapter double-wrap" (fix commit `52051c9`)

**Verdict: OURS (dev-branch bug; the double-wrap state was never committed — the committed pre-fix state had a single wrap).**

Evidence:

1. **All machinery is ours.** `git log origin/main -S"AntiWindupAdapter"` and `-S"anti_windup"` → empty. `AntiWindupAdapter` + `--anti-windup` CLI introduced in `2260f29`; `StepAdapterFactory` in `250e5b3`; `ClippedAdapter` in `980c249`.
2. **The double-wrap state never existed as a commit.** Scanned every commit reachable from every ref for the co-occurrence of the library default `Opt = detail::AntiWindupAdapter<detail::Adam>` and the CLI `if (anti_windup > 0)` template dispatch: zero hits. `52051c9` introduced the library default wrap **and** removed the CLI wrap atomically. The committed pre-fix state (`a091334`) was: CLI-side single wrap `ClippedAdapter<AntiWindupAdapter<Opt>>` (stan_cli.cpp:588–594 at `a091334`) + plain-`Adam` library default + `warmup_cfg.anti_windup_pass_rate(anti_windup)` set (stan_cli.cpp:530) — i.e., **one** `AntiWindupAdapter` with `pass_rate = anti_windup`.
3. **The session's causal story is imprecise.** A single wrap with `pass_rate = 64` passes 1-in-64 → "drops 63/64 observations" is exactly single-wrap semantics; a true double wrap (both layers rate 64) would drop 4095/4096. Whatever produced the sd=0 chains, every candidate line is ours, not upstream's.
4. **Post-fix regression found during this audit: the CLI `--anti-windup` flag is now inert.** The CLI always passes an explicit `Opt` (e.g. `run_walnuts<Adam>`, stan_cli.cpp:596–608 at HEAD) → `AdaptiveWalnuts<..., Adam>` → `make_configured_adapter<Adam>` → `StepAdapterFactory<Adam>::make`, which returns a **plain `Adam`** (no wrap; the `AntiWindupAdapter<Inner>` factory specialization only fires if the type itself is `AntiWindupAdapter<...>`). The config field `anti_windup_pass_rate` is therefore dead in the CLI path; only library users relying on the *default* template argument get the wrap. The fix's validation ("single-wrap run matches pass-through run") is trivially explained: both runs had **no** wrap at all.

---

## 2. Hunk audit: `git diff origin/main..dev/init-robustness`

Total: 13 files, +2222/−42, 51 hunks. **35 pure-addition hunks** (incl. 6 new files: `low_rank_mass.hpp`, `low_rank_metric.hpp`, `step_optimizers.hpp`, `warmup_heuristics.hpp`, `tests/leapfrog_property_test.cpp`, `tests/low_rank_metric_test.cpp`) — automatic extensions, skipped per task instructions. **16 hunks modify or delete upstream lines** (42 upstream lines). All enumerated below.

| # | File : upstream lines | Upstream lines removed/changed (essence) | Dev commit(s) | Classification |
|---|---|---|---|---|
| 1 | `examples/stan_cli.cpp:113–123` | `run_walnuts` signature: + template `<typename Opt>`, + 2 defaulted params (`mass_init_clamp=0.0`, `step_init_heuristic=false`) | `250e5b3`, `0e2df0c` | **refactor-for-extension** (defaulted params keep upstream call shape) |
| 2 | `examples/stan_cli.cpp:147–159` | `init_builder.masses(...)` gains `false, mass_init_clamp` args; `AdaptiveWalnuts` declared with explicit `<Opt>`; + step-init heuristic block | `250e5b3`, `0e2df0c` | **refactor-for-extension** |
| 3 | `examples/stan_cli.cpp:282–289` | `--step-accept-rate-target`: **deleted `->check(CLI::Range(min, 1.0))`** | `250e5b3` | **incidental deletion (collateral)** — not a fix, not needed by any feature. Validation still enforced later (`WarmupConfigBuilder::step_accept_rate_target` → `validate_probability`, config.hpp:819), so severity is low (error surfaces at config build instead of CLI parse). Recommend restoring. |
| 4 | `examples/stan_cli.cpp:351–363` | inline `model.initialize(...)` replaced by `init_positions` lambda (+`--init-file`); `run_walnuts` call replaced by optimizer-dispatch lambda | `fdd77ec`, `250e5b3` | **refactor-for-extension** |
| 5 | `include/walnutpie/adapt.hpp:220–226` | `return {geom_mean_mass, std::exp(mean_log_step)};` → + third aggregate member `log_mass_dispersion` (defaulted `0.0`, upstream 2-arg init still compiles) | `7afbf14` | **extension** |
| 6 | `include/walnutpie/adaptive_walnuts.hpp:52–58` | `MassEstimator` ctor init-list: + `init_score_var_`, `init_draw_var_` seed members | `172b993`, `9337fa9` | **extension** |
| 7 | `include/walnutpie/adaptive_walnuts.hpp:86–96` | `inv_mass_estimate()` body rewritten: upstream 4-line `sqrt(draw_var/score_var)` replaced by option-gated pipeline (drift-guard log-average, Stan-style shrinkage, variance floor, power-mean combine) | `172b993`, `9337fa9`, `fdd77ec` | **refactor-for-extension** — with all knobs at defaults (`metric_drift_guard_=false`, `mass_shrink_kappa_=0`, `mass_var_floor_=0`, `mass_combine_power_=0`) the returned vector is mathematically identical to upstream (`sqrt(draw·(1/score))`; only sub-ulp float-association differs) |
| 8 | `include/walnutpie/adaptive_walnuts.hpp:179–185` | class template gains `Opt` param; **default changed `Adam` → `AntiWindupAdapter<Adam>`** | `250e5b3` (param, default `Adam`), `52051c9` (default → `AntiWindupAdapter<Adam>`) | **refactor-for-extension** — behaviorally identical at default config (pass_rate 0 = pass-through) but changes the public default type; API-visible |
| 9 | `include/walnutpie/adaptive_walnuts.hpp:213–223` | ctor: `adam_(...)` 7-line init → `opt_(make_configured_adapter<Opt>(...))` | `250e5b3`, `52051c9` | **refactor-for-extension** |
| 10 | `include/walnutpie/adaptive_walnuts.hpp:231–250` | `operator()()` rewritten: drift phase, metric windows, rank-fold/full metric, max-error schedule, NoOp adapter during drift | `2260f29`, `5302ed8`, `1433e9f`, `5e56ff2` | **refactor-for-extension** — every gate defaults off (`drift_iters_=0`, `metric_window_=0`, `metric_rank_=0`, `metric_full_=false`, `metric_auto_=0`, `max_error_start_=0`); default path is behaviorally identical to upstream |
| 11 | `include/walnutpie/adaptive_walnuts.hpp:262–273` | `sampler()`: `return WalnutsSampler(...)` → named `out` + conditional `set_low_rank(U, c)` (the B1 fix) | `5e56ff2` | **extension** (gate `metric_rank>0 && metric_full` default false) |
| 12 | `include/walnutpie/adaptive_walnuts.hpp:284–290` | `step_size()`: `adam_` → `opt_` | `250e5b3` | **refactor-for-extension** |
| 13 | `include/walnutpie/adaptive_walnuts.hpp:351–359` | member `detail::Adam adam_;` → `Opt opt_;` | `250e5b3` | **refactor-for-extension** |
| 14 | `include/walnutpie/config.hpp:359–365` | `InitConfigBuilder::masses(...)` + defaulted `clamp = 0.0` param (body clamps only `if (clamp > 0)`) | `0e2df0c` | **extension** |
| 15 | `include/walnutpie/online_moments.hpp:152–158` | `OnlineMoments` ctor init-list: + `init_weight_`, `sum_sq_dev_init_` (seeds for shrinkage/reset) | `9337fa9`, `172b993` | **extension** |
| 16 | `include/walnutpie/walnuts.hpp:683–696` | `WalnutsSampler::operator()()`: upstream `transition_w` call moved verbatim into `else` branch; new `if (lrm_.U.cols() > 0)` low-rank branch (the B1 fix) | `5e56ff2` | **extension** (upstream path preserved character-for-character) |

### Other branches with commits not reachable from `dev/init-robustness`

| Branch / commits | Upstream-line-touching hunks | Classification |
|---|---|---|
| `upstream/adapt-with-stats` (`9361710`, parent = `origin/main`): `include/walnutpie/adapt.hpp` +56/−1 | **1**: `adapt.hpp:220–226` — same controller_loop return extension as hunk 5, plus pure-add `adapt_with_stats()` (upstream's `void adapt()` discards its `AdaptResult`; `9361710` adds a returning overload, `adapt()` untouched) | **extension** (both the struct field and the new overload; deliberately isolated as an upstream-PR candidate) |
| `dev/research-optimizer-notes` (`134b194`, `1edf39b`) | **0** — only add `docs/notes/optimizer_notes_pass{1,2}.md` (new files) | extension (docs) |

### Genuine upstream bug fixes found

**None.** Zero of the 17 upstream-line-touching hunks (16 on `dev/init-robustness` + 1 on `upstream/adapt-with-stats`) are changes that would be correct-and-desirable on upstream main independent of our features:

- 15/16 dev hunks either preserve upstream semantics exactly under default configuration (verified knob-by-knob against `config.hpp` defaults: everything off/zero) while opening a seam for a feature, or are pure feature gates.
- The single non-conforming hunk (#3, `250e5b3`) *deletes* an upstream input-validation line with no feature purpose — a (mild) weakening, not a fix. Actual validation is retained at the config layer.
- The closest thing to upstream-worthy content is the `adapt_with_stats` extension (already isolated on `upstream/adapt-with-stats`) — an API *addition*, not a bug fix.

---

## 3. Minimal isolated patches (task 3)

**No minimal upstream patches are warranted — there are no genuine upstream bug fixes to send.** Explicitly: nothing in our dev diff corrects a defect in `origin/main`; every behavioral delta is feature-gated and defaults to upstream behavior.

Housekeeping on **our** side (not upstream patches), in priority order:

1. **Restore the CLI range check** (hunk #3): re-add `->check(CLI::Range((std::numeric_limits<double>::min)(), 1.0));` after `->default_val(step_accept_rate_target);` in `examples/stan_cli.cpp` (~line 344 at HEAD). Validation exists at config build, so this is UX-level only.
2. **Fix the inert CLI `--anti-windup`** (found in this audit): either dispatch `run_walnuts<AntiWindupAdapter<Opt>>` when `anti_windup > 0`, or (cleaner) make the CLI rely on the library default by dropping the explicit `Opt` in `AdaptiveWalnuts` when no batching/clipping is selected. Smallest validation: a run with `--anti-windup 8` on a deliberately saturating config whose step-size trace now differs from a `--anti-windup 0` run (currently they are bit-identical).
3. **Fix the fold-mode freeze mismatch** (committed since `5302ed8`, present at HEAD): `AdaptiveWalnuts::inv_mass()` should return `rank_folded_estimate()` when `metric_rank() > 0` (or `sampler()` should freeze with the same vector warmup transitioned under). Smallest validation: correlated-Gaussian analytic-moment test in fold mode, warmup-frozen sampler only.
4. **Convert `walnuts.hpp:780`** to `uturn_lr<D>(span_accum, *maybe_next_span, lrm)` for metric consistency under the full operator (same identity as the other `_lr` helpers; the property tests in `tests/leapfrog_property_test.cpp` are the natural validation).

---

## Appendix: verdicts at a glance

| Bug | Fix commit | Buggy code introduced by | In `origin/main`? | Buggy form ever committed? |
|---|---|---|---|---|
| B1 (sampler drops low-rank at freeze) | `5e56ff2` | ours (`5302ed8` fold-mode instance; `5e56ff2` itself for `metric_full` mode) | **No** — requires `low_rank*`/`metric_full`, absent upstream (`-S` empty) | fold-mode variant: yes (`5302ed8`..HEAD); `metric_full` variant: no (born+fixed inside `5e56ff2`) |
| B1b (reversible/uturn under wrong Hamiltonian) | `5e56ff2` | ours (`5e56ff2`'s own pre-commit working state) | **No** — upstream `reversible`/`uturn` (root `6162d88`) are called with the same metric they integrate; mismatch needs our `transition_w_lr` | no (residual instance remains at HEAD `walnuts.hpp:780`) |
| B2 (anti-windup double-wrap) | `52051c9` | ours (`2260f29`/`250e5b3`/`980c249`) | **No** — `AntiWindupAdapter`/`anti_windup` absent upstream (`-S` empty) | double-wrap: no (never committed, verified across all refs); single CLI wrap: yes (`2260f29`..`a091334`) |
