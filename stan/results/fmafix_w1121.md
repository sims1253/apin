# W-112.1 — radon_var divergence root-cause: STOP-CLAUSE INVOKED — the divergence is NOT FMA-contraction-class; the machine-code archaeology EXONERATES the contraction schedule at every point (forward and reverse, proven by disassembly AND 100-point bitwise runtime parity); the ACTUAL mechanism is a THROW-SET divergence: W-112's disclosed drop of stock's per-element `check_finite(mu)` (and `check_not_nan(y)`) makes the primitive NOT THROW on non-finite-mu warmup states where stock throws, feeding the sampler `(lp=-inf/NaN, grad=NaN/±inf)` instead of the exception path's `(lp=-inf, grad=0)` — proven by log forensics + an on-demand boundary probe. No fix applied (different fix class ⇒ PI escalation per the pre-registration).

Executed 2026-08-29 per WORKLOG "W-112.1 PRE-REGISTRATION". Deliverable
per the pre-registration's stop-clause: the archaeology, the mechanism,
and a ready-to-apply pre-registration text for the follow-up. **No
production code was changed** (the worktree `external/math_dev_w1121`,
branch `gathered-normal-fmafix` @ `bc00891778`, is pristine — 0 commits);
gates (a)–(d) and the wall stanza were NOT run (they validate a fix;
none landed).

## 1. The contraction-schedule table (the pre-registered deliverable)

Both sides at the archive's build flags (`-O3 -mavx2 -mfma`, gxx_fixed).
Stock = the archive .so `scratch/w109/model_radon_variable_intercept_
slope_noncentered_alllayers/radon_variable_intercept_slope_noncentered_
model.so` (md5 f04f5ae325a1f16c8c211c291541f5f8, symbols intact).
Old primitive = the W-116b E′ .so `scratch/w116/model_radon_variable_
intercept_slope_noncentered_eprime/radon_variable_intercept_slope_
noncentered_model.so` (md5 5b14b5a25d6c436e3f539bd933311a69); the model
passes AoS `Matrix<var>` alpha/beta and `var` sigma, so the AoS route is
the operative one (the E′ instantiation
`normal_lpdf_gathered_impl<false,true,Matrix<var>,Matrix<var>,var>`).

