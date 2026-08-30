# W-133 — THE WRAP BENCHMARK (everything-v2): the promotion-decision artifact — the 21-CORE-model table with the E′ column (the gathered primitives), geomeans recomputed with conventions stated, the statistical-class supplementary arms flagged, and the composed-promotion paragraph

Executed 2026-08-30 per WORKLOG "W-133 PRE-REGISTRATION" (the W-132/W-133
entry, final two lanes). ANALYSIS-FIRST: **zero new sampling** — every number
below is assembled from existing measurements (one arithmetic derivation for
hier_2pl's E′ cell, shown in §4b; no missing number was worth a run). Machine
time: 0 sampler cells, 0 builds. WORKLOG.md/comms.md untouched (PI-owned).

Sources of record (read in full before assembly):
`results/everything_ess_w109.md` + `scratch/w109/w109_results.json` (the
21-model S/E base), `results/ess_wrap_w116b.md` (radon_pp, bym2 E′; walls),
`results/throwset_fix_w1122.md` (radon_var E′; wall 0.297), WORKLOG's
W-112.2 CLOSE-OUT (the compiled four-model table + geomean ≈3.2×),
`results/mapfix_w1081.md` (hier_2pl walls, three load readings),
`results/icar_gathered_w113.md`/WORKLOG W-113 (bym2 primitive),
`results/fused_interior_w118.md`/WORKLOG W-118 (fused interior — NOT in the
E′ walls, see §2), `results/glm_default_emit_w128.md` (statistical-class
emission), `results/ridge_budget_w125.md` (Package A decision data),
`results/tpvari_w130.md` + `results/pcm_gathered_w126.md` (the non-CORE side
models), `results/gathered_registry_w115.md` (emission rows 1–3),
`results/assembly_v2_w114.md` (Package A assembly v2).

---

## 1. ARMS and ruler conventions (stated, then never mixed)

- **S** = the recommended default: `external/walnutpie_mm2guard/build_mg`
  stan_cli at DEFAULT flags × the pristine stock `.so`, **with the protocol
  package** (pf inits per `scratch/w63/manifest.csv`, `--metric-window 50`,
  seeds 20260819+1000·rep+chain, w1000 s1000, 4 chains). W-109 archive,
  frozen.
- **E** = same binary × per-model MM2 posture (13 ON / 8 OFF per the W-84
  benefit list) × ALL-LAYERS math `.so` (SoA math#5 + W-102 gather/index fix
  + W-103 log1p kernel + `-mavx2 -mfma`). W-109 archive, frozen.
- **E′** = E + the landed **gathered primitives**, applied per model by
  pattern (the W-115 registry emits them automatically at `--O1`; the
  measured cells used the gated hand-edits, md5-equal to the emission's
  output where both exist):
  - `hier_2pl` → `bernoulli_logit_lpmf_gathered` (W-108 + the W-108.1
    FMA-contraction/operand-layout fix);
  - `radon_pp`, `radon_var` → `normal_lpdf_gathered` (W-112 + the W-112.2
    throw-set fix);
  - `bym2_offset_only` → `dot_self_gathered_diff` (the ICAR prior, W-113);
  - **the other 17 models: no primitive pattern applies** ⇒ compiler output
    byte-identical (each primitive's "no-op elsewhere" gate) ⇒ **E′ ≡ E by
    construction** — their E′ column is the W-109 E column, unchanged.

**Ruler/wall convention (the pre-registration's conversion warning, resolved
by inspection): every source here uses the SAME convention** — ESS =
`ess_bulk_min` rep-median over 4 combined chains (blessed split
`scratch/w88`); wall = **per-rep sum of ALL per-chain `total time:` stanzas**
(warmup+sampling), rep-median; ESS/s = per-rep ESS/wall, rep-median. W-116b
recomputed the archive E/S walls from the W-109 logs with this parser and its
sums equal `w109_results.json` EXACTLY (its §2 cross-check; re-verified here
against the json directly). **No stanza-sum↔per-rep-sum conversion was
needed.** The one real asymmetry is DISPATCH/LOAD context (hier_2pl's E′ ran
sequentially; W-109 ran a 4-worker grid) — handled in §4b with all three
recorded readings, not by mixing conventions.

**Bit-identity discipline:** all four E′ cells reproduce their W-109 archive
E cells **md5-for-md5** (radon_pp/bym2 12/12 W-116b; radon_var 12/12 W-112.2;
hier_2pl 12/12 W-108.1) — so ESS is *unchanged by measurement*, and each
E′/S cell moves by exactly 1/(E′/E wall ratio) vs the E cell.

## 2. What is NOT in the E′ column (upside, stated)

- **W-118 fused interior** (radon_pp −35.4% / radon_var −27.6% on the
  pre-registered G basis; bit-identical at its own gates) landed AFTER the
  W-116b/W-112.2 wall measurements and was never run at the W-109 protocol —
  the radon E′ cells here are **pre-fusion** and therefore understate the
  current branch state. Not imputed (no measurement exists at wall level).
- **W-125 ridge/floor lever** (Package A) is a sampler-quality lever, not an
  ESS/s lever (fixed-128 = 0.03–0.22× R0 ESS/s); presented in §6, not merged.
- **W-128 glm emission** is STATISTICAL class (draws differ) — it cannot
  enter a bit-identical E′ column; §5.

## 3. THE MAIN TABLE — 21 CORE models × {S, E, E′}

ESS/s = ESS_bulk_min rep-median ÷ per-rep stanza-summed wall (rep-median).
`—` = E′ ≡ E (no primitive pattern; byte-identical output). MM2 = the E-arm
posture. Walls are load-flagged as in their source records (W-109 grid ran
under loadavg median 3.98/max 6.67; the E′ stanzas under 0.86–4.43 — see
§4b for the hier_2pl asymmetry, the only cell where this moves the number).

| # | model | MM2 | S ESS/s | E ESS/s | E′ ESS/s | E/S | **E′/S** | primitive arm (E′ cells) |
|---|---|---|---|---|---|---|---|---|
| 12 | hier_2pl | ON | 2.215 | 4.845 | **12.275** | 2.19 | **5.54×** | bernoulli_logit gathered (W-108.1) |
| 8 | radon_partially_pooled_nc | ON | 3.047 | 2.756 | **8.080** | 0.90 | **2.65×** | normal gathered + throw-set fix (W-116b) |
| 9 | radon_variable_slope_nc | ON | 30.754 | 35.384 | **119.89** | 1.15 | **3.90×** | normal gathered + throw-set fix (W-112.2) |
| 16 | bym2_offset_only | off | 0.0792 | 0.1191 | **0.1422** | 1.50 | **1.80×** | ICAR dot_self_gathered_diff (W-113) |
| 14 | kronecker_gp | off | 0.197 | 0.214 | — | 1.09 | 1.09 | — |
| 10 | dogs_hierarchical | ON | 450.70 | 651.04 | — | 1.44 | 1.44 | — |
| 13 | gp_regr | ON | 6060.83 | 9001.49 | — | 1.49 | 1.49 | — |
| 4 | lsat_model | off | 28.41 | 43.19 | — | 1.52 | 1.52 | — |
| 17 | eight_schools_centered | off | 906.59 | 372.38 | — | 0.41 | 0.41 | — |
| 2 | blr | off | 512.66 | 621.01 | — | 1.21 | 1.21 | — |
| 20 | low_dim_gauss_mix | ON | 38.71 | 48.47 | — | 1.25 | 1.25 | — |
| 7 | diamonds | off | 0.300 | 0.424 | — | 1.41 | 1.41 | — |
| 19 | lotka_volterra | ON | 0.663 | 7.393 | — | 11.16 | 11.16 | — |
| 15 | accel_gp | off | 0.891 | 1.051 | — | 1.18 | 1.18 | — |
| 6 | wells_dist100_model | ON | 236.69 | 615.40 | — | 2.60 | 2.60 | — |
| 18 | garch11 | ON | 366.36 | 532.53 | — | 1.45 | 1.45 | — |
| 3 | kidscore_momiq | ON | 426.69 | 640.51 | — | 1.50 | 1.50 | — |
| 11 | pilots | off | 8.43 | 11.14 | — | 1.32 | 1.32 | — |
| 21 | arma11 | ON | 1938.90 | 2484.79 | — | 1.28 | 1.28 | — |
| 5 | logmesquite_logvash | ON | 279.77 | 635.35 | — | 2.27 | 2.27 | — |
| 1 | eight_schools_noncentered | ON | 17194.64 | 22525.19 | — | 1.31 | 1.31 | — |

(# = CORE_SET.md row. Per-model E′ footnotes: hier_2pl's likelihood is the
2PL bilinear `alpha[ii].*(theta[jj]-beta[ii])` → gathered bernoulli_logit;
radon_pp/var are gathered-normal likelihoods (variable intercept / intercept
+ slope), W-118's fused interior additionally available but unmeasured at
wall; bym2's is the ICAR `dot_self(subtract(gather,gather))` prior.)

## 4. GEOMEANS (conventions stated)

### 4a. Headline

| geomean (ESS/s ratios, n=21) | value |
|---|---|
| W-109 **E/S** (recomputed from the json: 1.4845) | **1.485×** |
| **everything-v2 E′/S** — E′ measured on 4 models, E on 17 (hier_2pl dispatch-matched) | **1.746×** |
| same, hier_2pl = W-108.1 primary (sequential) reading | 1.761× |
| same, hier_2pl = conservative quiet-load bound | 1.728× |

**The honest mixed table: 1.73–1.76×, quoted at 1.746×** (hier_2pl
dispatch-matched). Decomposition (all at the dispatch-matched reading):

- **the 4 E′ models: E′/S geomean 3.19×** (hier 5.54, radon_pp 2.65,
  radon_var 3.90, bym2 1.80) — *measured*, every draw md5-identical to its
  W-109 E cell. Primary reading: 3.34× (reproduces the W-112.2 close-out's
  "≈3.2× .. 3.3×" exactly).
- **the other 17 models: E/S geomean 1.515×** — *unchanged by construction*:
  bit-identity ⇒ E ≡ E′ where no primitive pattern applies (byte-identical
  compiler output, each primitive's no-op-elsewhere gate). These are not
  remeasured and not claimed as improved.
- Sanity: 1.515^17 × 3.185^4 ^(1/21) = 1.746 ✓.
- Absolute ESS/s geomeans: S 38.81 → E 57.61 → **E′(v2) 67.75**.
- everything-v2 vs S: **ESS ratio 1.467×, wall ratio 0.881×** (ESS ratio is
  W-109's by bit-identity; the entire E′ gain is wall).

### 4b. The hier_2pl cell — the one derived number (arithmetic shown)

W-108.1 measured hier_2pl's E′ wall three ways (12 cells, all md5 ==
archive): primary sequential **0.3281**, dispatch-matched 4-worker **0.3947**
(361.24/915.28 s), load-matched quiet **0.4884** (300.30/614.88 s). E′ ESS/s
= E ESS/s ÷ (E′/E wall) [ESS identical by md5]; E′/S = that ÷ S ESS/s:

| reading | E′/E wall | E′ ESS/s | **E′/S** |
|---|---|---|---|
| W-108.1 primary (E′ seq vs archive E under 4-worker + foreign load) | 0.3281 | 14.766 | 6.67× (load-asymmetric, flagged) |
| **dispatch-matched (4-worker E′ vs 4-worker archive) — USED** | 0.3947 | **12.275** | **5.54×** |
| load-matched quiet (both sequential, this box) | 0.4884 | 9.920 | 4.48× (lower bound; S was not re-measured quiet) |

The dispatch-matched reading is used in the main table because it is the
only one that matches the archive's worker count on both sides; the range
4.5–6.7× is carried in the geomean band (1.728–1.761×).

### 4c. Not in the geomean (flagged)

**E+** (the W-91 cap-relaxation family, `--max-hamiltonian-error 2.0`) on
its 3-model subset: E+/S = 1.508× geomean (hier_2pl E+/E 1.47, esc 1.69,
arma11 1.20) — a third, orthogonal, *statistical/trajectory* lever, reported
by W-109 and not stacked into E′ here.

## 5. THE SUPPLEMENTARY ARMS — flagged STATISTICAL class (cannot merge into E′)

### 5a. glm emission (W-128, `Optimize.emit_normal_glm`, default level)

The glm interior is analytically-equivalent, not bitwise: lp rel-L2 ~1e-16
(2 ulp), gradients differ in the last bits (99–100/100), **draws differ**.
Measured on the callgrind ruler (no W-109-protocol ESS/s cell exists —
bit-identity is what made the E′ column mergeable, and it is absent here):

| model | W-109 E/S (bit-identical stack) | W-128 emission (statistical) | class |
|---|---|---|---|
| kidscore_momiq | 1.50× | **whole run −56.3% Ir** (likelihood subtree 54.3→9.5 Ir/elem = −82.5%; complex −90.0%) | statistical |
| logmesquite_logvash | 2.27× | **complex −66.2% Ir** (K=5 append_col wrap 37.4 Ir/elem measured, does not eat the win; whole run −20.4% at N=46) | statistical |

Sampler-level check (3×4, w100 s50): rep ratios 1.000/0.315/0.941 vs stock's
own 96.5% rep spread; long-horizon control (w1000 s500): emit ESS 244 vs
stock 137, rhat 1.012 vs 1.057 — better-mixed at horizon, not an ESS/s claim.

### 5b. The non-CORE side table (model-level wins; no S/E baselines exist)

| model | arm | run cost | wall | class | record |
|---|---|---|---|---|---|
| election88_full | gathered_additive_tp (family 4, W-130) + emission (W-131) | 54.76e9 → 17.79e9 Ir = **−67.5%** | 5.73 → 1.39 s = **4.1×** | **bit-identical** (draws md5 `d2e2f896…` digit-for-digit, parity 0/100 exact-zero) | results/tpvari_w130.md |
| gpcm_latent_reg_irt | pcm_lpdf_gathered (family 3, W-126) | 214.3e9 → 25.1e9 Ir = **−88.3%** | 22.6 → 2.3 s = **9.7×** | **bit-identical** (draws md5 `a342848b…` doubly anchored, parity 0/100) | results/pcm_gathered_w126.md |

Both exceed their pre-registered bands favorably; both are Ir/wall ratios at
the W-29-class short protocol, **not** W-109 ESS/s cells — presented as
model-level evidence that the primitive families generalize beyond CORE_SET,
not as table rows.

## 6. THE PROMOTION PARAGRAPH — what a user adopting the full stack gets

**Adopting the full stack buys a measured 1.75× geomean ESS/s over the
recommended default on the 21-model CORE_SET (range 1.73–1.76×), with every
draw bit-identical to the tuned-default arm wherever a transform fires** —
composed of four independently-gated families, each with its class stated:

1. **Protocol + sampler posture (configuration class — changes trajectories
   by design, as any knob does):** pf inits + `--metric-window 50` + the
   per-model MM2 micro-step floor (13 of 21) + the all-layers math build (SoA
   + gather/index fix + log1p kernel + AVX2/FMA). This is W-109's **E/S =
   1.485×** — ESS ratio 1.467× at wall ratio 0.982×, with MM2 paying its ESS
   in grads (+14% wall on the ON-13) and the math layer −23% wall on the
   OFF-8. Optionally the E+ cap family (+1.44× on its 3-model subset).
2. **The gathered primitives (BIT-IDENTICAL, md5-proven):** the four
   CORE models whose likelihood/prior matches a gathered family run at
   **E′/S 3.19× geomean** (hier_2pl 5.54×, radon_var 3.90×, radon_pp 2.65×,
   bym2 1.80×) with *digit-for-digit identical draws* — pure wall wins, the
   suite's strongest math-layer result, plus the W-118 fused interior
   (−35%/−28% G, unmeasured at wall) as further upside. Outside CORE_SET the
   same families deliver election88 **−67.5% (4.1× wall)** and gpcm **−88.3%
   (9.7× wall)**, still bit-identical.
3. **Automatic emission (BIT-IDENTICAL at the compiler level):** the W-115
   registry + W-131 additive + W-132 pcm rows mean users get the primitives
   from source, no hand-edits — full-tree censuses show exactly the intended
   fires and no-op elsewhere.
4. **The glm emission for everyday regressions (STATISTICAL class — draws
   differ, lp/grads last-ulp):** kidscore-class **−56%** / logmesquite-class
   **−66%** of the likelihood complex at *default* compile level. The one
   component whose numerics change; upstream-shaped as `--Oexperimental-first`.
5. **Package A robustness (W-114 assembly v2, canary-green):** init guards,
   NaN guard, ridge guard with the graduated budget and the multi-chain
   dispatch restored. Not an ESS/s lever (W-125: 0.03–0.22× R0) but the
   ESS-floor healer — pilots-class cells heal up to 16× at the budget floor
   (`max(64, 16·F/5)`, cap 128 — the W-125 recommendation), and it is the
   lever for the ridge-locked floor models (bym2/accel/diamonds/pilots) that
   no math layer can move.

**Bottom line for the decision:** the bit-identical families alone take the
CORE_SET geomean from 1.485× to **1.746×** with zero numerical risk on the
models they touch and zero change on the models they don't; the statistical
glm emission and the Package A floor lever are the two further steps, each
flagged with its class, each measured.

## 7. Arithmetic verification performed (ruler discipline)

1. Recomputed W-109's E/S geomean from `w109_results.json` per-model
   `ess_per_s_med`: **1.48453** — matches the recorded 1.485× ✓.
2. radon_pp/bym2 E′ cells read from `scratch/w116/w116b_results.json`
   verbatim (E′ ESS/s 8.08017/0.14223; E′/S 2.6519/1.79623) and their S/E
   cells equal the W-109 json's ✓.
3. radon_var: E′ ESS/s 119.89 (per-rep 119.89/158.41/82.49, median) ÷ S
   30.75447 = **3.898** ≈ the record's 3.90×; ÷ E 35.3837 = 3.387 ≈ 3.39× ✓.
4. hier_2pl derived in §4b from W-108.1's three wall ratios; the resulting
   4-model geomeans (3.185 dispatch / 3.336 primary) reproduce the W-112.2
   close-out's "≈3.2× .. 3.3×" ✓ — independent confirmation the assembly
   matches the PI's compiled table.
5. Geomean identities: 21-model = (17-model × 17, 4-model × 4)^(1/21)
   verified; ESS-ratio 1.467× carried unchanged from W-109 (bit-identity);
   E′(v2) ESS/s geomean 67.75 / S 38.81 = 1.7455 ✓.
6. No conversion was applied between W-116b/W-112.2/W-108.1 stanza-summed
   walls and W-109's per-rep stanza-summed walls — same convention (§1);
   W-116b's cross-check of the archive walls against the json is reproduced
   by reading the json directly.

## 8. Deviations / disclosures

- **No new sampling, no builds, no callgrind** (pre-registration honored;
   nothing was missing that was cheap and needed).
- hier_2pl's E′ cell is a *derived* number (ESS identical by md5; wall from
   W-108.1's measured ratios) — the only derivation in the table, shown in
   §4b with all three load readings.
- Load-context asymmetries are inherited from the sources and flagged, not
  corrected: W-109 grid loadavg median 3.98/max 6.67; E′ stanzas 0.86–4.43;
  bym2's W-116b PASS carried a 9%-band load caveat (its 1.80× is a pure wall
  win over S with ESS_min ≈ 4.4 pinned by the A0 init pathology in every arm).
- The E′/S cells for radon_pp/radon_var are pre-W-118 (§2) — conservative.
- election88/gpcm are NOT CORE_SET and have no S/E baselines; §5b is a side
  table only, as pre-registered.
- Read-only reuse throughout: `scratch/w109/`, `scratch/w116/`,
  `scratch/w1121/`, `scratch/w1081/`, `scratch/w130/`, `scratch/w126/` and
  their records. WORKLOG.md/comms.md not written by this agent.
