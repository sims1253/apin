# W-38-E4: refinement-aware min-micro-steps (grow-m) — NEGATIVE RESULT, REJECTED

Date: 2026-08-23. Implementation: walnutpie `exp/grow-m`
(worktree `external/walnutpie_w38e4`, off `exp/safe-adapt-defaults` @
43b6435 + cherry-picked E1 accounting commit fe5dd61 (= 33cd398,
env-gated, draw-neutral per E1) + grow-m commit 9715518). Pre-registration
in WORKLOG (W-38-E4 entry, before any runs).

## Design as implemented

`MinMicroStepsAdaptHandler` keeps its existing shrink rule verbatim
(`max(config_floor, lround(mean_macro/target))`) and gains a grow FLOOR
fed per ACCEPTED macro step through a thread-local sink
(`include/walnutpie/grow_m.hpp`): a streak of `k` consecutive accepted
steps at h >= 1 grows the floor (1 -> 2 -> 4 ... or +1, capped); a
streak of `4k` consecutive accepted steps at h = 0 halves it
(1 -> 0 = fully off); a FAILED step (exhaustion / ladder reject) resets
both streaks — a pinned chain cannot ratchet m. Effective
`m = max(config floor, estimator, grow_floor)` at every call site,
including the `sampler()` freeze. Knobs in WarmupConfig
(`grow_min_micro_steps` default false, `grow_m_streak` 8, `grow_m_cap`
32, `grow_m_increment` 2), CLI `--grow-min-micro-steps` /
`--grow-m-streak` / `--grow-m-cap` / `--grow-m-increment`. Off ⇒ the
sink stays null, no FP/RNG touched, `floor()` = 0 ⇒ bit-identical.

## Gates

### (a) Canary — PASS 20/20 (12/12 required)

Default path of the new binary vs the W-38-E2 base arm runs
(`runs/w38e2/base`, themselves md5-verified against the
exp/safe-adapt-defaults binary in E2): arma11, blr, hier_2pl (required)
+ lsat_model, kronecker_gp (bonus), rep0 × 4 chains, 1000+1000 — every
chain CSV md5-identical.

### (d) Micro-search (blr, 3 reps × 4 chains, 1000+1000) — NO viable variant

| variant | rule | cells | evals/draw (samp) | total/draw | outcome |
|---|---|---|---|---|---|
| base (E2) | — | 3/3 | 9.3 | 25.2 | reference |
| g1 | k8, double, cap 32 | 0/3 | — | — | ABORT 9/9 (rc=-6) |
| g2 | k16, double, cap 32 | 0/3 | — | — | ABORT 9/9 |
| g3 | k8, +1 linear, cap 32 | 0/3 | — | — | ABORT 9/9 |
| t4 | k8, double, cap 4 | 1/3 | 9.4 | 28.0 | ABORT 2/3 |
| t2 | k8, double, cap 2 | 3/3 | 9.5 | 26.5 | survives; +2%/+5% evals; tail ESS 595 < base band 652 |

The abort is the known W-36/W-41 family (`macro_time must be in
(0, inf)` after nan gradients) but ARM-TRIGGERED: e.g. g1/blr/rep0
chain 0 burned 790,363 warmup evals (base ≈ 15k/chain) before dying.
Mechanism: blr's pin/escape regime accepts at h2–h4 with first-attempt
|dH| ≈ 8×10⁶ — alpha = exp(−|dH|) underflows to exactly 0, so the step
adapter has NO gradient signal to shrink eps; growing m then multiplies
the burn of every failed macro step (m·(2⁶−1) evals: 31 at m=1 → 992 at
m=32) until trajectories destabilize into nan positions. t2 (cap 2) is
the only variant that completes all reps, and it is worse than base on
evals. Per the pre-registered rule ("ties → smaller cap-contact") t2
went to the full grid.

### (b) Quality + efficiency grid (t2 arm, 5 models × 3 reps × 4 chains)

| model | arm | bulk ESS-min | tail ESS-min | R-hat max | evals/draw | ESS/wall | gate |
|---|---|---|---|---|---|---|---|
| arma11 | base / grow | 2939 / 2925 | 2529 / 2356 | 1.0016 / 1.0016 | 5.4 / 5.4 (1.001) | 5545 / 5421 (0.978) | **FAIL** (tail −1.7% vs band) |
| lsat_model | base / grow | 730 / 881 | 1210 / 1300 | 1.0112 / 1.0102 | 16.2 / 16.2 (1.002) | 19.6 / 23.3 (1.192) | PASS |
| hier_2pl | base / grow | 625 / 582 | 708 / 711 | 1.0093 / 1.0108 | 16.4 / 16.6 (1.014) | 4.04 / 3.75 (0.927) | **FAIL** (bulk −2.0%) |
| blr | base / grow | 510 / 484 | 704 / 595 | 1.0110 / 1.0061 | 9.3 / 9.5 (1.023) | 880 / 820 (0.932) | **FAIL** (tail −8.8%) |
| kronecker_gp | base / grow | 29.1 / 26.8 | 36.8 / 40.4 | 1.132 / 1.114 | 16.6 / 16.1 (0.974) | 0.46 / 0.42 (0.900) | PASS (band is wide: base rep R-hats 1.05–1.31) |

