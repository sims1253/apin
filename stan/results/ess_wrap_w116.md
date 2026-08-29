# W-116 — the PRIMITIVES ESS/s WRAP: STOP-GATE FIRED on hier_2pl (12/12 cells md5-mismatch); radon_pp/radon_var/bym2 E′ draws md5-reproduce the archive E cells at the W-109 protocol — NO wall numbers, NO ESS/s reported (pre-registered stop honored; root cause chain below)

Executed 2026-08-29 per WORKLOG "W-116 PRE-REGISTRATION" + the PI ruling
on the E′ hpp level (DEFAULT-level hand-edits, archive md5 reproduction is
the stop-gate). Arms S/E = the W-109 ARCHIVE (not rerun). Arm E′ = the
all-layers math + all three gathered primitives + default-level hand-edited
model hpps, built and run at the W-109 protocol verbatim (same
walnutpie_mm2guard/build_mg CLI read-only, w1000 s1000, pf inits per the
w63 manifest, seeds 20260819+1000·rep+chain, --metric-window 50, per-model
MM2 flags exactly as flags_for() in driver_w109.py: radon_pp/radon_var/
hier_2pl ON --min-micro-steps 2 --min-micro-guard, bym2 OFF, single chain
per process, nice 19, env -u LD_LIBRARY_PATH, OMP_NUM_THREADS=1).

**STOP-GATE VERDICT: FAIL — hier_2pl E′ draws mismatch the archive E cells
in 12/12 cells (all reps × chains, rc=0 everywhere; draws diverge from the
first sampling row). The other three models' pilot cells (rep0_c0) are
md5-FOR-MD5 identical to the archive E cells. Per the pre-registration the
measurement STOPS here: no wall table, no band verdicts, no ESS/s ratios,
no composed-stack geomean, and no fix was attempted. Everything preserved
under scratch/w116/.**

## 1. The E′ build (gate 0: PASS)

