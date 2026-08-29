# W-105 — Uniform `-mavx2 -mfma` model builds: ABORTED at pre-registered gate (a) — the FD tripwire fires on kronecker_gp, classified as the W-35 both-arms numerics (NOT an ISA miscompile); 4/5 models PASS the gate

Pre-registration: WORKLOG "W-105 PRE-REGISTRATION" (2026-08-28), written
before any build. This file is the full record of what was run, the verbatim
gate outcome, the classification evidence, and the stop.

## 1. Builds (complete, all 10 .so verified)

Arms from the pristine bundle `scratch/w53/bs_w53` (SoA state, math tree
clean @ 4915949; md5s recorded before start, re-verified at close):
`scratch/w105/pristine_md5.txt` — both OK at close-out.

```
cp -al scratch/w53/bs_w53 scratch/w105/bs_stock
cp -al scratch/w53/bs_w53 scratch/w105/bs_avx2
rm -f scratch/w105/bs_stock/src/bridgestan.o scratch/w105/bs_avx2/src/bridgestan.o   # private-inode discipline
```

Models (sources `stan/models/<m>.stan`, data/inits per `scratch/w63/manifest.csv`):
diamonds, kronecker_gp, accel_gp, hier_2pl, blr — per-variant dirs
`scratch/w105/model_<m>_<arm>/`.

Exact build commands (per model x arm; from the arm's bundle root, cwd
`scratch/w105/bs_<arm>`; driver `scratch/w105/build_w105.sh`, logs
`scratch/w105/build_logs/*.log`):

```
# stock arm — DEFAULT flags, no CXXFLAGS anywhere on the command line
nice -n 19 env -u LD_LIBRARY_PATH OMP_NUM_THREADS=1 \
  /usr/bin/make -j2 CXX=/home/m0hawk/Documents/apin/stan/scratch/w46/gxx_fixed \
  TBB_CXX_TYPE=gcc STANCFLAGS="--include-paths=." \
  /home/m0hawk/Documents/apin/stan/scratch/w105/model_<m>_stock/<m>_model.so

# avx2 arm — identical invocation plus prepended CXXFLAGS
nice -n 19 env -u LD_LIBRARY_PATH OMP_NUM_THREADS=1 \
  /usr/bin/make -j2 CXX=/home/m0hawk/Documents/apin/stan/scratch/w46/gxx_fixed \
  TBB_CXX_TYPE=gcc CXXFLAGS="-mavx2 -mfma" \
  STANCFLAGS="--include-paths=." \
  /home/m0hawk/Documents/apin/stan/scratch/w105/model_<m>_avx2/<m>_model.so
```

