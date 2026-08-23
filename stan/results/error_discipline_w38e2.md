# W-38-E2: error-discipline ablation, warmup-weighted — NEGATIVE RESULT (all arms rejected)

Date: 2026-08-22/23. walnutpie branch `exp/error-discipline` (worktree
`external/walnutpie_w38e2`, off `exp/safe-adapt-defaults` @ 43b6435,
commit b62969b). Pre-registration: WORKLOG.md "W-38-E2" (before any run).
Design source: `results/proposals_fewer_gradients.md` E2; ceilings from
`results/grad_accounting_w38.md` (E1: warmup overhead 32.7% of warmup
evals at hier_2pl 1000+1000 = 18.2% of total; blr pins ≤~400 warmup).

## Hypothesis under test

The dyadic overhead is gated by tolerance failures; loosening error
discipline DURING WARMUP ONLY (sampling keeps 0.5 / 5 halvings) cuts
total logp_grad calls materially (target ≥10% on the overhead class)
while preserving sampling quality on the W-25/W-28 marginal class.

## Arms (all warmup=1000 draws=1000, 4 sequential single-chain procs, 3 reps, seeds 20260819+1000*rep+c)

| arm | setting | mechanism |
|---|---|---|
| base | CLI defaults | canary reference |
| e2a | `--max-error-start 5.0 --max-error-iters 950` | EXISTING schedule knob: warmup cap decays 5.0→0.5 by iter 950 |
| e2b | `--warmup-max-step-halvings 3` | NEW knob: warmup-only halving-ladder cap; sampler keeps 5 |
| e2c | `--warmup-max-error 5.0` | NEW knob: constant loose warmup cap; sampler keeps 0.5 |

Models: arma11, lsat_model, hier_2pl (marginal class) + blr, kronecker_gp
(overhead class). Inits: inits_w25 pf (arma11, blr, hier_2pl, lsat_model),
inits_w36 deterministic (kronecker_gp). New knobs: WarmupConfig
`warmup_max_step_halvings` / `warmup_max_error` (both default off),
consumed only inside AdaptiveWalnuts; CLI `--warmup-max-step-halvings` /
`--warmup-max-error`. Functional check: pinned blr 10+10 warmup calls
312→72 under e2b (10*7+2; sampling unchanged 310) — knobs are live, not
silent no-ops.

## Gate (a) CANARY bit-identity: PASS 12/12

Default-path draws of the new binary md5-identical to the pre-change
binary (`build_w36exp` @ exp/safe-adapt-defaults 43b6435): arma11, blr,
hier_2pl x 4 chains, seed 20260819, 1000+1000. The knobs default off and
the default path is provably unchanged.

## Gate (b) QUALITY: all three arms FAIL (pre-registered band = base per-rep spread)

Medians of 3 reps; arviz rank-normalized bulk/tail ESS-min and max R-hat
over parameters (structurally constant GQ columns excluded — see
Deviations). PASS = bulk AND tail median ≥ min(base per-rep), rhat median
≤ max(base per-rep).

| model | arm | bulk_min | tail_min | rhat_max | gate | margin of failure |
|---|---|---:|---:|---:|---|---|
| arma11 | e2a | 2647.6 | 2387.7 | 1.0023 | FAIL | tail −8.0 ESS (−0.3%) vs band 2395.7; rhat +0.03% |
| arma11 | e2b | 2709.7 | 2468.5 | 1.0022 | FAIL | rhat +0.02% (hair) |
| arma11 | e2c | 2759.4 | 2395.4 | 1.0022 | FAIL | tail −0.3 ESS (−0.01%); rhat hair |
| lsat_model | e2a | 846.8 | 1125.7 | 1.0098 | FAIL | tail −3.2% vs band 1162.5 |
| lsat_model | e2b | 541.1 | 757.7 | 1.0160 | FAIL | **bulk −24%, tail −35%** (real) |
| lsat_model | e2c | 738.6 | 1162.4 | 1.0109 | FAIL | tail −0.1 ESS (hair) |
| hier_2pl | e2a | 606.1 | 782.4 | 1.0073 | PASS | — |
| hier_2pl | e2b | 454.1 | 654.1 | 1.0145 | FAIL | **bulk −24%, tail −3%** (real) |
| hier_2pl | e2c | 568.3 | 678.3 | 1.0134 | FAIL | bulk −4.4%; rhat 1.0134 vs 1.0124 |
| blr | e2a | 463.7 | 681.1 | 1.0127 | FAIL | rhat +0.07% (hair) |
| blr | e2b | 556.6 | 781.2 | 1.0094 | PASS | — |
| blr | e2c | 491.6 | 740.4 | 1.0084 | PASS | — |
| kronecker_gp | e2a | 36.3 | 31.1 | 1.0938 | PASS | (base band 10.5–67 — near-vacuous) |
| kronecker_gp | e2b | 31.2 | 52.5 | 1.1335 | PASS | n=2 (rep0 aborted, below) |
| kronecker_gp | e2c | 39.0 | 62.4 | 1.1020 | PASS | (band near-vacuous) |