| # | op (per element) | stock (archive .so) | old primitive (E′ .so) | verdict |
|---|---|---|---|---|
| F1 | mu assembly `alpha + x·beta` (forward) | `vmulsd` (multiply_vd vari value) + `vaddsd` (add value) — 2 roundings via vari memory round-trips | `vmulsd` + **volatile stack round-trip** + `vaddsd` (0x34fa6/0x34fb7/0x34fc4) — 2 roundings | **MATCH** |
| F2 | y_scaled `(y−mu)·inv_sigma` | `vsubsd`+`vmulsd` (0x1c050/0x1c070) | `vsubsd`+`vmulsd` (0x34288/0x3428e) | **MATCH** |
| F3 | y_scaled² | `vmulsd` (0x1c080) | `vmulsd` (0x34292) | **MATCH** |
| F4 | lp term `−0.5·sq + NLSQP` | **FUSED** `vfmadd132sd` (0x1c102) — 1 rounding | **FUSED** `vfmadd213sd` (0x34296) — 1 rounding | **MATCH** |
| F5 | `− log(sigma)` | `vsubsd` (0x1c116) | `vsubsd` (0x3429f) | **MATCH** |
| F6 | d_mu `inv_sigma·y_scaled` | `vmulsd` (0x1c0a9) | `vmulsd` (0x3422e) | **MATCH** |
| F7 | d_sigma `inv_sigma·sq − inv_sigma` | **FUSED** `vfmsub132sd` (0x1c0b8) — 1 rounding | **FUSED** `vfmsub132sd` (0x34239) — 1 rounding | **MATCH** |
| R1 | `m = adj_term·d_mu` (reverse) | rounded product: the lpdf edge's fused `vfmadd132sd` (0x1c5e0) lands on the add-vari's ZERO-INIT adjoint ⇒ value = `RN(adj·d_mu)` (fused-vs-unfused value-identical at addend 0) | `vmulsd` (0x1b611) | **MATCH** |
| R2 | alpha increment | plain `vaddsd` of the rounded product (the `operator+(var,var)` chain 0x1c5b0 adds the add-vari's adjoint into alpha's) — 2 roundings | `vaddsd` (0x1b617; GCC did NOT re-fuse `alpha+=m` — `m` has 2 uses) | **MATCH** |
| R3 | beta increment | **FUSED** `vfmadd132sd` (`multiply_vd_vari::chain` 0x1c500 — W-112's own note) | **FUSED** `vfmadd132sd` (0x1b62e) | **MATCH** |
| R4 | sigma increment | **FUSED** `vfmadd132sd` (the lpdf edge 0x1c5e0) | **FUSED** `vfmadd132sd` (0x1b643) | **MATCH** |
| C0 | check order per element | `check_not_nan(y)` → `check_finite(mu)` → `check_positive(sigma)` (vucomisd NaN tests present in 0x1bf80) | `check_positive(sigma)` ONCE up front; **`check_not_nan(y)`/`check_finite(mu)` DROPPED** (W-112 §6 disclosure) | **DIVERGENT — the root cause** |

FMA-count provenance (whole .so): archive 232 `vfmadd` + 18 `vfmsub` +
8 `vfnmadd`; E′ 240 + 19 + 8 (delta from surrounding model code, not
the likelihood path). Any future rebuild must keep `-mavx2 -mfma`
(counts in this class; the W-108.1 provenance check).

Runtime certification of the table (stronger than disassembly alone):
`scratch/w1121/probe_parity_w1121.py valid` — 100 W-103 points
(default_rng(20260822), N(0,0.5), D=175), full-model `bs_log_density_
gradient` on each .so: **lp mismatches 0/100, gradient-vector
mismatches 0/100 (bitwise, equal_nan)**. The two binaries are
arithmetically indistinguishable on every valid state.

## 2. The actual mechanism — throw-set divergence at non-finite mu

Causal chain, each step evidenced:

1. **The sampler wrapper treats exceptions and returned-NaN
   differently** (`external/walnutpie_mm2guard/include/walnutpie/
   load_stan.hpp:128-147`): on a bridgestan exception it sets
   `logp = -inf` AND `grad.setZero()`; on `rc==0` it passes through
   whatever the model returned (lp and/or grad may be NaN/±inf).
2. **Stock throws on non-finite mu; the primitive does not.** Stock's
   per-element `check_finite(mu)` fires whenever the TP block
   overflows (`alpha = mu_alpha + sigma_alpha·alpha_raw` → ±inf/NaN
   during degenerate warmup states) while sigma > 0. The primitive
   (checks dropped, W-112 §6) computes `y_scaled = ±inf/NaN`, returns
   `rc=0` with `lp = -inf/NaN` and **NaN/±inf gradient components**.
3. **On-demand proof** (`probe_parity_w1121.py degen`,
   `scratch/w1121/logs/probe_boundary_outputs.txt`), mu=+inf state
   (mu_alpha unc = +inf, sigma_y = 1):
   - archive: `rc=-1`, THROWS `normal_lpdf: Location parameter is inf`,
     grad all-zero (175/175);
   - E′: `rc=0`, `lp=-inf`, **grad 88/175 components NaN**.
   Control states behave identically in both arms: sigma=0 (both throw
   `Scale parameter is 0`), NaN in priors' data path (both throw
   `Random variable is nan`, both arms), finite-huge mu=1e307 (both
   `rc=0, lp=-inf, 1 NaN grad comp` — the no-throw overflow class
   where stock also does not throw).
