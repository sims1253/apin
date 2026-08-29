# W-110 — the ridge-composed E-arm on the 4 ridge-locked floor models: GATES (c) FAIL at the median — a QUALITY lever, not an ESS/s lever; plus the W-96 assembly dead-code defect, and the graduated-budget shortfall diagnosed

Executed 2026-08-29 per WORKLOG "W-110 PRE-REGISTRATION" + AMENDMENT
(the staged SoA-session measurement, run by the sole active session).
Arms: R0 = external_w86 (exp/ridge-guard @ 7dd0f71) binary, default path;
ER = same binary + `WALNUTPIE_RIDGE_GUARD=5`. Both `--chains 4
--chain-exec serial --fixed-warmup`, w1000/s1000, pf inits, mw50, seeds
20260819+1000·rep (per-chain +c), .so = the W-109 all-layers arms
(diamonds' from w106). 24/24 + 3 diagnostic cells rc=0. Ruler: blessed
split estimators. Artifacts: scratch/w110/.

## 0. The W-96 assembly defect (found at launch; on the record)

The assembly branch (assembly/combined-posture @ 472609b) DEFINES
`run_walnuts_multi` — containing the merged #22 ridge guard — but NEVER
CALLS it: main() dispatches only the single-chain path, so `--chains 4`
parses and then dies on the literal `{c}` init pattern. The assembly's
ridge guard is unreachable code; the mm2-guard (W-82) lineage it was
assembled around is single-chain-only. **Package A fix note: the
assembly needs the multi-chain dispatch lineage merged (or the guard
ported to the single-chain CLI) before its guard can fire.** W-110
therefore ran on the guard's home binary (external_w86 tip, carrying the
W-102 graduated budget) — the exact binary family W-88/99/102 validated,
with a real multi-chain dispatch (call site verified).

## 1. Gate results

- **(a) completion: PASS** — 24/24 rc=0, zero aborts.
- **(b) unfired bit-identity: VACUOUS** — the guard fired **12/12**
  cells (every model, every rep), exactly as the ridge-locked-floor
  prediction said; there are no unfired cells to compare.
- **(c) fired-cell ESS vs the W-88/99-derived thresholds: ALL FOUR FAIL
  at the median.** Measured (rep medians, ER vs R0): pilots 9.7 vs gate
  ≥20 (2.21× up); bym2 6.4 vs ≥9 (1.45×); diamonds 8.1 vs ≥30 (1.87×);
  accel 7.1 vs ≥8 (1.56×, marginal). The full-heal regime EXISTS but is
  rep-lottery: bym2 rep0 = 23.0 ESS with rhat-fails 9,412→743;
  diamonds rep1 = 61.5 with rhat-fails 17→6, rhat_max 1.06.
- **(d) R0 ≡ W-109 E at the ESS level: PASS exactly** — R0 medians
  4.4/4.4/4.3/4.6 reproduce the W-109 E table values on all four models
  (walls not comparable across layouts; see conventions below).

## 2. The table (per-rep; wall = sum of per-chain `total time` stanzas —
serial round-robin chains overlap, so this is ~4× true wall; consistent
within-table, NOT comparable to W-109's wall column)

| model | arm | rep | fire F | ESS-min | rhat-max | rhat-fails | wall s |
|---|---|---|---|---|---|---|---|
| pilots | R0 | 0-2 | — | 4.5/4.4/4.4 | 3.3-3.6 | 16/16/25 | ~5.5 |
| pilots | ER | 0-2 | 5.2/35.9/15.5 | 6.4/9.7/15.1 | 1.4-1.7 | 16/15/16 | 10.7/48.6/24.5 |
| bym2 | R0 | 0-2 | — | 5.7/4.0/4.4 | 1.9-inf | 9412/9610/9610 | 450/345/430 |
| bym2 | ER | 0-2 | 50/15924/112 | **23.0**/4.0/6.4 | 1.21/inf/1.99 | **743**/9610/9610 | 2903/19483/6313 |
| diamonds | R0 | 0-2 | — | 4.5/4.3/4.3 | 3.1-4.4 | 18/15/17 | ~37 |
| diamonds | ER | 0-2 | 27.4/74.2/48.2 | 6.4/**61.5**/8.1 | 1.05-1.70 | 13/6/9 | ~300 |
| accel | R0 | 0-2 | — | 4.7/4.6/4.5 | 3.0-3.8 | 72/72/70 | ~26 |
| accel | ER | 0-2 | 38.5/29.9/49.6 | 7.1/7.0/7.1 | ~1.57 | 72/72/34 | 1157/873/733 |

