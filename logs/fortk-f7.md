# F-7 log — T2 kernel integration + coverage opcodes (fortk/t2-coverage)

Started: 2026-08-26. Binding scope: WORKLOG "F-7 (LAUNCHED 2026-08-26 ...)".

## Setup

- Read first (per charter): WORKLOG F-5 VERDICT / F-6 VERDICT / F-7 charter,
  logs/fortk-f5.md (kernels), logs/fortk-f4.md + logs/fortk-f4b.md (emitter),
  logs/fortk-f6.md (census).
- Branch point recorded: **fortk/t2-coverage off fortk/t1-regions @ b7a3fd5**
  (`b7a3fd5b57548e902dd9e310c1b7271e22ac0fbc`, "fortk T1 direct path:
  single-region graphs emit fortk_grad_direct (F-4b i)").
- CONCURRENT-AGENT NOTE: the main checkout's working tree carries ANOTHER
  agent's UNCOMMITTED regions.cpp edits (a `--census W S` mode + walnuts
  include — their F-4b item (ii) sampler census). To avoid mixing their hunks
  into my commits, my branch lives in a dedicated git worktree:
  `/home/m0hawk/Documents/apin/stan/external/stanli-f7` (branch fortk/t2-coverage,
  off b7a3fd5 exactly). My source edits + build happen there; the main checkout
  is left untouched. This worktree is an extension of the fork, not a fork
  modification; documented here per provenance doctrine.
- Build: external/stanli-f7/build-f7 (cmake Release, -j4 max).
- Outputs: bench/fortk_f7/ (workspace).

## Plan (pinned before coding)

D1 (headline): vendor bench/fortk_t2/vecmath.{h,c} + accuracy harness into
tools/fortk/; run ulp harness ONCE from the fork location (gate: <= 2 ulp
re-confirmed, numbers cited). Emitter: bernoulli_logit vector path first —
block-of-4, scalar tail, cutoff-20 branch blends replicating Stan's saturated
tail semantics exactly per bench/fortk_t2/hier_2pl_vec.c (READ as reference).
Then other exp/log1p-dominated loops by judgment (list vectorized vs not).
GATE: hier_2pl fused-exec >= 1.8x vs unfused exec (census unfused 474 µs;
F-5 hand 191.9; emitter target <= 263 µs); verify 64 pts seed 20260826
grad rel-L2 AND logp rel < 1e-9 vs unfused executor; sampling smoke 3 seeds
statistical equivalence + 0 divergences both arms. esnc/blr/diamonds
re-timed, no regression.

D2 (coverage): SET_INDEX / SET_SLICE / SET_INDEX_INPLACE / SET_SLICE_INPLACE
(aliasing: runtime/src/inplace.cpp + optable.hpp kBackwardValueFree FIRST;
snapshot aliased boundary buffers per island/F-4 doctrine), CONSTRAIN_LU,
BERNOULLI_LPMF, BERNOULLI_LOGIT_GLM_LPMF (raw kernel sources only:
densities_impl.hpp, elementwise.cpp, constrain.cpp — F-3 lesson).
GATE: dogs_hierarchical + wells_dist100_model carve+verify PASS (64 pts
1e-9); arma11 >= 1.1x AND cold compile < 8 s (per-region .c files, parallel
clang <= 4 jobs).

D3: census row updates for hier_2pl, arma11, dogs, wells + 3 spot-check
unchanged models. Table in this log; WORKLOG untouched (parent owns).

## Log

- Session start: environment = same box as F-5 (Ryzen 9 5900X, AVX2+FMA).
  Foreign load: two niced python data-mining jobs (pids 12210/249639,
  loadavg ~1.8) — pin timing to a quiet core, pgrep before every timed run,
  re-run on >5% spread, record both.

## D1b/D2 — emitter work (commits a6e537d + obs-fusion; version fortk-t2r-v4)

