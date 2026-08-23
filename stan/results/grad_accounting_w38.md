# W-38 (E1): per-macro-step gradient accounting — measured buckets + E2/E3/E4 verdicts

Date: 2026-08-22. Instrumentation: walnutpie branch `exp/grad-accounting`
(worktree `external/walnutpie_w38`, off `exp/safe-adapt-defaults` @ 43b6435),
env-gated by `WALNUTPIE_GRAD_ACCOUNTING=1` following the
`WALNUTPIE_DEBUG_ALPHA/SPAN` precedent. New header
`include/walnutpie/grad_accounting.hpp`; hooks in `macro_step` /
`reversible` (+ low-rank mirrors), phase switch at the
`AdaptiveWalnuts`→`WalnutsSampler` boundary, report printed by the CLI at
end of run. Zero cost and zero behavior when unset (one statically-cached
bool check per attempt).

Four eval buckets exactly decompose every kernel logp_grad call:
forward-accepted (fa), forward-wasted (fw, tolerance-failed dyadic
attempts), backward-ladder (bl, `within_tolerance` walks inside
`reversible`), discarded-on-leaf-failure (dl, tolerance-passing attempt
rejected by a coarser backward lattice). Identity check per accepted
step refined to h: fw m(2^h−1) + fa m·2^h + bl m(2^h−1) = 3m·2^h − 2m.

## Gates

- **Canary (bit-identity): PASS 8/8.** Same binary, env on vs unset,
  blr + pilots × 4 chains (seeds 20260819+c), warmup=100 samples=100,
  default inits: every chain CSV md5-identical. Additionally a 3-way
  smoke check (blr, pf init): new-binary-off == new-binary-on ==
  PRE-CHANGE binary (`build_w36exp` @ 43b6435) — the code change itself
  is draw-neutral, not just the env gate.
- **Consistency: PASS 7/7 runs.** kernel_total(warmup) + 2 boundary
  evals (masses() init + chain start) == CLI warmup logp_grad calls,
  and kernel_total(sampling) == sampling calls, exactly, on every run
  (W-23 endpoint cache seeds the sampling phase: no start re-eval).

## Runs

1 chain, seed 20260819 (kronecker_gp deviation: seed 20260820 + chain_1
init — the seed-20260819/chain_0 run aborts with the KNOWN pre-existing
W-36 failure "macro_time must be in (0, inf)" after nan eigenvectors_sym
gradients; W-41's target, not re-litigated here). Inits: w25 pathfinder
for blr/hier_2pl, w36 deterministic for kronecker_gp/pilots (rep0
chain_0). Defaults otherwise (m=1, max_step_halvings=5, max_error=0.5,
drift off).

### Bucket table (% of phase kernel evals; ovh = fw+bl+dl)

| run | phase | macro steps | fa | fw | bl | dl | ovh | exh | rej | evals/trans |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| blr 100+100 (pf init) | warmup | 100 | 0.0 | **100.0** | 0.0 | 0.0 | 100.0 | 100 | 0 | 31.0 |
| blr 100+100 (pf init) | sampling | 100 | 0.0 | **100.0** | 0.0 | 0.0 | 100.0 | 100 | 0 | 31.0 |
| blr 100+100 default init | both | 100/100 | 0.0 | **100.0** | 0.0 | 0.0 | 100.0 | 100 | 0 | 31.0 |
| hier_2pl 100+100 | warmup | 266 | 13.8 | 73.6 | 10.3 | 2.3 | **86.2** | 74 | 21 | 36.5 |
| hier_2pl 100+100 | sampling | 537 | 40.2 | 25.3 | 24.8 | 9.7 | **59.8** | 0 | 94 | 21.9 |
| kronecker_gp 100+100 | warmup | 289 | 20.4 | 47.1 | 21.2 | 11.2 | **79.6** | 27 | 69 | 37.4 |
| kronecker_gp 100+100 | sampling | 429 | 34.3 | 25.1 | 22.9 | 17.6 | **65.7** | 0 | 100 | 16.0 |
| pilots 100+100 | warmup | 459 | 31.6 | 37.2 | 27.9 | 3.2 | **68.4** | 20 | 33 | 76.4 |
| pilots 100+100 | sampling | 680 | 46.7 | 22.8 | 22.3 | 8.1 | **53.3** | 0 | 73 | 21.3 |
| hier_2pl 1000+1000 | warmup | 12751 | 67.3 | 20.1 | 8.8 | 3.9 | **32.7** | 74 | 372 | 20.4 |
| hier_2pl 1000+1000 | sampling | 12046 | 78.4 | 8.6 | 8.6 | 4.3 | **21.6** | 0 | 353 | 16.3 |
| blr 1000+100 (pin-escape check) | warmup | 1053 | 3.5 | 93.3 | 3.2 | 0.0 | 96.5 | 968 | 0 | 33.3 |
| blr 1000+100 (pin-escape check) | sampling | 321 | 34.2 | 34.5 | 31.3 | 0.0 | **65.8** | 11 | 0 | 104.4 |

Accepted-halving histograms (sampling phase): hier_2pl@100 h0/h1/h2 =
133/246/64; kronecker h0/h1/h2 = 147/163/19; pilots = 348/201/55/3;
hier_2pl@1000 = 10640/1053/0; blr@1000 = 0/0/21/142/147 (h2–h4 ONLY);
pinned blr = none. Ladder successes are overwhelmingly level 0 (the
n/2 lattice): l0 vs l≥1 = hier 93:1, kronecker 97:3, pilots 71:2,
hier@1000 353:0 (sampling; pooled l≥1 per run: hier 3, kronecker 8,
pilots 3, hier@1000 2, blr@1000 0). **min_micro_steps = 1 in 100% of macro
steps in every run/phase** — the current estimator only ever pushes m
DOWN to its floor; the grow-m direction (E4) has never been exercised.

## Pre-registered verdicts

### E2 (warmup error-discipline ablation): **GO** (criterion: warmup
(fw+bl+dl) share ≥ 20% — measured 32.7–100%, every run passes)

