# W-112.2 — the throw-set fix for `normal_lpdf_gathered`: ALL GATES PASS; the W-116b divergent radon_var cells land on the archive values (rep1_c2 → fc7dbe12…, rep2_c0 → e6ab04e0…, full 12/12 == frozen archive including the knife-edge rep0_c2 == its FROZEN 65d8f98c, stable ×3); radon_pp 12/12 intact; W-112's original md5s reproduced; wall E′/E = 0.297 (band ≤0.60); ESS unchanged at 415.0; ESS/s E′/S = 3.90×

Executed 2026-08-29 per WORKLOG "W-112.2 PRE-REGISTRATION" (the PI-approved
escalation package from W-112.1). Deliverable: branch **`gathered-normal-fmafix`**
in worktree `external/math_dev_w1121`, 2 commits on top of the W-112 base
`bc00891778`: `9a07ffa459` (the header fix) + `559da085d5` (the TU's
ThrowSetParity). Not pushed. Artifacts under `scratch/w1121/`.

**Headline: two predicated compares per element — stock's per-element
`check_not_nan(y)` + `check_finite(mu)`, restored in the shared impl's term
loop in stock's order — close the W-116b radon_var divergence at its root
(the W-112.1 mechanism: exceptions are observable sampler behavior; stock's
`check_finite(mu)` throw becomes `(logp=-inf, grad=0)` in the sampler
wrapper, which a silently-computed NaN lp with NaN gradients does not
reproduce). Every gate green, both originally-divergent cells now
md5-exact against the frozen archive, and nothing that previously passed
regresses.**

## 1. The fix (commit `9a07ffa459`)

In `normal_lpdf_gathered_impl`'s term loop (both eta shapes and all four
operand routes share the impl):

```cpp
check_not_nan("normal_lpdf", "Random variable", y_d.coeff(k));
check_finite("normal_lpdf", "Location parameter", mu_val.coeff(k));
```

- **Order**: stock's per-element order (y then mu); sigma stays checked
  once per call (call-constant value ⇒ identical throw set; only the
  mixed sigma≤0-AND-bad-y/mu state reports Scale instead of Random
  variable/Location — pre-registered, message-CLASS parity).
- **Message fidelity**: the scalar overloads reproduce stock's exact
  text — the scalar lpdf's y_val/mu_val are scalars through
  `as_value_column_array_or_scalar`, so `elementwise_check`'s scalar
  branch fires (value printed, no index). Gate-proven byte-identical.
- **Cost/numerics**: ~2 predicated compares/element, branch not taken on
  valid states; zero FP ops added (FMA counts of the rebuilt .sos are
  IDENTICAL to their old-E′ counterparts — §3 provenance); value and
  gradient arithmetic untouched (gate (a) re-certifies W-112's 22,360
  valid-state bitwise checks at BOTH flag levels).

## 2. Gates

