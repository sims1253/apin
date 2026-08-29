# W-92 — Clang toolchain verification of the SoA patch (math#5): stock-clang vs soa-clang on hier_2pl — ALL GATES PASS; Ir win holds (−16.3%T / −17.4%G vs GCC's −17.8%/−19.1%); draws md5 fe7c57… IDENTICAL across BOTH compilers

Date: 2026-08-27 (session start 01:4x). Pre-registration: WORKLOG.md
"W-92 PRE-REGISTRATION" (scope, gates, expectation −12..−19%G).
Inputs: W-53 slice + W-57/W-58 batch 1/2 + W-59 fused loop (bundle math
state = batches 0+1+2+fused, scratch/w53/bs_w53); GCC reference numbers
W-59 close-out. Machine policy in force: rogue foreign grids at load
~12–13 = uncontrollable background; builds nice 19 (two -j1 compiles),
runs single at nice 19, count-based metrics load-safe, wall ratios-only
+ FLAG; `env -u LD_LIBRARY_PATH` everywhere (MANDATORY here: the ZCode
AppImage mounts pollute LD_LIBRARY_PATH and BREAK the stan/.venv python
— first symptom `No module named 'encodings'`); OMP_NUM_THREADS=1.

**Headline (the PR-risk answer).** The SoA win HOLDS under clang. Two
fresh clang-22.1.8 builds of hier_2pl (same stanc3 binary, same flags
from the bundle makefile, only CXX changed) reproduce every gate:
exact-zero parity (0/100 values, 0/100 grads), sampler draws md5
IDENTICAL — and, beyond the pre-registered requirement, the clang arms
reproduce the GCC arms' md5 fe7c57c99a7a6530ce2dcc408d6e9c65 EXACTLY,
i.e. **cross-compiler bit-identity end-to-end**. Instruction counts:
**T −16.31% / G −17.44%** (GCC same-state refs: −17.82%/−19.06%;
W-58 batch-012 refs: −15.9%/−17.1%) — inside the pre-registered
−12..−19%G band, ~1.5pp below GCC's fused number, with the gap fully
attributed to clang's reverse-callback codegen (NOT the SoA substrate;
see §4). In-sampler wall: warmup −11.4% / sampling −6.4% (3 interleaved
rounds, ratios only, load FLAG — foreign load receded to ~5 mid-run).

## 1. Build (exact commands; per-variant scratch dirs, cache rule)