Reading: e2a/e2c degrade the marginal class by hair-to-small margins
(e2a lsat tail −3.2%, e2c hier bulk −4.4%; the arma11/blr/lsat "hairs"
are <0.4% — noise-level, but the pre-registered rule counts them);
e2b degrades it MATERIALLY (−24% bulk on BOTH lsat_model and hier_2pl —
the same marginal class that killed W-25/W-28 warmup shortening).

## Gate (c) SPEED: e2a/e2c FAIL (0/3), e2b nominal 2/3 but unstable

logp_grad calls per chain (median of 3 reps; CLI stanzas), ratio vs base;
wall ratio in parentheses. Expectation was ≥10% reduction on ≥2 of
{hier_2pl, kronecker_gp, blr}.

| model | base | e2a | e2b | e2c |
|---|---:|---:|---:|---:|
| arma11 | 11048 | 10022 (0.907) | 10805 (0.978) | 9771 (0.884) |
| lsat_model | 34211 | 33770 (0.987) | 33322 (0.974) | 33811 (0.988) |
| hier_2pl | 36698 | 34331 (**0.935**) [wall 0.939] | 41323 (**1.126**) [1.184] | 33861 (**0.923**) [0.930] |
| blr | 25375 | 24853 (0.979) | 19434 (**0.766**) [0.608] | 24530 (0.967) |
| kronecker_gp | 34719 | 75721 (**2.181**) [1.960] | 29203 (0.841) [0.893] | 91092 (**2.624**) [2.370] |

- e2a/e2c realize only 6.5–7.7% on hier_2pl (the E1 production-settings
  ceiling was 18.2%) and EXPLODE kronecker_gp (+118%/+162% calls, walls
  ~2–2.4x): a loose warmup cap admits long high-error trajectories —
  the "wasted" failed attempts were also capping warmup trajectory
  growth. Speed gate FAIL.
- e2b passes the letter of the gate (kron −15.9%, blr −23.4%) but makes
  hier_2pl 12.6% MORE expensive, explodes blr rep1 4.5x (501k vs 111k
  calls; median hides it), and hard-aborted one kronecker_gp chain (see
  Deviations). Not adoptable.
- blr e2b's −23% is the pin effect (pinned transitions cost 31→7 evals),
  not a general win — and e2b's blr quality PASS coexists with its
  marginal-class collapse elsewhere.

## Gate (d) blr short-warmup probe: E2 does NOT fix the E1 pin — the E1 "would unpin" hypothesis is REFUTED

Pre-registered probe (warmup=400, draws=1000, 3 reps x 4 chains):
pinned chains = chains whose 1000 saved draws are all identical.

| arm | bulk_min_med | tail_min_med | calls_med | pinned chains (of 12) |
|---|---:|---:|---:|---:|
| probe_base | 612.4 | 621.4 | 23236 | **1** (rep1 chain_0) |
| probe_e2a5 (= e2a settings) | 552.2 | 530.5 | 22868 | **1** (same chain) |
| probe_e2a8 (start 1e8, iters 950) | 265.2 | 323.0 | 71014 | **1** (same chain) |

- At warmup=400 base is mostly UNPINNED already (the E1 pin-escape sits
  between ~100 and 400 for pf inits; E1's "≤~400" was an inference from
  100/1000 endpoints) — but rep1/chain_0 stays pinned in EVERY arm.