Quality 2/5 PASS. Efficiency: no model reaches the pre-registered 10%
evals/draw reduction (best −2.6% on kronecker_gp); ESS/wall worse on
4/5 (0.90–0.98), better only on lsat (1.19). The lsat positive is a
warmup-trajectory lottery, not the mechanism: at cap 2 the frozen m is
1 (below), so sampling-side deltas are a different frozen (eps, mass).

### (c) Mechanism (1 chain, 1000+1000, seed 20260819, E1 inits)

At the survivable cap (t2): the grow floor SELF-EXTINGUISHES before the
freeze — sampling-phase m histograms are m1-only on BOTH models. The
sampling kernel is therefore the base kernel; deltas are pure
warmup-trajectory perturbation:

| run | arm | evals/draw | sampling h0/h1/h2 | fw | bl | dl |
|---|---|---|---|---|---|---|
| blr@1000 | off | 9.6 | 6758 / 554 / 0 | 712 | 712 | 316 |
| blr@1000 | grow(t2) | 9.7 | 5352 / 797 / 3 | 1086 | 1086 | 560 |
| hier_2pl@1000 | off | 16.3 | 10640 / 1053 / 0 | 1406 | 1406 | 706 |
| hier_2pl@1000 | grow(t2) | 16.9 | 11749 / 1020 / 0 | 1283 | 1283 | 526 |

h-shift toward h = 0: hier +1.0 pp (91.0 → 92.0%), blr −5.4 pp (92.4 →
87.0%, WORSE). Evals/draw delta: blr +1.0%, hier_2pl +3.7%. Mechanism
gate NOT confirmed at cap 2.

At the design cap 32 (the g-variants; measured on hier_2pl 200+100
smoke before the blr aborts ruled them out) the rule does exactly what
it claims — and this is the decisive measurement: warmup m histogram
m1=110 → m32=263 (fully ratcheted), frozen m = 32, sampling accepted-h
histogram shifts h0 30% → 84% — but at 2.0× the sampling evals per
transition (5600/100 = 56 vs 2759/100 = 27.6) and 4.6× the warmup
evals (28886 vs 6265). The eps shrinkage the coupling buys costs more
than the ladder it removes.

## Verdict: **REJECT** (all three prongs of the pre-registered rule fail)

Quality not preserved (2/5), no ≥10% evals win anywhere, ESS/wall
degraded on 4/5. The failure decomposes cleanly by cap:

1. **cap 32 (design intent):** mechanically real (m ratchets, h → 0 via
   the alpha → eps coupling) but the coupling is a bad trade — the
   adapter pays for the bigger first-attempt error with a smaller eps,
   and evals per unit trajectory time go UP (≈ 2× sampling, 4.6×
   warmup on hier_2pl). On blr it is worse than a bad trade: alpha is
   saturated (underflowed to 0) so the adapter cannot respond, and
   growth multiplies the pin burn until nan aborts (9/9 cells).
2. **cap 2 (only survivable):** the shrink counterweight extinguishes
   the floor before the freeze; sampling is bit-comparable to base and
   what remains is an E2-style warmup-trajectory perturbation — which
   reproduces E2's lesson on the marginal class (arma11/hier_2pl/blr
   tail/bulk dips, small but consistently negative).

## Mechanistic close-out (why the pack's E4 premise was sign-inverted)

At fixed eps the first attempt integrates macro time m·eps, so its
error scales ≈ m·eps³: **growing m makes h = 0 harder, not easier**.
The accepted level at adapter equilibrium is pinned by
δ_adapter / max_error = −ln(0.8)/0.5 = 0.45 < 1 ⇒ h = 0 — and indeed
the settled kernels already sit at 90%+ h0 (E1: hier@1000 8.7% h≥1,
only 17.3% of sampling evals in fw+bl). Persistent h ≥ 1 marks step-
adapter LAG, and m can only help through the alpha→eps channel, which
(a) has nothing to buy where alpha is informative (h0 already dominant)
and (b) is dead exactly where h≥1 is structural (blr: alpha ≡ 0). E1's
GO criterion (P(h≥1) ≥ 10%) selected for the models where the grow
direction is most counterproductive. E4 closed; the fewer-gradients
pack is fully closed (E1 shipped, E2 rejected, E3 NO-GO, E4 rejected,
E5 opportunistic). The honest lever for blr's 104 evals/draw remains
W-41's freeze-time robustness (the pin/escape pathology), not the
ladder base.

## Deviations / notes

- Base arm reused from W-38-E2 (`runs/w38e2/base`) — same seeds/inits/
  models; legitimacy from the 20/20 canary md5 identity.
- Micro-search added two TUNE arms (t4/t2, smaller caps) after g1–g3
  aborted, per the pre-registered TUNE branch ("smaller cap documented").
- kronecker_gp rep0 chain_0 uses the chain_1 init file (E1/E2 recorded
  deviation, known W-36 abort); grid walls measured from per-chain CLI
  timing stanzas (elapsed-time prints were contaminated by concurrent
  load; per-chain walls are arm-identical on hier_2pl).
- Raw runs: `runs/w38e4/` (gitignored). Harness:
  `harness/run_w38e4.py`, `harness/analyze_w38e4.py`; parsed results:
  `results/w38e4_{canary,micro,grid,mech}.json`.
