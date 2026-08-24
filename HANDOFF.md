# apin project handoff

Canonical records live in the repo — this skill only routes you to them:

1. `WORKLOG.md` (append-only, W-1 … W-56) — every experiment, verdict, retraction.
2. `results/FINAL_REPORT.md` — consolidated findings incl. session-2 through session-6 addenda.
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

## Sessions 5/6 status (W-43 … W-56, all closed — FINAL_REPORT §8)

- Robustness complete: pin fixed (w100 ESS 5-9 to 779), -inf inits
  guarded, freeze clamped; community-sourced shields tested and rejected.
- Gradient-cost program closed (W-45..W-50, W-53): every lever shipped,
  refuted with mechanism, or packaged upstream.
- Filing: 9 fork-internal PRs live (Stan AI Contribution Policy): math #1-#4,
  stanc3 #1, docs #1, walnutpie #7-#9 + sims1253/stan#1. stan-math checklist
  verified locally per branch (W-56). Filing kit: external/pr/ (README index,
  bodies, DISCOURSE_POST.md, maintainer-response docs: reprex-3369.md,
  expect-ad-blindspot-3369.md). One session transcript published as the
  worked example: results/traces/w46-log1p-ceiling-transcript.md.
- Post text: stan/external/pr/DISCOURSE_POST.md (paste-ready).

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

### A''. Respond to maintainer engagement on the fork PRs (user drives)
- Ready-made replies: external/pr/reprex-3369.md (sign-flip amplification,
  verified both arms) and external/pr/expect-ad-blindspot-3369.md (the
  tol_min = tol^2 = 1e-8 floor makes sub-5e-9 gradients sign-uncheckable;
  the old mix test never entered the cutoff branch). Unfixed sibling:
  the OpenCL bernoulli_logit_glm variant carries the same missing-signs.
### B''. walnutpie exp-stack promotion (user decision)
- Per-idea robustness branches are clean and pushed (robustness/init-guard,
  freeze-clamp, step-heuristic-fix off dev/init-robustness). The perf stack
  (exp/safe-adapt-defaults lineage) is still local-only; suggested order in
  FINAL_REPORT §7; then re-run the W-36 benchmark on the promoted stack.
### C''. Open research directions (ranked by W-51 scan)
- Score/Fisher low-rank+diagonal metric in walnutpie warmup: arXiv:2603.18845
  (Seyboldt/Carlson/Carpenter; 4x median ESS/grad on 114 posteriordb models);
  walnutpie upstream is already becoming "Adaptive WALNUTS" — the clear
  next-direction, and our W-9/W-10 low-rank work is the local precedent.
- SoA arena batch rollout: W-53 verdict GO; 7-batch gated migration plan is
  the fresh-session artifact (results/soa_var_w53.md §2); mind the
  per-toolchain codegen-sensitivity risk and the bridgestan prebuilt-.o trap.
- kronecker_gp re-baseline under the fixed adjoint (only if math#1 adopted).
- Two-phase warmup (alpha-subsample early + truncated full re-adaptation):
  W-45 follow-up with mechanism-predicted modest ceiling.

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
- Machine discipline: ≤4 cores always, no GPU. `uv run python` for the project venv; posterior 1.7 needs per-variable `ess`. System valgrind 3.23 installed.
- Shallow clones bite later: squashing/rebasing on a shallow base produces parentless commits ("no history in common" on fork PRs). `git fetch --unshallow` first.
- bridgestan `compile_model` silently reuses a cached `.so` regardless of `make_args` — copy the `.stan` into a per-variant scratch dir; verify via `model_info()`.
- The gh token lacks `gist` scope; `/tmp` is volatile (inits live in-repo: inits_w25/, inits_w36/).
- Measurement priors (do not re-litigate without new data): logp_grad = 68–99.7% of walnutpie sampling wall (SIMD/kernel direction closed); warmup = 65–76% of total wall; checks ≤2.2% of cmdstan Ir (folklore rejected); fold ≈ rec core-set with good inits; basis-extraction rule is second-order (W-19); funnel class is a sampling/mode-lock problem, not adaptation.
