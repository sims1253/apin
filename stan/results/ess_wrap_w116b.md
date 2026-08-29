# W-116b — the 3-model E′ wall + ESS/s SALVAGE (PI-ruled via the W-108.1 pre-reg final paragraph): radon_pp and bym2 measured (24/24 cells md5-reproduce the archive E cells; wall bands PASS; radon_pp E′/S ESS/s = 2.65×, flipping the 0.90× floor case — HEADLINE MET); radon_var STOPPED at its gate (9/12 frozen-match + 2 REAL reproducible .so-level divergences + 1 environment-ill-posed cell — the W-116 pilot-clean ⇒ grid-clean assumption is FALSIFIED for it)

Executed 2026-08-29 per the "W-116 PRE-REGISTRATION" (gates/metrics/
bands), the W-116 CLOSE-OUT (the PI's 3-model salvage ruling), and the
"W-108.1 PRE-REGISTRATION" final paragraph (defines W-116b: bands
radon_pp ≤0.55, radon_var ≤0.60, bym2 ≤0.90; ESS/s E′/E, E′/S; headline
radon_pp E′/S > 1.3×). Arms S/E = the W-109 ARCHIVE (frozen, not rerun;
wall RECOMPUTED from its logs). Arm E′ = the W-116 builds reused verbatim
(no rebuilds): `scratch/w116/bs_eprime` (bundle untouched this session —
0 files newer than the W-116 pilot scripts, verified) + per-model trees
`scratch/w116/model_<m>_eprime/` with .so md5s: radon_pp
bac85ddd3c90b14a785cd7141e175e69, radon_var
5b14b5a25d6c436e3f539bd933311a69, bym2
7e20948af3e118505734068f0b3aa4df. hier_2pl EXCLUDED (W-108.1 owns it;
its tree under runs/Eprime/hier_2pl untouched, mtime 12:44 = W-116's).

Protocol = driver_w109.py VERBATIM (read-only reference): sampler
`external/walnutpie_mm2guard/build_mg/examples/stan_cli`, w1000 s1000,
pf inits per the w63 manifest (radon_pp/bym2 → inits_w36, radon_var →
inits_w63), seeds 20260819+1000·rep+chain, --metric-window 50, MM2 flags
per flags_for() (radon_pp/radon_var in MM2_BENEFIT → --min-micro-steps 2
--min-micro-guard; bym2 NOT in the list → metric-window only), single
chain per process, nice 19, env -u LD_LIBRARY_PATH, OMP_NUM_THREADS=1,
≤4 workers, driver `scratch/w116/grid_w116b.py` (resume-capable:
DONE iff csv+log complete AND md5 == archive), log
`scratch/w116/logs/grid_w116b.log`.

## 1. STOP-GATE (gate 1): 24/24 measured-model cells frozen-matched; radon_var fired — pattern + same-env root-cause evidence

All 36 cells run rc=0 with complete stanzas. E′ md5 vs frozen
`scratch/w109/runs/E/<model>/rep{r}_c{c}.csv`:

- **radon_partially_pooled_noncentered: 12/12 MATCH** (pilot rep0_c0
  81828b3d… reused + 11 fresh).
- **bym2_offset_only: 12/12 MATCH** (pilot 6a53d147… + 11 fresh).
- **radon_variable_intercept_slope_noncentered: 9/12 MATCH; STOPPED** —
  pattern (per-cell md5s in the driver log; alternates preserved):

| cell | verdict | E′ md5 | archive md5 |
|---|---|---|---|
| rep0_c2 | **ENV-ILL-POSED** (E′ exculpated) | c7ce20bfa0d4e07d4e0d254b1d253869 (isolated ×2) | 65d8f98c4051fd2c7dbd20c6eab9ae7e |
| rep1_c2 | **REAL DIVERGENCE** (stable, .so-level) | 59e2b30b1de169d6bc2c0276a08f0ee1 (4-worker AND isolated ×2) | fc7dbe12a4229b6f9963cb51c5bbbc95 |
| rep2_c0 | **REAL DIVERGENCE** (stable, .so-level) | 651d52361e27da49554c4740e56f021f (isolated ×2) | e6ab04e03be0902de6f8e45d51bcc027 |
| other 9 | frozen-MATCH | = archive | — |

Same-environment experiments (`scratch/w116/runs/Eprime_rerun/`, the
W-109 protocol, the ARCHIVE .so
`scratch/w109/model_radon_variable_intercept_slope_noncentered_alllayers/`
run read-only at its original path):

- **rep0_c2**: archive-.so isolated → c7ce20bf (×2, stable) = E′ isolated
  (×2) — **E′ and the archive binary agree bit-for-bit in matched
  environments**; the FROZEN 65d8f98c is unreproducible by the archive
  binary itself outside W-109's original 4-worker+foreign-load
  environment; my 4-worker grid produced a third value 671d8097. The
  cell is a knife-edge (70 borderline sigma=0 exception events; the
  W-115-documented Eigen malloc-layout sensitivity class). E′ exculpated;
  the accepted tree value is the same-env-verified c7ce20bf.
- **rep1_c2**: E′ stable at 59e2b30b across ALL environments (4-worker
  grid == isolated ×2); archive-.so stable at fc7dbe12 == frozen. Both
  arms individually deterministic, **differ from each other** — first
  diff at csv line 2 (the FIRST sampling draw; warmup fork), 1000/1000
  lines differ. NOT environment, NOT protocol (9 sibling cells at the
  identical protocol match).
- **rep2_c0**: same signature — E′ stable 651d5236 (×2), archive-.so
  stable e6ab04e0 == frozen (×2).

Attribution boundary (owned): the two real divergences are a
trajectory-conditional .so-level difference between the E′ build and the
archive all-layers .so that manifests only on trajectories grazing
degenerate likelihood states (sigma=0 exception storms: 506/70 events on
neighboring cells) — the hier_2pl-class failure family (operand-layout/
boundary-path gap in a gathered primitive; radon_var's likelihood is
gathered-normal, W-112's) but 1000× rarer (2 of 12 cells vs hier_2pl's
12/12). NOT root-caused at the gradient level here (W-116-style parity
probes on radon_var are a PI-ruled follow-up, the W-108.1 pattern).

Verdict granularity follows the W-116 precedent (model-scoped): the
per-model stop-gate protects that model's measurement — **radon_pp and
bym2 are measured; radon_var's wall/ESS/s numbers are VOID** (its 0.60
band and its geomean entry unreported), its pattern preserved above.
LESSON (negative-space, load-bearing for future salvages): radon_var's
W-116 PILOT cell (rep0_c0) was md5-clean — pilot-level cleanliness does
NOT extend to the full grid for this model class.

## 2. WALL (per-rep sum of per-chain 'total time:' stanzas; model = median of 3 rep sums; archive E recomputed from its logs)

| model | E wall (reps 0/1/2; median) | E′ wall (reps 0/1/2; median) | E′/E (per-rep) | band | verdict |
|---|---|---|---|---|---|
| radon_pp | 120.07 / 117.56 / 140.43; **120.07 s** | 41.81 / 40.09 / 52.48; **41.81 s** | **0.348** (0.348/0.341/0.374; sum 134.37/378.06 = 0.355) | ≤ 0.55 | **PASS** (37% margin) |
| bym2 | 39.19 / 37.24 / 37.21; **37.24 s** | 29.99 / 30.67 / 31.16; **30.67 s** | **0.824** (0.765/0.824/0.837; sum 91.83/113.64 = 0.808) | ≤ 0.90 | **PASS** (9% margin — load-caveated, below) |
| radon_var | 11.73 / 10.42 / 8.91; 10.42 s | (3.49 / 3.24 / 2.35; 3.24 s) | 0.311 observed | ≤ 0.60 | **VOID (stop-gate)** |

Recompute cross-check: my archive-E/S log sums equal w109_results.json
exactly (E: 120.07/10.42/37.24; S: 72.46/7.78/55.97) — the table was
not trusted; it checked out. Load flags (per-cell in the driver log):
E′ session n=54 loadavgs min 0.86 / median 3.13 / max 4.43 —
predominantly my own ≤4 nice-19 workers on this 12-core box; no sibling
compile observed coincident with the measured cells (sporadic W-108.1
≤2-core compiles are sanctioned). Archive W-109 session: median 3.98,
max 6.67 (its own 4 workers + foreign desktop load 1.5–3.4).
Interleaving with the frozen archive is impossible (pre-registered
disclosure); the residual load asymmetry favors E′ (E walls measured
under somewhat higher ambient load) — the effect should be small (both
grids 4-worker on 12 cores with idle cores remaining), but **bym2's 9%
band margin is within plausible load-bias range and its PASS is flagged
load-caveated**; radon_pp's 37% margin is robust to any plausible bias.
ESS is load-invariant throughout.

## 3. ESS/s (blessed split ruler scratch/w88/blessed_estimators.py, DROPS + 'X' + constant columns excluded; ESS_bulk_min rep-medians; ESS/s = per-rep ess_min/wall, median over reps)

| model | S ESS | E ESS | E′ ESS | S ESS/s | E ESS/s | E′ ESS/s | E′/E | E′/S |
|---|---|---|---|---|---|---|---|---|
| radon_pp | 220.77 | 370.99 | 370.99 | 3.047 | 2.756 | **8.080** | **2.932** | **2.652** |
| bym2 | 4.43 | 4.43 | 4.43 | 0.0792 | 0.1191 | **0.142** | **1.194** | **1.796** |
| radon_var | — VOID (stop-gate) — | | | | | | | |

- **E′ ESS == archive E ESS** exactly, as required for bit-identical
  arms: verified by direct recomputation on sample rep0 cells from the
  ARCHIVE csvs (radon_pp 417.63, bym2 5.67 — bit-equal to the E′ tree
  values), and true for all 24 measured cells by md5 construction. The
  E′/E ESS/s ratio therefore measures 1/(wall ratio) exactly (per-rep:
  radon_pp 2.93, bym2 1.19).
- **HEADLINE MET: radon_pp E′/S ESS/s = 2.65×** (pre-registered > 1.3×;
  the archive E/S cell was 0.904×, the worst math-attributable ESS/s
  cell in W-109). Mechanism as pre-registered: ESS unchanged (bit-
  identical draws), wall 0.348× → ESS/s moves by exactly 1/wall vs E.
- bym2 context: its ESS_min ≈ 4.4 is the known A0-inherent init-
  pathology pin (W-84/W-105b; rhat_max inf, ~9.5–9.6k of 9610 params
  >1.02 in every arm incl. the archive S/E) — the E′/S 1.80× is a pure
  wall win over S (E′/E 1.19× on top of the archive E's own 1.50×).
- radon_pp E′ diagnostics: rhat_max 1.0113, zero params >1.02 — clean.
- **2-MODEL GEOMEAN (PARTIAL — radon_var stopped; doubly partial: a
  subset of the already-4-model-partial wrap): E′/S ESS/s 2.183× | E′/E
  ESS/s 1.871× | E′/E wall 0.536.**

## 4. Deviations / disclosures (all owned)

- **radon_var measured NOTHING**: 2 of its cells are REAL, reproducible
  divergences between the E′ build and the frozen archive binary (both
  arms individually deterministic and stable — proven by ×2 isolated
  reruns each); its wall/ESS/s rows, 0.60 band, and geomean entry are
  VOID per the pre-registered stop. The env-ill-posed third cell
  (rep0_c2) is exculpated by the archive binary itself matching E′ in
  the same environment. Deep gradient-level root-cause NOT attempted
  (W-108.1-class follow-up; likely the gathered-normal primitive's
  boundary/operand path — W-112's counterpart of hier_2pl's W-108 gap).
- **Measurement scope narrowed from 3 models to 2** by the above — the
  pre-registered headline (radon_pp) and 2 of 3 bands survive; the
  "3-model geomean partial" became a 2-model partial, flagged as such.
- Driver crashed once mid-grid (Popen.stdout NoneType — stdout is a file
  object, not a pipe); 4 launched cells completed as valid orphans and
  were md5-verified on resume (SKIP lines in the driver log); no cell
  was double-run to completion except by that verified resume path.
- The 3 pilot cells (rep0_c0 × 3 models) are the W-116 pilot runs
  (2026-08-29 12:33, isolated single-process, load 0.23–1.13 per the
  W-116 record) — reused per the resume rule, contributing their
  'total time' stanzas to rep0 sums; disclosed for the wall table
  (per-rep spread 40.09–52.48 s dwarfs any single-cell condition
  difference).
- radon_var rep0_c2 tree cell = the same-env-verified isolated rerun
  (c7ce20bf); the 4-worker grid value 671d8097 and all probe runs
  preserved (MISMATCH copies + runs/Eprime_rerun/).
- Same-env probe runs (archive .so read-only at its original path, E′
  reruns) were executed at the exact W-109 protocol — they are extra
  machine time (~10 cells-worth), all logged, no rebuilds.
- Mid-analysis session interruption claimed the E′ artifacts were lost;
  verified FALSE (all files intact, analysis process alive); no restart
  or rerun was triggered by it. No effect on any number.
- Machine discipline: ≤4 workers nice 19 throughout; env -u
  LD_LIBRARY_PATH; OMP_NUM_THREADS=1; single chain per process; no
  callgrind; no rebuilds (bs_eprime 0 files modified — verified);
  hier_2pl tree untouched; WORKLOG.md/comms.md not written by this
  agent.
- Fast csv loader (np.fromstring) verified byte-equal to np.loadtxt
  (the W-109 loader) on bym2 and radon_pp files before use.

## 5. Artifacts

- `scratch/w116/`: `grid_w116b.py` (driver), `analyze_w116b.py`
  (analysis; conventions verbatim from scratch/w109/analyze_w109.py),
  `w116b_results.json` (all tables + per-rep detail + gate rows),
  `logs/grid_w116b.log` (per-cell rc/md5/load flags),
  `logs/analyze_w116b.log`, `runs/Eprime/<3 models>/` (36 cells;
  radon_var MISMATCH copies + the exception cell),
  `runs/Eprime_rerun/` (same-env probes: E′ ×, archive-.so ×, per
  rep0_c2/rep1_c2/rep2_c0).
- References reused read-only: `scratch/w109/runs/{S,E}/`,
  `scratch/w109/driver_w109.py`, `scratch/w109/analyze_w109.py`,
  `scratch/w109/w109_results.json` (cross-check only),
  `scratch/w63/manifest.csv`, `scratch/w88/blessed_estimators.py`,
  `external/walnutpie_mm2guard/build_mg/examples/stan_cli`,
  `scratch/w109/model_radon_variable_intercept_slope_noncentered_alllayers/`
  (archive .so, same-env probes).