4. **The NaN gradient poisons the sampler state**: leapfrog
   `p += eps·grad` with NaN grad ⇒ NaN momentum ⇒ NaN parameters at
   the next call ⇒ the *priors'* `check_not_nan` throws
   `Random variable is -nan` at a different call, and the tree/
   divergence bookkeeping sees different values (e.g. `H=NaN` fails
   the `>1000` divergence comparison that `H=inf` from the exception
   path's `lp=-inf` triggers) ⇒ different discrete decisions ⇒
   permanent fork.
5. **Log forensics matches 1:1 on the divergent cells**
   (W-116b-preserved logs):
   - rep1_c2: archive = 13× `Scale 0` + **1× `Location is -nan` + 1×
     `Location is -inf`**; E′ = 13× `Scale 0` + **2×
     `Random variable is -nan`** (the downstream NaN-parameter
     signature).
   - rep2_c0: archive = 4× `Scale 0` + **1× `Location is -nan`**
     (stable ×2 archive reruns); E′ = 4× `Scale 0` only — the
     Location state never throws on the E′ side (4 vs 5 exceptions).
6. **Why only 2/12 cells forked (conditional amplification)**: the
   archive-E logs show `Location` events on 10 of 12 cells (e.g.
   rep0_c0: 7, rep0_c1: 14, rep1_c1: 19, rep2_c2: 5) — yet E′ matched
   those cells' md5s. The behavioral difference exists at every such
   state, but it propagates into the recorded draws only when the
   differing `(lp, grad)` values land tree-relevantly (change an
   accepted draw or the RNG-consuming tree growth); otherwise both
   arms reject the degenerate subtree and continue identically. The
   12-significant-digit csv format additionally hides bounded 1-ulp
   noise — but there IS no residual arithmetic noise (0/100 parity),
   so the conditional-fork reading is the only consistent one.
7. **Causal closure**: the chains differ ⟹ some state's `(lp,grad)`
   differed ⟹ the state was one where the binaries' behavior differs
   ⟹ the only such state-class is non-finite-mu-with-sigma>0 (§2.2,
   §2.3; everything else bitwise-identical) — noting both arms are
   individually deterministic (W-116b ×2 isolated reruns). The forks
   originate at stock's `check_finite(mu)` states. ∎

This also cleanly explains W-116b's original attribution boundary
("trajectory-conditional .so-level difference … on trajectories
grazing degenerate likelihood states") and why radon_pp (single-gather
eta = `alpha[ii]`, no TP-overflow-prone slope path in the same warmup
regime, and no Location events) matched 12/12: its E′ grid never
visited a mu-non-finite state.

## 3. The follow-up fix (PROPOSED — pre-registration text for the PI; NOT applied)

W-112.2 (one editor per header): in
`stan/math/rev/prob/normal_lpdf_gathered.hpp`'s
`normal_lpdf_gathered_impl` term loop, restore stock's per-element
check semantics in stock's order, hoisting the constant sigma check
(throw-set-equivalent):

```cpp
// stock's per-element checks (normal_lpdf: check_not_nan(y),
// check_finite(mu)); sigma is checked once up front (its value is
// constant per call — identical throw set, stock checks it per
// element after y/mu).
if (unlikely(std::isnan(y_d.coeff(k))))
  check_not_nan("normal_lpdf", "Random variable", y_d.coeff(k));
if (unlikely(!std::isfinite(mu_val.coeff(k))))
  check_finite("normal_lpdf", "Location parameter", mu_val.coeff(k));
```

Hot-path cost ~2 predicated compares/element (branch not taken on
valid states); value/gradient arithmetic untouched (0/100 parity
already proven for it). Expected effect: rep1_c2 → archive fc7dbe12…,
rep2_c0 → e6ab04e0…, full 12/12; rep0_c2 expected at its same-env
value c7ce20bf… (archive frozen 65d8f98c… is unreproducible by the
archive binary itself outside W-109's env — W-116b). Gates: W-112.1's
(a)–(d) verbatim PLUS new throw-set parity unit cases (non-finite mu
via inf/NaN alpha and x·beta overflow, NaN y, sigma≤0 — both arms
must throw; valid states unchanged), both eta shapes, both layouts
(AoS + SoA — the SoA route shares the impl), at `-O3 -mavx2 -mfma`
AND `-O2`; radon_pp E′ rebuilt + 12/12 re-verified (its trajectories
never visit the state class, so draws must be unchanged); W-112's
original non-FMA md5s (4a9ca349…/bbafc652…) re-verified. Then the
radon_var wall stanza + ESS/s cell (bands from the W-112.1 prereg:
wall ≤ 0.60, ESS = archive E's 415.0 by md5-identity, ESS/s vs
archive S wall 7.8 s / ESS 254.3).

Optional same-session PI decision points: (i) unify the check
messages to stock's `normal_lpdf` prefix (numerically irrelevant —
proven: the 13 differing-text Scale-0 events did not fork anything);
(ii) W-118's C2 fused interior should fold these checks into the
single pass (they are per-element anyway).

## 4. Deviations / disclosures (all owned)

- **Stop-clause invoked; no fix, no gates, no wall cell, no commits.**
  The pre-registered DESIGN (volatile-barrier schedule matching) was
  executed as archaeology and produced a NEGATIVE: every contraction
  point already matches (§1). Per the pre-registration ("if the
  disassembly proves the divergence is NOT contraction-class, stop
  and report the actual mechanism — PI escalation; do not improvise a
  different fix class"), the check-restoration fix class was NOT
  applied — §3 is the escalation package. Worktree
  `external/math_dev_w1121` (branch `gathered-normal-fmafix` @
  `bc00891778`, 0 commits, clean) left in place for the follow-up.
- The mission's "composed-reference probe built at -O3 -mavx2 -mfma"
  sub-task was satisfied by a STRONGER evidence pair instead: the
  archive .so vs the E′ .so themselves (same flags, same compiler,
  the actual divergent pair), decoded statically (§1) and certified
  at runtime (0/100 parity). W-112's own gate (a) had already run
  22,360 checks at `-mavx2 -mfma -O3` with 0 mismatches (its §3) —
  consistent with §1; not re-run (no code changed).
- The boundary probe's `err` strings can show a STALE message from
  the previous call when `rc==0` (bridgestan does not clear the out-
  param on success); the verdicts use `rc` + `lp` + grad counts, which
  are unaffected (d1 test: `rc=0`, `lp=-inf`, 88/175 NaN — the proof).
- W-116b's preserved logs/runs and the archive .so were used
  READ-ONLY; nothing under scratch/w109, scratch/w116, or any sibling
  worktree was modified. Machine: no builds this session (≤2-core
  budget unused), no callgrind, sampler-free diagnostics only (two
  .so loads via ctypes, nice 19, env -u LD_LIBRARY_PATH).
- /tmp held only the two parity npz files (copied to
  scratch/w1121/logs/); WORKLOG.md/comms.md not written (PI-owned).

## 5. Artifacts

- `scratch/w1121/probe_parity_w1121.py` (valid + degen modes, one .so
  per process, W-112 harness conventions).
- `scratch/w1121/logs/`: `probe_boundary_outputs.txt` (§2.3 evidence),
  `w1121_{ref,test}.npz` (100-point lp+grad arrays),
  `arch_so_chains.txt` + `eprime_so_chains.txt` (the §1 disassembly
  extracts at the recorded addresses), `fma_counts.txt`.
- References read-only: the two .sos (§1), `scratch/w116/runs/
  Eprime{,_rerun}/` + `scratch/w116/logs/`, `scratch/w109/runs/E/
  radon_variable_intercept_slope_noncentered/*.log` (the §2.5/§2.6
  histograms), `external/walnutpie_mm2guard/include/walnutpie/
  load_stan.hpp`, `scratch/w116/pristine/radon_variable_intercept_
  slope_noncentered.diff`.
