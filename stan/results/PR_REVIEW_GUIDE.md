# PR review guide — everything open on your forks (2026-08-27, overnight sessions)

One-page map for your review session. Ordered by suggested review order,
with evidence and interdependencies. `wp` = sims1253/walnutpie.

## The promote package (review together; this is the +232% stack)

Evidence base: `results/combined_posture_w93.md`, `results/pf_init_w74.md`,
`results/ridge_guard_w88.md`, `results/w99_ess.json` (out-of-sample),
W-101 (rep-noise closure). All bit-identity canaries green.

1. **wp#7** init guard (fail-fast + retries) — foundation, no deps.
2. **wp#8** freeze clamp (macro_time abort → auditable fallback).
   Validated live by W-75 (accel cells complete).
3. **wp#9** find_reasonable_step fixes (W-43; blr-pin class). Note:
   single-chain-only flag, deliberately kept so after W-100.
4. **wp#10** NaN-alpha guard — the one that prevents the accel poisoning
   upstream of the clamp (W-75: clamp never even fired).
5. **wp#22** ridge guard (86 lines) — needs #7–#10's lineage
   (`exp/robust-stack-w75` is its PR base). +57% alone, composes to
   +232% with pf inits, generalizes out-of-sample (0 false positives).
**Cost honesty (W-93 addendum):** ESS/s geomean of the package is
**1.15×** (not 2.3× — that figure is ESS-quality). Fired cells pay the
128-micro budget: healthy-but-fired models cost 10–40% ESS/s; broken
models gain up to 125×. Models that were healthy and stay silent pay
nothing. Graduated budget SHIPPED on the branch (F-scaled 16–128); accel-class
cases can override with WALNUTPIE_RIDGE_MINMICRO=128.

6. **Workflow (not a PR):** generate Pathfinder inits per suite run
   (~5% wall) — `harness/run_w74`-style pipeline; `inits_w74/` is the
   worked example.

## NEW: stock-lineage upstream candidates from the final packaging pass

- **wp#24** ridge guard ported to stock library+python (`ridge_guard=5`
  kwarg) — default-off bit-identical to v0.0.2; fixes the pilots lock on
  pure upstream (rhat 3.87→1.14). The strongest single upstream PR from
  the apin campaign; #22 is its fork-lineage twin with the full evidence.
- **wp#23** non-finite acceptance-statistic guard — stock seed-6 accel_gp
  repro (constructor error before, completes after); md5 canary green.

## Independent correctness fixes (review anytime; small)

- **wp#12** Welford aliasing — bug VERIFIED present in upstream's
  `online_moments.hpp` (diff-checked). Highest upstreamability on wp.
- **wp#19** low-rank momentum wrong invariant + 244-check property
  suite — sibling-verified; affects anyone using `--metric-rank
  --metric-full`; PR#12's fix independently re-verified here.
- **wp#21** refuse `--chain-exec threads` on STAN_THREADS=false .so
  (TSan-verified races) — cheap, prevents silent corruption.
- **wp#18/#17** init screening extensions (constraint-boundary class —
  the kronecker LKJ pathology; poisoned-gradient naming).
- **wp#14** wrapper flags no-op under `--chains>1` (PR#14 class; fork
  lineage only — multi-chain CLI is ours).
- **math#2/3/4** (square pow→mul; two sign-factor fixes), **math#1**
  (eigenvector adjoint gauge), **stanc3#1** (eigh pair-fusion),
  **cmdstan#1** (mixed-build guard), **stan#1** (scratch hoist) — all
  measured wins/bug fixes with gates in WORKLOG; upstreamable as-is.

## Tooling / experiment lineage (internal; merge at will)

- **wp#11** warmup tracer; **wp#15** trajectory-depth diagnostics;
  **wp#16** loud single-chain flag failure; **wp#20** min-micro-guard
  (sibling's reactive pin detection — NOTE: W-85 showed pilots-class
  locks are length-binding; combine thinking with #22 before promoting
  both); **wp#13** low-rank auto-screen gating (direction closed, fix
  kept); **wp#1–#6** historical idea record.

## Known interactions to keep in mind

- #22's base is the unmerged robust stack; merging #7–#10 first makes
  #22's diff minimal.
- #20 (min-micro restart) and #22 (budget bump) address overlapping
  failure classes with different mechanisms — pick one as primary after
  reviewing W-85's length-binding evidence.
- Re-run the W-36 benchmark once the stack merges to refresh the
  headline number (the +232% uses build_w86 = stack + guard).