| gate | evidence | verdict |
|---|---|---|
| (a) bitwise unit, MODEL FLAGS + -O2 | `scratch/w1121/test_prim.cpp` (W-112's gate extended with 10 throw-set cases), built on the bs_alllayers stack with the fixed header FIRST on the include path (`build_gate_a.sh`), at `-O3 -mavx2 -mfma` AND `-O2` | **22,380 checks, 0 mismatches at BOTH levels** (`logs/gate_a_O3.out`, `logs/gate_a_O2.out`); all 10 throw cases byte-identical messages: `Location parameter is inf/nan/-inf`, `Random variable`-ordering cases, `Scale parameter is 0/-1` (sigma prefix normalized per prereg) |
| (b) PRIMARY stop-gate, radon_var 12-cell grid | E′ = `model_radon_var_eprime22/…so` (fixed header at a private inode in `bs_eprime22` = cp -al of w116's bs_eprime; hpp byte-identical to W-116's E′ hpp, md5-verified; linked against the W-106-lineage bridgestan.o); W-109 protocol verbatim (w1000 s1000, inits_w63 pf rep{r}/chain_{c}, seeds 20260819+1000·rep+chain, mw50, MM2 ON, single chain, sequential, nice 19, env -u LD_LIBRARY_PATH) via `grid_w1122.py` | **12/12 == frozen archive** (`logs/grid_w1122.log`): rep1_c2 = **fc7dbe12** (predicted ✓), rep2_c0 = **e6ab04e0** (predicted ✓) — both W-116b REAL divergences fixed; the other 9 = archive; rep0_c2 = **65d8f98c = the FROZEN archive value** (see §2b) |
| (c) regressions | radon_pp E′ rebuilt with the fixed header (`model_radon_pp_eprime22`, 12-cell grid `grid_pp_w1122.py`, inits_w36, MM2 ON) + W-112's original protocol (w36exp CLI read-only, seed 20260819, w100 s50, mw50, pf rep0/chain_0) on the fixed .sos | **radon_pp 12/12 MATCH** (all 12 archive md5s, `runs/stopgate_pp/`); **bbafc6523f1bfd40804c6bbafc4c4dec** (radon_var) and **4a9ca34923b6d2c314e636d6b335338d** (radon_pp) both reproduced **digit-for-digit** (`runs/w112proto/`) |
| (d) TU + controls | `normal_lpdf_gathered_test.cpp` + new `ThrowSetParity` (5 cases); math-repo make -j2 | **TU 5/5 PASSED**; controls `prim/prob/normal_test` **4/4**, `rev/prob/normal_log_test` **1/1**, `mix/prob/normal_test` **1/1** — all PASSED |

### 2b. The rep0_c2 knife-edge (env-ill-posed cell) — documented, better than expected

Pre-registered expectation: c7ce20bf (the W-116b same-env archive-binary
value). Outcome: the fixed E′ produced **65d8f98c — the FROZEN archive
value itself — three times** (grid + ×2 stability reruns,
`runs/wall/rep0_c2_stab{1,2}.csv`), while the ARCHIVE .so in today's env
still gives **c7ce20bf ×2** (`runs/envprobe/`) — W-116b's finding
reproduced. The cell remains the W-115-class environment knife-edge (its
outcome is binary- and environment-conditional); for the stop-gate the
fixed E′ landing on the FROZEN reference is the strongest available
outcome (12/12 vs frozen), and no four-way attribution was needed since
nothing mismatches the frozen archive. Disclosed as a deviation from the
pre-registered expectation, in the favorable direction.

## 3. FMA-count provenance (the W-108.1 check; `-mavx2 -mfma` kept)

| .so | vfmadd | vfmsub | vfnmadd |
|---|---|---|---|
| radon_var archive (stock loop) | 232 | 18 | 8 |
| radon_var old E′ (W-116b, buggy) | 240 | 19 | 8 |
| **radon_var E′22 (fixed)** | **240** | **19** | **8** |
| radon_pp archive | 222 | 18 | 8 |
| radon_pp old E′ | 223 | 18 | 8 |
| **radon_pp E′22 (fixed)** | **223** | **18** | **8** |

The fix adds ZERO FMA-class FP ops (identical counts to the old E′ arms;
the two compares are scalar integer-class branches). .so md5s: radon_var
E′22 `4787219a2cb5648a70b1dc74fc1727b5`, radon_pp E′22
`fcbc6668d8aef327b930ebb901fd3ff4`.

Boundary-state .so-level confirmation (the W-112.1 d1/d0/d3 probe against
the fixed .so): mu=+inf now `rc=-1` throwing
`normal_lpdf: Location parameter is inf` with an ALL-ZERO gradient
(= archive behavior; the old E′ returned `rc=0, lp=-inf, 88/175 NaN
grads`); sigma=0 and finite-huge-mu classes unchanged, matching both
arms.

## 4. The radon_var WALL stanza + ESS/s cell

12 cells E′ sequential (W-109 protocol; the stanza runs double as
stop-gate confirmations — 12/12 md5 vs frozen archive), per-chain sums of
all `total time:` stanzas (2 per log, parsed identically on both arms);
E recomputed from the frozen archive logs the same way (per-rep sums
11.7288/10.4190/8.9084 s — EXACTLY W-116b's recomputed values,
cross-checked against w109_results.json). Ambient load 1.19–1.25
(sequential stanza, no sibling compile observed during measured cells).

| cell | E′ (s) | E (s) | E′/E | | cell | E′ (s) | E (s) | E′/E |
|---|---|---|---|---|---|---|---|---|
| rep0_c0 | 0.9830 | 3.4721 | 0.283 | | rep1_c2 | 0.6921 | 2.3075 | 0.300 |
| rep0_c1 | 0.9626 | 3.2440 | 0.297 | | rep1_c3 | 0.8271 | 2.7942 | 0.296 |
| rep0_c2 | 0.8182 | 2.6945 | 0.304 | | rep2_c0 | 0.6579 | 2.3014 | 0.286 |
| rep0_c3 | 0.6979 | 2.3183 | 0.301 | | rep2_c1 | 0.6482 | 2.2073 | 0.294 |
| rep1_c0 | 0.6162 | 2.0620 | 0.299 | | rep2_c2 | 0.7095 | 2.2858 | 0.310 |
| rep1_c1 | 0.9700 | 3.2553 | 0.298 | | rep2_c3 | 0.6510 | 2.1139 | 0.308 |

**Sum 9.2338 / 31.0562 s = 0.297** (per-rep 0.295/0.298/0.299).
**Band E′/E ≤ 0.60: PASS at a 2× margin** (consistent with W-116b's
voided 0.311 observation, now measured on md5-clean draws).

**ESS/s cell** (W-116b conventions; ESS unchanged by md5-identity —
per-rep ESS = archive E's [415.01, 491.92, 219.97], median 415.01 = the
mission's expected 415.0):

| quantity | value |
|---|---|
| E′ wall (per-rep median) | 3.105 s |
| E′ ESS/s (per-rep, median) | 119.89 (per-rep 119.89/158.41/82.49) |
| E′/E ESS/s | **3.39×** (archive E 35.38) |
| E′/S ESS/s | **3.90×** (archive S 30.75; S wall 7.78 s, S ESS 254.26) |

radon_var's ESS/s moves from the archive E's 35.4 to 119.9 — the
previously-VOID wall/ESS/s cell is now measured and is the suite's
strongest E′/S ratio alongside radon_pp (2.65×) and hier_2pl (~5.6-6.7×).

## 5. Deviations / disclosures (all owned)

- **rep0_c2 landed on the FROZEN value** (65d8f98c ×3) rather than the
  pre-registered same-env c7ce20bf — favorable direction, 12/12 vs
  frozen; the archive binary today reproduces c7ce20bf ×2 (the cell
  stays classified env-ill-posed / W-115 knife-edge; full four-way
  evidence preserved under `runs/{wall,envprobe}/`).
- **A cp -al hygiene slip, caught and verified harmless**: the radon_pp
  model tree was hardlink-copied including the OLD .so before the `rm`
  (which failed on a zsh glob before reaching it); the link step's `-o`
  unlinked-and-recreated (fresh inode 11668218 vs the sibling's 11461014)
  — the W-116 sibling .so verified byte-intact afterwards (bac85ddd…,
  its recorded md5). The protocol order should have been rm-first; owned.
- **Grid run sequentially** (single chain at a time), not ≤4-worker: a
  deliberate choice to give the knife-edge rep0_c2 the cleanest
  environment (W-116b documented 4-worker concurrency perturbing it);
  the other 11 cells' md5s are load-invariant (W-116b evidence + this
  session). The wall stanza is sequential with per-cell load flags
  (1.19–1.25).
- Gate (a)'s first run had a TEST-CASE bug (shape-A NaN assigned to an
  unused beta coefficient — both arms correctly no-threw); fixed by
  adding an `alpha_nan_j` field; the recorded PASS runs are the final
  binaries at both flag levels.
- The first grid driver's `total time` parser missed the stanzas' leading
  spaces (its log shows totaltime=0.0); the wall stanza's parser sums
  all stanzas correctly — all wall numbers come from the stanza.
- W-112-protocol reruns (gate (c) part 2) used the E′22 .sos (byte-
  identical hpps to W-112's prim trees, md5-verified) on the bs_eprime22
  stack rather than rebuilding bs_w112 copies — equivalent by
  construction; disclosed.
- Machine: ≤2-core builds (nice 19, gxx_fixed, /usr/bin/make for TUs,
  env -u LD_LIBRARY_PATH), no callgrind (attribution never demanded it;
  0 running at each check), sampler cells single-process nice 19 with
  OMP_NUM_THREADS=1. WORKLOG.md/comms.md not written by this agent.
- Read-only reuse: w109 archive (cells/logs/.sos — the envprobe ran the
  archive .so at its original path), w116 (bundle + model trees + runs +
  pristine diff), w106 bs_alllayers, w112 (test_prim, data includes,
  draws, build recipes), w46 gxx_fixed, walnutpie CLIs (build_mg +
  build_w36exp), inits_w63/w36, w109_results.json (ESS/wall citations).
  Sibling integrity re-verified post-session: bs_eprime's primitive
  header 509d374a…, w116's radon_var E′ .so 5b14b5a2…, radon_pp E′ .so
  bac85ddd…, bs_alllayers bridgestan.o e4b6077b… — all unchanged.

## 6. Artifacts

- Branch `gathered-normal-fmafix` @ `559da085d5` (base `bc00891778`):
  `9a07ffa459` (header) + `559da085d5` (TU). DCO + AI notes. Not pushed.
- `scratch/w1121/`: `test_prim.cpp` + `build_gate_a.sh` +
  `test_prim_{O3,O2}` (gate a), `grid_w1122.py` / `grid_pp_w1122.py`
  (stop-gates), `wall_stanza_w1122.py` (stability + wall + ESS inputs),
  `bs_eprime22/` (bundle copy, fixed header at private inode),
  `model_radon_{var,pp}_eprime22/` (E′ .sos), `runs/{stopgate,stopgate_pp,
  wall,w112proto,envprobe}/`, `logs/` (all builds, gates, grids, TU +
  controls), plus the W-112.1 archaeology set (`probe_parity_w1121.py`,
  disassembly extracts, parity npz).
- Campaign note: W-118 (fused interior) branches off `559da085d5` per the
  W-112.2 pre-registration (one editor per header).