Uniformity (the pre-reg's core safety property), verified from the recorded
compile lines in the build logs — math's `make/compiler_flags` uses
`override CXXFLAGS += ... -O3 ...`, so the arms differ by ISA flags only,
and `src/bridgestan.o` + model `.o` were compiled in the SAME make
invocation per arm (bridgestan.o was `rm`'d in each arm copy first; the
first model build of each arm rebuilt it — 1x "Compiling Stan bridge" per
arm log; stock log contains 0 occurrences of "mavx2", avx2 arm carries
`-mavx2 -mfma` on BOTH the bridge and model compile lines):

- stock bridge:  `gxx_fixed -std=c++17 -D_REENTRANT ... -O3 ...`
- avx2 bridge:   `gxx_fixed -mavx2 -mfma -std=c++17 -D_REENTRANT ... -O3 ...`

W-103 gotcha honored: `TBB_CXX_TYPE=gcc` alongside `CXX=gxx_fixed`.
10/10 builds rc=0 (03:21:52–03:26:45). Load verification (each .so via
bridgestan, `log_density_gradient` at a benign 0.1-vector): 10/10 OK,
logp/|g| identical to 6 digits across arms per model. D: hier_2pl 669,
kronecker_gp 438, accel_gp 66, diamonds 26, blr 6.

## 2. GATE (a) — FD tripwire (run FIRST, per pre-reg) — VERDICTS

Protocol exactly as pre-registered: per model x avx2 .so, 20 random
unconstrained points (`numpy.random.default_rng(2026).standard_normal(D)`),
autodiff gradient vs central finite differences of logp (propto=True,
jacobian=False, the W-103 parity convention), h_i = 1e-5 * max(1, |x_i|),
rel-L2 = ||g - g_fd||/||g_fd||, PASS iff all points <= 1e-6.
Script `scratch/w105/gate_fd_w105.py`; raw per-point results
`scratch/w105/gate_fd_results.json`. The stock arm was run through the
IDENTICAL gate as a classifier (arm-symmetry evidence).

| model | avx2 max rel-L2 | verdict | stock max rel-L2 (classifier) |
|---|---|---|---|
| diamonds | 7.328e-10 | PASS (20/20) | 7.406e-10 |
| kronecker_gp | 5.734e-02 | **FAIL (19/19 evaluable > 1e-6; 1 throw)** | **6.848e-02 (19/19 fail; same throw)** |
| accel_gp | 2.750e-09 | PASS (20/20) | 2.761e-09 |
| hier_2pl | 3.549e-09 | PASS (20/20) | 3.570e-09 |
| blr | 2.524e-10 | PASS (20/20) | 2.539e-10 |

**GATE (a) FAIL (kronecker_gp, avx2 arm). Pre-registered clause invoked:
"ANY failure = STOP, report verbatim (the miscompile tripwire)." Gates
(b), (c), (d) were NOT run.** (Prepared-but-unexecuted drivers left in
place for any re-registration: `scratch/w105/driver_ess_w105.py`,
`run_callgrind_w105.sh`, `wall_w105.sh`, `analyze_ess_w105.py`.)

Per-point kronecker table (both arms, same points): every evaluable point
fails in BOTH arms at near-identical magnitudes, e.g. pt1 1.919e-2 vs
1.917e-2, pt4 9.028e-3 vs 9.027e-3, pt16 4.362e-2 vs 4.361e-2; pt3 throws
in both arms (`lkj_corr_cholesky_lpdf: Random variable[30] is 0, but must
be positive!`).

## 3. Classification (evidence, not gate re-interpretation): the tripwire fired on a property that predates the ISA change

1. **Arm-symmetric failure**: the stock (SSE2-baseline) arm fails the same
   gate on the same 19/19 points with a WORSE max (6.85e-2 vs 5.73e-2).
2. **Worst components identical across arms** at the worst point (pt13):
   L.435, L.351, L.348, L.347, L.349, L.350, L.344 ... (the L block
   downstream of the eigendecomposition of near-singular Lambda = L L^T),
   with autodiff VALUES agreeing cross-arm to 4+ digits (e.g. L.435:
   -1.7176 both arms) while FD collapses toward 0 for those components in
   BOTH arms — the FD estimate, not the autodiff gradient, is the outlier.
3. **logp cross-arm agreement at pt13: rel 2.78e-14** — rounding-level
   only, exactly the permitted GEMM-accumulation reordering.
4. **Cross-arm gradient rel-L2 on the 20 pts: median 6.65e-3, max 4.29e-2**
   — the W-35 signature (GEMM rounding diff ~1e-14 amplified O(1e2..1e3x)
   by the rounding-degenerate eigendecomposition; W-35 close-out:
   "rev eigenvector adjoint ... silently return FD-inconsistent gradients
   in EVERY build, and any permitted FP variation moves them O(1)").
5. The four healthy models show avx2-vs-stock max rel-L2 agreement at the
   1e-9..1e-10 level with arm differences in the 3rd digit — no ISA
   anomaly anywhere the model is well-posed.

Conclusion: this is NOT a `-mavx2 -mfma` codegen bug — it is the
W-35-classified kronecker_gp numerics (eigenvector adjoint on degenerate
spectra) that the gate (as registered) cannot distinguish from one. The
pre-registration's own risk clause ("treat ANY gradient anomaly as a
stop") binds: the experiment stops here regardless, and the G-reduction
targets (diamonds/kronecker/accel −15..−40%, hier_2pl −3..−10%, blr ~0)
remain UNTESTED. For any future re-registration, the tripwire needs a
kronecker-compatible form, e.g. (i) FD gate on well-posed models +
cross-arm FD-symmetry on kronecker (fail iff the avx2 arm's FD deviation
EXCEEDS the stock arm's at the same points), or (ii) repair the model's
conditioning (jitter floor), or (iii) land the W-40-class cluster-aware
adjoint first. This is recorded as a gate-design lesson, not a license to
rerun under a moved goalpost.

## 4. AVX-512 (per pre-reg: hardware-gated follow-up, CLOSED on this box)

This box is Zen 3 (AVX2+FMA, NO avx512f; /proc/cpuinfo): an 8-lane island
is unrunnable and unvalidatable here; post-AVX2-kernel its target is only
the ~5-8% residual kernel share (best case 2-4% G). Reopened only on
Zen 5 / Sapphire Rapids hardware with the ulp/dispatch harness rerun.

## 5. Artifacts

- `scratch/w105/` — build_w105.sh, build_logs/ (10 logs, full compile
  lines), bs_stock/, bs_avx2/ (private bridgestan.o inodes), model_*/
  (10 .so), pristine_md5.txt (both OK at close), gate_fd_w105.py,
  gate_fd_results.json, driver_ess_w105.py, analyze_ess_w105.py,
  run_callgrind_w105.sh, wall_w105.sh (last four prepared, NOT run).
- Pristine `scratch/w53/bs_w53` untouched (md5-verified; its bridgestan.o
  inode never written through — the arm copies built their own).
- No walnutpie/math tree changes; the gate binary
  `external/walnutpie/build_w36exp/examples/stan_cli` was read-only
  (never invoked — gates (b)-(d) not run).
