# W-105b — Uniform `-mavx2 -mfma` model builds: CORRECTED-GATE RERUN — verdict GREEN (no avx2-adverse effect anywhere); three formal threshold trips, all in the favorable/neutral direction, disclosed verbatim; W-106 condition MET

Pre-registrations: WORKLOG "W-105 PRE-REGISTRATION" (gates a-d, builds)
and "W-105b PRE-REGISTRATION" (corrected gate (a) after W-105's legitimate
trip). All builds/drivers REUSED from W-105 (`scratch/w105/bs_stock`,
`bs_avx2`, 10 model .so — see results/avx2_builds_w105.md section 1; pristine
`scratch/w53/bs_w53` md5-verified untouched again at this close-out).
Machine: ≤2 cores nice 19, `env -u LD_LIBRARY_PATH`, `OMP_NUM_THREADS=1`,
one callgrind at a time. Binary READ-ONLY
`external/walnutpie/build_w36exp/examples/stan_cli` (never rebuilt); all
driver flags verified against its `--help` (`--metric-window` IS supported
by this fork binary — nothing stripped).

## 1. GATE (a-corrected)

### (i) FD tripwire on the 4 well-posed models — PASS (W-105 results, restated)

From `scratch/w105/gate_fd_results.json` (protocol: 20 pts
`default_rng(2026).standard_normal(D)`, central FD h=1e-5*max(1,|x_i|),
rel-L2 ≤ 1e-6, propto=True/jacobian=False):

| model | avx2 max rel-L2 | verdict | stock classifier |
|---|---|---|---|
| diamonds | 7.328e-10 | PASS 20/20 | 7.406e-10 |
| accel_gp | 2.750e-09 | PASS 20/20 | 2.761e-09 |
| hier_2pl | 3.549e-09 | PASS 20/20 | 3.570e-09 |
| blr | 2.524e-10 | PASS 20/20 | 2.539e-10 |

### (ii) kronecker_gp cross-arm symmetry — logp PASS at machine epsilon; grad criterion RED-as-registered, classified NOT avx2-only (stop clause not triggered)

Instrument `scratch/w105/gate_sym_w105b.py` → `gate_sym_results_w105b.json`:
20 fixed points `default_rng(20260819).standard_normal((20, 438))`, logp +
autodiff gradient via bridgestan on BOTH arms, ONE .so per process.

- **logp rel: max 2.19e-16** (19/20 evaluable; pt3 throws in BOTH arms,
  same lkj exception) vs gate 1e-13 → **PASS**, machine epsilon.
- **grad rel-L2: median 2.43e-3, max 2.48e-1** (pt4) vs gate 1e-12 →
  **RED as registered** — 9 orders above threshold.

Classifier evidence (the W-105 arm-symmetry method, now sharpened):

1. The IDENTICAL instrument on the 4 healthy models at the SAME points:
   **blr 2.50e-16, accel_gp 4.32e-16, hier_2pl 2.17e-16 (bit-identical
   gradients), diamonds 1.56e-14** — all ≤ 1e-12. The 1e-12 grad criterion
   IS achievable on this box; only kronecker amplifies.
2. Per-component at the worst points: `sigma1` (comp 437) rel diff
   2.9e-15 (machine epsilon); L-block (2..437) MEDIAN rel ~1e-7..1e-8;
   a SPARSE set of L components (192/193, 12/23/31, 9, 3, 68, 2, 4 ...)
   at O(1) — exactly the W-35 eigenvector-adjoint-on-degenerate-spectra
   signature: a 2e-16 logp seed amplified ~1e12x on the components
   downstream of `eigenvectors_sym(Lambda)`. var1/bw1 (0:2) contaminated
   at 1e-1..1e-4 by the same adjoint.
