# Session summary + upstreaming assessment — ox-alpha rounds (2026-08-24 → 08-28)

For the user's return. Covers my sessions only (siblings' work referenced
where it intersects). Ledger: WORKLOG W-63..W-102 (all closed with gates).

## 1. What I did

### Experiments (every one pre-registered, 3-rep medians, canaried)

| # | question | verdict |
|---|---|---|
| W-63/70 | metric-window chopping (100/250/500) | REJECT 3×; non-monotone, high-variance redistribution |
| W-64/71R | step optimizer (naked + wrapped DA, belief) | Adam default confirmed 2×; found the wrapper no-op bug on the way |
| W-72 | discounted min-micro-steps | REJECT (no call reduction) |
| W-73 | Adam hyperparameters (lr, accept-target) | REJECT 3×; named the easy/hard split pattern |
| W-74/75 | pf-inits-for-all × robustness stack | +84.7% aggregate, 30/30 cells, all gates PASS |
| W-85..W-102 | ridge-guard arc (below) | feature shipped + fully validated |
| W-99 | out-of-sample generalization (11 unseen models) | 0 false positives, 9/9 fired cells improved |
| W-100 | multi-chain step-init heuristic | REJECT for flag-lift; env knob kept (radon_vis +650%) |
| W-101 | pf "regressions" | rep noise — package unconditionally positive |

### The ridge guard (the round's deliverable)

86 lines on the robust stack (`exp/ridge-guard`, draft PR #22): after
warmup, cross-chain position dispersion vs adapted within-chain scale
(F); F>5 ⇒ chains locked on a likelihood-null ridge (invisible to every
log-mass statistic) ⇒ rebuild frozen samplers with a graduated trajectory
budget (16–128 by F). Validated end-to-end: +57% alone, **+232% ESS
composed with pf inits, ≈1.26× ESS/s**, zero harm anywhere, unfired
cells bit-identical always, threshold calibrated against the F
distribution (silent ≤5.1 vs locked ≥8.8), generalizes out-of-sample.

### Root causes found (with siblings where noted)

- Multi-chain wrapper-flag silent no-op (mine; PR #14).
- accel finalize abort: NaN alpha → Adam poisoned → freeze ctor throws
  after all compute (mine; #8/#10 fix it).
- pilots: exact likelihood-null ridge; length-binding not metric-
  binding; ridgeF detector (mine).
- The "bad models" reframing: init artifacts, not sampler capability
  (my mining subagent) — redirected the whole program.
- Shell `pkill` shadowed by ZCode pgrep — the stray-grid root cause.

### Knowledge contributions

Two-phase warmup design doc (expect-REJECT ceiling); selector-program
closure (4 dead selectors, Fisher-ratio included — W-76); ESS-quality vs
ESS/s accounting discipline; 5-rep rule for per-model claims; the
easy/hard model-split pattern that dooms global knob changes.

## 2. What's worth upstreaming — and how

### Tier A: upstream-code fixes, evidence complete (file as-is when you choose)
Nothing NEW from my rounds enters this tier — wp#12 (Welford aliasing,
verified present in upstream code) remains the strongest walnutpie
candidate; math#1–#5, stanc3#1, cmdstan#1, stan#1 carry their measured
gates from earlier sessions.

### Tier B: upstream-relevant CONCEPTS from my work (need adaptation; high value)
1. **The null-ridge lock mechanism** (best upstream candidate of the
   round). Findings: (i) models with exact likelihood-null directions
   (additive-shift invariances — common in centered hierarchical
   parameterizations) deterministically lock walnutpie-style short-
   trajectory samplers at different ridge points per chain; (ii) every
   log-mass diagnostic is structurally blind (invariance); (iii)
   cross-chain POSITION dispersion detects it exactly (F statistic,
   bimodal 2–5 vs 8–16000); (iv) it is trajectory-LENGTH-binding, not
   metric-binding (metric variance-floor refuted); (v) a graduated
   budget response fixes it with zero false positives out-of-sample.
   Upstreamable as: a Discourse post / issue with the pilots reprex +
   F-distribution data, or eventually the detector itself once the
   multi-chain orchestration exists upstream. The SCIENCE is
   model-class-general (applies to any short-trajectory sampler).
2. **NaN-alpha adapter poisoning class**: upstream's Adam path feeds
   min_accept; an unflagged NaN logp mid-trajectory poisons the step
   optimizer irrecoverably (probe evidence: WALNUTPIE_DEBUG_ALPHA
   stream). Our #10 fix is fork-lineage, but the class is testable
   against upstream main with a small repro (model returning NaN).
   Upstream fix would be ~5 lines + the non-finite feed guard.
3. **pf-init evidence**: +82% aggregate ESS from initialization posture
   alone on 21 posteriordb models (W-74/101). Supports upstream
   recommendations to default to Pathfinder inits (docs-level, or a
   cmdstan-style `init=pathfinder` convenience).

### Tier C: fork-internal (our lineage; not upstreamable as code)
- wp#14 (multi-chain wrapper dispatch fix), wp#22 (ridge guard
  implementation), graduated budget, W-100 env knob, W-72 branch.
- All experiment harnesses (run_arms.py etc.) — repo tooling.

### Deliberately NOT recommended for upstream
Negative-result knob sweeps (W-63/64/70-73) as PRs — they're ledger
knowledge; could seed a "validated defaults" discussion post at most.

## 3. Decision package recap (fork-level, awaiting you)

Merge wp#7/#8/#9/#10 + #22, adopt pf-init workflow: +232% ESS-quality,
≈1.26× ESS/s, 30/30 completion. Review guide: results/PR_REVIEW_GUIDE.md.