**ER/R0 ESS/s geomean on the 4 models: 0.150×.** ESS rises 1.45-2.21×
everywhere and rhat-max collapses (3.0-4.4 → 1.2-2.0), but walls rise
4.4-14.7×: at these budgets the escape is a large net ESS/s LOSS.
rhat-fail COUNTS at the median improve only on diamonds (17→9); pilots
16→16, bym2 9610→9610, accel 72→72.

## 3. Why the gates failed — two diagnosed mechanisms

**(i) The graduated budget under-budgets the fired class.** POST-HOC
DIAGNOSTIC (labeled as such; 3 pilots cells, `WALNUTPIE_RIDGE_MINMICRO=128`):
ESS-min **103.0/8.4/12.2** (rhat-max 1.17/1.44/1.27) vs graduated
6.4/9.7/15.1. rep0's F=5.2 lock was graduated to only 16 min-micro and
healed to 6.4 ESS; at 128 the SAME rep heals to 103 — a 16× forfeit
from the budget rule. This generalizes W-102's accel-wants-128 finding:
**three of the four fired models (pilots, accel, and bym2's rep0 at 23)
do better at or want the full 128; only diamonds wanted graduation
(W-102).** The W-102 "F ranges overlap, no budget selector" problem
deepens: the default graduation is systematically too small for this
class. Note even fixed-128 is not an ESS/s win at the median (pilots
median ESS/s ≈0.17× R0) — only rep0 (103 ESS at ~4× wall) is a per-cell
ESS/s win (~1.4-5.6×).

**(ii) The deepest locks are not trajectory-budget-healable at all.**
bym2 rep1: F=15,924 — the guard fired, sampling ran 4,824 s/chain at
128 min-micro, and the chain stayed locked (ESS 4.0, rhat inf, 9,610
fails). Consistent with W-84's A0-init-pathology diagnosis: this class
needs a different fix (init/mode separation), not a longer budget.

## 4. Consequences for the composed-posture projection

W-109's "with ridge composed, E/S geomean lands 2-3×" is **REFUTED for
the ESS/s metric on the floor models**: composing ER onto E on these 4
models would multiply the E/S geomean by ~0.15×, not lift it. What the
ridge composition actually buys on this class is QUALITY — rhat-max
collapse and ESS floors rising 1.5-2.2× (with full heals in the right
budget/rep regime: 103/61/23 ESS) — the W-93 framing (ESS-quality vs
ESS/s) repeats here in miniature. The honest composed-stack statement:
the ESS/s headline (1.485×) should be quoted WITHOUT ridge; the ridge
posture is a per-model quality escape (and its budget rule needs the
(i) fix before it is cheap).

## 5. Records

- The staged measurement is CLOSED: negative at the pre-registered
  gates, mechanisms diagnosed, all cells + diagnostic archived
  (scratch/w110/runs/{R0,ER,ER128}, run_w110.py, analyze_w110.py,
  grid.log).
- Open follow-ups (user-decision lane, not auto-run): budget-rule
  revision for the fired class (fixed-128 default vs a smarter
  graduation curve); bym2-rep1-class deep locks = init-class lane; the
  assembly multi-chain fix (Package A note above).
