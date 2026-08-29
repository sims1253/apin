# W-108.1 — the Map/Holder operand-layout fix for `bernoulli_logit_lpmf_gathered`: ALL GATES PASS; the W-116 hier_2pl stop-gate now reproduces the archive E cells 12/12; root cause REDEFINED at machine-code level (an FMA-contraction schedule gap affecting EVERY layout, not Map-specific)

Executed 2026-08-29 per WORKLOG "W-108.1 PRE-REGISTRATION" (after the W-116
close-out). Deliverable: branch **`gathered-glm-mapfix`** in worktree
`external/math_dev_w1081` (2 commits on top of `gathered-glm` @
`ea96b3c9fa`): `56c88d2440` (the header fix) + `eb8fe63f9c` (the TU's Map
case). Not pushed. Artifacts under `scratch/w1081/`.

**Headline: the primitive now replicates the composed stock expression's
reverse pass bit-for-bit in EVERY operand layout the stanc deserializer
produces — `Matrix<var>`, `var_value<Matrix<double>>`, and `Map<const
Matrix<var>>` (the DEFAULT-level layout) — with the hier_2pl E′ stop-gate
passing 12/12 md5-for-md5 against the W-109 archive E cells, both W-108 O1
regression md5s reproduced, and the wall stanza's E′/E ratio at 0.328
(band ≤ 0.75; load-context asymmetry flagged and supplementary load-matched
arms measured).**

## 1. Root cause — what the archaeology actually found

The W-116 diagnosis (Map theta takes a "third adjoint schedule" the
primitive lacks) was directionally right but mechanically incomplete. The
machine-code archaeology (disassembly of the composed reference in a probe
built with the model's exact flags, CROSS-CHECKED against the archive E
`hier_2pl_model.so` itself — `scratch/w106/model_hier_2pl_alllayers/…`,
symbols decoded at 0x4e800 elt chain / 0x2cd40 subtract chain) shows:

- The composed route (lazy `make_holder` rvalue views → `subtract` →
  `elt_multiply` → `bernoulli_logit_lpmf`) compiles, at the model's build
  flags (`-O3 -mavx2 -mfma`, gxx_fixed), to reverse chains with an ASYMMETRIC
  arithmetic schedule:
  - **alpha** (a `Matrix<var>` lvalue through the AoS elt_multiply chain):
    `alpha_adj = vfmadd213sd` — a FUSED multiply-add, one rounding of the
    whole `sub_val*e + alpha_adj`;
  - **the subtraction output's record**: `vfmadd132sd` into its
    zero-initialized adjoint = ONE ROUNDED PRODUCT `RN(a_val * e)`;
  - **theta**: subtract's chain applies that product with a PURE `vaddsd`
    (`theta_adj = RN(theta_adj + RN(a_val*e))` — two roundings);
  - **beta**: the SAME product value with a PURE `vsubsd`.
