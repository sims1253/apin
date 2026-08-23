# W-43: blr short-warmup pin — root cause, escape mechanism, and fix

Date: 2026-08-23. walnutpie branch `exp/pin-diagnosis` (worktree
`external/walnutpie_w43`, off `exp/grad-accounting` @ 33cd398), commits
8853fd7 (instrumentation) + 468e60f (heuristic fix). Pre-registration:
WORKLOG.md "W-43" (before any run). Instrumentation: new env-gated
`WALNUTPIE_PIN_TRACE=1` per-iteration trace (`include/walnutpie/
pin_trace.hpp` + hooks at the W-38 accounting sites + a per-iteration
record in the CLI handler): iteration, lp, step, inv-mass
{geo,min,max}, position drift, moved?, per-transition macro-steps /
attempts / evals / momentum z-norm / the adapter-facing alpha and dH
(min-micro attempt), min |dH| over ALL attempts, tolerance-pass flag,
accepted halving level, ladder rejections, exhaustions. Zero behavior
(smoke canary: env-on vs env-off draws md5-identical, blr 100+100).

## Headline verdict

**The pin is a step-size descent race in a saturated-alpha regime (M2),
with the escape event itself a first-passage whose scatter is
momentum-driven (M4). The mass estimate is FROZEN for the entire pin
(M1 refuted), no window/batch boundary exists at defaults (M3 excluded
by construction), and no attempt ever passes tolerance before escape —
the reversibility ladder never even runs (M5 refuted as the pinning
verdict; it acts only post-escape). The pinned and escaped phases
differ in exactly one bit of internal state: whether
`exp(-|dH_min-attempt|)` has underflowed to ~0 (pinned) or not
(escaped). Everything else — frozen inv-mass, 31-eval signature,
constant position, zero ESS — follows from that saturation.**

Mechanism chain (all quantities from the trace):

1. The CLI seeds mass from `|grad|` at the init. At blr's default init
   (lp = -3.35e7) the gradient is enormous: seeded mass ~ 1.6e7
   (inv-mass geo 6.4e-8), so a macro step of 1.0 integrates a
   trajectory with min-attempt |dH| = 8.2e6 (E1's "8e6" was iteration
   0; the pf init starts at |dh| up to 2e12). Every halving refines the
   same macro time; all 5 attempts fail the 0.5 cap -> 31 evals
   (1+2+4+8+16), macro step rejected, position unchanged.
2. alpha = `exp(-|dH|)` underflows to exactly 0.0. Adam (target 0.8)
   sees a constant gradient and descends log-step at lr/t^0.5:
   measured log(step0/step(n)) = 0.100*(sqrt(n+1)-1) to within 2% over
   948 iterations (e.g. it=875: measured 2.837 vs predicted 2.860).
   This descent is the ONLY state that changes during the pin.
3. Because the chain does not move, draws and scores are constant, and
   both OnlineMoments accumulators share one discount schedule — the
   var_draw/var_score ratio, hence inv-mass = sqrt(ratio), is EXACTLY
   constant. Trace: invm_geo pinned at 6.42493e-08 (all printed digits)
   for all 948 pinned iterations (def), 0.0021367 for 198 (pf). The
   mass estimate is not "maturing"; it is dormant. It starts moving
   only AFTER escape (consequence, not cause).
4. |dH| declines as a power of step (def: |dH_min-attempt| ~ step^3.9;
   the finest attempt's |dH| ~ step^~2.5-4) until the FINEST attempt
   (h=4, step/16) crosses 0.5. Escape = first tolerance pass. At the
   def boundary the margin is 0.3%: mindh 0.5017 (it=947) -> 0.4987
   (it=948). The fresh momentum z each iteration makes the crossing a
   first-passage event: escape iteration spreads across seeds
   {574, 778, 948, >1000} for def inits (seed 20260822 stays pinned for
   the full 1000 — mindh still 0.93 at it=999; E2's rep1/chain_0
   analog), but clusters tightly {185, 189, 198, 200} for pf inits,
   where the pinned |dH| envelope falls ~ step^16 (steep approach =>
   concentrated passage times) vs the def-init trend (shallow approach
   => z-scatter of ~1% around a ~0.3%/iteration decrement => spread).
5. After escape: draws vary, inv-mass starts adapting, macro-steps per
   transition grow (1 -> 2-31), ladder rejections appear (M5 operates
   here), alpha becomes informative and Adam re-inflates the step
   (pf: log(step0/step) falls from 1.90 at it=250 to 1.35 at it=875).

The zero-ESS outcome has a second layer: if warmup ends while pinned,
the FROZEN sampler (no adapter, cap 0.5, divergent step) re-pins
immediately — all sampling draws identical at 31 evals/draw (verified:
w100 CSVs = 1 unique row of 100). E2's paradox (a constant 1e8 warmup
cap "still pins" at w100) is thereby explained: the loose cap does
admit warmup movement, but after only ~1 nat of descent the frozen
step is still ~1000x divergent, so SAMPLING pins regardless; E2's
pinned-draws metric cannot distinguish the two.

