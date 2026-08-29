# Overnight session-cluster summary — 2026-08-24/25 (for review on return)

Four concurrent agent sessions measured walnutpie ESS/s levers for ~10h
under the standard protocol (3 reps, medians, pre-registration). Every
result below is recorded with gates in WORKLOG.md; this file is the map.

## TL;DR

No adopted performance changes. The defaults survived every head-to-head
(Adam step optimizer, exponential metric discounting, lifetime
min-micro-steps mean). Two robustness/UX bugs were found and fixed as
draft PRs on sims1253/walnutpie (#13, #14). Several big research
directions are now CLOSED WITH DATA rather than open questions.

## Verdict table (all REJECT unless noted)

| lane | experiments | outcome |
|---|---|---|
| Step optimizer choice | W-64 naked {da,belief} vs adam; W-71R wrapped da | Adam confirmed 2×; naked DA aborts 5/10 models; wrappers don't rescue; diamonds +234% was a naked-DA artifact |
| Metric windowing | W-63 chop@100, W-70 chop@{250,500} | Discounting default confirmed 2×; chopping = high-variance ESS redistribution, non-monotone in window |
| Min-micro-steps estimator | W-72 EWMA decay=0.99 | ESS neutral, zero gradient-call reduction; lifetime mean stays |
| Partial momentum refresh | W-63 (#2) α∈{0.5,0.7} | REJECT; centered funnels are the ANTI-target (sign inverted) |
| Low-rank Fisher metric | W-63 campaign + W-65 screen fix + W-66 threshold sweep (1020+240 jobs) | DIRECTION CLOSED at CORE_SET scale: winners exist (2.5–3.4×) but no viable screen separates them from harm; window_cross_ratio ordering inverted |
| DEER/Picard trajectory parallelism | W-70 feasibility (#2) | NO-GO on all four pre-set conditions |

## Shipped (draft PRs on sims1253/walnutpie, awaiting your review)

- **#14** `fix/multi-wrapper-dispatch` → `exp/safe-adapt-defaults`:
  `--anti-windup` / `--step-grad-clip` / `--step-opt-batch-stride`
  silently no-op'd under `--chains>1` (wrapper type-ladder only wired in
  the single-chain dispatch). Fix verified by md5-different draws +
  bit-identical unflagged canary. Any prior multi-chain wrapper-flag
  numbers elsewhere should be treated as naked-optimizer numbers.
- **#13** (orchestrator #2) auto-screen gating for the full low-rank
  operator, off `dev/init-robustness`, byte-identical default path.

## Root-caused robustness items (ledger entries, not yet fixed)

- kronecker_gp rep0 chain pin: deterministic-normal init lands on the
  LKJ-Cholesky constraint boundary (diagonal exactly 0) — model throws
  at every eval; explains three separate historical anomalies.
  Suggests the −inf/fail-fast init screen (W-42) needs this class too.
- NaN-adapter-feed poisoning: fixed on branch `rob/nan-alpha-guard`
  (draft PR #10); residual −inf-init gap noted there.

## State of the queue after tonight

HANDOFF C'' leads: Fisher low-rank → CLOSED (above); SoA arena batches →
shipped through batch 2 (W-57/W-58, separate thread); two-phase warmup →
STILL OPEN (only remaining queued sampler-side lead with literature
backing); kronecker re-baseline → still parked pending math#1.
New leads surfaced but unrun: model-adaptive metric-window screen (no
selector known), conditional step-optimizer for easy targets,
min-micro×max-macro-steps joint policy (P3 stage-1 log parse is cheap).

## Infra notes

- Branches/worktrees created tonight: `fix/multi-wrapper-dispatch`,
  `exp/discounted-min-micro` (worktree `external_w72/walnutpie_w72`,
  contains both experiment changes, not merged anywhere);
  `exp/safe-adapt-defaults` pushed to the fork as PR base (exact local
  state; promotion into main remains YOUR decision per B'').
- Reusable harness: `harness/run_arms.py` (multi-arm grid runner with
  env/binary overrides), `harness/analyze_arms.py` (multi-arm ESS vs
  baseline with abort accounting).

## ERRATUM (evening follow-up, quality-gap mining W-74-prep)

The "bad cells" quoted in the verdict table context (bym2 geoESS 5.9,
accel 42, diamonds 60) are measurements under deterministic NORMAL(0,1)
inits (inits_w36) on the W-36 grid — an init-sensitivity artifact, NOT
current sampler capability. With Pathfinder inits (pf_full / clang_native
arms in results/table_per_config.csv) current walnutpie sits AT OR ABOVE
CmdStan parity on bym2 (4722 vs 4594), diamonds (3333 vs 3302),
kronecker_gp (1671 vs 1672), hier_2pl, lotka (2991 vs 1115 — walnutpie
WINS). Genuine remaining walnutpie-specific gaps: pilots rep-collapse
(min 6 vs cmd 31), eight_schools_centered 3.66x geo gap (tau funnel,
rep0 rhat 1.45), accel_gp mid-trajectory abort discipline, and the
kronecker dead-init cell (LKJ-boundary init). Consequence: init
robustness, not adaptation tuning, is the remaining quality lever.
Full comparison: comms.md overnight-2 section / table_per_config.csv.
