# apin project handoff

Canonical records live in the repo — this skill only routes you to them:

1. `WORKLOG.md` (append-only, W-1 … W-22) — every experiment, verdict, retraction.
2. `results/FINAL_REPORT.md` — consolidated findings incl. the session-2 addendum.
3. `external/upstream_audit_walnutpie.md` — provenance of every bug we found (all ours, none upstream).

Portable checkout: `git clone --recurse-submodules git@github.com:sims1253/apin.git` then
follow `BOOTSTRAP.md`. walnutpie fork branch `dev/init-robustness`; cmdstan fork branch
`nindan/mixed-build-guard`. Local working tree: `/home/m0hawk/Documents/apin/stan`.

## Queued fresh-session items (each is a ONE-decision start; do NOT batch them)

### A. walnutpie endpoint-gradient threading (from W-20)
- Measured: exactly ONE redundant logp_grad per transition (start re-eval; dups = warmup+draws+1 on every model). ~4–6% of all gradient calls.
- Fix: thread (theta, grad, logp) through WalnutsSampler/AdaptiveWalnuts state.
- **Gate: draws must stay bit-identical** (reusing an identical double changes no arithmetic — a wrong implementation cannot pass silently). 3 models × 2 seeds, then w17g-style grad-count check.
- Touches `include/walnutpie/walnuts.hpp` (hot path — the 2026-08-21 template-surgery mishap happened there: make one edit, build, test, commit; never batch template edits).

### B. cmdstan stan-2a2 scratch-hoist (Phase 2a)
- Plan is COMPLETE in `patches/stan-2a2-scratch-hoist-PLAN.md`: hunks, recursion-safety argument, 5 gates (bit-identity first — the rho-hoist history says do not assume it), what never to touch.
- Target: `external/cmdstan/stan/src/stan/mcmc/hmc/nuts/base_nuts.hpp` @ submodule d13c50c0f (~630 heap allocs/transition at depth 6; pilots memcpy share 21%).
- Ship as PR to the cmdstan fork, `develop` base, never upstream.

### C. walnutpie library-level warmup early-exit (from W-21/W-22)
- CLI knob shipped (default off; `--early-exit-warmup`): 1.3–2.4× wall where it exits but hurts the marginal class.
- W-22 root cause: on those models the **step size** still grows +170% late in warmup while mass is stable (+2–13%) — the quality-preserving gate must be step-drift (<5% over last 2 windows), and ideally cross-chain (the `adapt()` controller already has the machinery).
- The natural place is the multi-chain controller, not the CLI.

## Protocol (violating these produced both retractions)

- **3 reps, medians, or it didn't happen.** Single-rep comparisons on this benchmark swing 10–30× (hier_2pl min-ESS 20–420 on bit-identical code). Seeds: 20260819+1000·rep+c, 4 chains, pf inits from `/tmp/winit` (regenerate via `harness/run_pathfinder.py`).
- **Pre-register in WORKLOG.md before running** (expectation + gates). Negative results get recorded and PR'd, same as wins.
- Retract loudly: post the correction where the claim was made (PR #4 comments are the ledger).
- Comparisons across code versions need bit-identity checks on unchanged paths (default path = canary).

## Gotchas (each cost real time)

- After scripted header edits in walnutpie: **delete the .o / build --clean-first** — incremental builds have skipped header changes (.o mtime < header mtime shipped a heap-corrupting binary while manual builds were clean).
- CLI dispatch has 8 `run_walnuts<>` call sites; a new `run_walnuts` parameter must be wired at **all 8** or flags silently no-op (grep the arg after editing).
- BridgeStan model instances are not thread-safe: serialize `logp_grad` (mutex) or one instance per chain. Constrained output includes GQ — headers must match column count. Adaptive stopping ⇒ ragged chains ⇒ trim to min length before ESS.
- A shared `std::normal_distribution` interleaved across two RNGs is NOT reproducible (Box–Muller cache) — one distribution object per stream.
- cmdstan argv: separate tokens (`data` `file=x`); `init=` is one token. `pgrep -f` self-matches — use `kill -0`.
- Machine discipline: ≤4 cores always, no GPU. `uv run python` for the project venv; posterior 1.7 needs per-variable `ess`.
- Measurement priors (do not re-litigate without new data): logp_grad = 68–99.7% of walnutpie sampling wall (SIMD/kernel direction closed); warmup = 65–76% of total wall; checks ≤2.2% of cmdstan Ir (folklore rejected); fold ≈ rec core-set with good inits; basis-extraction rule is second-order (W-19); funnel class is a sampling/mode-lock problem, not adaptation.

## Repo hygiene (2026-08-23 incident, now standing rule)

**Never `git add -A` in the stan repo.** It swept `runs/` (26,692 files) and
model `.so` binaries into history (44GB of loose objects; purged via
git-filter-repo, `.git` now 86MB). `runs/`, `bs_models/`, `bs_models_o3/`,
`models/*_model.so` are gitignored — stage explicitly (`git add WORKLOG.md
harness/ ...`).
