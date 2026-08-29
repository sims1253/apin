# W-107 — log1p-kernel multi-accumulator unroll: gates (a)/(b)/(c)/(d-wall) PASS, (d-callgrind) FAIL at +1.50% Ir — a WALL win that trades +1.5% instructions for −3.5..−7.4% model wall

Executed 2026-08-28 per WORKLOG "W-107 PRE-REGISTRATION". Deliverable:
`scratch/w107/bernoulli_kernel_ilp.patch` (+306/−0, pure insertion, pristine
develop base md5 `2954671f…`, apply-checked; result md5 `fa423fb1…`).
The W-103 artifact `scratch/w103/bernoulli_logit_lpmf_targetclones.patch` is
UNTOUCHED (the W-107 patch is an independent variant, not an edit of it).

## 1. Dependency map of the W-103 island (the pre-registered question)

Evidence: `scratch/w107/codegen_probe.s` / `fwd_avx2_orig.s` (the verbatim
W-46/W-103 island body, `harness/w46/kernel_block.cpp`, compiled -O3).

**GCC does NOT unroll the island loop** — one 4-lane block per iteration,
~143 instructions, loop `.L13`. Per block there is essentially ONE dominant
dependent chain:

| chain | ops (att coutes from the loop body) | serial latency |
|---|---|---|
| `w46_exp_negabs` | `vorpd→vmaxpd→vfmadd→vroundpd→2×vfnmadd→vmulpd(z2)→2×fma(px)→vmulpd→vdivpd→vfmadd→4 chained vmulpd` | ~60–65 cyc |
| `w46_log1p_poly` Clenshaw | 16 × (`vfmadd231pd` 4 cyc → `vsubpd` 3 cyc), fed by `w` | **~112–118 cyc** |
| second `vdivpd` (q = w/(1+w)) | off the critical path, ~4.5 cyc divider occupancy | — |
| scalar accumulator | `vmovsd`→`-8(%rsp)` / `vaddsd` reload (loop-carried through memory) | 4 vaddsd |

Critical path ≈ 65 + 118 ≈ **178 cycles per 4-lane block**, against a pipe-work
floor of ≈ 27–30 cycles/block (≈80 FP-pipe ops at ~3/cyc on Zen 3's 2 FMA +
1 FADD pipes, plus 2 `vdivpd` ≈ 9 cyc of divider time that overlaps). Island
utilization ≈ **17–20% of the two 256-bit FMA ports** — the bottleneck is
LATENCY of the single Chebyshev recurrence, exactly the pre-registration's
hypothesis. Measured `fwd_avx2` = 7.44 ns/elem (≈33 cyc/elem at ~4.4 GHz
= 132 cyc/block) is consistent with the chain estimate minus partial overlap.

## 2. The unroll (design + why it is bit-identical)

`fwd_avx2_unroll<W>`: W ∈ {2,3,4} independent 4-lane blocks per group,
**separate accumulators**, phased structure (exp for all W blocks → poly for
all W → value/partial finish for all W) so GCC's scheduler can interleave the
W independent Clenshaw chains. Two live-set flavors:

- `u*`: phase 1 keeps {px, sg, w, y, nw, gt, lt} per block (7 ymm × W);
- `lean*`: phase 1 keeps only {px, sg, w, y} (4 × W) and recomputes
  `nw/gt/lt` in phase 3 from px/w (3 cheap ops/block, same values, same
  order) → fewer spills (464 → 453 instr per 3-block group; 151 vs 143 instr
  per 4-lane block vs u1's 143, lean4 = 154.8).

**Bit-identity is a designed property, not luck**: every per-lane vector op
is the same instruction on the same lane, and the per-block horizontal
reduction `(t0+t1)+(t2+t3)` is accumulated into the same scalar chain **in
block order**, so `fwd_avx2_unroll<3>` returns the same double and writes the
same partials as W-103's `fwd_avx2` for EVERY n (leftover 4-lane blocks take
the W-103 loop verbatim, then the scalar tail). Proven in
`scratch/w107/bench_ilp.cpp`: 0 differing bits in partials on 1,804,800
elements × 4 real x-sets (with alternating sg = −1 lanes), sums bit-identical,
and 25 odd/remainder sizes (1…4096, incl. 19201) all bit-identical, for all 6
variants.

## 3. Gate (c) — microbench (the kill-switch): PASS at 1.408x

`scratch/w107/bench_ilp.cpp` (u1 = the verbatim W-103 island as control),
cache-resident 19,200-element regime (the hier_2pl working set), 11 reps × 2
inner × all passes, interleaved, medians; 2 cores, nice 19:

