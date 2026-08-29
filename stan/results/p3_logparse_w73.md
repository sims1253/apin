# P3 stage-1: min-micro-steps × max-macro-steps joint policy — pure log-mining analysis (W-73)

Date: 2026-08-25. Zero sampling runs, zero builds, single-core python. Inputs only:

- A0 grid logs: `stan/scratch/w63/runs/A0/<model>/w1000_pf/rep<r>_c<chain>.log`
  — 21 models × 3 reps × 4 chains = **252 logs, all present, all parse** (warmup 1000 / samples 1000,
  A0 = default arm, flags `--metric-window 50` only).
- W-63 A0 pin battery: `stan/scratch/w63/runs/A0/blr/w{100,400}_{pf,def}/` (12 chains per cell).
- ESS join: `stan/scratch/w63/lowrank_results.json` (`grid[model]["A0"]` — my independent
  gradient-call parse reproduces its `grads` per rep exactly, 6/6 spot checks).
- Semantics from source (read-only): `external/walnutpie/examples/stan_cli.cpp`,
  `include/walnutpie/walnuts.hpp`, `include/walnutpie/adaptive_walnuts.hpp`, `include/walnutpie/config.hpp`.

w66 T0.65/T0.8 skipped (rank arms, per brief).

---

## 1. Format inventory — what the logs actually expose

Per log file (one chain), the single-chain CLI (`stan_cli.cpp:run_walnuts`) prints exactly:

```
[Error in logp_grad: ... lines]                      <- zero or more, countable
    total time: Ts                                   <- warmup stanza
logp_grad time: Ts
logp_grad fraction: F
        logp_grad calls: N
        time per call: Ts
Adaptation completed.
Note: multi-chain mode ... single-chain CLI does not.
Macro time = X                                       <- ONCE, from the FROZEN sampler
Mass matrix diagonal = [d1 ... dk]                   <- k = parameter count
    total time: Ts                                   <- sampling stanza (same 5 lines)
        logp_grad calls: N
<param>: mean = ..., stddev = ...                    <- one per parameter
```

All 252 logs have exactly 2 stanzas. No `Early warmup exit` or `Heuristic initial step size`
lines anywhere (A0 does not use those flags). `Error in logp_grad` spam present in 20/21 models.

**What is NOT in the logs (checked by grep across all 21 models):** trajectory depth,
treedepth, min-micro-steps, step size, halvings, U-turn info, accept stats — zero hits for
`depth|micro|step_size|trajectory|tree|iteration` tokens. The companion CSVs carry ONLY
parameter columns (no `treedepth__`/`n_leapfrog__`-style sampler columns).

### Semantics of what IS there (source-verified)

- **`Macro time = X` is not wall time.** It is the frozen sampler's **adapted macro step
  size** (`WalnutsSampler::macro_time()`, `walnuts.hpp:992`), i.e. the `step` handed to
  `transition_w` for every sampling trajectory. It plays the macro-scale role in the
  min-micro × max-macro pair.
- **`Mass matrix diagonal` is actually the inverse-mass diagonal** (variance-scale;
  `stan_cli.cpp:235` prints `inverse_mass_matrix_diagonal()`), so per-dim posterior sd ≈
  `sqrt(printed)`.
- **Cost model per macro step** (`walnuts.hpp:310 macro_step`): starts at `min_micro_steps`
  micro steps and doubles while the Hamiltonian error exceeds `max_error`
  (`max_step_halvings` cap). `reversible()` (`walnuts.hpp:257`) costs **zero extra calls when
  `num_steps == 1`**. With the W-23 endpoint cache, a `min_micro=1` trajectory with no halvings
  costs **exactly one call per state**. A trajectory has `2^depth` states, depth ≤
  `max_trajectory_doublings` = **5 (default)** → 32 states max.
- **min-micro adaptation** (`adaptive_walnuts.hpp:367 MinMicroStepsAdaptHandler`): during
  warmup it observes `1 << depth` per transition and sets
  `min_micro = lround(mean_states / max_macro_steps_target)`, target default **15** —
  i.e. the two knobs are ALREADY coupled by design; P3 asks whether a different joint point wins.