Ceiling = warmup-overhead share × warmup eval share of total:
hier_2pl@1000+1000 **18.2%** (32.7% × 55.6%) — the only
production-settings measurement, squarely in the pack's 10–30% realistic
band. Short-warmup regimes are far above it (hier_2pl@100 53.9%,
kronecker 55.7%, pilots 53.5%, blr@1000 73.5% — the last dominated by
the pin, see below). Quality gates per the pack (W-25/W-28 marginal
class + failure counts) unchanged; E2 remains the pack's best expected
value.

### E3 (truncated backward ladder): **NO-GO** (dead end, as the pack
suspected)

Pre-registered criterion (ladder > 15% of pooled kernel evals AND deep
successes ≥ 1% of macro steps) passes only on kronecker_gp (21.7%,
1.11%) and fails everywhere else (hier_2pl@100 15.8%, 0.37%; pilots
26.7%, 0.26%; hier_2pl@1000 8.7%, 0.01%; blr@1000 9.9%, 0%). The
decisive number is the PRIZE, not the share: truncation only saves
ladder evals BEYOND level 0, and with m=1 an h=1 step's full ladder is
a single level-0 eval (prize zero). Beyond-level-0 prize per sampling
phase ≈ 2.9% (hier@100), 1.2% (kronecker), 3.0% (pilots), 0%
(hier@1000), 14.1% (blr@1000). The one non-trivial case (blr) fails the
ladder-share bar, has zero ladder successes ever (truncation would be
behaviorally vacuous there), and is subsumed by E4 anyway (see below).

### E4 (refinement-aware min_micro_steps): **GO** (criterion: sampling
P(h≥1) ≥ 10% AND fw+bl ≥ 15% of sampling evals — passes 4/5)

hier_2pl@100 57.7% & 50.2%; kronecker 42.4% & 48.0%; pilots 38.1% &
45.2%; blr@1000 96.6% & 65.8% — all pass. The exception is the settled
production kernel hier_2pl@1000+1000: 8.7% & 17.3% (P(h≥1) just under
the bar). Recalibrated expectation from the 100 vs 1000 comparison:
E4's payoff is concentrated where adaptation is short/mis-settled
(including every production blr run — h2–h4 refinement is STRUCTURAL
there, 104 evals/draw), while a fully settled kernel already sits near
h≈0. The m-floor observation makes E4 cleanly testable: the estimator
has never once raised m above 1, so "grow m toward h≈0" is an untested
direction, not a marginal tweak. Ablation per the pack: co-primary
grads/draw + ESS/grad, W-25/W-28 marginal-class gates, report joint
(m, h) trajectories.

## Bonus finding (pre-existing, now measured): blr pins at short warmup

At CLI defaults with EITHER pf or deterministic default inits, blr's
chain does not move at all for ≤ ~400+ warmup iterations: every
transition = 1 macro step, all 5 halvings fail (|ΔH| ≈ 8×10⁶ at the
min attempt, still > 0.5 after halving to eps/16), 31 evals burned per
transition, 100% into fw, all sampling draws identical (zero ESS).
Corroboration: W-23's canary arithmetic (blr 18602 calls / 600
transitions ≈ 31 + boundary) means the pin was fully present in those
400+200 runs too — bit-identity kept it invisible. Escape happens
between 400 and 1000 warmup iterations (at 1000: alive, but accepting
only at h3–h4). Relevant to: E2 (a warmup-only loose cap
`--max-error-start` is config-only and would unpin), the W-25/W-28
short-warmup work, and W-41 (freeze-time robustness). Not caused by
W-38 — old binary is bit-identical.

## Caveats

- Aggregate counters cannot see within-phase bursts: the 100 vs 1000
  hier_2pl sampling contrast is the burstiness proxy (57.7% → 8.7%
  P(h≥1) as adaptation settles); per-transition traces would be needed
  for a stronger statement.
- Single chain, single seed per cell (E1 is an accounting item, not a
  3-rep benchmark); kronecker_gp uses the seed-20260820 chain-1
  deviation recorded above.
- Multi-chain runs pool counts process-wide (atomics keep totals
  correct under `--chain-exec threads`; no per-chain split); the W-28
  pilot gate would mislabel pilot draws as sampling-phase (off by
  default, not exercised here).
- Runs raw: `runs/w38/` (gitignored); parsed numbers:
  `runs/w38/accounting.json`; harness: `harness/run_w38.py`.