- Bundle: `scratch/w116/bs_eprime` = `cp -al` of `scratch/w106/bs_alllayers`
  (the W-109 E-arm bundle: SoA math#5 slice + W-102 gather/index fix +
  W-103 bernoulli kernel; verified this session: relative to
  `w103/bs_w103_kernel` the ONLY math-tree difference is the bernoulli
  header's fvar-fallback cosmetics — the w46 kernel island is identical).
  Three primitive headers dropped in (new inodes; originals untouched,
  md5s recorded):
  `stan/math/rev/prob/normal_lpdf_gathered.hpp` ← external/math_dev_w112,
  `stan/math/rev/fun/dot_self_gathered_diff.hpp` ← external/math_dev_w113,
  `stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp` ← **the W-108
  KERNEL-interior variant** `scratch/w108/bernoulli_logit_lpmf_gathered_w46.hpp`
  (see §2). `src/bridgestan.o` link removed in-copy and rebuilt
  (-mavx2 -mfma, gxx_fixed, TBB_CXX_TYPE=gcc, /usr/bin/make -j2, nice 19,
  env -u LD_LIBRARY_PATH) — the W-112/113 private-inode dance;
  bs_alllayers verified untouched afterwards (its bridgestan.o and kernel
  header intact).
- Model trees `scratch/w116/model_<m>_eprime/`: .stan hardlinked from the
  W-109/W-106 all-layers trees, hpp = the hand-edit (fresh inode, newer
  than .stan so stanc never regenerates — verified by post-build md5).
  Gate 0 via the bridgestan C ABI (ctypes): all four .so load; model name
  and D match the archive .so exactly — radon_pp 389, radon_var 175,
  bym2 3845, hier_2pl 669 (`scratch/w116/logs/gate0.log`).

## 2. Wiring verifications that shaped the build (both load-bearing)

**(a) The hier_2pl primitive interior must be the KERNEL one.** The
mission's parenthetical ("verify which of prim/prim_k is the stock-interior
variant; use the stock-interior one") dissolves on inspection:
`model_hier2pl_prim/hier_2pl.hpp` and `model_hier2pl_prim_k/hier_2pl.hpp`
are BYTE-IDENTICAL (diff rc=0) — both include
`<stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp>`; the interior is
decided by WHICH HEADER sits at that path in the bundle. The archive E
hier_2pl .so was built in bs_alllayers whose `bernoulli_logit_lpmf`
carries the W-103 kernel arm for double partials with RUNTIME AVX2
dispatch (this CPU has AVX2) — the archive draws flowed through
`internal::w46::bernoulli_logit_fwd`. The branch header
(external/math_dev_w108) has the stock select-tree interior, which W-108
itself proved numerically DISTINCT from the kernel island (its md5s:
stock-stack fe7c57c9… vs kernel-stack 1744c208…). The kernel-interior
variant delegates to the bundle's OWN island — the archive-matched choice.
VINDICATED post-hoc by parity: lp exact-zero (§4).

**(b) The W-108 hand-edit hpp is an --O1 artifact; it was ported to
DEFAULT level.** `stancflags = --O1 --debug-optimized-mir` is IN the
W-108 hpp file, with O1 hallmarks throughout (constant-folded sym1__
bounds and num_params_r__, decl-init removal, explicit SoA
`var_value` read of theta). Building it would have imported exactly the
stock O1 drift the PI ruling excludes. The pristine-diff check (regenerate
default-level hpps with bs_eprime's own stanc — the same generator/flags
the archive .so used — and diff) confirmed: radon ×2 and bym2 hand-edits
ARE default-level (residual = exactly the primitive rewrite + string-table
noise), hier_2pl is not. The port (`scratch/w116/edit_hier2pl_w116.py`,
verbatim-assert script in the W-112 style) applies the SAME two line
groups W-108 gated — the include + the rev-mode likelihood statement
`bernoulli_logit_lpmf_gathered<propto__>(y, theta, jj, alpha, beta, ii)`,
double-mode instantiation untouched — onto the pristine default-level hpp;
residual diff = exactly those 2 groups. The port is VINDICATED for the
value path (lp exact-zero) and by the three passing models.

String-table noise in all pristine diffs (version comment, .stan source
paths in exception strings, stancflags string) is cosmetic; the three
passing models' full-run md5 equality across different .so paths proves it
never reaches the draw stream.

## 3. STOP-GATE (gate 1) — the md5 table

Pilot cells (rep0_c0, seed 20260819, exact archive protocol), E′ vs
`scratch/w109/runs/E/<model>/rep0_c0.csv`:

| model | verdict | E′ md5 | archive md5 |
|---|---|---|---|
| radon_partially_pooled_noncentered | **MATCH** | 81828b3d34f59c9aca636163c2f4f62c | 81828b3d34f59c9aca636163c2f4f62c |
| radon_variable_intercept_slope_noncentered | **MATCH** | 7fb6854a851212d36c07219bf82dc0d8 | 7fb6854a851212d36c07219bf82dc0d8 |
| bym2_offset_only | **MATCH** | 6a53d147ca268354942bf36bcbe96d08 | 6a53d147ca268354942bf36bcbe96d08 |
| hier_2pl | **MISMATCH** | 1ae0c6dab70302bee47e3399c19efab2 | 6462701b988928e2e70b87176d36fa72 |

hier_2pl full pattern (12/12 MISMATCH, rc=0 all; per-cell md5s in
`scratch/w116/logs/hier2pl_pattern.log`, runs under
`scratch/w116/runs/Eprime/hier_2pl/`): rep0 {c0 1ae0c6da, c1 4bd341e2,
c2 dd16690e, c3 dbb88d1c}, rep1 {4695c107, e2f7cd95, 8c93b638, 1969b339},
rep2 {f7778a49, 8cb7fa0c, b26d5c83, 0d543a19} — none equal to the archive
cells. First-diff location (rep0_c0): csv line 2 (the FIRST sampling
draw), column 1 = theta.1: archive `1.78969064441` vs E′ `3.42649104487`
— the trajectories diverged during warmup, as expected for a per-gradient
last-bit difference compounding through adaptation.

Per the pre-registration: STOP. The remaining 33 cells of the three
passing models were NOT run (stopped at pilot-level evidence; the pilot
csv/log cells exist and the build is in place should the PI rule a
3-model salvage — but that reading, including any wall number, is the
PI's call, not taken here).

## 4. Root cause (proven at the gradient level; no fix attempted)

Parity probe (`scratch/w116/parity_hier2pl_w116.py`, W-103 point scheme:
default_rng(20260822), standard_normal(669)·0.5, 100 points, archive
w106 all-layers .so vs E′ .so, raw-ctypes C ABI, one .so per process):

- **lp: 0/100 mismatches (exact-zero, max rel 0.0)** — the value path
  (operand gathering + kernel island interior) is bit-identical. This
  vindicates wiring decisions (a) and (b): right interior, right codegen
  level.
- **gradients: 100/100 vectors mismatch, max rel 3.653e-12** — a
  reverse-sweep accumulation-schedule deviation.
- Block breakdown (25 points, `parity_breakdown_w116.py`):
  **theta[0:600]: 8067/15000 components differ, max rel 6.4e-13;
  alpha[600:632]: 0/800 EXACT; beta[632:664]: 432/800, max rel 1.3e-14;
  mu/tau/L_Omega (priors): 0/125 EXACT.**

Mechanism. DEFAULT-level stanc emits
`auto theta = in__.read<Eigen::Matrix<local_scalar_t__,-1,1>>(J)` —
and this stack's deserializer hands back
`Eigen::Map<const Eigen::Matrix<var_value<double>,-1,1>>` (W-113's
"third layout"; in math 5.x `var` ≡ `var_value<double>`, so this is a
Map over AoS var elements — NOT the SoA `var_value<VectorXd>`). The
archive's composed `rvalue(theta, index_multi(jj))` on ANY eigen-vector
type takes the LAZY `make_holder` route (stan/src
`model/indexing/rvalue.hpp`, EigVec multi-index overload) — theta's
adjoints flow through the holder/subtract expression callbacks.
W-108's model-level bit-identity gates used the O1 hpp, where theta is
read EXPLICITLY as `var_value<VectorXd>`: that route is the
`rvalue_varmat` gather + `reverse_pass_callback` scatter, and THAT is
the schedule the primitive's reverse pass replicates bit-exactly
(gate-proven on its mix). In the primitive,
`is_var_v<Map<const Matrix<var>>>` is false, so the Map binds the plain
AoS route — which reproduces alpha's schedule EXACTLY (alpha is
Matrix<var> in both arms: 0/800 differ) but not theta's holder-route
schedule (the dominant 6.4e-13), with beta riding the shared subtract
callback interleaving (1.3e-14). The priors blocks are untouched.

In short: **the W-108 primitive's reverse pass has an operand-layout
coverage gap — the deserializer's Map layout at default-level codegen —
not an interior error, not a protocol or build error.** The archive E
hier_2pl draws are therefore unreachable by ANY wiring of the current
primitive: the O1 hpp alternative swaps in the O1 codegen drift
(W-115: O1-stock hier_2pl ≠ default draws). Both branches fail the
stop-gate; a W-108.1 adding the Map/Holder theta adjoint route (the
mirror of W-113's layout-2 work, which is exactly why bym2's primitive
PASSES here) is the minimal path to a compliant hier_2pl E′. That is a
PI decision; none of it was attempted under W-116.

Positives carried by the passing pilots (new facts, cheap to state):
the W-112 normal primitive and the W-113 ICAR primitive reproduce the
W-109 ARCHIVE E cells md5-for-md5 at the full W-109 protocol on the
archive binary — their default-level-layout coverage is complete, so a
3-model E′ arm (radon_pp, radon_var, bym2) is one PI ruling away from
being resumable with the stop-gate intact.

## 5. Disclosures / deviations (all owned)

- **Kernel-interior variant used for hier_2pl** against the mission's
  "stock-interior" parenthetical — verification chain in §2(a); the
  alternative fails the stop-gate by construction (W-108's own md5
  evidence). lp exact-zero confirms the choice.
- **Default-level port of the W-108 hier_2pl hand-edit** (the artifact is
  --O1-level; PI ruling mandates default) — §2(b); script with verbatim
  asserts, residual diff = exactly the 2 gated line groups.
- **One wall glance occurred pre-stop** during pilot wiring sanity
  (radon_pp rep0_c0 'total time' stanza sums). It is disclosed here as a
  suppressed observation; no wall statistic, band verdict, or ratio
  appears anywhere in this record.
- hier_2pl's 12 cells were run AFTER the pilot mismatch purely to
  document the mismatch pattern the pre-registration asks for; the three
  passing models were not continued past their pilot cells.
- Machine: builds sequential -j2 nice 19 (≤2 cores); all sampler cells
  single-process nice 19, env -u LD_LIBRARY_PATH, OMP_NUM_THREADS=1;
  /proc/loadavg 0.23–1.13 throughout the runs (quiet box; no sibling
  compiles observed). No callgrind.
- Archive/artifact hygiene: bs_alllayers, the w109/w106 model trees, and
  the w108/w112/w113 hand-edit sources were read-only (bs_alllayers's
  bridgestan.o and kernel header md5 re-verified intact; w116 .stan
  files are hardlinks, never written).
- The mission's pre-registered bands (radon_pp ≤0.55 etc.), the radon_pp
  E′/S > 1.3× headline, and the 4-model partial geomean are ALL VOID
  under the stop — none computed, none reported.

## 6. Artifacts

- `scratch/w116/`: `bs_eprime/` (bundle copy + 3 headers + rebuilt
  bridgestan.o), `model_<m>_eprime/` ×4 (hpp + .so; .stan links),
  `pristine/` (pristine hpps + per-model diffs), `edit_hier2pl_w116.py`,
  `gate0_w116.py` + `logs/gate0.log`, `pilot_w116.sh`, `pilot2_w116.sh`,
  `hier2pl_pattern_w116.sh` + `logs/hier2pl_pattern.log`,
  `parity_hier2pl_w116.py` + `logs/parity_hier2pl.log`,
  `parity_breakdown_w116.py` + `logs/parity_breakdown.log`,
  `logs/pilot_md5.log`, `logs/build_*.log`, `runs/Eprime/` (4 pilot
  cells + hier_2pl's 12), `md5/`.
- References reused read-only: `scratch/w109/runs/{S,E}/` (archive),
  `scratch/w109/driver_w109.py` (protocol), `scratch/w63/manifest.csv`
  (inits), `scratch/w88/blessed_estimators.py` (loaded, not needed — no
  ESS computed under the stop),
  `external/walnutpie_mm2guard/build_mg/examples/stan_cli` (executed
  read-only), `external/math_dev_w{108,112,113}` and `scratch/w108/
  bernoulli_logit_lpmf_gathered_w46.hpp` (header sources),
  `scratch/w46/gxx_fixed`.