## Escape-boundary tables (the crux)

Default init, seed 20260819, escape at it=948 (step CONTINUOUS across
the boundary; inv-mass frozen; alpha jumps; accepted at h=4 = finest):

| it | step | invm_geo | dH min-attempt | mindh (all attempts) | alpha | moved | hacc | evals |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 943 | 0.04979 | 6.42493e-08 | -132.2 | 0.5159 | 4.0e-58 | 0 | - | 31 |
| 944 | 0.04971 | 6.42493e-08 | -130.7 | 0.5102 | 1.7e-57 | 0 | - | 31 |
| 945 | 0.04963 | 6.42493e-08 | -130.9 | 0.5109 | 1.4e-57 | 0 | - | 31 |
| 946 | 0.04955 | 6.42493e-08 | -128.3 | 0.5007 | 1.9e-56 | 0 | - | 31 |
| 947 | 0.04947 | 6.42493e-08 | -128.5 | **0.5017** | 1.5e-56 | 0 | - | 31 |
| **948** | 0.04931 | 6.42493e-08 | -378.2 | **0.4987** | 5.7e-165 | **1** | **4** | 77 |
| 949 | 0.04907 | 6.4237e-08 | -369.0 | 0.4821 | 5.5e-161 | 1 | 4 | 123 |
| 950 | 0.04883 | 6.4187e-08 | -360.1 | 0.4737 | 4.1e-157 | 1 | 4 | 123 |

pf init, seed 20260819, escape at it=198 (stochastic flavor: mindh
dips near 0.5 repeatedly for 10 iterations before the first pass; the
min-attempt dH remains ~1e6-7e7 through the boundary):

| it | step | invm_geo | dH min-attempt | mindh | moved | hacc | evals |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 194 | 0.26580 | 0.00213671 | 7.4e5 | 8.03 | 0 | - | 31 |
| 195 | 0.26485 | 0.00213671 | 1.4e6 | 1.98 | 0 | - | 31 |
| 196 | 0.26391 | 0.00213671 | 8.4e5 | 11.7 | 0 | - | 31 |
| 197 | 0.26297 | 0.00213670 | 2.0e6 | 3.96 | 0 | - | 31 |
| **198** | 0.26020 | 0.00213670 | 6.9e7 | **0.071** | **1** | **4** | 138 |
| 199 | 0.25568 | 0.00042793 | 2.1e4 | 0.050 | 1 | -1 (ladder) | 223 |
| 200 | 0.25304 | 0.00016920 | 3.3e3 | 0.127 | 1 | 3 | 66 |

Pin invariants across ALL 8 traced runs (4 seeds x 2 inits, w1000):
strictly pre-escape, tolerance passes = 0 and ladder rejections = 0 in
every run; attempts=5, evals=31, macro=1, exhaust=1 every pinned
iteration; inv-mass constant to all printed digits.

## Fix (shipped, opt-in): `find_reasonable_step` was broken 3 ways

The in-tree mitigation for exactly this pathology — the CLI's
`--step-init-heuristic` (Stan-style step probe, config-only) — could
not work because the probe itself was defective
(include/walnutpie/warmup_heuristics.hpp, commit 468e60f):

1. **Momentum scale inversion**: it drew `p = z .* sqrt(inv_mass)`
   (~N(0, inv_mass)) while the sampler draws `rho = sqrt(mass) .* z`
   (~N(0, mass)). Under the pin's seeded mass ~1.6e7 the probe moved
   ~1e7x less per step than a real transition, always "accepted", and
   returned eps >= 1 (measured: eps = 2.0 on the |dH|=8e6 cell). The
   library's other heuristic (`adapt_step`, util.hpp) uses the correct
   convention — the two disagreed.
2. **Fresh momentum per probe**: the loop redraws z each probe, making
   the one-step error's SIGN a lottery (Hoffman-Gelman Alg 4 draws
   once). Fixed to a single draw.
3. **Asymmetric accept statistic**: `exp(-(h1-h0))` is inf > 0.5 for
   divergent-direction errors (energy gain), steering the probe UP on
   the pinned cell (error negative at e=1, positive at e=2 -> returned
   eps=2 again). Now `exp(-|h1-h0|)`, mirroring the sampler's own
   alpha and tolerance test.