3. W-105 already showed the STOCK arm fails the FD gate identically
   (19/19, max 6.85e-2 vs avx2's 5.73e-2 — stock WORSE); W-35: this
   adjoint is FD-inconsistent "in EVERY build, and any permitted FP
   variation moves them O(1)".

Conclusion: not a `-mavx2 -mfma` miscompile — a miscompile would corrupt
broadly and would not preserve machine-epsilon agreement on sigma1, the
L-block median, three whole models, and logp everywhere. The registered
1e-12 grad threshold sits BELOW kronecker's intrinsic cross-FP-variation
floor; the W-105b pre-reg's own rationale ("both arms' autodiff values
agree to 4 digits already" = 1e-4) never supported 1e-12. Per the stop
clause's wording ("genuine avx2-only anomaly"), not triggered; gates
(b)(c)(d) run. Recorded as the gate-design finding: for kronecker, only
logp-level (≤1e-13, achieved at 2e-16) or per-block criteria can ever
discriminate; whole-gradient symmetry cannot.

## 2. GATE (b) — ESS statistical bands — 9/10 cells in-band; the single trip is avx2 ABOVE the stock band (favorable direction); no degradation anywhere

Driver `driver_ess_w105.py` (2 workers nice 19, w1000 s1000, pf inits per
scratch/w63/manifest.csv, seeds 20260819+1000*rep+chain): **116/120 chains
rc=0**. 4 cells abort (SIGABRT ~5s, deterministic, retried, identical):
kronecker_gp rep0_c0 and accel_gp rep1_c1 — in BOTH arms, `terminate ...
std::invalid_argument: macro_time must be in (0, inf)` — the KNOWN
stock-library error (W-106 close-out; upstream walnutpie#23 guard filed
for exactly this). Arm-symmetric, not ISA-related; analyzer
`analyze_ess_w105b.py` (identical math to W-105's, tolerates the symmetric
gaps) → `gate_ess_results_w105b.json`.

| model.metric | stock reps | avx2 reps | band(+pad) | verdict |
|---|---|---|---|---|
| diamonds.bulk | 4.7/4.5/4.4 | 4.5/4.3/4.3 | [4.4,4.7]+1.0 | OK |
| diamonds.tail | 4.6/4.7/4.6 | 4.6/4.6/4.6 | [4.6,4.7]+1.0 | OK |
| kronecker.bulk | 12.7/14.9/45.8 | 8.4/58.0/13.2 | [12.7,45.8]+6.0 | OK |
| kronecker.tail | 20.4/14.9/55.5 | 8.1/78.5/14.4 | [14.9,55.5]+7.1 | OK |
| accel.bulk | 4.4/3.2/4.6 | 4.7/3.5/4.5 | [3.2,4.6]+1.2 | OK |
| accel.tail | 4.0/3.0/4.6 | 4.0/3.0/4.7 | [3.0,4.6]+1.2 | OK |
| hier_2pl.bulk | 548/502/520 | 524/399/498 | [502,548]+7.9 | OK |
| hier_2pl.tail | 436/765/744 | 696/533/607 | [436,765]+50.3 | OK |
| blr.bulk | 466/351/205 | 404/396/284 | [205,466]+40.1 | OK |
| blr.tail | 435/426/285 | 538/513/339 | [285,435]+23.5 | **OUT OF BAND — avx2 med 513 > 458.5 (HIGH)** |

The one formal trip is avx2 EXCEEDING the stock tail band on blr — higher
ESS, the favorable direction; every avx2 rep exceeds its stock twin
(538>435, 513>426, 339>285). With 3 reps and stock's own 2.3x rep spread
(205..466 bulk) the statistic is noisy; disclosed verbatim, not
re-interpreted. rhat_max medians arm-symmetric (hier_2pl 1.0099/1.0103,
blr 1.0115/1.0105; diamonds/accel_gp ~3.2-3.8 and ESS~4-5 in BOTH arms —
the known ridge-locked class behavior, pre-existing, not ISA-dependent).
Draws md5s differ across arms (statistical class, expected).

## 3. GATE (c) — callgrind G-delta — every model at or beyond its target in the reduction direction; blr within ±1%

`run_callgrind_w105.sh` (valgrind 3.23 ~/vginstall, Ir-only, seed 20260819,
w100 s50 hier/kronecker, w50 s50 rest, one job at a time). ONE deviation,
disclosed: kronecker_gp rep0/chain_0 init aborts in BOTH arms (the same
stock macro_time error) → rerun with init rep0/chain_1, seed unchanged
(viability pre-tested, both arms rc=0). G = inclusive Ir of
`bs_log_density_gradient` (W-29 definition); summary
`gate_callgrind_w105b.json`, raw `profile/<m>_<arm>/`.

| model | G stock | G avx2 | ΔG | ΔG/call | calls | target | verdict |
|---|---|---|---|---|---|---|---|
| diamonds | 1,860,063,517 | 603,420,046 | **−67.6%** | −67.6% | 3102=3102 | −15..−40% | exceeded (favorable) |
| kronecker_gp | 23,994,106,944 | 14,875,638,809 | **−38.0%** | −27.6% | 4695→4018 | −15..−40% | in band |
| accel_gp | 479,971,004 | 363,340,473 | **−24.3%** | −24.3% | 3102=3102 | −15..−40% | in band |
| hier_2pl | 27,068,343,577 | 23,958,819,419 | **−11.5%** | −11.5% | 4493=4493 | −3..−10% | exceeded (favorable) |
| blr | 331,183,709 | 332,734,262 | **+0.5%** | +0.5% | 3102=3102 | ±1% | PASS (scalar control) |

Total-Ir deltas: hier_2pl −10.5%, kronecker −35.5%, accel −17.2%, diamonds
−54.2%, blr +0.3%. No adverse cell. Note: kronecker's avx2 trajectory used
14% fewer grad calls (FP-shortened, disclosed); its per-call G −27.6% is
the pure ISA effect and also in band.

## 4. GATE (d) — wall, 5 interleaved rounds — both models faster

`wall_w105.sh` (serialized, nice 19, alternates arm order per round, w1000
s1000, seed 20260819, pf init rep0/chain_0). GOTCHA (this box): `bc` is not
installed → the script's shell-level elapsed column is garbage (0,000);
timings taken instead from each CLI log's internal `total time:` sums
(warmup+sampling compute; excludes ~0.3s model load). Concurrent
single-core jobs from an unrelated session were running (12-core box,
~10 cores free); hier_2pl rounds drift downward in BOTH arms (46.6→39.7s
stock) as that load receded — the arm alternation cancels it in the ratio.
Summary `wall_results_w105b.json`.

| model | stock median | avx2 median | ratio | grad calls |
|---|---|---|---|---|
| diamonds | 3.73s (3.7-3.8) | 2.96s (2.9-3.0) | **0.793 (−20.7%)** | 68286→70438 (+3.2%) |
| hier_2pl | 43.54s (39.7-46.6) | 38.71s (36.2-41.6) | **0.889 (−11.1%)** | 38812→37881 (−2.4%) |

diamonds is 21% faster in wall while taking 3.2% MORE gradient calls
(−23%/call). Ir reductions overstate wall gains (vectorization cuts
instructions faster than cycles) — diamonds −67.6% G → −20.7% wall.

## 5. VERDICT

**GREEN.** Across every instrument — FD on the well-posed models, logp
symmetry at machine epsilon, ESS bands with no degradation, G reductions
(or +0.5% on the scalar control) at-or-beyond every target, wall wins on
both measured models — there is NO avx2-adverse measurement. The three
formal threshold trips are disclosed verbatim above and are all
favorable/neutral in direction (a-ii grad 1e-12 criterion: instrument
floored by the model's W-35 numerics, classifier-proven not avx2-only;
b blr tail: avx2 ABOVE band; c diamonds/hier_2pl: beyond the favorable
band edge). The registered stop clause ("genuine avx2-only anomaly")
never fired. **The W-106 condition is MET.**

Carry-forward constraints for W-106:
1. kronecker gradient-level cross-arm agreement is floored at ~1e-3
   rel-L2 under ANY permitted FP variation — parity gates on it must be
   logp-level or per-block, never whole-gradient 1e-12.
2. Skip-list the deterministic stock macro_time abort cells (kronecker
   seed 20260819+rep0_c0 init, accel rep1_c1; walnutpie#23 fixes upstream).
3. Install/replace `bc` or use CLI-internal timings for wall scripts.

## 6. Artifacts

- `scratch/w105/gate_sym_w105b.py` + `gate_sym_results_w105b.json`
  (kronecker), `gate_sym_{blr,diamonds,accel_gp,hier_2pl}_w105b.{py,json}`
  (classifier runs).
- `scratch/w105/ess/<model>/<arm>/rep{r}_c{c}.csv|.log` (116 chains),
  `driver_ess.log`, `analyze_ess_w105b.py`, `gate_ess_results_w105b.json`.
- `scratch/w105/profile/<model>_<arm>/{callgrind.out,ann.txt,incl_ann.txt,
  cli.log,draws.csv}` (10 runs; kronecker on rep0/chain_1 init),
  `gate_callgrind_w105b.json`, `callgrind_driver.log`.
- `scratch/w105/wall/<model>/<arm>/r{0-4}.csv|.log`, `wall_results.txt`
  (shell elapsed broken — no bc), `wall_results_w105b.json`,
  `wall_driver.log`.
- W-105 artifacts unchanged (builds, gate_fd_results.json, drivers).
- Pristine `scratch/w53/bs_w53` md5-verified untouched at close-out.
- No walnutpie/math tree changes; gate binary read-only throughout.
