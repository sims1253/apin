# W-125 — the ridge-budget decision matrix: fixed-128 vs graduated on the fired class — the curve's cap makes bym2's "choice" vacuous; fixed-128's only big win is the marginal-lock (low-F) class; recommendation = raise the floor, not flatten the curve

Executed 2026-08-29 per WORKLOG "W-125 PRE-REGISTRATION". Arm: ER-128
= external_w86 binary + `WALNUTPIE_RIDGE_GUARD=5` +
`WALNUTPIE_RIDGE_MINMICRO=128`; protocol W-110 verbatim (chains 4,
serial, fixed-warmup, w1000/s1000, pf inits, mw50, seeds
20260819+1000·rep; walls = sum of per-chain `total time` stanzas,
~4× process wall, load-sensitive — see §4). Ruler: blessed split
estimators (DROPS+'X' excluded). 9/9 ER-128 cells rc=0.

## 0. The structural finding: graduated already IS fixed-128 for F ≥ 40

The W-102 graduated curve in stan_cli.cpp is
`budget = clamp(16·F/5, 16, 128)` — CAPPED at 128. Per the W-110 ER
mc.logs, bym2's F = 50/15,924/112, diamonds rep1/2's 74.2/48.2 and
accel rep2's 49.6 ALL clamped to 128 in the graduated arm: same
binary, same seed, same inits, same effective budget ⇒ bit-identical
by construction. Those 5 cells were REUSED (symlink + REUSED marker,
scratch/w125/runs/ER128/…); the equivalence claim is anchored
EMPIRICALLY: fresh ER-128 bym2 rep0 (F=50, also a clamped cell) came
out **4/4 chains md5-equal** to the W-110 ER archive cell. Fresh cells
run: bym2 rep0 (the anchor), diamonds rep0 (87→128), accel rep0
(123→128), accel rep1 (95→128). Fresh-cell F values reproduce W-110's
exactly (38.514/29.886/27.429) — deterministic warmup. The bym2 ~1h
warning never bit (fresh rep0 ≈ 20 min process wall; rep1's 19,483 s
cell was reused, not re-run); the 2h kill rule was not needed.
Consequence: **the pre-registered "does 128 beat bym2's graduated
23.0?" question dissolves — 23.0 IS the fixed-128 value.**

## 1. Per-rep cells (ESS = ess_bulk_min; fails = rhat>1.02 count)

| model | arm | rep0 ESS/fails | rep1 ESS/fails | rep2 ESS/fails | F per rep |
|---|---|---|---|---|---|
| pilots | R0 | 4.5/16 | 4.4/16 | 4.4/25 | — |
| pilots | ER-grad (16/114/49) | 6.4/16 | 9.7/15 | 15.1/16 | 5.2/35.9/15.5 |
| pilots | ER-128 | **103.0**/15 | 8.4/16 | 12.2/16 | same F |
| bym2 | R0 | 5.7/9412 | 4.0/9610 | 4.4/9610 | — |
| bym2 | ER-grad ≡ ER-128 (all clamp 128) | **23.0**/743 | 4.0/9610 | 6.4/9610 | 50/15924/112 |
| diamonds | R0 | 4.5/18 | 4.3/15 | 4.3/17 | — |
| diamonds | ER-grad (87/128/128) | 6.4/13 | **61.5**/6 | 8.1/9 | 27.4/74.2/48.2 |
| diamonds | ER-128 | 7.9/15 | 61.5/6 | 8.1/9 | same F |
| accel | R0 | 4.7/72 | 4.6/72 | 4.5/70 | — |
| accel | ER-grad (123/95/128) | 7.1/72 | 7.0/72 | 7.1/34 | 38.5/29.9/49.6 |
| accel | ER-128 | 7.2/72 | 7.2/72 | 7.1/34 | same F |

## 2. THE DECISION TABLE (rep medians; walls stanza-summed)

| model | arm | ESS | wall s | ESS/s | rhat_max | fails | E128/R0 E/s | E128/ER E/s |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| pilots | R0 | 4.4 | 5.5 | 0.805 | 3.50 | 16 | | |
| pilots | ER-grad | 9.7 | 24.5 | 0.398 | 1.62 | 16 | | |
| pilots | **ER-128** | **12.2** | 73.2 | 0.166 | **1.27** | 16 | 0.21× | 0.42× |
| bym2 | R0 | 4.4 | 430 | 0.010 | 3.42 | 9610 | | |
| bym2 | ER-grad ≡ ER-128 | **6.4** | 6313 | 0.001 | 1.99 | 9610 | 0.10× | **1.00×** |
| diamonds | R0 | 4.3 | 37 | 0.117 | 3.79 | 17 | | |
| diamonds | ER-grad ≈ ER-128 | 8.1 | 320 | 0.025 | 1.47 | 9 | 0.22× | 1.00× |
| accel | R0 | 4.6 | 27 | 0.172 | 3.25 | 72 | | |
| accel | ER-grad ≈ ER-128 | 7.1/7.2 | 873/1597 | 0.008/0.005 | 1.57/1.55 | 72 | 0.03× | 0.55× |