- Supplementary post-hoc probes (labeled as such; not pre-registered):
  warmup=100 and 200, base vs e2a8 (decaying 1e8) vs a CONSTANT 1e8
  warmup cap (`--warmup-max-error 1e8`, the e2c mechanism). At w100 base
  pins 3/4 chains per rep (bulk 5–9; E1's 31-evals/transition signature
  in the call counts); e2a8 pins IDENTICALLY (3/4, bulk 5.2–9.6); the
  constant-1e8 cap ALSO fails to unpin (3/4, bulk 5.3–9.4). At w200 one
  chain remains pinned in rep1/rep2 under every arm.
- Conclusion: the blr pin is NOT gated by error discipline at all — even
  caps 10x above the E1-measured pinned |dH|≈8e6, constant or decaying,
  leave the chain pinned (the failing attempts are evidently not
  tolerance verdicts the cap can pass — non-finite error/gradient or
  reversibility-ladder rejection; distinguishing these needs the E1
  instrumentation on the pinned chain, not more caps). Meanwhile e2a8
  degrades healthy cells (w400 rep2 bulk 612→265) at 3.1x calls. The pin
  belongs to W-41 (freeze-time robustness), not to E2. E1's suggestion
  "--max-error-start would unpin, config-only" is refuted.
- Main-grid blr (warmup=1000): no pinned chains in any arm (escape
  confirmed at production warmup).

## Verdict (pre-registered rule: REJECT if any marginal-class model fails the quality band)

- **e2a REJECT** — quality fails (lsat tail −3.2%, plus hair-level arma11/
  blr misses); speed fails (hier −6.5% only, kronecker +118%).
- **e2b REJECT** — quality fails MATERIALLY (lsat −24%, hier_2pl −24%,
  the W-25/W-28 marginal class again); plus a hard kronecker_gp abort and
  a 4.5x blr call explosion in one rep. The only arm that beats 10%
  anywhere does so by making the failure-dominated cells cheaper while
  degrading the healthy ones.
- **e2c REJECT** — quality fails (hier bulk −4.4% + hairs); speed fails
  (kronecker +162%).
- Pack-level: E2 (warmup error-discipline ablation) is CLOSED as a
  quality-preserving gradient-count lever. Mechanistic summary: the E1
  "overhead" decomposition counted failed dyadic attempts as waste, but
  those failures double as a trajectory-growth limiter during warmup —
  removing them lengthens warmup trajectories (kronecker +118–162%) or
  destabilizes the frozen sampler (e2b marginal-class −24%). The
  realized saving on the one production-relevant model (hier_2pl,
  e2a/e2c −6.5/−7.7% calls, wall −6/−7%) is real but below the 10% bar
  and bought with marginal-class quality. The pack's remaining live
  lever is E4 (refine-aware min_micro_steps; E1 GO, m=1-in-100% never
  tested upward); E5 (boundary dups) unchanged.

## Deviations / notes

- kronecker_gp rep0 chain_0: the deterministic init triggers the KNOWN
  pre-existing W-36 abort ("macro_time must be in (0, inf)" after nan
  eigenvectors_sym gradients), init-dependent and seed-independent (both
  20260819/20260820 abort; E1 recorded the same). That one cell uses the
  chain_1 init file (E1's deviation), all arms identically. e2b
  kronecker_gp rep0 chain_2 then hit the same known abort UNDER e2b's
  changed warmup trajectories (recorded as an e2b failure; e2b kronecker
  medians over 2 reps). W-41's target, not re-litigated here.
- hier_2pl (4) and kronecker_gp (466) CSVs contain STRUCTURALLY CONSTANT
  GQ columns (Cholesky identities, correlation-matrix diagonal: L_Omega.
  1.1=1, L.1.2=0, ...) — constant in every arm including base; their
  R-hat is nan (inf) and they are excluded from ESS/R-hat (identical
  mins with/without exclusion for ESS; R-hat becomes finite/honest).
- ESS vectorization: one 3D (chain, draw, param) xarray variable instead
  of a per-param Python loop — validated EXACT on blr (max abs diff 0.0);
  ~1000x faster on kronecker_gp (5450 params). Per-param loop numbers
  (analyze_w36 pattern) and vectorized numbers agree.
- Raw runs: runs/w38e2/ (gitignored). Parsed: results/w38e2_{canary,
  calls, ess, probe}.json. Harness: harness/run_w38e2.py (runner + canary
  + probe + supplementary probes), harness/analyze_w38e2.py.
- Worktree external/walnutpie_w38e2 (branch exp/error-discipline) LEFT
  in place per supervisor instruction; knobs ship default-off and
  bit-identical, available for any future targeted use.