| variant | lanes/group | draws | cloud | random | pfinit | **geomean** |
|---|---|---|---|---|---|---|
| u1 (W-103) | 4 | 7.444 ns/elem | 7.377 | 7.408 | 7.439 | 1.000x |
| u2 | 8 | 1.227x | 1.216x | 1.237x | 1.221x | 1.229x |
| u3 | 12 | 1.395x | 1.384x | 1.403x | 1.394x | 1.394x |
| u4 | 16 | 1.367x | 1.355x | 1.378x | 1.364x | 1.366x |
| lean2 | 8 | 1.227x | 1.216x | 1.237x | 1.221x | 1.225x |
| lean3 | 12 | 1.414x | 1.393x | 1.421x | 1.406x | **1.408x** |
| lean4 | 16 | 1.414x | 1.409x | 1.425x | 1.407x | 1.414x |

Gate >= 1.15x → **PASS** (4x above the bar). W=3 lean ships: wall within
noise of lean4 with the fewest instructions per lane (u4/lean4 lose to
register pressure: ~30 ymm spill stores + 33 spill loads per group at W=4;
u2 leaves ports idle). The 1.41x — not the theoretical 3.5x — is the
achievable point: 2 FMAs/cycle is shared with the adds/subs/blends and the
2 `vdivpd` per block's divider occupancy.

## 4. Gates (a) ulp and (b) dispatch: PASS, values = the W-46/W-103 records

`scratch/w107/test_kernel_ilp.cpp` (W-46 `harness/w46/test_kernel.cpp`
re-run against the W-107 header) and `scratch/w107/dispatch_check_ilp.cpp`
(W-103 dispatch check + a NEW 16-lane unrolled-path check):

- **(a)** `val_max_ulp=3.000` on all 4 real sets, `p_max_rel=4.409e-16`,
  `sum_rel=0.000e+00` (EXACT — the unrolled island reproduces the W-103 sum
  bit-for-bit). Island 5.46 ns/elem vs scalar 23.61 (4.32x); W-46 recorded
  8.26 ns/elem for the same grid (1.51x at the harness level). The "UNIT
  prim 8 ulp" line is the W-46-disclosed round-trip artifact; the
  exact-argument measurement is (b).
- **(b)** runtime dispatch, n=1, 2,500,001 pts: **max 1.000 ulp vs glibc**
  (= W-103). 4-lane batches (the unchanged remainder loop): 4.580e-16 value
  sum, 3.388e-16 partials (= W-103). NEW 16-lane batches (the unrolled group
  path): 6.355e-16 value sum (16-term reference sum, grows with n as
  expected), partials 3.388e-16 (identical — per-lane bits unchanged).
- cpuid bits set (`avx2`=1024, `fma`=16384); `fwd_avx2_unroll<3>` present in
  the model `.so` (`nm`), island compiled in.

## 5. Model-level control: BIT-IDENTICAL lp and gradient

`scratch/w107/parity_bits_w107.py`: hier_2pl `log_density_gradient` over 50
deterministic points, W-103 kernel arm `.so` vs W-107 unrolled `.so` —
**lp + gradient BIT-IDENTICAL** (hex-compare of all 50 × (1+669) doubles).
This is strictly stronger than the statistical parity gates of W-103
(1.473e-16 rel-L2): the unroll changes no output bit anywhere in the model.

## 6. Gate (d) — callgrind: FAIL as pre-registered (+1.50% Ir); wall: PASS

`scratch/w107/run_callgrind_w107.sh` (W-29/W-103 protocol verbatim: warmup
100 samples 50, seed 20260819, pf init rep0/chain_0, --metric-window 50,
valgrind 3.23 ~/vginstall, OMP_NUM_THREADS=1, one job):

| metric | W-103 kernel arm (ref) | W-107 unrolled arm | delta |
|---|---|---|---|
| total Ir | 21,547,099,162 | 21,865,855,215 | +1.48% |
| grad calls | 4493 (3737+756) | 4493 (IDENTICAL trajectory) | 0 |
| **Ir / grad** | **4,795,704** | **4,866,649** | **+1.50%** (gate was <= −0.5% → FAIL) |
| island Ir | 2,994,415,368 (13.90%) `fwd_avx2` | 3,320,450,896 (15.19%) `fwd_avx2_unroll<3>` | +10.9% |
| glibc `__log1p` | ~0 | ~0 | — |

