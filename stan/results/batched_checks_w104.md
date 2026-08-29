# W-104: batched domain checks in normal_lpdf — NEGATIVE RESULT, stopped at the audit (no code change)

Pre-reg (WORKLOG "W-104 PRE-REGISTRATION") authorized this stop: "if the audit
shows the cost is NOT in a batchable predicate (e.g. the throw itself is
irreducible), STOP after step 1-2 with the negative result." The audit shows
exactly that, with a mechanism correction to the pre-reg's premise: **the hot
check on blr is the SCALAR `check_positive` on sigma — there is no per-element
loop on the throw path to batch — and ~97% of the complex is libstdc++/libgcc
throw+unwind machinery whose invocation count is pinned by the pre-reg's own
gates (a) and (b).** Gate (c) (−30..−45% G) is arithmetically unreachable from
the math side (ceiling ≈ 1–3% G). No implementation was built, no gates run,
all trees left pristine.

## 1. The check path on blr (exact sites)

blr model (`external/posteriordb/posterior_database/models/stan/blr.stan`,
D=6, N=100): `normal_lpdf(beta|0,10)` (beta var-vector), `normal_lpdf(sigma|0,10)`
(sigma scalar var), likelihood `normal_lpdf(y | X*beta, sigma)` — y = double
data map, mu = var matrix, **sigma = `var_value<double>` SCALAR**.

In `normal_lpdf` (`stan/math/prim/prob/normal_lpdf.hpp`), after
`as_value_column_array_or_scalar`+`to_ref`:

- `:61 check_not_nan(function, "Random variable", y_val)` → Eigen per-element
  loop `prim/err/elementwise_check.hpp:150-177` (loop at `:153`, cold-path
  indexed message at `:157-160`). On blr: y is data — passes always; the same
  instantiation on **beta** (prior call) is the one that throws (NaN probes).
- `:62 check_finite(function, "Location parameter", mu_val)` → same Eigen
  loop. Passes on blr (X*beta finite whenever the beta check above did not
  already throw earlier in the model body).
- `:63 check_positive(function, "Scale parameter", sigma_val)` →
  `prim/err/check_positive.hpp:30-33`; sigma_val is a plain `double` (val of
  the scalar var) → **scalar overload `elementwise_check.hpp:114-126`** — ONE
  compare, cold-path lambda `:120-124` → `internal::elementwise_throw_domain_error`
  (`elementwise_check.hpp:88-92`): stringstream message, `throw
  std::domain_error(ss.str())` at `:91`. **This is the #1 blr throw site.**
  There is no loop here to batch — the pre-reg/task premise ("elementwise_check
  on sigma fires per-element") is disproven by the profile: the hot
  instantiation is `elementwise_check<check_positive<double>::{lambda}, double, …>`
  with `T = double`.

Propagation: throw#1 unwinds (libgcc `_Unwind_RaiseException` phase 1 +
`_Unwind_Find_FDE` per frame) to the stanc3-generated try/catch wrapping the
model body inside `bs_log_density_gradient` (blr_model.so), which calls
`stan::lang::rethrow_located(e, …)` — compiled into the model .so, NOT math —
which builds the located message and throws#2 (`__cxa_throw` phase 1+2,
cleanup `_Unwind_Resume`), caught by the CLI → "Error in logp_grad: …" line →
gradient evaluation marked failed → sampler rejects that evaluation.

## 2. Measured decomposition (W-102 profile re-analyzed, no new runs needed)

Source: `scratch/w102scan/profile_blr/callgrind.out` (runner
`run_callgrind_w102.sh`; warmup 100 + samples 50, seed 20260819, pf init;
verified by `callgrind_annotate --inclusive --tree=calling`, decomposed flat
and cross-checked against `cli.log`).

- Program 521,943,894 Ir; G = `bs_log_density_gradient` inclusive
  **450,337,861 Ir** over **4,652 gradient calls**.
- **2,394 throws** (= 2,394 "Error in logp_grad" lines, reconciled exactly:
  2,302 "Scale parameter is 0" [scalar check_positive, sigma==0 exactly —
  exp() underflow of the `<lower=0>` transform] + 92 "Random variable … nan"
  [79 Eigen-array check_not_nan on beta + 13 scalar check_not_nan on the
  sigma-prior call]). 51.5% of gradient evaluations throw.