- The W-108 primitive's reverse scatter wrote all three increments as
  single-expression `adj += a * e` statements — which GCC
  (`-ffp-contract=fast`) compiles to FUSED FMAs for theta and beta. One
  rounding instead of two: ~1 ulp per addend, ~50% of gradient components
  per call, compounding through warmup adaptation into the 12/12 draws
  divergence W-116 measured (its theta 6.4e-13 / beta 1.3e-14 / alpha exact
  pattern is exactly this asymmetry: alpha's stock statement IS fused).
- This is NOT Map-specific: at the model flags the deviation exists for
  `Matrix<var>` theta identically (the same elt/subtract chains — the Map
  and Matrix instantiations emit the same instruction sequences). It was
  invisible to W-108's own unit gate because that binary was built without
  the model's FMA-capable flags (its compiled stock chains were unfused and
  the then-primitive's statements happened to match), and to W-108's O1
  model gate because that build (no arch flags — 0 `vfmadd` in the
  `model_hier2pl_prim` .so) compiled both sides unfused everywhere.
- Why W-116 saw it: the E′ build is the FIRST primitive-vs-archive
  comparison made at the archive's own build flags (`CXXFLAGS="-mavx2
  -mfma"`, the W-106 all-layers wiring).

## 2. The fix (commit `56c88d2440`)

One semantic change in the reverse callback of
`stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp` (value path
untouched):

- **theta and beta increments**: `volatile const double inc = a_val * e;`
  then pure `adj += inc;` / `adj -= inc;` — the volatile barrier forces the
  two-rounding form (a plain statement split is re-fused by GCC after
  inlining — verified by disassembly of the first attempt);
- **SoA (`var_value<>`) alpha**: rounded product + pure add (`ainc`),
  because SoA operands reach their adjoints through `rvalue_varmat`'s
  gather whose scatter is a pure add;
- **AoS alpha**: kept as the single-expression `adj += sub_val * e` so the
  compiler fuses it exactly as stock's elt_multiply chain does.

The route selection (is_var_v → SoA matrix-vari vs AoS per-vari) is
unchanged and remains correct for `Map<const Matrix<var>>` (the holder
route's adjoints land on theta's own varis — the AoS route's target).

## 3. Gates

| gate | evidence | verdict |
|---|---|---|
| (a) unit bitwise, REAL `stan::model::rvalue`/`index_multi` composed references | `scratch/w1081/test_prim.cpp` (W-108's gate extended with layout 3 = Map theta over an AoS buffer; W-108's `hier2pl_data.inc` reused read-only), built ON the bs_alllayers-lineage bundle (`scratch/w1081/bs_mapfix`, cp -al of w106/bs_alllayers + kernel-variant header) with the MODEL's flags (`-O3 -mavx2 -mfma`, gxx_fixed) AND at `-O2` | **12,000 bitwise checks, 0 mismatches** (4 layouts × 22 cases × lp+gradients), at BOTH -O3 and -O2: `==== GATE (a): 12000 bitwise checks, 0 mismatches => PASS ====` |
| (b) DEFAULT-level hier_2pl E′ stop-gate (the W-116 rerun) | E′ = `scratch/w1081/bs_mapfix` (fixed kernel-interior header at a private inode, `src/bridgestan.o` rebuilt under `CXXFLAGS="-mavx2 -mfma"`; 1202 vfmadd = the archive .so's exact count) + `scratch/w1081/model_hier_2pl_eprime/` (hpp regenerated pristine-identical to W-116's, then W-116's verbatim-assert port script reused; final hpp byte-identical to `scratch/w116/model_hier_2pl_eprime/hier_2pl.hpp`); W-109 protocol verbatim (build_mg stan_cli read-only, w1000 s1000, seeds 20260819+1000·rep+c, pf inits per the w63 manifest = inits_w25, --metric-window 50, MM2 ON, single chain per process, nice 19, env -u LD_LIBRARY_PATH, OMP_NUM_THREADS=1) | **12/12 cells md5 == archive E cells** (`scratch/w1081/logs/stopgate_table.txt`): rep0 {6462701b988928e2e70b87176d36fa72, d0b6f5ba1ffd7d2edf3241a5aa18f128, 154f0865f6a4ee53dfe81021168a0245, fa70840dc2e7fccded4a5f5feb24ebbc}, rep1 {f87735482b597ae996bd9bc1e4c3e62e, f011673255993f58600ed87035985b19, f9b51f786ed3236563f88cebfea89fcd, dedd73fbb3e3c3f2b75d418f8c88c2d8}, rep2 {241d4512283a6d5c86f2ecbef15f8d7b, c0e9ec5ea54b081fdfdcd52f12cffa48, 6570e80e66963b8785b7f057e3e27b63, f88fa9d643eb98be9c20a3cb92b7218f} — every E′ md5 equals its archive cell |
| (c) O1 regression (no-arch-flags stacks, W-29 protocol) | `scratch/w1081/bs_o1regr` (cp -al of w108/bs_prim_stock, prebuilt W-103-era bridgestan.o kept, fixed STOCK-interior header) + the W-108 O1 hand-edit hpp byte-identical; and `bs_o1regr_k` (cp -al of w108/bs_prim, kernel-interior variant) | **stock stack: `fe7c57c99a7a6530ce2dcc408d6e9c65` EXACT**; **kernel stack: `1744c2087c7049203b0e78bc6f4b5107` EXACT** (both = W-108's recorded values; the fix regresses nothing on the landed path) |
| (d) TU + control | `test/unit/math/rev/prob/bernoulli_logit_lpmf_gathered_test.cpp` extended with layout 2 (Map theta both arms); math-repo make | **3/3 PASSED**; untouched control `rev/prob/bernoulli_logit_glm_lpmf_test`: **22/22 PASSED** |

## 4. The hier_2pl wall stanza (12 processes, W-109 protocol)

E′ = the gate-(b) .so, run sequentially (single chain per process, nice 19,
env -u LD_LIBRARY_PATH, OMP_NUM_THREADS=1), per-chain sums of the logs'
`total time:` stanzas; E = recomputed from the frozen archive
`scratch/w109/runs/E/hier_2pl/*.log` (2 stanzas per log, both arms parsed
identically). **Every E′ cell's draws md5 equals its archive cell** (the
wall runs double as stop-gate confirmations).

| cell | E archive (s) | E′ (s) | E′/E | E′ loadavg flag |
|---|---|---|---|---|
| rep0_c0 | 71.2464 | 24.8270 | 0.3485 | 0.95→2.16 (sibling grid) |
| rep0_c1 | 78.6085 | 24.8250 | 0.3158 | ~1.5–2.2 |
| rep0_c2 | 78.8526 | 25.4483 | 0.3227 | 1.46 |
| rep0_c3 | 76.1576 | 25.0783 | 0.3293 | 1.46→2.16 |
| rep1_c0 | 76.7207 | 26.0296 | 0.3393 | 2.10 |
| rep1_c1 | 74.6565 | 25.3210 | 0.3392 | 2.10→2.73 |
| rep1_c2 | 77.1556 | 24.8546 | 0.3221 | ~2.5 |
| rep1_c3 | 78.9276 | 24.8765 | 0.3152 | ~1.4–1.6 |
| rep2_c0 | 75.1094 | 24.6946 | 0.3288 | ~1.5 |
| rep2_c1 | 75.8625 | 24.8413 | 0.3275 | 1.41 |
| rep2_c2 | 76.2381 | 24.8765 | 0.3263 | 1.47 |
| rep2_c3 | 75.7455 | 24.6273 | 0.3251 | 1.47→1.54 |
| **sum** | **915.2810** | **300.3000** | **0.3281** | — |

**Band E′/E ≤ 0.75: PASS (0.328).** LOAD-CONTEXT DISCLOSURE (the
pre-registered flag): the archive E cells ran inside W-109's 4-worker grid
(driver.log loadavg 4.70–6.48 during the hier_2pl cells), while the E′
stanza ran sequentially on a box whose ambient loadavg (1.4–2.7) came from
the sibling W-116b grid — interleaving with a frozen archive is impossible,
and this asymmetry inflates the measured ratio's speedup. Supplementary
load-matched arms (both labeled supplementary, not the pre-registered
primary): (i) a QUIET sequential E arm executing the archive's own .so
read-only on this box, (ii) a 4-worker E′ grid mimicking the archive's
dispatch — table appended in §4b.

## 4b. Supplementary load-matched arms

Both run on this box, W-109 protocol verbatim, draws md5-verified 12/12
against the archive cells in both arms (the quiet-E arm also re-proves the
archive .so reproduces its own recorded draws bit-exact here).

**(i) QUIET sequential E arm** (the archive's own
`scratch/w106/model_hier_2pl_alllayers/hier_2pl_model.so` executed
read-only, single chain per process; ambient loadavg 1.2–1.6, one cell at
2.4–2.7):

| | per-chain mean | 12-cell sum | E′(sequential)/E(quiet) |
|---|---|---|---|
| E quiet (this box) | 51.24 s | 614.88 s | **0.4884** |
| E′ sequential | 25.03 s | 300.30 s | |

Per-cell ratios 0.476–0.508 (`logs/wall_table_quiet.txt`). **This is the
load-matched statement of the wall effect: −51% on hier_2pl**, consistent
with (and slightly better than) W-108's −40.9% T instruction-count
prediction.

**(ii) 4-worker E′ grid** (4 concurrent single-chain processes, mimicking
the archive's dispatch; ambient loadavg ~1–4): per-cell 29.5–31.2 s, sum
361.24 s → E′₄w/E_archive = **0.3947** (md5 12/12 OK). The remaining gap to
(i) reflects the archive grid's heavier co-residency (its loadavg 4.7–6.5
across 21 models vs this box's lighter ambient).

All three readings — the pre-registered primary (0.328, flagged), the
load-matched (0.488), and the dispatch-matched (0.395) — sit well inside
the E′/E ≤ 0.75 band.

## 5. Deviations / disclosures (all owned)

- **The pre-registration's framing ("Map/Holder = a third adjoint route")
  was mechanically wrong, and the fix proves it**: the holder route touches
  the SAME elt_multiply/subtract chains for `Matrix<var>` and Map operands
  alike (identical instruction sequences decoded in both the probe and the
  archive .so). The real gap was the FMA-contraction schedule, present for
  ALL layouts at the archive's build flags. The implemented fix therefore
  lives in the EXISTING routes' arithmetic (not a new Map-specific branch),
  which is what the gates (a)-(d) certify. Owned here as the
  pre-registration's diagnosis error; W-116's empirical attribution (theta
  block dominant, alpha exact) is fully explained by the asymmetry.
- **W-108's original unit gate under-detected** (its binary lacked the
  model's FMA flags; both sides unfused). Gate (a) now runs at the model's
  exact flags — that is the load-bearing change to the gate.
- Gate (b)'s first build attempt accidentally omitted `CXXFLAGS="-mavx2
  -mfma"` (0 vfmadd; caught by comparing FMA counts vs the archive before
  running any sampler) — rebuilt with the W-106 wiring; disclosed.
- The stop-gate grid's later cells (rep1_c2 onward) overlapped my own -j2
  TU build (loadavg ~1.6–2.2); the gate is md5-based (load-invariant) and
  every wall-stanza rerun cell reconfirmed the md5s under quiet load.
- The wall stanza's cells are bit-identical draws confirmed per cell (the
  stanza doubles as a stop-gate rerun); all 12 rc=0.
- Machine: builds -j2 nice 19 (≤2 cores); sampler cells single-process
  nice 19, env -u LD_LIBRARY_PATH, OMP_NUM_THREADS=1; no callgrind
  (pre-registered). Sibling W-116b's 3-model grid was running during parts
  of the wall stanza (ambient loadavg flagged per cell). /tmp used only
  for one disassembly text file.
- Read-only reuse: `scratch/w116/` (wiring + pristine + edit script +
  bs_eprime headers), `scratch/w109/` (archive cells + driver + manifest),
  `scratch/w106/` (bs_alllayers + its model .so + build script),
  `scratch/w108/` (bs_prim_stock, bs_prim, hpps, draws, data include),
  `scratch/w46/gxx_fixed`, walnutpie CLIs, `external/math_dev_w108`
  (worktree add only). The PI's WORKLOG.md/comms.md untouched.
- Bundle hygiene: `bs_mapfix`/`bs_o1regr`/`bs_o1regr_k` are cp -al copies;
  only private-inode files were modified (the primitive header paths were
  rm'd before cp — no shared inode was ever written; bridgestan.o in the
  two stock-stack copies kept prebuilt). `bs_alllayers`'s own
  `bridgestan.o` md5 re-verified `e4b6077bf7bdc28fccbb87361375040f`
  (untouched).

## 6. Artifacts

- Branch `gathered-glm-mapfix` @ `eb8fe63f9c` in `external/math_dev_w1081`
  (parent `ea96b3c9fa`): commits `56c88d2440` (header) + `eb8fe63f9c`
  (TU). DCO + AI notes in both. Not pushed.
- `scratch/w1081/`: `bs_mapfix/` (+ E′ bundle), `bs_o1regr{,_k}/`,
  `model_hier_2pl_eprime/`, `model_hier2pl_o1regr{,_k}/`,
  `test_prim.cpp` + `test_prim{,_O2}` binaries + `test_prim.o`s,
  `make_kernel_variant.py` (sourcing the w1081 worktree),
  `run_eprime_grid.sh`, `wall_stanza.sh`, `wall_quiet_E.sh`,
  `wall_eprime_4w.sh`,
  `runs/{Eprime,o1regr,wall_Eprime,wall_Eprime_4w,wall_E_quiet}/`,
  `logs/` (builds, `stopgate_table.txt`, `wall_table.txt`,
  `wall_table_quiet.txt`, stanza logs, TU/control logs).