**Consequence (the one strong inferential lever):** chains pinned at exactly `calls/draw =
2^d` reveal depth and min-micro jointly. In this corpus the 64-rung is empty (0/252 chains
within 0.5% of 64 calls/draw) → the whole corpus runs in the **min_micro = 1 regime**, where
**`calls/draw ≈ E[2^depth]` = mean trajectory length in states**. The exact-32 chains
(e.g. `bym2 rep1` all four chains: `samp_calls == 32000` exactly) are trajectories that run
to the depth-5 cap every single draw with zero micro-halvings.

---

## 2. Per-model table (A0, medians over 12 chains; ESS from lowrank_results.json)

`steps/sd` = geometric-mean posterior sd ÷ macro time = **upper bound** on macro steps needed
to cross one sd (upper because true time per macro step is `min_micro × macro_time`, here
min_micro=1 so tight). `p(cap)` = lower bound on fraction of draws at depth 5 from the
two-rung mixture bound `p32 ≥ (E[states]−16)/16`. "class": dead = ESS_min < 100.

| model | dim | calls/draw | warm/it | warm share | macro time | CV(mt) chains | steps/sd | p(cap) | ESS_min | ESS/draw | ESS/call | class |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pilots | 18 | 33.0 | 33.7 | 0.51 | 0.0665 | 0.27 | 6.2 | 1.00 | 2 | 0.00 | 0.0000 | dead |
| bym2_offset_only | 3845 | 32.0 | 32.0 | 0.50 | 0.0565 | 0.60 | 0.8 | 1.00 | 2 | 0.00 | 0.0000 | dead |
| accel_gp | 66 | 28.2 | 33.9 | 0.55 | 0.0824 | 0.48 | 2.6 | 0.77 | 2 | 0.00 | 0.0000 | dead |
| diamonds | 26 | 25.8 | 42.8 | 0.62 | 0.0329 | 0.11 | 0.7 | 0.61 | 2 | 0.00 | 0.0000 | dead |
| **blr** | 6 | **23.9** | 31.0 | 0.56 | 0.0342 | 0.03 | 0.5 | **0.49** | **347** | 0.09 | 0.0016 | **healthy** |
| **eight_schools_centered** | 10 | **20.9** | 15.4 | 0.42 | 0.554 | 0.47 | 3.3 | 0.30 | **103** | 0.03 | 0.0007 | **healthy** |
| kronecker_gp | 438 | 17.8 | 20.5 | 0.53 | 0.1075 | 1.36 | 1.6 | 0.11 | 8 | 0.00 | 0.0001 | dead |
| logmesquite_logvash | 7 | 17.4 | 18.0 | 0.51 | 0.196 | 0.04 | 0.8 | 0.08 | 102 | 0.03 | 0.0007 | healthy |
| radon_partially_pooled_nc | 389 | 17.1 | 21.2 | 0.55 | 0.209 | 0.14 | 1.8 | 0.07 | 217 | 0.05 | 0.0014 | healthy |
| hier_2pl | 669 | 16.7 | 23.1 | 0.58 | 0.196 | 0.02 | 2.2 | 0.05 | 493 | 0.12 | 0.0031 | healthy |
| lsat_model | 1006 | 16.7 | 21.7 | 0.57 | 0.228 | 0.08 | 4.0 | 0.04 | 941 | 0.24 | 0.0058 | healthy |
| radon_var_intercept_slope_nc | 175 | 16.6 | 19.4 | 0.54 | 0.228 | 0.06 | 3.6 | 0.04 | 267 | 0.07 | 0.0018 | healthy |
| lotka_volterra | 8 | 16.4 | 16.4 | 0.50 | 0.167 | 0.59 | 0.8 | 0.02 | 10 | 0.00 | 0.0001 | dead |
| kidscore_momiq | 3 | 11.7 | 14.4 | 0.55 | 0.200 | 0.05 | 1.3 | 0 | 283 | 0.07 | 0.0026 | healthy |
| garch11 | 4 | 11.3 | 12.6 | 0.53 | 0.335 | 0.04 | 1.4 | 0 | 747 | 0.19 | 0.0083 | healthy |
| low_dim_gauss_mix | 5 | 10.7 | 12.6 | 0.54 | 0.153 | 0.04 | 0.5 | 0 | 779 | 0.19 | 0.0084 | healthy |
| eight_schools_noncentered | 10 | 8.7 | 9.5 | 0.52 | 0.628 | 0.16 | 1.7 | 0 | 1470 | 0.37 | 0.0200 | healthy |
| wells_dist100_model | 2 | 6.9 | 7.5 | 0.52 | 0.405 | 0.06 | 0.2 | 0 | 749 | 0.19 | 0.0126 | healthy |
| arma11 | 4 | 6.8 | 7.7 | 0.53 | 0.268 | 0.03 | 0.2 | 0 | 1022 | 0.26 | 0.0167 | healthy |
| gp_regr | 3 | 6.6 | 6.9 | 0.51 | 0.581 | 0.08 | 0.6 | 0 | 2262 | 0.57 | 0.0419 | healthy |
| dogs_hierarchical | 2 | 5.7 | 6.2 | 0.52 | 0.393 | 0.04 | 0.6 | 0 | 1592 | 0.40 | 0.0329 | healthy |