**Mechanism (why this sub-gate could not pass)**: callgrind counts RETIRED
INSTRUCTIONS, and a latency-hiding unroll ADDS instructions — spills
(~30 ymm stores + 33 loads per group), recomputed blend masks, and
per-group loop bookkeeping — while retiring them FASTER. The +10.9% island
Ir × the 13.9% island share ≈ +1.5% G, matching the measurement. The
pre-registration's "<= −0.5% further Ir" expectation was written under an
instruction-savings mental model and is structurally unmeetable by ANY
multi-accumulator unroll of this kernel; the honest statement is that W-107
is invisible-to-contrary on the Ir ledger.

`scratch/w107/gate_timing_w107.py` (W-103 protocol: 5 interleaved rounds ×
one subprocess per arm, 50 deterministic points × 3 internal reps,
taskset -c 0-1, nice 19; sibling-agent compile load present — W-59
disclosure: absolute us inflated, the ratio is the measurement):

| pass | k103 median | kilp median | ratio | gate <= 0.99 |
|---|---|---|---|---|
| 1 | 893.2 us/call | 827.3 us/call | **0.9262 (−7.38%)** | PASS |
| 2 | 877.1 us/call | 846.6 us/call | **0.9652 (−3.48%)** | PASS |

Consistency check: at island-local 1.408x, a −7.4% model wall implies the
island is ≈ **28% of the kernel arm's wall** — versus its 13.9% Ir share.
That 2x gap IS the latency-boundness measured in section 1, and it is what
the unroll monetizes (the extra instructions ride ports that were idle).

## 7. Verdict and posture

- Gates (a) ulp, (b) dispatch, (c) microbench (1.408x), (d-wall) — **PASS**;
  bit-identity at kernel AND model level.
- Gate (d-callgrind Ir <= −0.5%) — **FAIL at +1.50%**, by mechanism not by
  accident (section 6).
- Net: on hier_2pl, W-107 takes the W-103 kernel arm's wall −13.9% further
  by −3.5..−7.4% (two passes), at the price of +1.5% retired instructions.
  The pre-registration's own "HONEST CEILING: 1-3% G total" was framed on
  the wrong metric for this transformation; the honest ceiling on WALL is
  what was delivered.
- NOT promoted unilaterally: whether a +1.5% Ir / −5% (median) wall trade is
  wanted is a metric-choice decision (the G ledger is the campaign's
  internal proxy; wall is the user-facing quantity). The patch variant is
  recorded, apply-checked, and ready either way. Composes with the W-105/
  W-106 uniform-avx2 layer (orthogonal: ISA flags vs loop structure).

## 8. Risks/disclosures

- Bug-compat sign partials (x>20 → −w without signs) replicated untouched
  (bit-identity with the W-103 kernel arm is the proof).
- W=3 hard-coded: hier_2pl's N=19,200 = 3·4·1600 → the unrolled group loop
  covers the whole array; other sizes take the bit-identical remainder path.
- The unroll is Zen-3-tuned (2 FMA ports, 4-cyc FMA latency); on wider
  machines lean4 was the marginally better flavor (1.414x vs 1.408x) — a
  one-line `<3>` → `<4>` change, re-gated by the same harnesses.
- `external/math_soa` pristine (`2954671f…`); `math_dev_soa` untouched
  (`a43e868` clean; its one untracked file
  `stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp` pre-dates W-107);
  `scratch/w103/*` untouched (`bs_w103_kernel` header re-verified
  `2c61408a…` after the `cp -al`); `bs_w53` untouched.
- cpplint: the patched file's only >80-col line is the SAME inherited
  `w46_exp_negabs` return W-103 disclosed (kept byte-identical on purpose);
  the W-107 additions add zero new findings.

## 9. Artifacts

`scratch/w107/`: `bernoulli_kernel_ilp.patch` (deliverable) +
`bernoulli_logit_lpmf.hpp.ilp` + `make_ilp_header.py` (deterministic
assert-anchored splice from the validated bodies), `kernel_ilp.hpp` (all 6
variants) + `kernel_block_orig.cpp` (u1 control) + `bench_ilp.cpp`/
`bench_ilp.out`/`bench_ilp_v2.out` (gate c), `test_kernel_ilp.cpp/.out`
(gate a), `dispatch_check_ilp.cpp/.out` (gate b), `codegen_probe*.s` +
`fwd_avx2_orig.s`/`fwd_avx2_u3.s`/`cg_count.s` (dependency map),
`bs_kilp/` (kernel+unroll bundle, private-inode header),
`model_hier_2pl_kilp/` + `build_model_w107.py/.log`,
`parity_bits_w107.py/.out` (model bit-identity), `run_callgrind_w107.sh` +
`callgrind_w107.out` + `profile/kernel_ilp/` (gate d-Ir),
`gate_timing_w107.py` + `.out` + `_pass2.out` (gate d-wall).
