# W-118 — the fused single-pass `normal_lpdf_gathered` interior: ALL FOUR GATES GREEN (radon_pp G −35.4% — exceeds the band's favorable edge, disclosed; radon_var −27.6% in band), bit-identical everywhere (draws md5 12/12 + 12/12 vs the frozen archive, 100-pt parity exact-zero, 27,821 unit checks at both flag levels)

Executed 2026-08-29 per WORKLOG "W-118 PRE-REGISTRATION" (C2 from the
W-117 audit). Base: `9a07ffa459` (the W-112.2 throw-set fix) in worktree
`external/math_dev_w118`, branch `gathered-normal-fused`, commits
`e78ea066c5` (implementation) + `d600b17111` (doc). Not pushed.
Artifacts under `scratch/w118/`.

**Headline: the C2 interior landed with every pre-registered component —
the y copy killed, the loops fused behind ONE vectorized term pass
(per-lane = stock's scalar sequence, contraction points preserved),
W-53-class batched no-stack term records, the dead d_sigma store skipped —
and the throw-set contract not merely preserved but made STRICTLY
stock-ordered on mixed-defect states. G drops 10.76 → 6.95e9 Ir on
radon_pp (−35.4%) and 647 → 468e6 on radon_var (−27.6%) with digit-for-
digit identical draws on all 24 archive cells.**

## 1. What was implemented (commit e78ea066c5)

1. **Redundant y copy eliminated**: `y` is read in place (`y.data()` for
   direct-access Eigen; one-time evaluation fallback for exotic
   expressions); same for the SoA alpha/beta `val_` arrays (J-sized
   copies gone).
2. **Loops fused behind one VECTORIZED term pass**: the standalone
   `gathered_term_pass` computes the term, both edge partials, and the
   validity mask in one traversal; the shape-specific gather pass (A:
   clamped gather + range bit; B: the volatile-barrier linear predictor
   + both range bits) runs ahead of it. The prereg's literal "one
   traversal" is refined to "gather pass + one vectorized term pass":
   GCC 16 never auto-vectorizes arbitrary-index gathers (`a[b[k]]` —
   probe-verified), and B's volatile barrier excludes its mul-add from
   any vector loop regardless. Net 3 traversals → 2.
3. **Per-lane SIMD**: no horizontal ops, no control flow in the term
   pass. At model flags it emits `vsubpd+vmulpd` (F2 unfusable),
   `vmulpd` (F3), `vfmadd132pd` (F4 CONTRACTED — stock's `vfmadd132sd`
   per lane), `vsubpd` (F5), `vmulpd` (F6), `vfmsub132pd` (F7
   CONTRACTED — stock's `vfmsub132sd` per lane), `vcmpneqpd` NaN/finite
   checks, with scalar epilogues in the matching `sd` forms. Three
   GCC 16 behaviors had to be engineered around (each probe- and
   disassembly-verified): (i) per-bit ternary masks and the
   double+int+uchar store mix block vectorization — the mask became a
   single-bit int store; (ii) **`-fPIC` (the .so build) makes the
   vectorizer refuse to version the loop for aliasing** — true
   `__restrict__` parameters restore it; (iii) **inside the stanc model
   TU (one ~31 KB translation unit) GCC vectorizes NO double loop of
   the inlined primitive** — a `noinline` term-pass function restores
   it IN the model .so (packed FMA verified in the built .sos:
   vcmpneqpd ×8, vfmsub132pd ×4, both models).
4. **W-53-class batched no-stack term records**: one arena allocation
   of N `vari_value<double>` via a new `vari_no_stack` tag constructor
   in `vari.hpp` (W-53's exact tag shape; inert unless called), NO
   per-record nochain push, ONE `gathered_term_zeroer` (a `vari_base`
   on the nochain stack) giving `set_zero_all_adjoints` per-record
   zeroing parity — required because the accumulator's `sum` chains
   ACCUMULATE into term adjoints (repeated-grad parity is unit-gated).
5. Plus: dead `d_sigma` store skipped when sigma is data; ONE arena
   revdata struct captured by pointer replaces ~11 by-value closure
   copies; the reverse scatter keeps the W-112.2 statements verbatim
   (contraction points re-verified by disassembly: same
   `vmulsd`/`vaddsd`/`vfmadd132sd` classes as the md5-proven baseline).
6. **Throw-set strengthened**: stock's per-element conditions (alpha
   index → beta index → y NaN → mu finite) become mask bits in the hot
   passes, re-derived in stock's EXACT order by a cold path at the
   first bad element. Mixed-defect states the two-loop W-112.2
   structure ordered differently (all bounds before any y/mu) are now
   strictly stock-ordered — a strict superset of the W-112.2 contract.

Honest floor (as pre-registered): the reverse scatter stays a separate
serial pass; the sigma-adjoint accumulation stays store-to-load serial.

## 2. Gates

| gate | evidence | verdict |
|---|---|---|
| (a) bitwise unit, MODEL FLAGS + -O2 | `scratch/w118/test_prim.cpp` (W-112.2's harness + fusion-edge N grid {1..8,15,16,17,31,32,33,100,919,12573} × both shapes × both layouts × sigma var/dbl + J=1 degenerate + 10 strict-order mixed-defect throw cases + repeated-grad batching parity), BOTH changed headers first on the include path, at `-O3 -mavx2 -mfma` AND `-O2` | **27,821 checks, 0 mismatches at BOTH levels**; every throw case byte-identical (incl. `vector[uni] indexing: … index 99 out of range…`, bounds-before-y and y-before-mu orderings); contraction points disassembly-verified (§1.3) |
| (b) draws md5 + parity | E′ = `bs_eprime118` (cp -al of w1121's eprime22 bundle; BOTH headers at private inodes; bridgestan.o rebuilt in-copy; −mavx2 −mfma; model hpps byte-identical to W-112.2's, md5-asserted PRE and POST build); `grid_w118.py` (W-109 protocol: w1000 s1000, seeds 20260819+1000·rep+chain, mw50, MM2 ON, sequential, nice 19); `gate_parity_w118.py` (100 W-103 points vs the W-109 archive .so) | **radon_pp 12/12 == archive** (incl. rep0_c0 `81828b3d…`); **radon_var 12/12 == frozen archive** — rep1_c2 `fc7dbe12…`, rep2_c0 `e6ab04e0…`, rep0_c2 `65d8f98c…` **stable ×3**; parity **lp 0/100, grad 0/100 exact-zero BOTH models** |
| (c) callgrind, band −15..−30% G | W-29 protocol (w36exp CLI, seed 20260819, w100 s50, mw50; one arm at a time; baselines = the W-112.2 E′ .sos read-only); draws md5 IDENTICAL within each arm pair (`4a9ca349…` pp, `bbafc652…` var — bit-identity certified under the traced runs); grad calls identical per pair (6,378 / 6,372) | **radon_pp: G 10,760,447,558 → 6,952,369,981 = −35.39%** (EXCEEDS the band's favorable edge — disclosed below); **radon_var: 647,234,746 → 468,425,448 = −27.63% IN BAND**; total run Ir −29.95% / −13.10% |
| (d) TU + controls | `normal_lpdf_gathered_test.cpp` (W-112.2's 5 + `FusionEdgeWidths` + `StrictOrderThrowSet` + `BatchedRecordsRepeatedGrad`); normal-distribution controls + rev-core controls (vari.hpp blast radius) | TU **8/8 PASSED**; `prim/prob/normal_test` 4/4, `rev/prob/normal_log_test` 1/1, `mix/prob/normal_test` 1/1, `rev/core/set_zero_all_adjoints_nested_test` 1/1, `nested_rev_autodiff_test` 4/4, `callback_vari_test` 5/5, `build_vari_array_test` 1/1 — all PASSED |

## 3. Gate (c) detail — Ir/elem before/after and attribution

G = inclusive Ir of `bs_log_density_gradient`; per-elem = G/(grad
calls)/N.

| model | arm | G (Ir) | Ir/grad | Ir/elem |
|---|---|---|---|---|
| radon_pp | W-112.2 E′ | 10,760,447,558 | 1,687,119 | 134.2 |
| radon_pp | **W-118 fused** | **6,952,369,981** | **1,090,055** | **86.7** |
| radon_var | W-112.2 E′ | 647,234,746 | 101,575 | 110.5 |
| radon_var | **W-118 fused** | **468,425,448** | **73,513** | **80.0** |

Attribution (self-Ir per element, likelihood-path symbols):

| complex | radon_pp | radon_var |
|---|---|---|
| primitive forward body (inlined symbol) | 82.8 → 38.6 | 69.8 → 40.8 |
| `gathered_term_pass` (the vectorized pass, separated) | 0.0 → 6.2 | 0.0 → 3.8 |
| nochain-stack pushes (`vari_base*&` emplace) | 8.7 → **0.1** | 5.5 → **0.3** |
| reverse scatter (callback) | 12.5 → 13.4 | 10.4 → 11.0 |
| accumulator complex (`sum` + its callback) | 11.2 → 11.2 **identical** | 11.2 → 11.2 **identical** |
| **primitive-own total (fwd+pass+push+scatter)** | **103.9 → 58.3 (−43.9%)** | **85.7 → 55.9 (−34.8%)** |

Reading: the pre-registered component estimates all materialized —
y-copy + fusion + loop overhead inside the forward body (−38.0/elem on
pp), the batching kills the pushes to noise (−8.6/elem), the SIMD term
pass carries the arithmetic (6.2/elem for the whole vectorized pass on
pp), and the scatter + accumulator are untouched by design (the
scatter is the honest floor; +0.9/elem from struct-indirect reads,
disclosed). The primitive-own 103.9 → 58.3 Ir/elem lands INSIDE the
pre-registered 55–65 floor window (the W-117 audit's 97.4 was
protocol-relative; this protocol's baseline was 103.9).

**Band verdict**: radon_var −27.63% is inside −15..−30%. radon_pp
−35.39% EXCEEDS the band's favorable edge — the overdelivery is the
SIMD term pass landing fully in the model .so (the noinline rescue of
§1.3(iii)), which the W-117 estimate priced conservatively; no
mechanism change is implied and every bit-identity gate passed. Owned
as a favorable deviation, not an in-band result.

## 4. Deviations / disclosures (all owned)

- **radon_pp G overdelivers the band** (−35.39% vs ≤−30%): favorable;
  mechanism = the vectorized term pass reaching the model .so (above).
- **"3 traversals → 1" implemented as → 2** (gather pass + one
  VECTORIZED term pass): GCC 16 does not auto-vectorize
  arbitrary-index gathers, and B's volatile barrier excludes its
  mul-add regardless; the gather pass is the honest floor. The
  Ir-dominant term pass IS vectorized.
- **Two GCC 16 behaviors engineered around** (§1.3): -fPIC
  alias-versioning refusal (fixed by true `__restrict__`) and whole-TU
  vectorization loss in stanc model TUs (fixed by a `noinline` term
  pass). Neither changes arithmetic; both documented in the header.
- **`vari.hpp` gained 19 lines** (the `vari_no_stack` tag + ctor,
  W-53's exact shape): the one substrate touch, inert for all other
  code; rev-core controls widened accordingly.
- **A build-wiring trap caught and hardened**: with the model `.hpp`
  and `.stan` copied in the same second, bridgestan's make REGENERATED
  the stock loop over the hand-edit — three early .so builds silently
  built stock (caught because the .so md5 was invariant across header
  edits; no wrong-arm number was ever recorded). The setup script now
  sleeps+touches the hpp and asserts the hpp md5 pre/post build plus
  `strings | grep normal_lpdf_gathered`.
- **A callgrind-waiter self-deadlock, diagnosed and fixed live**: the
  waiter's own script name matched the `[c]allgrind` ps grep, so it
  counted ITSELF busy and waited ~5.5 h after the sibling had freed
  the tool (the coordinator's stall probe caught it); the check now
  counts only `valgrind --tool=callgrind` processes. The four arms
  then ran clean, serialized, one at a time.
- The scatter is +0.9/+0.6 Ir/elem (struct-indirect reads) — net
  noise against the forward drops; disclosed.
- The mixed degenerate state (sigma ≤ 0 AND bad index/y/mu) still
  reports Scale first (the hoisted sigma check — W-112.2's disclosed
  class); with sigma VALID all mixed states are strictly stock-ordered.
- Machine: ≤2-core builds, nice 19, `env -u LD_LIBRARY_PATH`,
  `/usr/bin/make` for TUs, callgrind serialized (one at a time),
  sampler cells single-process nice 19 OMP_NUM_THREADS=1.
  WORKLOG.md/comms.md not written by this agent.
- Sibling integrity re-verified post-gates: w116's E′ .sos
  (5b14b5a2…, bac85ddd…), bs_alllayers bridgestan.o (e4b6077b…), and
  w1121's E′22 .sos (fcbc6668…, 4787219a… — the gate-(c) baselines)
  all byte-intact; every bundle file W-118 wrote was rm-firsted to a
  private inode.

## 5. Artifacts

- Branch `gathered-normal-fused` @ `d600b17111` (base `9a07ffa459`):
  `e78ea066c5` (header + vari.hpp + TU) + `d600b17111` (doc fix). DCO +
  AI notes. Not pushed.
- `scratch/w118/`: `test_prim.cpp` + `build_gate_a.sh` + binaries
  (gate a); `setup_gate_b.sh` + `bs_eprime118/` + `model_radon_*_w118/`
  (gate-b wiring with the stanc-regeneration assertions); `grid_w118.py`
  + `runs/{stopgate_pp,stopgate_var,rep0c2_stab}` + `gate_parity_w118.py`
  (gate b); `probe_vec*.cpp` + disassembly extracts (the vectorization
  forensics); `run_callgrind_w118.sh` + `analyze_gate_c.py` +
  `profile_radon_{pp,var}_{base,fused}/` (gate c); `logs/` (all builds,
  gates, grids, TU/controls, vec reports).