(ESS/draw = ESS_min ÷ 4000 draws; ESS/call = ESS_min ÷ total grads, matching
`ess_per_grad_med` in the JSON. Error-spam maxima: kronecker_gp 64k, lotka 63k, bym2 2.8k lines.)

### Findings

- **F1 — spend does not buy mixing (cross-model).** Among the 15 healthy models,
  Spearman(calls/draw, ESS/draw) = **−0.83** and Spearman(calls/draw, ESS/call) = **−0.94**
  (n=15). The 4.2× calls/draw spread (5.7 → 23.9) is NOT compensated by ESS/draw; if anything
  the spendy models mix worse per draw. Confounded by model hardness (ecological correlation),
  but it removes the "expensive trajectories are earning their keep" defense.
- **F2 — depth-cap saturation is real and visible.** Exact 2^d rung pinning: bym2 7/12 chains
  at exactly 32.0, accel_gp 2/12, kronecker_gp and blr 1/12 each at 16.0; 0/252 at 64.
 pilots (median 33.0, never exact) = cap + ~1 micro-halving call/draw — the min-micro ×
  max-macro interaction in one number. Healthy models with p(cap) > 0.25: **blr (0.49),
  eight_schools_centered (0.30)**.
- **F3 — the spendiest models are ESS-dead, and the 6 dead models hold 44% of the corpus
  sampling-call mass.** Their signature: calls/draw at/near 32 + high cross-chain CV of the
  adapted macro time (kronecker 1.36, bym2 0.60, lotka 0.59 vs ≤0.16 for all healthy).
- **F4 — the joint structure shows up as a sign flip in how the adapted macro step relates
  to spend.** Within-model, across 12 chains, Spearman(macro time, sampling calls):
  negative in coverage-limited models (diamonds −0.77, bym2 −0.65, eight_schools_nc −0.55 —
  bigger step → fewer states needed), positive in error-limited models (lotka +0.76,
  hier_2pl +0.66, kronecker +0.63, radon_vis +0.52 — bigger step → more micro-halvings to
  stay under `max_error`). Both regimes contain healthy models. A joint policy is exactly a
  placement along this coverage/error trade-off, and the flip says the operating point is
  model-dependent — but the logs cannot resolve micro-halving counts, so the regime of the
  middle of the table is inferred, not measured.
- **F5 — spend correlates with scale-normalized step and dimension.** Spearman(calls/draw):
  steps/sd +0.45, log10(dim) +0.66 (healthy models). Small adapted macro step relative to
  posterior sd (many macro steps per sd) is the coverage-limited profile.
- **F6 — pin battery isolates the mechanism** (A0/blr, 12 chains/cell): `w100_def` — 12/12
  chains stuck (1 unique CSV row) at **exactly** 32.0 calls/draw, macro time 0.395;
  `w400_pf` — 1/12 stuck, calls/draw 21.3, macro time collapsed 10× to 0.038, chains move.
  Exact-32 pinning is the always-reject signature (identical position → identical trajectory
  geometry → depth 5 every draw, min_micro 1, no halvings). Also visible in the grid:
  stuck bym2 chains sit at exactly 32000/1000 draws.

---

## 3. Verdict — pre-registered style

**Conditional GO for a small stage-2 sampling campaign; the full joint-policy program is
blocked by a logging gap (below). No source of evidence in these logs can close the
equal-ESS question by itself.**

### Win bound (calls/draw × ESS/call arithmetic)

- **Mechanical (provable from rung arithmetic), depth cap 5→4 (32→16 states):** sampling-call
  saving ≤ (E[states]−16)/E[states] if ESS/draw is unchanged. Healthy: blr ≤33%,
  eight_schools_centered ≤23%, logmesquite ≤8%, everything else ≤7%. The pre-registered
  ≥10% bar is plausible for **exactly two healthy models (blr, eight_schools_centered)** —
  and both are the p(cap) ≥ 0.3 models, so the cap would actually bind often.