- In-G throw complex:
  - `rethrow_located` inclusive 224,468,622 = **49.84% G** (2,394×) — model-.so
    side: message concat + throw#2 + unwind.
  - scalar `check_positive` cold path inclusive 109,414,147 = **24.29% G**
    (2,302×) — of which message formatting is only ~11.3M ≈ **2.5% G**
    (ostream _M_insert<double> 4.07M + __ostream_insert 3.82M + stringbuf
    str() 1.49M + ios init 1.02M + domain_error ctor + stringstream dtor …);
    the other ~98M = throw#1 `__cxa_throw` (58.6M incl) + `_Unwind_Resume`
    (38.9M) + unwind phases. **The W-102 scan's "24.38% message formatting"
    was an inclusive-number mislabel — formatting is ~1/10 of that.**
  - vector `check_not_nan` cold path inclusive 2,891,321 = 0.64% G (79×).
- Per failure cycle ≈ 139.5k Ir (≈141k incl. the vector sites), of which
  formatting ≈ 4.7k — **>96% is `__cxa_throw`/`_Unwind_*`/`__gxx_personality_v0`
  LSDA parsing** (program-wide: `__cxa_throw` 9,576 calls = 4 per cycle;
  `_Unwind_Resume` 112.95M Ir; `read_encoded_value` 90.4M Ir over 2.03M calls).

## 3. Why the pre-registered change cannot reach its own gate

The batched-predicate change (aggregate `(sigma.array() > 0).all()` etc.,
per-element report loop only on failure) attacks exactly two costs:

1. Per-element scan loops on passing evaluations — only y/mu have loops
   (sigma is scalar), N=100 each, inlined into normal_lpdf's 17.1M self Ir;
   the scan share is a few M Ir ≈ **≤1% G** even if zeroed.
2. Message formatting on failure — ≈ 11.3M ≈ **2.5% G** ceiling.

Combined ceiling ≈ 1–3% G, realistically ~1–2%. Gate (c) requires −30..−45% G.

The remaining ~72% G of the complex is the throw/unwind cycle itself, and its
count is fixed by the pre-reg's own invariants: gate (a) (draws md5
`11fb5b6f…` — throws are the sampler's rejection signal, so the trajectory
pins the throw set) and gate (b) (error-line COUNT parity = 2,394 throws). Same
throws ⇒ same 4×`__cxa_throw`/unwind phases ⇒ the complex stands. Neither the
unwinder (libgcc), the second throw (`rethrow_located`, stanc3-generated model
code), nor the CLI catch (walnutpie) is reachable from math headers. Gates
(a)/(b) and gate (c) are jointly unsatisfiable for ANY math-side
implementation — the pre-reg's −30..−45% band was derived from "the complex is
49.8%, expect most of it" under the wrong premise that the 49.8% was per-element
scanning + formatting; it is unwinding.

Sanity checks considered and rejected: reordering checks to test sigma first
(saves the y/mu scans on the 2,394 failing evals ≈ 1% G — noise, message
precedence changes); cheaper formatter than stringstream (≤2.5% G — outside
pre-reg scope and noise); returning −inf instead of throwing (changes sampler
behavior ⇒ gate (a) fails, and gate (b) loses its error lines); throwing from a
shallower frame (FDE-lookup saving is single-digit M Ir).

## 4. Where the lever actually lives (for a future pre-reg)

The scan already suspected it and this audit confirms it: the −30..−45% is a
**walnutpie/sampler-posture lever, not a math one**. 51.5% of blr's gradient
evaluations die on sigma==0 (exact exp-underflow of the `<lower=0>` transform)
at warmup/metric-window probe points. Options that DO remove the unwind cost:
a sampler-side cheap pre-reject of transform-domain-invalid proposals before
calling logp_grad, or an init/probe guard — i.e. avoid the 2,394 doomed
evaluations (or their exception-based reporting), rather than make math's
throw cheaper. That is walnutpie work under its own pre-registration.

## 5. State

- No code changes anywhere: math_dev_soa clean @ a43e868823 (W-103 kernel
  HEAD, no branch created); math_soa develop @ 344d7167a0 + the standing W-53
  SoA slice (pre-existing, untouched); `scratch/w53/bs_w53` bundle untouched
  (normal_lpdf.hpp md5 9f5ad345… identical in both math trees).
- Gates (a)–(d): NOT RUN — vacuous without an implementation; the audit is
  the result.
- Evidence: this re-analysis used only existing artifacts —
  `scratch/w102scan/profile_blr/{callgrind.out,cli.log}` + code reading of
  `prim/prob/normal_lpdf.hpp`, `prim/err/{check_positive,check_not_nan,
  elementwise_check}.hpp`. No machine time consumed beyond annotation.
