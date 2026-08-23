# W-37: trajectory-geometry warmup-exit gate — SEPARABILITY REFUTED (negative result, first-class)

Date: 2026-08-22. Pre-registration: WORKLOG.md "W-37" (+ the appended
T3 formula correction, made before any outcome was inspected).
Instrumentation: walnutpie branch `exp/traj-gate` (worktree
`external/walnutpie_w37`, off `exp/grad-accounting` @ 33cd398), commits
862381f + ec90f3f — per-window warmup accounting series, env-gated by
`WALNUTPIE_GRAD_ACCOUNTING=1` (window 50 via `WALNUTPIE_GRAD_WINDOW`),
zero behavior change. Harness: `harness/run_w37.py` +
`harness/analyze_w37.py`; raw runs `runs/w37/` (local, gitignored);
parsed numbers `results/w37_separability.json`.

## Headline verdict

**The pre-registered separability criterion FAILS at every candidate
exit point, under both class assignments, and (labeled post-hoc) at
every window boundary in the entire warmup. The hypothesis is
REFUTED: the trajectory-geometry quantities the E1 accounting
instruments do NOT distinguish the marginal class from the easy class
at any point where an exit would matter. Per the pre-registered stop
rule, NO gate was implemented — this closes the library-level warmup
early-exit direction permanently (4th independent gate: W-21 CLI knob,
W-25 static step/mass drift, W-28 dynamic lp pilot, W-37 trajectory
geometry).**

## Design (pre-registered)

Signals per window (50 warmup transitions, per chain): mean_h (mean
accepted-halving level), P(h≥1), ept (kernel evals/transition),
fw/bl shares. Gate statistics at boundary k: temporal drifts D_h =
max-chain |mean_h(k) − mean_h(k−2)|, D_e = max-chain relative ept
drift; cross-chain spreads S_h, S_e = max/min ept − 1. Normalized
distance D(k) = max(D_h/0.05, D_e/0.10, S_h/0.10, S_e/0.20); D ≤ 1
means the gate would exit. PIN RULE: windows with 0 accepted macro
steps (the E1 blr-pin signature) count as not converged. Separability
= ∃k ∈ {400, 450, 500, 550, 600}: max over EASY D(k) ≤ 0.5 AND min
over MARGINAL D(k) ≥ 2.0. Primary classes: easy {blr,
eight_schools_noncentered, arma11}, marginal {hier_2pl, lsat_model};
secondary (W-21 historical): marginal includes arma11.

Runs: 6 models × 4 chains (sequential single-chain processes), seeds
20260819+c, warmup 1000 / samples 100, rep0 inits per the W-36
assignment (kronecker_gp chain_0 uses the chain_1 init — E1's recorded
deviation for the known W-36 abort cell). 24/24 cells completed, 20
windows each. Instrumentation canary: env-on vs env-off draws
md5-identical 8/8 (blr, pilots × 4 chains). Consistency: window eval
sums + 2 boundary evals match CLI warmup calls within 1–15 evals on
every cell = exactly the final transition's work (the boundary
snapshot fires at the START of the boundary transition; one-transition
lag, uniform across cells, no effect on window-level signals).

Data note: the measurement grid ran instrumentation commit 862381f,
whose window records printed delta-of-deltas for sum_h/ge1 (fixed in
ec90f3f). The true series is recoverable EXACTLY by telescoping
(pure integer identity, no approximation); recovery verified against
the final phase histograms (e.g. blr_c0: recovered total sum_h = 803
= 642·1 + 64·2 + 3·3 + 6·4, the printed warmup histogram). Nothing was
re-run; no numbers below depend on the buggy revision.

## Result 1: the classes share the same settlement schedule — early

Chain-averaged mean_h per window (pin windows excluded as undefined):

| model (class) | w100 | w200 | w300 | w400 | w500 | w600 | w800 | w1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| blr (easy) | 4.000 | 1.205 | 0.089 | 0.076 | 0.097 | 0.095 | 0.102 | 0.077 |
| eight_schools_nc (easy) | 0.101 | 0.094 | 0.111 | 0.113 | 0.088 | 0.129 | 0.099 | 0.080 |
| arma11 (easy/borderline) | 0.049 | 0.064 | 0.095 | 0.082 | 0.113 | 0.122 | 0.100 | 0.130 |
| hier_2pl (marginal) | 1.486 | 0.086 | 0.100 | 0.077 | 0.077 | 0.072 | 0.080 | 0.074 |
| lsat_model (marginal) | 0.282 | 0.186 | 0.091 | 0.124 | 0.107 | 0.086 | 0.120 | 0.140 |
| kronecker_gp (overhead) | 0.990 | 0.101 | 0.071 | 0.100 | 0.054 | 0.071 | 0.074 | 0.062 |

By window 300–400 EVERY model, marginal class included, sits at the
settled floor mean_h ≈ 0.05–0.14 (E1's production aggregate for
hier_2pl@1000 was 0.090 — consistent). P(h≥1) is the same story
(0.05–0.14 everywhere by w300). The class differences live EARLY
(w100 mean_h: blr 4.0 [pin escape, see below], hier 1.49, kron 0.99,
lsat 0.28, esc 0.10, arma 0.05) — exactly where every previous gate
already knew exiting is unsafe. ept likewise flattens early: hier 38.9
→ 16.0 by w500 and 16.4 at w1000; lsat 22.4 → 16.8; blr 31.1 (pin) →
9.7.

