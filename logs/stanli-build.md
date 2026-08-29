# stanli build log — 2026-08-26

Machine: WSL2 linux x64, 24 cores (HARD RULE: max -j4), 47G RAM, 15G free disk at start.
Toolchain: cmake 3.22.1, g++ 11.4.0, clang++ 14.0.0, python3 3.10.12, uv 0.11.23, ninja available.
Repo: /home/m0hawk/Documents/apin/stan/external/stanli @ 85a8f11 (clean tree)

## Plan (from README.md "Build" section, manual path)
    ./deps/fetch.sh
    cmake -B build
    cmake --build build -j4        # README says -j; capped at 4 per machine rule
    ctest --test-dir build -j4


## Resume after reboot — 2026-08-26 (agent 2)

Inherited state verified: repo clean @ 85a8f11, deps fetched (build/libsundials.a present),
build/ has CMakeCache.txt (Unix Makefiles, empty CMAKE_BUILD_TYPE, /usr/bin/c++),
44 .o files already compiled. Disk: 144G free (df -h .) — no disk pressure.
Raw build output for this session: logs/stanli-build-resume.out

### Task 1: incremental build
Command: cd external/stanli && cmake --build build -j4  (timed, background)
Result: SUCCESS rc=0, wall time 1330s (22m10s) for the incremental portion (44 -> 247 .o files,
all targets: libstanli.so, stanli_run, stanli_check, bench_*, dump_*, ~60 test_* executables).
Raw output: logs/stanli-build-resume.out (no errors, no warnings of note).
NOTE: CMAKE_BUILD_TYPE empty => unoptimized; executables are ~1.4 GB each, build/ totals 91G.
Disk: 144G free at resume start -> 52G free after build (df -h /). Above the 4G floor; monitoring.

### Task 2: test suite
Command: ctest --test-dir build -j4 (122 tests registered in CTestTestfile.cmake)
Result: 100% tests passed, 0 tests failed out of 61. Total time 0.93s. rc=0.
(CTestTestfile.cmake has exactly 61 add_test entries; my earlier count of 122 was a bad grep.)
Verbatim tail:
    59/61 Test #40: test_cross_path ..................   Passed    0.47 sec
    60/61 Test #61: test_verify_refs .................   Passed    0.29 sec
    61/61 Test #59: test_conformance_harness .........   Passed    0.45 sec
    100% tests passed, 0 tests failed out of 61
    Total Test time (real) =   0.93 sec
Spot checks (verbose):
    test_eight_schools: "test_eight_schools OK" (real end-to-end NUTS test)
    test_conformance_harness: python3 tests/test_conformance.py, "Ran 74 tests ... OK"
    test_verify_refs: python3 tests/test_verify_refs.py, "Ran 17 tests ... OK"
Note: the full corpus oracle (tools/verify_refs.py over deps/posteriordb) is a separate
out-of-ctest step and deps/posteriordb is not fetched; the ctest-registered tests above
are the harness self-tests. No failures to record.

### Task 3: smoke test (CLI)
Model+data written to /tmp/stanli-smoke/ (normal-location model, N=10).
Commands (from external/stanli):
    STANC=deps/stanc3/stanc build/stanli_run /tmp/stanli-smoke/model.stan \
        /tmp/stanli-smoke/data.json --seed 1 --warmup 200 --samples 200 --summary \
        > /tmp/stanli-smoke/draws.csv 2> /tmp/stanli-smoke/summary.err
Result: RC=0, 0.034s total (90% cpu). CSV on stdout = header + 200 draw rows (mu,sigma).
Summary on stderr (verbatim, key lines):
    name           Mean       MCSE     StdDev         5%        50%        95%   ESS_bulk   ESS_tail      R_hat
    mu           2.0783     0.0061     0.0817     1.9294     2.0827     2.1996        182        133      0.999
    sigma        0.2998     0.0081     0.0765     0.1999     0.2908     0.4291        116         62      1.010
    No divergent transitions. ... Tail ESS falls to 62 (sigma), below 100. [draw more samples]
    stanli_run: 2428 gradient evaluations
(Data y has mean 2.09, sd 0.23; posterior mu~2.08, sigma~0.30 is correct. The one
"diagnostic check failed" line is the informational small-ESS warning, exit code 0.)

### Task 4: python binding
Assembly (mirrors tools/build_wheel.sh; python/stanli/_bin/ is gitignored):
    cp build/libstanli.so python/stanli/_bin/
    cp deps/stanc3/stanc python/stanli/_bin/stanc && chmod +x (no stanc_embed.o => subprocess fallback)
Test command: cd /home/m0hawk/Documents/apin/stan && uv run python /tmp/stanli-smoke/py_demo.py
Result: RC=0, 0.18s wall. Verbatim output:
    stanli imported from: .../external/stanli/python/stanli/__init__.py
    embedded stanc: False
    n_unconstrained: 2
    constrained_names: ['mu', 'sigma']
    log_prob_grad at q=0: -22.368143551314212 [20.9  34.89]
    mu mean: 2.082998741358811  sigma mean: 0.2970148695441355
Notes: parent uv venv (.venv, py3.12, has numpy via cmdstanpy) + sys.path insert of
external/stanli/python; no pip install needed. stanc subprocess fallback used (embedded=False).
Cross-check (/tmp/stanli-smoke/lp_check.py): grad[0]=20.9 = sum(y) exactly. lp is the
SAMPLING (propto) density, as documented in python/README.md: full-constants lp=-35.9238,
stanli=-22.3681, diff 13.5556 = 10/2*log(2pi) + 1/2*log(2*pi*25) + log(2*pi) i.e. exactly
the dropped ~-statement constants; propto closed form matches -22.36814 to the last digit.
sample() 4 chains x 200+200: mu=2.083, sigma=0.297, agreeing with stanli_run (2.078/0.300).

### Task 5: artifacts
-rwxr-xr-x 1 m0hawk m0hawk     133872 Aug 26 10:44 build/bench_dispatch
-rwxr-xr-x 1 m0hawk m0hawk 1468509536 Aug 26 13:32 build/bench_grad
-rwxr-xr-x 1 m0hawk m0hawk 1438808592 Aug 26 13:33 build/bench_opcost
-rwxr-xr-x 1 m0hawk m0hawk 1470179808 Aug 26 13:33 build/dump_islands
-rwxr-xr-x 1 m0hawk m0hawk 1468457024 Aug 26 13:33 build/dump_ops
-rwxr-xr-x 1 m0hawk m0hawk 1518303384 Aug 26 13:33 build/libstanli.so
-rw-r--r-- 1 m0hawk m0hawk    2221520 Aug 26 10:44 build/libsundials.a
-rwxr-xr-x 1 m0hawk m0hawk 1472873664 Aug 26 13:33 build/stanli_check
-rwxr-xr-x 1 m0hawk m0hawk 1478830184 Aug 26 13:32 build/stanli_run
-rwxr-xr-x 1 m0hawk m0hawk     814096 Aug 26 13:41 build/test_capi
54
91G	build
1.5G	python/stanli/_bin
/dev/sdc       1007G  906G   51G  95% /
85a8f11 docs: TESTING.md becomes the why-you-can-trust-this page