- **Dead models (44% of call mass):** cap saves ~50% with ESS staying ≈ 2/4000 — formally
  "equal ESS", practically still dead. The real lever there is adaptation repair (F3/F6:
  macro-time miscalibration ~10×), which is a warmup-policy question, not a trajectory
  policy.
- **Class-closure bound (requires the untested ESS-flatness assumption):** spendy-healthy
  class (7 models, mean 18.5 calls/draw) vs lean-healthy class (8 models, mean 8.6): closing
  the gap at equal ESS/draw would save ~54% of healthy-model sampling calls. The −0.83
  inversion (F1) is consistent with over-spend but cannot establish causality — that is
  precisely what stage-2 randomizes.

### Recommended stage-2 (small, cheap, pre-registered gates)

Models: blr, eight_schools_centered, logmesquite_logvash, radon_partially_pooled_nc (the
healthy, p(cap) > 0, spendy set) + hier_2pl as a low-p(cap) control. Arms (pure CLI, no
code): `--max-trajectory-doublings 4` vs default 5 (primary); optionally a joint arm
`doublings 4 + min-micro 2` to probe the coupling direction (target_macro 15 ↔ min_micro
ladder). w400/s500, 3 reps × 4 chains ≈ 5 models × 3 arms × 12 = 180 chain-runs, minutes each.
Gates: advance iff ESS_min/draw ≥ 0.95× baseline AND grads/draw ≤ 0.9× baseline per model;
two-sided, per-model verdicts, no aggregate-only claims. Expected from the bounds: blr and
eight_schools_centered are the only models with headroom ≥ the 10% bar; treat 3/5 nulls as
the likely outcome.

### GAP REPORT — what walnutpie must log for the joint-policy program to be measurable

The P3 observables exist internally but are discarded (all in `external/walnutpie/`):

1. **`min_micro_steps` final adapted value** — `WalnutsSampler` stores it
   (`min_micro_steps_`, `walnuts.hpp:1049`) but has **no getter**; add next to
   `macro_time()` (line 992) and print beside `Macro time =` (`stan_cli.cpp:234`).
   One-line getter + one-line print. This alone pins the min_micro regime per run
   (the 32-vs-64 rung inference becomes direct).
2. **Per-draw trajectory depth** — `WalnutsSampler::operator()` receives `depth` from
   `transition_w` and throws it away (`walnuts.hpp`, operator() body). Accumulate a
   6-bin histogram (or count-at-cap + mean) and print in the sampling summary block
   (`stan_cli.cpp` `end_timing` for stanza 2). This converts p(cap) from a mixture bound
   into a measurement.
3. **Micro-halvings per macro step** — the halving loop counter in `macro_step`
   (`walnuts.hpp:310-315`) and `macro_step_lr`; aggregate mean/max per stanza. This is the
   F4 error-limited regime made visible, and the only way to attribute spend between
   depth and micro refinement for mid-table models.
4. **(Optional, best for future analyses)** per-draw CSV columns `depth__`,
   `micro_per_macro_mean__` alongside the parameter columns written by `write_draws`.

Items 1+2 are a ~15-line UX PR candidate (default-path canary must stay byte-identical);
3 is slightly more invasive. Note also: `WALNUTPIE_DEBUG_ALPHA` already emits per-macro-step
min-accept alphas + macro step size for the first N steps (`walnuts.hpp:339-346`) — usable
for stage-2 diagnosis via env var, no code change, but rerun-only and truncated.

---

## 4. Method / reproducibility

Parsing was stdlib-python (regex, single core), no artifacts written outside this file and
the worklog entry. Core patterns: `logp_grad calls: (\d+)` (stanza order: warmup, sampling),
`Macro time = ([0-9.e+-]+)`, `Mass matrix diagonal = \[(.*?)\]` (split on whitespace),
`Error in logp_grad` line counts; ESS/draw = `ess_min_med / 4000`; grads cross-checked
equal to `lowrank_results.json` `per_rep[].grads`. Analysis numbers behind the table:
per-chain records for all 252 logs (calls warm/samp, times, macro time, mass diag, errors)
aggregated to medians; Spearman/Pearson as stated; p(cap) two-rung bound `p32 ≥ (E−16)/16`
valid for support on {1,2,4,8,16,32}.
