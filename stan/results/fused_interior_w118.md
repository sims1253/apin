# W-118 — the fused single-pass `normal_lpdf_gathered` interior: gates table (filling)

Executed 2026-08-29 per WORKLOG "W-118 PRE-REGISTRATION" (C2 from the
W-117 audit). Base: `9a07ffa459` (the W-112.2 throw-set fix) in worktree
`external/math_dev_w118`, branch `gathered-normal-fused`, commit
`e78ea066c5`. Not pushed. Artifacts under `scratch/w118/`.

STATUS: gates (a), (b), (d) GREEN; gate (c) (callgrind) pending a free
measurement window (sibling W-120 holds the tool; poller armed). This
file is finalized when (c) lands.

## 1. What was implemented (commit e78ea066c5)

The C2 candidate, all four pre-registered components:

1. **Redundant y copy eliminated** (−8 Ir/elem class): `y` is read in
   place (`y.data()` for direct-access Eigen, one-time evaluation
   fallback for exotic expressions); the `value_of(y)` materialization
   is gone. Same for the SoA alpha/beta `val_` arrays (read in place,
   J-sized copies gone).
2. **Loops fused**: ONE vectorizable term pass computes the term, both
   edge partials, the per-element validity mask, and the 0-based index
   store; the shape-specific gather pass (A: clamped gather + range
   bit; B: the volatile-barrier linear predictor assembly + both range
   bits) runs ahead of it. The prereg's literal "one traversal" is
   refined to "gather pass + ONE vectorized term pass": GCC 16 never
   auto-vectorizes arbitrary-index gathers (`a[b[k]]` — verified by
   probe), so the gather cannot live inside the vector loop; shape B's
   volatile mul-add barrier excludes it anyway. Net: 3 traversals → 2
   (A: gather+term; the old code paid y-copy + gather + term).
3. **Per-lane SIMD of the term pass**: the loop body has no horizontal
   ops and no control flow; at model flags it compiles to
   `vsubpd+vmulpd` (F2, unfusable), `vmulpd` (F3), `vfmadd132pd` (F4,
   CONTRACTED — stock's `vfmadd132sd` per lane), `vsubpd` (F5),
   `vmulpd` (F6), `vfmsub132pd` (F7, CONTRACTED — stock's
   `vfmsub132sd` per lane), `vcmpneqpd` NaN/finite checks, with scalar
   epilogues in the matching `sd` forms. Three GCC 16 findings made
   this work (each verified by `-fopt-info` probes + disassembly):
   (i) a per-bit ternary mask and the double+int+uchar store mix block
   vectorization — the mask became a single-bit int store;
   (ii) **`-fPIC` (the .so build) makes the vectorizer refuse to
   version the loop for aliasing** — `__restrict__` on the pass's
   parameters restores it (true: distinct arena allocations);
   (iii) **inside the stanc model TU (one ~31 KB translation unit) GCC
   vectorizes NO double loop of the inlined primitive** — the term
   pass is a standalone `noinline` function, which restores
   vectorization in the model .so itself (packed FMA verified in the
   built .sos: vcmpneqpd ×8, vfmsub132pd ×4).
4. **W-53-class batched no-stack term records**: one arena allocation
   of N `vari_value<double>` records via a new `vari_no_stack` tag
   constructor in `vari.hpp` (W-53's exact tag shape; inert unless
   called; layout/value/zero-adjoint identical to
   `vari_value(x,false)`), NO per-record nochain-stack push, ONE
   `gathered_term_zeroer` (a `vari_base` on the nochain stack) giving
   `set_zero_all_adjoints` the same per-record zeroing — required
   because the accumulator's `sum` chains ACCUMULATE (`+=`) into the
   term adjoints (repeated-grad parity gate-proven).
5. Plus: the dead `d_sigma` store skipped when sigma is data; ONE arena
   revdata struct captured by pointer replaces ~11 by-value closure
   copies; the reverse scatter is byte-for-byte the same statements as
   the W-112.2 header (contraction points unchanged, re-verified by
   disassembly: same `vmulsd`/`vaddsd`/`vfmadd132sd` mix as the
   md5-proven baseline).
6. **Throw-set**: the two W-112.2 checks are preserved and
   STRENGTHENED — stock's per-element conditions (alpha index → beta
   index → y NaN → mu finite) are computed as mask bits in the hot
   passes and re-derived in stock's EXACT order by a cold path on the
   first bad element; mixed-defect states that the two-loop W-112.2
   structure ordered differently (all bounds before any y/mu) are now
   strictly stock-ordered (unit-cased, see gate (a)).

Honest floor (unchanged from the prereg): the reverse scatter stays a
separate serial pass; the sigma-adjoint accumulation stays
store-to-load serial.

## 2. Gates

