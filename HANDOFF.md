# apin project handoff

Canonical records live in the repo — this skill only routes you to them:

1. `WORKLOG.md` (append-only, W-1 … W-42) — every experiment, verdict, retraction.
2. `results/FINAL_REPORT.md` — consolidated findings incl. session-2/3/4 addenda.
3. `external/upstream_audit_walnutpie.md` — provenance of every bug we found (§4: STAN_THREADS hazard).
4. `external/upstream_candidates.md` — the ranked upstream push list (stan-math/stanc3/bridgestan).

Portable checkout: `git clone --recurse-submodules git@github.com:sims1253/apin.git` then
follow `BOOTSTRAP.md`. walnutpie fork branch `dev/init-robustness` (kept PRISTINE —
personal-fork branches/PRs are idea history, never merge into mainlines; experimental
stacking branches: `exp/endpoint-grad-threading+chains` → `exp/pilot-burst-gate` →
`exp/parallel-chains` → `exp/safe-adapt-defaults`); cmdstan fork branch
`nindan/mixed-build-guard`; `sims1253/stan` PR #1 = scratch-hoist idea history.
Local working tree: `/home/m0hawk/Documents/apin/stan`.

## Session-3 status (W-23 … W-34, all closed — see FINAL_REPORT §6)

- Shipped in walnutpie exp stack: endpoint-gradient threading (W-23),
  parallel multi-chain 3.2× wall + busy-poll fix (W-30), safe adapt defaults
  (W-31, early exit OFF by default), `--chains N` multi-chain CLI.
- Closed by measurement: warmup early-exit (W-21/25/28 — refuted three ways),
  compile flags (W-27; `-march=native` = hard ban, miscompiles gradients),
  cholesky rev pass at n≤35 (W-33, at algorithmic floor).
- Upstream pack ready in `external/upstream_candidates.md`: stanc3 eigh
  pair-fusion (W-32, −19.4% Ir bit-identical), stanc3 eltwise-fusion /
  gathered-GLM primitive (W-34, −28.2% Ir), stan-math square() pow→mul
  (W-33, one-liner), bridgestan .so cache + STAN_THREADS signals (W-27/W-31).
- Environment gotchas since added to the ledger: ambient LD_LIBRARY_PATH
  (ZCode AppImage) breaks cmake — `env -u LD_LIBRARY_PATH`; interactive make
  aliased -j12 — call `/usr/bin/make`; `install_cmdstan` uses `--cores`;
  multi-chain sampling needs STAN_THREADS=1 .so (`bs_models_threads/`).

## Session-4 status (W-35 … W-42, all closed — see FINAL_REPORT §7)

- Verified end-to-end: exp tip vs stock = **2.93× geomean**, 28/28 cells
  bit-identical (W-36). Warmup early-exit CLOSED by 4 gates (W-37 separability:
  no windowed statistic separates the classes). Fewer-gradients pack closed
  (E1 shipped as standing tool; E2/E4 rejected with mechanism; E5 in W-42).
- Upstream packages READY (external/upstream_pr_kits.md): stanc3 eigh
  pair-fusion (patch + tests + validation, W-39); stan-math cluster-aware
  eigh adjoint (patch + gates incl. kronecker ESS 29→411, W-40); square()
  pow→mul (W-33); bridgestan cache/threads issues (W-27/W-31); walnutpie
  safe-defaults + silent-failure trio (candidate 7, exp-branch fixes).
- Robustness: −inf-init fail-fast + random-init retry policy (exp/init-guard),
  freeze clamp (exp/freeze-clamp); blr short-warmup pin mechanism still open.
- walnutpie exp branches all local, per-idea; suggested promotion order in
  FINAL_REPORT §7. Pre-W-40 kronecker quality numbers carry the wrong-gradient
  caveat.

## Queued fresh-session items (each is a ONE-decision start; do NOT batch them)

### A''. Upstream pushes (user drives; kits ready in external/upstream_pr_kits.md)
- File order suggestion: stan-math cluster adjoint (strongest: ESS evidence),
  stanc3 peephole (patch carries tests), square() one-liner, bridgestan
  issues, walnutpie robustness set. Eigen-5 revalidation of Kit 4's repro
  before filing (gate noted in kit).
### B''. walnutpie exp-stack promotion (user decision)
- Cherry-pick order suggestion: init-guard → freeze-clamp → grad-accounting
  (tool); reject error-discipline + grow-m (history only); then re-run W-36
  benchmark on the promoted stack.
### C''. Open mechanisms (research-grade)
- blr-class short-warmup pin (not tolerance-gated; W-38-E2 probe data).
- kronecker_gp re-baseline under the fixed adjoint (only if W-40 adopted).

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
