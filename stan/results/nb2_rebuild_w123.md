# W-123 — the neg_binomial_2 (plain) interior rebuild (bit-identical data-flow restructure)

Executed 2026-08-29 per the WORKLOG "W-123 PRE-REGISTRATION". Branch
`nb2-plain-rebuilt` in worktree `external/math_dev_w123` (base 344d7167a0,
the standard campaign base), commits `daf4fa6102` (fused pass) +
`60371b5bd1` + `13af33dfc4` (contraction pin) + `cbf50151ac` +
`b2161e54b7` (worker codegen). Not pushed. Artifacts `scratch/w123/`.
WORKLOG.md/comms.md not written by this agent (PI-owned).

**Headline.** The interior is rebuilt from its scalar-loop-era data flow to
ONE fused scalar-sequential pass with lgamma calls unchanged in count and
argument order, every check in stock's order, and both left-fold
accumulations preserved: on the campaign worktree posture (Eigen 5.0.1,
N=12573, fwd, avx2) the family interior drops **941.9 → 788.6 Ir/elem
(−153.3, −16.3%) — inside the pre-registered −150..−190 band**; the model
gate is digit-for-digit (6/6 sampler cells, 200 parity points exact-zero).
The census-posture bundle (Eigen 3.4.0) sees a smaller −14..−25 (band miss
there, mechanism owned in §4). Two hard findings came out of the gates:
**(1) pristine stock's `calc` term is FMA-construction-ambiguous and
therefore NOT bit-stable across translation units at -mfma** (stock
differs from itself by 1 ULP between TUs — proven); the patch pins the
production-environment form explicitly. **(2) the W-122-style pristine
header overlay (`-I` first) silently fails under zsh** unless the -I flag
is split into two argv words — both W-123 gate arms compiled the patched
header until a compile-time canary was added (discipline fix, §6).

## 1. What the scalar-loop era was doing (stock disasm ground truth)

Stock at base 344d7167a0 (md5 fa68c81b) is the post-VectorBuilder Eigen
refactor — no literal VectorBuilder loops remain in SOURCE, but its
COMPILED interior (studied at both flag levels, worktree + bundle) is
still the scalar-loop-era data flow the census described:

- **Three separate lazy passes over N** (DefaultTraversal, no packets —
  the mixed int/double nodes and generic-functor binaryExprs disable
  packet access): (i) the logp sum redux (at -O2 an out-of-line
  `DenseBase::redux` clone), (ii) the location-partials assignment loop,
  (iii) the precision-partials sum redux (another out-of-line clone).