Per-model verdict data:
- **pilots: fixed-128 wins on ESS** (median 12.2 vs 9.7; rhat_max
  1.62→1.27) — but the win is ONE rep: rep0 (F=5.2, graduated budget
  16) heals 6.4→103.0 (16.1×, the grid's only per-cell ESS/s win,
  1.66×); rep1 9.7→8.4 and rep2 15.1→12.2 are slightly WORSE at 128.
- **bym2: no choice exists** — every F clamps past the cap; the arms
  are one arm (md5-verified). The deep lock (rep1, F=15,924) is
  budget-immune at 128 (5.4 h, ESS 4.0, rhat inf) = init-class lane.
- **diamonds: graduated** — median tie (8.1 = 8.1; reps 1/2 identical
  cells); rep0 buys +23% ESS (6.4→7.9) for +39% wall and fails
  13→15. The W-102 "diamonds wants graduation" reading survives.
- **accel: graduated** — 123→128 and 95→128 buy +0.1/+0.2 ESS
  (7.1→7.2) for +39%/+83% wall; ESS ceiling ~7.1-7.2 regardless of
  budget ≥ ~95. The W-102/W-110 "accel wants 128" hypothesis is
  refuted at the margin: it wanted ≥95, not 128.

Pre-registered expectations: diamonds-fixed-worse = tie at median
(rep0 opposite, disclosed); accel ≥ graduated = trivially true (+0.1);
bym2 = dissolved by the cap. Fixed-128 is a net ESS/s LOSS everywhere
(0.03-0.22× R0) — W-110's "quality lever, not ESS/s lever" conclusion
now holds for BOTH ridge budgets.

## 3. CURVE RECOMMENDATION (decision data, not a verdict)

The response of ESS to budget is a STEP at the marginal-lock class
and flat-to-noise elsewhere: 16→128 on pilots rep0 = 16× ESS;
114→128 (pilots rep1), 49→128 (rep2) = slightly negative;
87→128 (diamonds), 123→128/95→128 (accel) = +23%/~0. Crucially the
benefit ANTI-correlates with F: the cell that wants the full 128 has
the LOWEST F (5.2), so no monotone-in-F curve can separate the classes
— flattening to fixed-128 overspends mid-F cells (+83% wall on accel
rep1 for +0.2 ESS), while the current 16·F/5 starves exactly the
marginal lock (rep0 got 16, forfeited a 16× heal). The shape that
dominates both measured arms on every measured cell is **raise the
floor: budget = max(64, 16·F/5), cap 128** — identical to graduated
on every measured cell except pilots-class (F≲16), where it lifts
16→64 toward the heal regime, and never above graduated+ε elsewhere.
Residual risks, stated: (i) the 64-response of the heal class is
UNTESTED (one cheap follow-up cell: pilots rep0 at MINMICRO=64;
rep0's heal could need the full 128); (ii) pilots rep2 (F=15.5) got
its BEST ESS at 49 and fell at 128 — a 64-floor may also cost it a
little; (iii) n = 3 reps × 4 models, and the heal itself is
rep-lottery (W-110 §3). The alternative reading — permanent class
split with a selector — fails on exactly the F anti-correlation: F
cannot predict who benefits, so the floor is the only knob the data
supports. bym2 needs no budget knob at all (any curve lands at 128;
its rep1-class fix is the init/mode-separation lane, not budget).

## 4. Conventions and records

Wall caveat: bym2 rep0 re-ran md5-identical to W-110 yet walled
3527 vs 2903 s (+21%) — stanza-sum walls are load-sensitive (this
grid shared the box with W-118 at ≤2 workers, nice 19); ratios
within-table only. Artifacts: scratch/w125/ (run_w125.py with the
reuse/verify logic, analyze_w125.py, analysis.log, grid.log,
runs/ER128/<model>/rep<r>/ with DONE + REUSED markers; reused cells
symlink into scratch/w110/runs/ER/). W-110 archive reused read-only:
runs/{R0,ER}, its ER128 pilots diagnostic. No WORKLOG/comms writes
(PI-owned).