All three live only on the opt-in path (the flag is default-off and
single-chain), so the default path is untouched.

### Gates

- **(a) Canary bit-identity: PASS 12/12.** Default-path draws of the
  post-fix binary vs the pre-fix binary (same worktree, saved build):
  arma11, blr, hier_2pl x 4 chains, 1000+1000, seeds 20260819+c, rep0
  pf inits — md5-identical on every cell (results/w43_canary.json).
- **(b) Pin elimination + quality (blr, 3 reps x 4 chains, E2 seed
  protocol, post-fix binary + `--step-init-heuristic`): 0 of 48 chains
  pinned** (pinned = all 1000 draws identical; base pins 3/4 chains/rep
  at w100 and 1/12 at w400-pf / 1/4 at w1000-def).

| arm | bulk_min med | tail_min med | rhat_max med | pinned | base reference |
|---|---:|---:|---:|---:|---|
| w100 pf | **779.0** | 769.5 | 1.0048 | **0/12** | E2 w100 base: bulk 5-9, 3/4 chains pinned/rep |
| w400 pf | **630.4** | 693.7 | 1.0056 | **0/12** | E2 probe base: bulk 612.4 (rep1 = 86.5 from its pinned chain), 1/12 pinned |
| w100 def | 4.2 | 4.6 | 4.56 | **0/12** | def w1000 BASE itself: bulk 4.2, rhat 5.40, 1/4 pinned |
| w400 def | 4.3 | 4.6 | 4.29 | **0/12** | (same — no healthy def-init base exists at any warmup <= 1000) |

Reading: on the init class with a healthy reference (pf — the
production protocol), the fix restores SHORT warmup to full health:
w100 bulk 779 vs the w1000 base band 432.9-545.5 (E2 main grid) and vs
5-9 pinned at w100 base; w400 630 > the 612 base median with the
pinned chain eliminated. On the default-init class the pin is equally
eliminated (0/12, chains move from iteration ~1, lp climbs -3.347e7 ->
-2.93e7 over 100 warmup iters) but short warmup stays DRIFT-limited:
the init sits at lp = -3.3e7 and even the full-warmup BASE is garbage
there (rhat 5.4, bulk 4.2, one chain still pinned — the never-escape
seed). That is an init-protocol problem (W-42's territory), not the
pin; honestly recorded as outside this gate.

- Cost: the probe adds <= ~62 logp_grad calls once; knob chains run
  CHEAPER than pinned ones (pinned = 31 wasted evals/iteration forever):
  def w100 warmup 937 calls (vs 3102 pinned), sampling 8.2 calls/draw
  (vs 31 pinned); pf w100 3605 total calls vs base w1000 25375.

Also fixed upstream-relevant: the W-41 freeze-clamp branch
(exp/freeze-clamp) uses `find_reasonable_step` as its fallback (b); the
same three defects apply there — port commit 468e60f when that branch
is touched next (one-line port; recorded, not done here to avoid
cross-branch churn).

## Repro

```
# pinned-phase trace (default init, pin for 948 iters):
env -u LD_LIBRARY_PATH OMP_NUM_THREADS=1 WALNUTPIE_PIN_TRACE=1 \
  external/walnutpie_w43/build_w43/examples/stan_cli \
  bs_models_threads/model_blr.so data/blr.json --seed 20260819 \
  --warmup 1000 --samples 100 --output /tmp/x.csv   # grep pin-trace
# mitigation (opt-in):
  ... --step-init-heuristic --warmup 100 --samples 1000 ...
```

Artifacts: results/w43_{canary,knob,ess}.json; harness/run_w43.py
(canary + grid), harness/analyze_w43.py (ESS); raw logs
runs/w43/ (local, gitignored). Worktree left in place.

## Caveats

- Escape-iteration spread measured on 4 seeds x 1 init protocol each;
  the def-init ">1000" cell is one seed (20260822) — its mindh trend
  (0.93 at it=999, ~0.3%/iter decline) projects escape ~it 1300-1600.
- The frozen-sampler re-pin explanation of E2's 1e8-cap paradox is
  inference from the mechanism (frozen step after ~1 nat of descent is
  still divergent; w100 CSVs show all-identical sampling draws); the
  loose-cap warmup trajectory itself was not traced (the e2c knob is
  on the exp/error-discipline branch, not merged into exp/pin-diagnosis).
- Knob is single-chain-only (CLI restriction); the study harness runs
  chains as sequential single-chain invocations, but multi-chain
  library users would need the port.
- The W-37 finding that a constant-signal gate reads a pinned chain as
  "maximally stable" stands; the trace's `moved`/exhaust flags are the
  pin signature a future gate would need (out of scope here — W-37
  closed the gate direction).