Toolchain: clang 22.1.8 (/usr/sbin/clang++, defaults to libstdc++ —
probe linked /usr/lib/libstdc++.so.6), prebuilt gcc TBB/sundials
archives linked unmodified (same C++ ABI). The bundle Makefile takes
the compiler from `CXX` (env overrides the `origin default` g++ in
math's make/compiler_flags:35-43); flags themselves are untouched
(clang++ -std=c++17 -O3 -fPIC -fvisibility=hidden …, verbatim from
the makefile — nothing invented).

    # bundle copies (hardlinks; rm+rebuild gives each a clang bridgestan.o;
    # originals untouched: bs_w53/src/bridgestan.o still the Aug-24 gcc one)
    cd scratch/w92
    cp -al ~/.bridgestan/bridgestan-2.9.0 bs_stock_clang
    cp -al ../w53/bs_w53                      bs_soa_clang
    grep -c make_nochain bs_soa_clang/stan/lib/stan_math/stan/math/rev/core/make_nochain_vari_array.hpp   # 1 (patch present; W-59 fused loop + W-58 LinearAccessBit fallback verified in file)
    (cd bs_stock_clang && rm src/bridgestan.o && env -u LD_LIBRARY_PATH nice -n 19 make CXX=clang++ src/bridgestan.o)
    (cd bs_soa_clang   && rm src/bridgestan.o && env -u LD_LIBRARY_PATH nice -n 19 make CXX=clang++ src/bridgestan.o)

    # model builds (same invocation shape as bridgestan.compile_model:
    # make STANCFLAGS=--include-paths=. <abs .so> run in the bundle dir)
    mkdir -p model_hier_2pl_stock_clang model_hier_2pl_soa_clang
    cp ../w53/model_hier_2pl_stock/hier_2pl.stan model_hier_2pl_stock_clang/
    cp ../w53/model_hier_2pl_stock/hier_2pl.stan model_hier_2pl_soa_clang/   # .stan identical across arms (diff-verified)
    (cd bs_stock_clang && env -u LD_LIBRARY_PATH CXX=clang++ nice -n 19 \
       make STANCFLAGS=--include-paths=. $PWD/../model_hier_2pl_stock_clang/hier_2pl_model.so)
    (cd bs_soa_clang   && env -u LD_LIBRARY_PATH CXX=clang++ nice -n 19 \
       make STANCFLAGS=--include-paths=. $PWD/../model_hier_2pl_soa_clang/hier_2pl_model.so)

Both compiles + links clean (only the bundle's known benign warnings:
`-lpthread/-ltbb unused` during .o compile, `msvc::forceinline`
ignored). stanc3 binary identical across both bundles (md5
3ce8bce9…) ⇒ identical generated hpp. Loads verified one-.so-per-
process: both arms `hier_2pl_model`, D=669.

Note: two -j1 model compiles ran concurrently = 2 cores peak, nice 19,
per board policy.

## 2. Gate (a): exact-zero parity, stock-clang vs soa-clang — PASS

scratch/w92/gate_parity_clang.py (adapted from w53's; W-27 point
scheme verbatim: rng 20260822, 100 pts, scale 0.5; ref = STOCK-CLANG
arm per pre-registration):

    hier_2pl PASS: value_mismatch=0/100 grad_mismatch=0/100 (exact-zero gate, clang-vs-clang)

BONUS cross-compiler REPORT comparison (pre-registered as report-only,
"differences expected/allowed"): the SAME 100 points through the GCC
stock .so (w53/model_hier_2pl_stock) are BIT-IDENTICAL to stock-clang
— 0/100 value mismatches, 0/100 grad mismatches, max abs diff 0.0 on
values and on every gradient component. At -O3 without fast-math,
neither compiler reorders FP on this model's expression templates.
This predicts (and §3 confirms) that the draws md5 matches across
compilers too.

## 3. Gate (b): sampler draws md5 — PASS (+cross-compiler bonus)

W-29 protocol verbatim (walnutpie build_w36exp/examples/stan_cli,
READ-ONLY; warmup 100, samples 50, seed 20260819, pf init,
--metric-window 50), scratch/w92/gate_draws.sh:

    fe7c57c99a7a6530ce2dcc408d6e9c65  draws_stock_clang.csv
    fe7c57c99a7a6530ce2dcc408d6e9c65  draws_soa_clang.csv
    fe7c57c99a7a6530ce2dcc408d6e9c65  w53/draws/draws_stock.csv  (GCC-stock, recorded)
    DRAWS MD5-IDENTICAL (clang-vs-clang): PASS

The GATE (clang-vs-clang, same-compiler bit-identity as all previous
SoA gates) passes — and the "expected/allowed" cross-compiler
difference does not materialize: both clang arms land on the GCC md5
digit-for-digit. Four-way identity (gcc-stock, gcc-soa, clang-stock,
clang-soa) = fe7c57c99a7a6530ce2dcc408d6e9c65.

## 4. Measurement (c): callgrind Ir (W-29 protocol, ~/vginstall, one job at a time) — win holds, gap attributed

| arm | T (PROGRAM TOTALS) | G (logp_grad incl.) | calls |
|---|---|---|---|
| stock-clang | 37,476,899,030 | 35,049,517,505 | 3737+756 = 4493 |
| soa-clang | 31,362,307,060 | 28,934,915,315 | 3737+756 = 4493 |

**T −16.31%, G −17.44%** (per-grad 7.801e6 → 6.441e6 Ir). Identical
call counts (trajectory identity, as with GCC).

GCC same-state references (W-59, batches 0+1+2+fused):
T 37,130,441,910 → 30,514,462,110 (−17.82%), G 34,703,678,559 →
28,087,600,877 (−19.06%). The W-92 brief's −15.9%/−17.1% were the
W-58 batch-012 (pre-fuse) refs; the bs_w53 tree is the fused state,
so W-59 is the like-for-like GCC comparison. Either way the clang
win sits inside the pre-registered −12..−19%G band, ~1.5pp below
GCC's.

ATTRIBUTION of the ~1.5pp cross-compiler gap (annotate, ann.txt):
- WITHIN clang, the two reverse callbacks are instruction-IDENTICAL
  across arms (elt_multiply chain 1,783,783,344; subtract chain
  1,359,079,344 in BOTH ann files) — the SoA patch still touches
  only forward record construction, exactly as under GCC.
- ACROSS compilers, clang's codegen for those callbacks costs
  3,142,862,688 vs GCC's 2,293,512,200 (+849,350,488); the whole
  soa-arm total delta clang-vs-GCC is +847,844,950 — the callback
  excess accounts for it to 0.2%. The absolute Ir gap is reverse-
  callback codegen, NOT the SoA substrate (which clang keeps as a
  clean out-of-line make_nochain_vari_array pair, 934,636,405 +
  934,592,165, where gcc inlines it into subtract/elt_multiply).
  Being a compiler-constant term in BOTH clang arms, the fatter
  callbacks merely dilute the ratio (denominator effect).
- stock-arm cross-compiler total delta is +0.35e9 (clang slightly
  dearer overall on this model too) — consistent picture.

PR-risk conclusion: no toolchain-specific failure mode. Clang emits a
different but still winning codegen; the patch's own code paths
(record construction) are compiler-robust, and bit-identity holds at
every level (values, grads, full sampler draws) across BOTH
compilers.

## 5. Measurement (d): in-sampler wall — ratios only (LOAD FLAG)

3 interleaved rounds × (stock-clang, soa-clang), scratch/w92/wall.sh
(W-59 parser: both "time per call" stanzas from cli logs), nice 19:

    warmup_us: stock med 1382.5 [1378.1..1384.4]  soa med 1224.3 [1217.8..1237.7]  ratio 0.8856  (−11.4%)
    samp_us:   stock med 1394.2 [1389.5..1415.5]  soa med 1305.2 [1297.4..1317.6]  ratio 0.9362  (−6.4%)

Per-round bands NON-OVERLAPPING in both stanzas, direction consistent
every round. FLAG per board policy: foreign grid load was ~12–13 at
session start, receded to ~5 during the wall rounds (recorded per
round in scratch/w92/wall/raw.txt) — absolute us/call are
cross-session non-comparable (also ~1.3–1.4 ms/call here vs ~1 ms in
the quiet W-57 session); the RATIO is the measurement. Warmup −11.4%
is at the top of the GCC wall range (−5..−7% across three sessions),
sampling −6.4% squarely in it.

## 6. Verdict

- GATE (a) within-compiler parity: PASS (0/100 + 0/100).
- GATE (b) draws md5: PASS — and four-way identity with GCC (bonus).
- (c) Ir: win HOLDS under clang, T −16.31% / G −17.44% at identical
  call counts; cross-compiler gap fully attributed to callback
  codegen (§4), a non-actionable compiler constant.
- (d) wall: −11.4% warmup / −6.4% sampling (ratios, FLAGged).
- math#5's per-toolchain codegen gate is now CLOSED for
  GCC/Eigen-3.4 (bundle), GCC/Eigen-5 (develop, W-59), and
  clang/Eigen-3.4 (this work). Clang cannot invalidate the patch.

Artifacts: this file; scratch/w92/{bs_stock_clang, bs_soa_clang,
model_hier_2pl_stock_clang, model_hier_2pl_soa_clang, gate_parity_
clang.py, gate_draws.sh, run_callgrind.sh, wall.sh, build_stock.log,
build_soa.log, draws/, profile/{stock_clang,soa_clang}/, wall/};
refs /tmp/w92_ref_hier_2pl_{clang,gccstock}.npz.