| gate | evidence | verdict |
|---|---|---|
| (a) bitwise unit, MODEL FLAGS + -O2 | `scratch/w118/test_prim.cpp` (W-112.2's harness + fusion-edge N grid {1..8,15,16,17,31,32,33,100,919,12573} × both shapes × both layouts × sigma var/dbl + J=1 degenerate + 10 strict-order mixed-defect throw cases + repeated-grad batching parity), built with BOTH changed headers first on the include path, `-O3 -mavx2 -mfma` AND `-O2` | **27,821 checks, 0 mismatches at BOTH levels**; all throw cases byte-identical messages incl. `vector[uni] indexing: … index 99 out of range` and y-before-mu/bounds-before-y orderings; disassembly-verified contraction points (§1.3) |
| (b) model draws md5 + parity | E′ = `scratch/w118/bs_eprime118` (cp -al of w1121's eprime22 bundle; BOTH headers at private inodes; bridgestan.o rebuilt in-copy; -mavx2 -mfma; model hpps byte-identical to W-112.2's, md5-asserted PRE and POST build) + `grid_w118.py` (W-109 protocol: w1000 s1000, seeds 20260819+1000·rep+chain, mw50, MM2 ON, sequential, nice 19) + `gate_parity_w118.py` (100 W-103 points vs the W-109 archive .so) | **radon_pp 12/12 == archive** (incl. rep0_c0 `81828b3d…`); **radon_var 12/12 == frozen archive** — rep1_c2 `fc7dbe12…`, rep2_c0 `e6ab04e0…`, rep0_c2 `65d8f98c…` **stable ×3** (grid + 2 reruns); parity **lp 0/100, grad 0/100 exact-zero BOTH models** |
| (c) callgrind, band −15..−30% G | W-29 protocol, one at a time, baseline = W-112.2 E′ .so vs fused E′ .so, both models | **PENDING** (sibling holds the tool; poller armed; script + analyzer ready) |
| (d) TU + controls | `normal_lpdf_gathered_test.cpp` extended (W-112.2's 5 + `FusionEdgeWidths` + `StrictOrderThrowSet` + `BatchedRecordsRepeatedGrad`); normal distribution controls + rev-core controls (vari.hpp blast radius) | TU **8/8 PASSED**; `prim/prob/normal_test` 4/4, `rev/prob/normal_log_test` 1/1, `mix/prob/normal_test` 1/1, `rev/core/set_zero_all_adjoints_nested_test` 1/1, `nested_rev_autodiff_test` 4/4, `callback_vari_test` 5/5, `build_vari_array_test` 1/1 — all PASSED |

## 3. Gate (c) — PENDING

Placeholder; filled when the callgrind window opens.

## 4. Deviations / disclosures (owned; extending as gates complete)

- **The prereg's "3 traversals → 1 forward" is implemented as
  "→ 2"** (gather pass + one VECTORIZED term pass): GCC 16 does not
  auto-vectorize arbitrary-index gathers, and shape B's volatile
  barrier excludes its mul-add from any vector loop regardless. The
  gather pass is the honest floor; the term pass (the Ir-dominant one)
  IS vectorized. Disclosed as the C2 mechanism refinement.
- **Two GCC 16 behaviors had to be engineered around** (probe-verified,
  §1.3): -fPIC alias-versioning refusal (fixed by true `__restrict__`)
  and whole-TU vectorization loss in stanc model TUs (fixed by a
  `noinline` term-pass function). Neither changes arithmetic; both are
  documented in the header.
- **`vari.hpp` gained 19 lines** (the `vari_no_stack` tag + ctor,
  W-53's exact shape): the one substrate touch, inert for all other
  code; the rev-core control set was widened accordingly (gate (d)).
- **A build-wiring trap caught and hardened**: with the model `.hpp`
  and `.stan` copied in the same second, bridgestan's make regenerated
  the STOCK loop over the hand-edit (three W-118 .so builds silently
  built stock — caught because the .so md5 was invariant across header
  edits); the setup script now sleeps+touches the hpp and ASSERTS the
  hpp md5 pre/post build plus `strings | grep normal_lpdf_gathered`.
  The trap explains why no wrong-arm numbers were recorded.
- The mixed degenerate state (sigma ≤ 0 AND bad index/y/mu) still
  reports Scale first (the hoisted sigma check — the W-112.2 disclosed
  class); with sigma VALID all mixed states are now strictly
  stock-ordered.
- Machine: ≤2-core builds, nice 19, `env -u LD_LIBRARY_PATH`,
  `/usr/bin/make` for TUs, callgrind serialized behind the sibling
  (armed waiter, fires into any ≥20 s gap), sampler cells single-process
  nice 19 OMP_NUM_THREADS=1. WORKLOG.md/comms.md not written by this
  agent.
- Sibling integrity re-verified post-gates: w116's E′ .sos
  (5b14b5a2…, bac85ddd…), bs_alllayers bridgestan.o (e4b6077b…), and
  w1121's E′22 .sos (fcbc6668…, 4787219a… — the gate-(c) baselines)
  all byte-intact; every bundle file W-118 wrote was rm-firsted to a
  private inode.

## 5. Artifacts

- Branch `gathered-normal-fused` @ `e78ea066c5` (base `9a07ffa459`):
  the header, the vari.hpp tag, the extended TU. DCO + AI notes. Not
  pushed.
- `scratch/w118/`: `test_prim.cpp` + `build_gate_a.sh` + both binaries
  (gate a), `setup_gate_b.sh` + `bs_eprime118/` + `model_radon_*_w118/`
  (gate b wiring), `grid_w118.py` + `runs/` (stop-gates + rep0_c2
  stability), `gate_parity_w118.py`, `probe_vec*.cpp` (the
  vectorization forensics), `run_callgrind_w118.sh` +
  `analyze_gate_c.py` + `profile_*/` (gate c), `logs/`.