Vectorized transcendental paths (all with the vendored kernels, block-of-4 +
aligned-buffer tail so tail lanes see the identical vector code):
- **bernoulli_logit vector path** (n >= 8): pass A gathers nth/sign into
  register-resident nt4/sg4, pass B does vexp/vlog1p + the cutoff-20 branch
  blends (hi: nt>20 -> lp=-emn, adj=-emn; lo: nt<-20 -> lp=nt, adj=sg; mid:
  lp=-log1p(emn), adj=sg*emn/(emn+1) — value mid on strict <-20, partial mid
  on >=-20, exactly Stan's asymmetry), pass C accumulates + stores partials.
- **obs-chain fusion** (scope judgment, documented): the hier_2pl pattern
  BERN_LOGIT(MUL(GATHER(a), SUB(GATHER(m0), GATHER(m1)))) with all-internal
  single-consumer intermediates fuses the FIVE ops into that loop — F-5's
  logged follow-up ("gather fusion est. ~120-140 us/call"). Fwd gathers the
  sources straight into registers (the five 19200-local round-trips + 2 ivsnap
  memcpys vanish); bwd recomputes a/d from the tiny L1-resident sources
  (F-5 pass-3) and scatters the whole chain in one loop. Bit-identity argued
  + confirmed: hier_2pl verify UNCHANGED (1.042e-15 / 1.221e-14 — the same
  numbers as F-4's scalar emitter and the F-6 census).
- CONSTRAIN_LOWER exp loop -> vexp_arr for n >= 16.
- **BERNOULLI_LOGIT_GLM_LPMF** (new opcode): vectorized from birth (GEMV
  scalar per column, then the same blend family; beta partials = X^T td).
Deliberately NOT vectorized (judgment, listed): CAUCHY_LPDF's log1p(t*t)
(esnc is overhead-bound, 10 transcendentals total — nothing to win);
STUDENT_T (lgamma dominates, no kernel); BERNOULLI_LPMF (log/log1m, dogs is
750 obs dispatch-bound; log has no kernel); CONSTRAIN_LU (n=1 scalars in
dogs); GATHER fwd/bwd (not transcendental; AVX2 scatter/gather out of
scope).

New coverage opcodes (raw-kernel transcriptions only):
- SET_INDEX / SET_SLICE + _INPLACE (elementwise.cpp + inplace.cpp contracts
  mirrored in op_supported). Aliasing doctrine: the inplace backward hands
  the written cells to the RHS and CLEARS them on the SHARED cell (value/
  adjoint storage is whatever the slot already has — region-local when
  defined inside, arena when live_in); the carver allows chain REPOKES
  (arma11's 1 copy + 199 inplace writes on one vector) but refuses to poke
  a snapshotted live_in (post-poke readers would read the pre-poke island
  snapshot) and never classifies a poked slot internal from the poke itself.
- CONSTRAIN_LU (constrain.cpp clu_fwd/clu_bwd): n==1 sign-branching
  inv_logit vs vector e/(1+e) inf-guard; jac via log1p_exp's own branch;
  shared/varies bound routing incl. the lane-reduction for shared bounds.
- BERNOULLI_LPMF (densities_lpmf.cpp over the raw prim source): vector
  per-lane + scalar-theta closed forms (sum==N / sum==0 / mixed).
- Carve: length-1 runs of transcendental densities now form regions
  (wells' entire graph is ONE GLM op); cheap ops still need >= 2.
- Compile: per-region clangs run <= 4-wide (popen window, no threads).

Bugs caught by the 1e-9 gate (log for the record):
1. C precedence: `"cell + 0.0"` and `"arena + N"` inlined into
   multiplications/subscripts re-bind (`a + b * c` problem) — the CONSTRAIN_LU
   jac-adjoint term silently degraded to `+ j2` (dogs grad off by 1.2e-2 rel
   with logp EXACT). Fixed by parenthesizing such accessor strings at
   construction. The F-4 emitters were immune (they only use those forms in
   declarations).
2. `int64_t` in emitted code without stdint.h — loops now `int`.

### Results so far (core 23, box with the usual 2 niced foreign python jobs)

- **dogs_hierarchical**: carve 2 regions (CLU x2 | MUL+BERN+ADD_N), verify
  BITWISE (0.0/0.0) PASS. Converted from census REJECT. Ratio 0.97
  (dispatch-bound 7-op model, no perf gate).
- **wells_dist100_model**: carve 1 region (single GLM op — the new 1-op
  rule), verify 1.631e-15 / 4.757e-15 PASS; direct path eligible and PASS
  (same numbers). Converted from census REJECT. fused 27.9 us vs unfused
  38.2 (1.37x, informational).
- **arma11**: carve = ONE region over ALL 806 ops (the 228-op SET_INDEX
  family fused; 607 internal slots). Verify 7.778e-16 / 3.958e-15 PASS
  (region AND direct). **BENCH 5.577x** (unfused 6932 ns, fused 1243 ns,
  direct 1191 ns) — gate >= 1.1x cleared 5x over (census was 0.97x). Cold
  clang 1.349 s (region) + 2.910 s (direct) = 4.26 s < 8 s gate (census cold
  26.6 s); rep spread < 5%.
- **hier_2pl**: verify 1.042e-15 / 1.221e-14 PASS (unchanged). Fused
  225.1 us/call vs unfused 535.7 in-loop => **2.380x** (census-baseline
  arithmetic: 474/225 = 2.11x) — gate >= 1.8x CLEARED; emitter target
  <= 263 us met with 38 us margin; F-5 hand reference 191.9 us. Scratch
  58922 -> 20586 doubles (spill cut).

## D1c — hier_2pl gates + no-regression (2026-08-26)

- **Perf (census protocol, core 2, fresh cache, 3-rep medians, spread <3%)**:
  unfused 473.9 us, fused 215.1 us => **2.203x** (>= 1.8x GATE PASS).
  Core-23 run same binary: 535.7/225.1 = 2.380x (unfused arm drifts with
  box load; both recorded per protocol). F-4 was 0.99x; F-5 hand-fused
  191.9 us.
- **Verify**: 64 pts seed 20260826 grad rel-L2 1.042e-15, logp rel 1.221e-14
  vs unfused executor — UNCHANGED from F-4/F-6 (the vector kernels' <=2 ulp
  and the fusion's bit-identical chains are invisible at 1e-9).
- **Sampling smoke (NUTS, F-4 gate (c) methodology)**: 150/150: 0/0
  divergences; worst z 3.07/5.15/2.37 (seeds 1/7/42). The seed-7 z=5.15
  exceeded F-4's 2.7-2.8 range => re-run at 400/400: z 3.32/3.63/2.36,
  0/0 divergences — small-n noise on heavy-tailed marginals confirmed
  (z uses ess=n, i.e. conservative overestimate). Statistical equivalence
  holds; lp trajectories track (chaotic divergence as in F-4).
- **esnc/blr/diamonds no-regression** (kernels must not touch them; their
  regions are vecmath-free — confirmed by grep of the emitted .c):
  esnc 8.15x (census 8.04), blr 3.85x re-run / 3.14 first set (census 3.95,
  F-4b 3.6-4.2 — first set had 5.7% fused spread, re-run tight at 1.5%),
  diamonds 0.853-0.838x (census 0.92, F-4 0.85 — the known memory-bound
  negative, unchanged within its own history). No regression.
- ctest: **63/63 PASS** (62 inherited + fortk_t1r_smoke; full-suite build
  in the F-7 worktree build-f7 — only tools/fortk/* + the fortk_t1r CMake
  target changed, runtime sources untouched).

## D2c — coverage gates

- **dogs_hierarchical**: REJECT -> carve 2 regions / 5 regops (71% of 7
  ops), verify BITWISE PASS. GATE PASS.
- **wells_dist100_model**: REJECT -> carve 1 region / 1 op (the single-op
  rule; 100% of the graph), verify 1.631e-15 / 4.757e-15 PASS; direct path
  eligible, VERIFY_DIRECT PASS, BENCH_DIRECT 27.0 us. GATE PASS.
- **arma11**: 0.97x -> **5.467x** (census-protocol run: unfused 6655 ns,
  fused 1217 ns; core-23 run 5.577x; spreads <3%) — GATE >= 1.1x PASS.
  ONE region over all 806 ops (was 201 regions / 606 regops; now 1/806,
  100% coverage — the 228-op SET_INDEX family fused). Cold compile:
  region clang 1.348 s + direct 3.020 s = **4.37 s total < 8 s GATE PASS**
  (census cold 26.6 s). Verify 7.778e-16 / 3.958e-15 (region AND direct).

## D3 — census row updates (F-6 table -> F-7; core 2, fresh cache, 3-rep
medians; raw bench/fortk_f7/<model>.run.txt)

Rows that changed (11 — the 4 named + lsat (bernoulli vectorized) + the 6
models whose graphs contain newly-supported opcodes):

| model | ops | regions F6->F7 | regops(cov%) F6->F7 | verify F7 (F6 same unless noted) | unfused us | fused us | ratio F6->F7 |
|---|---|---|---|---|---|---|---|
| hier_2pl | 97 | 2->2 | 96 (99%) | 1.0e-15 / 1.2e-14 | 473.9 | 215.1 | 1.00 -> **2.20** |
| arma11 | 806 | 201->1 | 606 (75%) -> 806 (100%) | 7.8e-16 / 4.0e-15 | 6.66 | 1.22 | 0.97 -> **5.47** |
| dogs_hier. | 7 | REJECT->2 | 0 -> 5 (71%) | bitwise (was —) | 22.0 | 22.8 | — -> 0.97 |
| wells | 1 | REJECT->1 | 0 -> 1 (100%) | 1.6e-15 / 4.8e-15 | 37.7 | 25.8 | — -> 1.46 |
| lsat_model | 28 | 1->1 | 28 (100%) | 1.7e-16 / 1.2e-15 | 82.0 | 44.5 | 1.06 -> **1.84** |
| pilots | 21 | 3->1 | 16 (76%) -> 21 (100%) | 7.4e-16 / 0.0 | 0.773 | 0.213 | 2.87 -> **3.63** |
| bym2_offset | 25 | 4->5 | 15 (60%) -> 18 (72%) | bitwise | 54.6 | 43.3 | 1.28 -> 1.26 |
| accel_gp | 68 | 10->12 | 29 (43%) -> 39 (57%) | 0.0 / 9.8e-16 | 9.98 | 8.72 | 1.22 -> 1.14 |
| garch11 | 8 | 1->2 | 3 (38%) -> 7 (88%) | 1.3e-15 / 8.6e-16 | 11.1 | 10.2 | 1.09 -> 1.09 |
| kronecker | 223 | 63->33 | 131 (59%) -> 162 (73%) | bitwise | 285.1 | 281.1 | 0.99 -> 1.01 |
| low_dim | 16 | 4->4 | 8 (50%) -> 10 (63%) | bitwise | 71.9 | 71.4 | 1.01 -> 1.01 |

Spot-checks (3 unchanged models — no new opcodes, vecmath-free regions,
emitted code identical modulo version): esnc 8.04 -> 8.15, blr 3.95 ->
3.85 (re-run; first set 3.14 on a 5.7%-spread rep set), diamonds 0.92 ->
0.85 (F-4's own value). No regression in the tool.

Coverage/recalc: carve 19/21 -> 21/21 models with >=1 region (dogs + wells
converted). lotka_volterra still carves but verify-crashes on nan ODE
solutions at the seeded points — model-level, F-6 documented, path
untouched by F-7 and NOT retried per its own note => full-pipeline accept
18/21 -> 20/21 (95.2%); rejects 0. Cold compile now parallel (<=4 clangs):
hier_2pl 4.0 s (2 regions, vecmath TU), kronecker 11.8 s (33 regions),
arma11 4.37 s total.

## D1a — kernels vendored, ulp gate re-confirmed (2026-08-26)

- `tools/fortk/vecmath.{h,c}` = verbatim copy of bench/fortk_t2 (md5 match,
  committed 0af980c). Harness bench/fortk_f7/acc_f7.py (acc_f5.py with the lib
  path pointed at a .so built from the FORK's vecmath.c; run ONCE, seed
  20260826, core 23):
  - vexp: MAX 0.8165 ulp (worst at x=708.0239, over_boundary grid);
    92678/97830 bit-equal to correctly-rounded.
  - vlog1p: MAX 1.8721 ulp (worst x=0.13036, model grid);
    96812/103540 bit-equal.
  - lane consistency: bitwise PASS both kernels (rotations 1/2/3/5, chunks
    1/2/3/5/7).
  - GATE (a) re-confirmed from the new location, numbers identical to F-5's
    verdict table (0.8165 / 1.8721) — vendoring is a pure move.

## F-7 VERDICT (2026-08-26) — ALL GATES PASS

| gate | requirement | result |
|---|---|---|
| D1 kernels | ulp <= 2 re-confirmed from fork location | **PASS**: vexp 0.8165 ulp, vlog1p 1.8721 ulp (seed 20260826, ~200k pts each), lane-consistent bitwise — identical to F-5 |
| D1 hier_2pl perf | fused exec >= 1.8x vs unfused (target <= 263 us) | **PASS**: 473.9/215.1 us = **2.203x** (core-23 arm 2.380x); F-4 was 1.00x |
| D1 hier_2pl verify | 64 pts seed 20260826, grad & logp < 1e-9 | **PASS**: 1.042e-15 / 1.221e-14 (unchanged from F-4) |
| D1 sampling smoke | 3 seeds statistical equivalence + 0 div both arms | **PASS**: 400/400 draws, worst z 3.63, divergences 0/0 all arms |
| D1 no-regression | esnc/blr/diamonds unchanged | **PASS**: 8.15x / 3.85x / 0.85x (within their own histories; regions vecmath-free) |
| D2 dogs | REJECT -> carve+verify PASS | **PASS**: 2 regions / 71% ops, verify BITWISE |
| D2 wells | REJECT -> carve+verify PASS | **PASS**: 1 region / 100%, 1.6e-15 / 4.8e-15 (+ direct path) |
| D2 arma11 | >= 1.1x AND cold compile < 8 s | **PASS**: **5.47x**; cold clang 1.35 + 3.02 = **4.37 s** (one region over all 806 ops) |
| D3 census | rows updated honestly | 11 changed rows + 3 spot-checks in this log; carve 21/21, accept 20/21 (lotka's nan-ODE verify crash unchanged, not retried) |

Branch: fortk/t2-coverage (worktree external/stanli-f7), off fortk/t1-regions
@ b7a3fd5. Commits: 0af980c (vendor kernels), a6e537d (T2 emission + coverage
opcodes), f8a1f12 (obs-chain fusion). Not pushed. ctest 63/63.

Surprises / traps (what bit us, for the record):
1. **C-precedence leakage of accessor strings**: "cell + 0.0" and
   "arena + N" inlined into multiplications/subscripts silently re-bind
   (j2*(1-2il) degraded to j2: dogs grads off by 1.2e-2 with logp EXACT —
   values right, ONE adjoint term wrong). The F-4 emitters were immune
   because those forms only ever appeared in declarations. Rule adopted:
   parenthesize composite accessor strings at construction.
2. **Inplace-aliasing** (the charter's flagged trap): the subtle part was
   NOT the backward's hand-off+clear (transcribing the kernel verbatim on
   the shared cell just works) but the CARVER: pokes must be allowed to
   re-define their chain's base (arma11 = 1 copy + 199 repokes on one
   vector — the F-4 redefinition guard would have shattered it into
   fragments), while a poke on a SNAPSHOTTED live_in must be refused
   (post-poke readers would see the island's pre-poke snapshot) and a poke
   must never classify its base internal from the poke itself. The graph's
   own value_reader legality (only value-free backwards precede a poke)
   transfers to regions unchanged — the bwd sweep re-reads exactly the
   post-poke values the executor's would.
3. **Saturated-tail semantics**: F-5's blend-polarity warning replayed as a
   checklist (value mid on strict nt < -20, partial mid on nt >= -20 —
   the asymmetry matters at exactly nt = -20); the 1-op-region GLM emitter
   reused the identical blend block, so the trap needed catching only once.
4. **Single-op graphs**: wells needed the >=2-op region minimum lifted for
   transcendental densities (a blanket lift would have sprouted clang
   calls from isolated cheap ops on other graphs).
5. **Sampling z at n=150**: hier_2pl seed-7 z=5.15 (F-4 range 2.7-2.8)
   shrank to 3.63 at 400 draws — heavy-tailed marginals + ess=n
   conservatism; recorded both rather than quietly re-rolling.
6. The F-5 "gather fusion" follow-up estimate (~120-140 us) was about
   right: 313 -> 225 us actual (88 us) from fusing the 3 GATHER + SUB +
   MUL into the bernoulli loop, on top of the kernels' 474 -> 313.