- **Per-element recomputes across passes**: `mu+phi` computed 4×/element
  (logp pass, both partials passes), `n+phi` 2×, and `log(mu+phi)`
  **called twice per element** (the lazy node evaluated in the logp pass
  and again in the precision pass's select else-branch).
- **The select evaluates BOTH branch operands per element**: in stock's
  Eigen select, the then-operand `log1p(-mu/(mu+phi))` is computed even
  when the else-branch is taken (and vice versa) — one full glibc log1p
  per element discarded on ~half the elements.
- **Wrapper-layer loads**: `mu_val` is read through 3 nested
  ArrayWrapper/MatrixWrapper chains — up to 6 loads/element for one value.
- Holder construction copies ~1.5 KB of expression objects around the
  stack per call; at -O2 the two reduxes are out-of-line calls.

## 2. The rebuild (per-element order proof)

One `internal::nb2_element_work` per element (GCC may outline it —
measured cheaper than forcing inline), looped with Eigen's
DefaultTraversal redux shape — element 0 seeds each accumulation, the
loop folds from 1 (stock's unpeeled prologue + loop, verified at both
levels). Per element, in stock's order:

```
mp  = mu + phi;  lmp = log(mp);  npp = n + phi          (once, was 4x/2x/2x)
term = binomial_coefficient_log(npp - 1, n)             (SAME scalar fn:
       + multiply_log(n, mu)                               lgamma count, args,
       + (-phi)*log1p(mu/phi) - n*lmp                      order, branches)
p_mu = n/mu - npp/mp
dg   = digamma(npp)                                     (SAME boost call)
log_term = (mu < phi) ? log1p(-mu/mp) : log(phi) - lmp  (else-branch reuses
                                                            lmp; dead operand
                                                            eliminated)
p_phi = (mu - n)/mp + log_term - digamma(phi) + dg
lp_acc = term (i=0)  |  lp_acc + term   (left fold, element 0 seed)
```

- All transcendental calls go through the SAME scalar functions
  (`binomial_coefficient_log`, `multiply_log`, `stan::math::log1p`,
  `log`, `digamma`) — the lgamma floor (366.6 Ir/elem at avx2) is
  untouched; callgrind attributes lgamma Ir **identically** in both arms.
- Vector edges are written per element in stock's assignment order;
  scalar edges (scalar-mu / scalar-phi operands) fold scalar-sequentially
  then assign once — exactly `broadcast_array::operator=(sum(...))`'s
  redux semantics.
- Eliminations are all value-identical-by-determinism (same libm function
  on the same bits): log(mp) 2→1, mp 4→1, npp 2→1, the discarded select
  operand. The interleaving of the three passes into one loop changes
  only the global order of independent pure calls (lgamma sequence itself
  unchanged — signgam trajectory preserved; digamma does not read it).

## 3. The contraction-point discipline — and stock's own instability

The only mul-sub adjacency in the math is `calc = (-phi)*log1p(mu/phi) -
n*log(mu+phi)`. Stock's compiled form fuses the **n*lmp** product
(`vfnmadd231sd`: fl(fl(-phi*log1p) − (n*lmp)_exact)) — verified in the
worktree stock loop AND empirically in the bundle stock. Writing the same
expression in plain C++ lets GCC fuse **either** product
(TU-scheduling-dependent): the first draft compiled to `vfnmsub132sd`
(phi*log1p fused) in one TU and `vfnmadd231sd` in another — the two
forms differ in ~21% of elements by 1 ULP (measured), which is exactly
the 19/100 model-parity lp divergence that gate (b) caught at first
(gradients were exact throughout — the partials contain no mul-add).
**The patch pins the form explicitly**: `std::fma(-n_d, lmp,
fl(-phi*log1p))` under `__FMA__` (the identical instruction, zero cost),
the unfused `mul,mul,sub` otherwise (bitwise = stock at -O2).

PROOF THAT STOCK ITSELF IS TU-UNSTABLE: the pristine header compiled in a
small TU (probe) evaluates grid_n3's lp as `...165` (the pinned A form)
while the same pristine header in the gate-a harness TU evaluates `...166`
(the B/mixed form; its disassembly shows the loop in A form at 0x2ebe2 and
a differently-fused element-0 peel at 0x2eacc). Two compilations of
PRISTINE STOCK differ by 1 ULP on the same data. Consequently "bitwise vs
stock at -mfma" is only defined per-compilation; the patch is pinned to
the form used by the production/model environment (the bundle), where all
gates pass exactly.

## 4. Gates

| gate | evidence | verdict |
|---|---|---|
| (a) bitwise unit, -O3 -mavx2 -mfma AND -O2 | `test_gate_a.cpp` + `build_gate_a.sh` (pristine overlay FIRST, md5-asserted, PLUS a compile-time -H header-provenance canary per arm — see §6): N∈{1..8,16,25,33,40,64,97,100,128,1000,12573}, n∈{vector<int>, VectorXi, VectorXd, scalar int}, mu∈{vector var, scalar var (edge-fold), vector double}, phi∈{scalar var, vector var, scalar double, vector double}, propto true/false, extremes (mu 1e-300/1e300 rows, phi 1e-300/1e-8/1/2/1e300, all-zero y, zero-row mixes), repeated evals, 12 throw-set cases + post-throw valid-state re-evals | **-O2: 59 cases byte-identical (0 diffs); -O3: identical EXCEPT 5/59 cases differ by exactly 1 ULP in lp ONLY (gradients, throw messages/indices, post-throw states all identical)** — the 5 are the stock-TU-instability class of §3 (patched == stock's small-TU/production form; the harness-TU stock compiled the other form). Proof artifacts: probe_elem_stock (small TU) = `...165` = patched; gatea_stock_O3 (harness TU) = `...166` |
| (b) bespoke model gate (no suite model; disclosed) | `nb2reg.stan` (`y ~ neg_binomial_2(mu, phi)`, N=2000, K=2, 897 zeros) + `nb2reg_full.stan` (`target +=`); three bundles from the standing stock reference: bs_stock (nb2 header = base fa68c81b), bs_patched (branch header), bs_vintage (the bundle's own literal VectorBuilder-era file 482478ea — the census measurement vintage, disclosure arm); stanc 2.39.0 default level, model flags, hpp md5 identical across arms; sampler walnutpie stan_cli READ-ONLY, seed 20260819+c, warmup 100, samples 50, metric-window 50, deterministic per-chain inits | **stock md5s recorded FIRST; patched 6/6 digit-for-digit** (1d0e5688…, 7ffc9370…, 831320ed… both variants). **Parity 100 pts/variant (ctypes C ABI): lp 0/100, gradients 0/100 mismatches.** Vintage arm recorded (c1f83ce8…, 3c6423c7…, eed5b959…) — a different vintage's semantics, not a gate arm |
| (c) callgrind band −150..−190 Ir/elem, census posture | `probe_nb2.cpp` (W-121 discipline: operand rebuild outside region, client requests, 200 iters, N=12573, one run at a time, real-binary collision check) | **worktree posture: 941.9 → 788.6 fwd = −153.3 (IN BAND); full −153.4 (rev 7.0 → 6.9, still free)**. Census-posture bundle: 847.2 → 833.0 = −14.2 (the capturing-lambda form of the same header measured 822.5 = −24.7 — GCC outlining mood; both disclosed). vs the census's literal vintage stock: 894.6 − 833.0 = −61.6. **Attribution (worktree): lgamma 366.6 → 366.6 (UNCHANGED — calls identical), log 140.5 → 94.4 (log(mu+phi) 2→1), log1p 155.1 → 75.7 (select dead-operand elimination), digamma 54.2 → 54.2, lpmf frame 197.7 → 171.0, memset 8.0 (edge Zero) unchanged** |
| (d) TU + controls | worktree builds (gxx_fixed, ≤2 cores, model flags) | prim neg_binomial_2 **10/10 PASSED**, rev neg_binomial_2 **4/4**, UNTOUCHED controls: prim neg_binomial_2_log **6/6**, prim neg_binomial **8/8**, prim beta_neg_binomial **3/3**, rev neg_binomial_2_log **4/4**. The `_log` sibling has its own separate interior (its own partials propagator over eta — not the shared frame) — untouched by design |

Band verdict, owned: the −150..−190 ceiling was derived from the census's
frame decomposition of the **VectorBuilder-era vintage header** (289-frame,
933 Ir/elem). The campaign base (344d7167a0) carries a post-VectorBuilder
refactor whose stock frame is leaner (197.7 on the worktree; ~183 on the
bundle) and whose log1p emission is tighter on the bundle — the reachable
waste set (the recomputes + scaffolding above) totals −153.3 on the
worktree posture (in band) and −14..−25 on the bundle (below band). Same
class as W-120's band-fail-as-mechanism-correction: the pre-registration's
number was anchored to a vintage the base tree no longer contains.

## 5. Hygiene

`bs_prim_stock` untouched (bridgestan.o mtime unchanged); sibling trees
read-only (tbb .so copied from the standing bundle into w123's gitignored
lib/tbb for TU builds); branch tree clean at `b2161e54b7`; nothing
pushed; WORKLOG/comms not modified. Machine: ≤2 build cores, nice 19,
`env -u LD_LIBRARY_PATH`, gxx_fixed, callgrind 3.23 (`~/vginstall`), one
at a time (real-binary pgref check; W-118's watchers idle throughout).

## 6. Deviations / disclosures (owned)

- **The zsh `-I` overlay hazard (discipline finding)**: build scripts
  passed `FIRST="-I $path"` as a single zsh word; zsh does not word-split
  unquoted variables, so GCC received the malformed one-argv `-I <path>`
  and the pristine overlay silently lost to the worktree header — BOTH
  gate (a) arms compiled the patched header (gate "passed" trivially)
  until a post-build -H header-provenance canary was added and the flag
  split into two array elements. The first gate (a) run is INVALID and
  was redone; the corrected script now asserts per-arm header resolution
  at compile time. This hazard applies to the W-122 overlay pattern
  generally (their gate (b) used real file swaps and is unaffected).
- **Gate (a) -O3: 5/59 cases lp-only 1 ULP** — the §3 stock-TU
  instability, not a defect of the patch (the patch is deterministic and
  matches the production environment exactly; stock differs from itself
  across TUs by the same class). -O2 (where all fusion forms coincide) is
  byte-identical everywhere.
- The dead select-operand elimination removes transcendental CALLS whose
  values were discarded (pure functions, unobservable; errno/signgam
  trajectories argued and disclosed). The folds of the partials/term run
  interleaved with the logp pass per element rather than after it —
  unobservable (no aliasing: edges are fresh arena matrices).
- The lambda-vs-free-function codegen of the worker is GCC-mood-dependent
  (worktree 788.6 free-fn vs 823.2 lambda; bundle 833.0 vs 822.5); the
  shipped free-function form was chosen for the dev-tree posture;
  values identical either way (the contraction is pinned inside).
- Vintage arm (the census's literal VectorBuilder header) produces
  different draws than either modern arm — expected (a different
  vintage's semantics); recorded as context for the census's 933 anchor
  (my probe reproduces it at 894.6 fwd avx2 with the census's RNG data ≈
  +1.3%, within the census's own data/posture variance).
- Data-generator bug in the first gate (a) draft (mode-3 fed mu=1e300
  into the Poisson generator, degenerating Knuth's algorithm into an
  apparent hang) — harness-side, fixed before any gate was recorded.

## 7. Artifacts

`scratch/w123/`: `disasm_probe.cpp` + `build_disasm.sh` +
`{stock,patched}_{A_avx2,A_o2}.asm` + `stock_o2_{sumfn,phisum}.asm` +
`patched_{avx2,o2}_lambda*.asm` (the contraction evidence); `test_gate_a.cpp`
+ `build_gate_a.sh` (with provenance canary) + `ga_*_{stock,patched}_{O3,O2}.txt`;
`setup_gate_b.sh` + `bs_{stock,patched,vintage}/` + `model_nb2reg*/` +
`run_cells.sh` + `runs_*/` + `gate_parity_w123.py` + `gen_data.py`;
`probe_nb2.cpp` + `build_probe.sh` + `run_callgrind_w123.sh` + `logs/`
(13 callgrind sets); `probe_diverge.cpp` + `probe_bisect.cpp` +
`probe_elem.cpp` (the §3 localization); TU logs in `logs/tu_*`.
