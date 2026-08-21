**Follow-up 12: provenance audit of this branch vs upstream + four fixes (one changes results).**

I ran an independent audit of every hunk in `origin/main..dev/init-robustness` (full report file: `external/upstream_audit_walnutpie.md` in our benchmarking repo). Findings:

**Provenance of the session's bug fixes: all three bugs (metric drop at freeze, reversible/uturn under wrong Hamiltonian, anti-windup wrap) were introduced *and* fixed on this branch — none exist in upstream `main` (6162d88).** 51 hunks audited: 35 pure additions; 16 touching upstream lines, all classified extension/refactor-for-extension with default-off knobs. **No genuine upstream bug fixes to forward.** The minimal observable slice (`adapt_with_stats` + dispersion) is extracted as #6.

**Correction to my own earlier claim (follow-ups 9/10):** the sd=0-chain anti-windup incident was a *single* wrap with pass-rate-8 semantics (drops 7/8 saturated updates), not a "double wrap dropping 63/64" — and the "single-wrap matches pass-through" validation was trivially explained: after the fix the CLI path had *no* wrap at all, because the CLI passes an explicit adapter type and the library-default wrap never applied. I.e. follow-up 10's fix accidentally made `--anti-windup` **inert**. Both corrected in 6fd6664: the CLI dispatch now selects `AntiWindupAdapter<...>` explicitly (factory reads the config rate).

**The audit also caught two live correctness bugs at HEAD**, now fixed:
1. **Fold-mode freeze mismatch (present since the first low-rank commit 5302ed8):** warmup transitions used `rank_folded_estimate()`, but the frozen sampler used the unfolded `inv_mass_estimate()` — a silent metric change exactly at the warmup/sampling boundary, same family as the full-mode bug in 5e56ff2. `inv_mass()` now mirrors warmup's rank-active logic.
2. **Rank-mode combined-span uturn:** `transition_w_lr`'s combined-span check called the diagonal `uturn(..., lrm.D)` while the trajectory integrates the full operator; now `uturn_lr`.

**Effect on results (4 chains, pf inits, 1000+500, rep0):**

| config | blr | hier_2pl |
|---|---|---|
| recommended (default path) | 439 / 1.0139 — **bit-identical to pre-fix** | 25 / 1.122 |
| `--metric-rank 10` (fold) | 340 / 1.0082 | **38 / 1.093** |
| `--metric-rank 10 --metric-full` | 413 / 1.0077 | **167 / 1.030** |

The two rank fixes turn the rank modes from *handicapped* to *winning*: hier_2pl full-rank is now 6.7x min-ESS vs diagonal (strongest result yet on that model). Default-path users see zero change.

**W-15 (targeted reinit):** outlier attribution + scored pool draws + consensus mass/step seeds — roughly neutral on the funnel class (esc 62->71 med ESS, pilots R-hat 2.83->2.53, diamonds unchanged), consistent with the diagnosis that the residual is single-chain in-sampler mode-lock, not an initialization problem.