**hier_2pl's late warmup — the segment W-25 showed is worth 4× ESS
(exit at ~350 collapsed bulk-ESS 519 → 126) — is FLAT in every
trajectory-geometry signal: mean_h 0.077 → 0.074, ept 16.0 → 16.4
across windows 400→1000.** Whatever late warmup improves on the
marginal class, per-transition trajectory counters average it out.

## Result 2: no separating threshold exists (the D tables)

Normalized distance D(k) (D ≤ 1 = gate would exit; smaller = more
stable):

| model | D@400 | D@450 | D@500 | D@550 | D@600 |
|---|---:|---:|---:|---:|---:|
| blr | 2.37 | 3.13 | 1.58 | 2.32 | 1.53 |
| eight_schools_nc | 1.83 | 0.76 | 1.71 | 1.66 | 2.31 |
| arma11 | 2.99 | 2.81 | 2.38 | 2.43 | 3.11 |
| hier_2pl | 4.49 | 4.64 | 2.81 | **1.00** | **1.40** |
| lsat_model | 3.87 | 2.87 | 2.26 | 3.14 | 3.01 |
| kronecker_gp | 3.19 | 2.02 | 5.05 | 3.43 | 1.96 |

Separability (criterion easy_max ≤ 0.5 AND marginal_min ≥ 2.0):
**FAIL at every k ∈ {400..600}, under the primary AND the secondary
class assignment** (secondary best case k=500: easy max 1.71 vs
marginal min 2.26 — a nominal ordering, but the easy side is 3.4×
above the 0.5 margin line, i.e. the gate would not actually exit
there). Post-hoc scan (labeled, NOT pre-registered): **0/18 window
boundaries in 100–1000 separate under either assignment** (easy_max_D
range 1.58–36.8; marginal_min_D range 0.58–13.0; the ranges overlap
everywhere).

Two readings, both fatal:
- At the pre-registered thresholds the gate would essentially NEVER
  exit — even the easy class sits at D ≈ 1.5–3 from the noise floor
  (the W-28 failure mode, recreated one layer deeper).
- hier_2pl's D at k=550/600 (1.00/1.40) drops BELOW blr's, esc's and
  arma11's at the same ks — the marginal class is momentarily MORE
  "stable" than the easy class. Loosen thresholds until exits happen
  and hier_2pl exits too (the W-25 failure mode).

## Result 3: the residual is a stochastic noise floor, not class signal

Component dominance at k ≥ 400 (which normalized term is the max):
D_e (ept window drift) dominates 23/29 model-k cells; S_e (cross-chain
ept spread) dominates 4 (lsat 3 of them — the marginal model with the
LARGEST cross-chain ept spread, S_e = 0.45 at k=500 vs esc 0.14);
D_h dominates 3. ept is a heavy-tailed per-transition count (macro
steps × dyadic attempts × ladder), so 50-transition window means swing
10–30% between adjacent 2-window spans on BOTH classes — e.g. at
k=500: hier D_e = 0.281 vs blr D_e = 0.158 vs esc 0.171 vs lsat 0.195.
The class ordering inverts k to k. This is structural: no threshold on
these statistics can be simultaneously below the easy class's noise
floor and above the marginal class's.

## Result 4: incidental observations

- The pin rule fired as designed: blr chains show acc = 0 (all-wasted,
  31 evals/transition) for the first 2–3 windows (pf inits), with the
  escape signature at w100 (mean_h 4.0) landing in w150–250 — E2's
  pin-escape window (~100–400) confirmed at window resolution. A
  constant-signal gate would have found the PIN maximally "stable";
  the pre-registered pin rule is what keeps that from being an exit.
- kronecker_gp's series look like hier_2pl's (settled by w300, ept
  ~16–17): its E2 pathology (loose caps admitting long trajectories)
  is not visible in settled-phase window statistics either.

## Verdict and closure

Per the pre-registered verdict rule (no separating k ⇒ REFUTED ⇒ STOP,
no implementation): **the trajectory-geometry gate is not implemented
and should not be.** The four-gate record now reads: CLI temporal knob
(W-21: fast but quality-destroying), static step/mass drift (W-25:
quality-destroying on the marginal class), dynamic lp pilot (W-28:
quality-preserving only by never exiting), trajectory geometry (W-37:
not class-separating at any exit-relevant point). The consistent
picture: on this benchmark the marginal class's late-warmup quality
gains are not observable in ANY cheap windowed statistic of the
sampler's operation — not step/mass state, not the lp stream, not the
search structure. They are only visible in long-horizon min-dimension
ESS itself, whose measurement costs what it would save. Warmup length
stays fixed (defaults unchanged); any future early-exit proposal
carries the burden of naming a quantity outside this exhausted list.

Ship state: instrumentation only, `exp/traj-gate` @ ec90f3f (default
path bit-identical; the per-window series is a standing measurement
tool for any future adaptation work). Worktree left in place.

## Caveats

- One seed set (rep0), 4 chains per model — the W-37 measurement is a
  separability probe, not a 3-rep benchmark; the effect sizes (flat
  0.07–0.14 mean_h everywhere vs pre-registered 0.05/0.10 margins, and
  cross-class D overlap at every k) are far larger than rep noise.
- Window boundaries lag the transition stream by one transition
  (snapshot fires at the start of the boundary transition; 1–15 evals
  of the final transition excluded uniformly — see consistency note).
- samples=100 (separability needs only warmup); the frozen-sampler
  sampling-phase accounting is not part of this analysis.
