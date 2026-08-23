# W-49: Within-chain speculative parallelism for WALNUTS — measured ceiling, paper mapping, verdict

Date: 2026-08-22. Item X3. Pre-registration: WORKLOG W-49. Feasibility
first: every number below comes from existing artifacts — W-38-E1
gradient accounting (`runs/w38/accounting.json`,
`results/grad_accounting_w38.md`), the W-36 parallel-session walls
(`results/session_benchmark_w36.md`), W-29 instruction shares
(`results/hotspot_atlas_w29.md`) — plus the two papers. No new runs, no
builds. The deliverable is the verdict.

**VERDICT: NO-GO (parked with numbers).** The dependency-honest ceiling
for speculation on the production kernel (hier_2pl@1000+1000) is
**1.21x** (sampling phase) / **1.31x** (pooled) *with unlimited cores and
zero overhead*; with the 4-core budget it is below even the most generous
clairvoyant bound (2.43x), which itself loses to the already-shipped
4-chain parallel null (2.77x geomean, 3.43x on hier_2pl itself). The
pre-registered gate — build only if the honest ceiling >= 1.5x absolute
AND ~1.5x over the null (~4.2x) — fails on every defensible reading.
Prototype NOT built. The direction is parked with the numbers below, and
the conditions that would reopen it are listed at the end.

Paper-ID note (verified): the Picard-map paper is **arXiv:2506.09762**
(Grazzi et al., Biometrika 2026). arXiv:2506.09355 is de Leeuw's
generalized-eigenvalue derivatives note (scan §2) — unrelated; the
context prompt's "verify" resolves to the scan's listing.

---

## 1. What the Picard-map paper actually does, and what maps to WALNUTS

Grazzi et al. reformulate a K-step zeroth-order Metropolis recursion
`X_{i+1} = X_i + f(X_i, W_i)` (RWM, Metropolis-within-Gibbs, D-HMC) as a
fixed-point problem over K-step trajectories: each Picard iteration
evaluates the update `f` at K *guessed* states in parallel, and the
iteration converges (in finitely many iterations for piecewise-constant
updates like RWM's accept-bit-times-proposal) to the true trajectory
prefix. The measured deliverable in their precision-medicine application
is a parallel speedup factor G_hat = 4.37 with K = 8, an *effective*
speedup 2.52 once per-round overhead ε is priced (ε ≈ c, the per-call
evaluation cost, so effective = G_hat·c/(c+ε) ≈ G_hat/2).

Two properties make it work there:

1. **The expensive part is separable from the state update.** For RWM,
   the increment is `b·z` with `z` drawn and frozen (piecewise constant
   in the accept bit `b`); the expensive thing — evaluating π — happens
   at a *guessed* state and remains *valid* for the true trajectory as
   long as the guess was right. The sequential dependency is a single
   bit per step.
2. **A contraction supplies long correct prefixes.** Under optimal
   scaling (variance h/Ld), the chain moves O(1/√d) per step, so
   guessed accept bits have error probability O(i/d) at lag i; correct
   prefixes of length O(√d) come free in high dimension — hence the
   O(√d) exact / O(d) biased parallel speedup.

### The mapping table

| Picard ingredient | WALNUTS counterpart | Maps? |
|---|---|---|
| Expensive π eval at guessed states | leapfrog micro-step: one logp_grad per step (walnuts.hpp L330-334) | **inverted** — the expensive thing IS the state update; a "guessed" micro-step is not evaluable at discount, and is only usable if the guess was bit-exact |
| Accept bit (scalar, threshold fn, tolerant to small state error) | decision bits: tolerance pass per dyadic attempt, reversibility outcome, U-turn bit, direction coin, selection | **tolerance/reversibility bits are functions of the evaluations themselves** (need the final logp of the very attempt in question — unresolvable without doing the work); the direction coin (L594) is state-independent Bernoulli(1/2); U-turn/combine use no gradients at all (L194-203, L379-398) |
| Piecewise-constant increment (guess = freeze the z's) | the orbit is a deterministic lattice given (θ0, ρ0), zero per-step randomness (walnutpie implements the paper's **D** variant — deterministic micro-selection) | **maps better than RWM**: nothing random inside the orbit at all; but see next row |
| Contraction → O(√d) correct prefixes | Hamiltonian transport is ballistic to the U-turn; the dyadic tolerance test exists precisely to detect trajectory-scale divergence (stiff dynamics, |ΔH| vs max_error) | **anti-maps**: no contraction anywhere; the one truly guessable bit (coin) has error prob exactly 1/2 every step → expected correct-prefix length 1 doubling = O(1) macro steps = **1 gradient call at m=1** |
| Decision latency to hide speculation behind | W-29: walnutpie-internal (non-logp_grad) loop = **0.2–5.5%** of sampler-loop Ir; decisions are O(dim) vector ops next to ~1 ms gradient calls (hier_2pl 950–968 µs/call native; 966 µs solo / 1200 µs under 4-way contention, W-36) | **nothing to hide behind**: perfect prefetch of all decision latency bounds the win at ~1.05x; the only shadow big enough is other evaluation |

### What maps perfectly — and is already priced by the paper

The genuinely parallel, zero-guess, bit-identical structure in the
kernel is the **dyadic redundancy itself**: all halving attempts in a
`macro_step` restart from the same span endpoint (L326-328) and are
mutually independent; the ladder rungs in `reversible`/`within_tolerance`
(L269-279) are independent integrations from the accepted endpoint.
No guessing, no RNG on the helper, commit/discard on the main thread —
the numerics discipline of the contingent prototype would have been
sound.

The WALNUTS paper (arXiv:2506.18746, §4.1) **already anticipates exactly
this mechanism**: "When measuring performance in terms of gradient
evaluations, both the forward and backward micro-computations are
counted, even though backward micro-computations *may be run on a
different processor and thus only adding negligible (wall clock)
computation time*." The authors treat the backward (reversibility-check)
walks as wall-clock-free — which is why our ESS-per-gradient accounting
counts them. W-38-E1 now prices that anticipated parallelism: **bl =
8.6% of sampling evals on hier_2pl@1000** → the mechanism the paper
already claims is worth **1.094x** wall on the settled production
kernel. That single number is the shape of the whole verdict.

## 2. Ceiling arithmetic from the measured buckets

Splits (pre-registered in W-49), per W-38-E1 buckets of kernel
logp_grad evals — fa = forward-accepted, fw = forward-wasted (tolerance-
failed dyadic attempts), bl = backward-ladder, dl = discarded-on-leaf-
failure:

- **Split A** (clairvoyant upper bound; fa speculative, rest serial):
  Amdahl S(N) = 1/(s + p/N).
- **Split B** (dependency-honest; hideable = fw+bl only, critical path =
  fa+dl): S ≤ 1/(fa+dl), *independent of core count beyond 2* — the
  micro-chains inside accepted attempts are strictly serial, macro steps
  chain endpoint-to-endpoint, and the coin's expected useful lookahead
  is O(1) steps.

| run.phase (W-38-E1) | fa | fw | bl | dl | A: S(2) | A: S(4) | A: S(∞) | B: S(∞) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hier_2pl@1000 warmup | .673 | .201 | .088 | .039 | 1.51 | 2.02 | 3.05 | 1.41 |
| **hier_2pl@1000 sampling** | **.784** | .086 | .086 | .043 | 1.64 | **2.43** | 4.62 | **1.21** |
| hier_2pl@1000 pooled | .722 | .150 | .087 | .041 | 1.56 | 2.18 | 3.60 | 1.31 |
| hier_2pl@100 sampling | .402 | .253 | .248 | .097 | 1.25 | 1.43 | 1.67 | 2.01 |
| kronecker_gp@100 sampling | .343 | .251 | .229 | .176 | 1.21 | 1.35 | 1.52 | 1.92 |
| pilots@100 sampling | .467 | .228 | .223 | .081 | 1.30 | 1.54 | 1.88 | 1.82 |
| blr@1000 sampling (pin-escape) | .342 | .345 | .313 | .000 | 1.21 | 1.35 | 1.52 | 2.92 |
| blr@100 (pinned) | .000 | 1.000 | .000 | .000 | 1.00 | 1.00 | 1.00 | — (100% "hideable") |

### The headline cell: hier_2pl@1000, 4 cores, "perfect speculation"

- Task's own most generous framing (Split A, clairvoyant, 4 cores):
  **2.43x** (sampling) / 2.18x (pooled). Pricing the measured +10–25%
  memory-bandwidth contention on the 3 helper cores (helpers run the
  speculative evals, W-36's measured penalty class): **1.84x**.
- Dependency-honest (Split B): **1.21x** with *unlimited* cores and
  zero sync overhead. 91.0% of accepted macro steps are h=0 there
  (10640/11693; P(h≥1) = 8.7%): one gradient eval, no second attempt,
  no ladder — nothing to overlap, full stop.
- Structure per transition (sampling): 16.3 evals = 12.7 fa + 1.4 fw +
  1.4 bl + 0.7 dl over 12.0 macro steps. The entire hideable envelope is
  **2.8 evals/transition (17.2%)**; the producer-consumer prototype
  shape (pre-integrate the next macro-step's forward span during ladder/
  decision time) has a shadow of ≤1.4 bl evals/transition, a speculative
  quantum of 1 eval (m=1 in 100% of steps, W-38-E1), and a coin-gated
  hit rate ≤1/2 → expected useful work ≤0.5 evals/transition ≈ **3%** of
  the kernel, before sync costs and before the wasted speculative evals
  contend for memory bandwidth.

### The null it had to beat (same 4 cores, W-36, measured)

4-chain parallel `exp_par`/`exp_seq` = **2.77x geomean end-to-end;
3.43x on hier_2pl** (155.06 s → 45.26 s), already carrying the +10–25%
contention and slowest-chain skew — and delivering 4 independent chains
(R-hat) instead of 1. The gate required the speculation ceiling to be
≥1.5x over this (~4.2x). Even the unphysical clairvoyant 4-core bound
(2.43x) loses to the null outright; the honest bound (1.21–1.31x) loses
by ~3x. Speculation and chain parallelism are substitutes for the same
cores: with 4 chains on 4 cores there is no idle core to speculate with,
so the only regime where the question lives is cores > chains — and
there the honest ceiling is 1.2–1.3x on production kernels.

### The counter-cells, honestly stated

Split B is large exactly where the kernel is *mis-settled*: blr@1000
sampling 2.92x, hier_2pl@100 sampling 2.01x, pilots 1.82x — deep
persistent dyadic refinement (h2–h4 structural on blr: 104 evals/draw).
But those evals are **waste by definition** (fw+bl = the overhead the
W-37p pack exists to remove): the E2/E4 lane deletes them serially, on
one core, with no hardware — parallelizing waste is strictly dominated
by deleting it. The pinned blr cell's "100% hideable" is really "100%
deletable" (the chain does not move; 31 evals burned per transition, all
fw — W-38 bonus finding). And after E4-style fixing, those kernels
converge toward the hier@1000 profile (91% h=0) where the speculation
ceiling collapses back to ~1.2x. The direction is self-undermining: its
best cells are the cells another lever eliminates.

## 3. Why the idea fails — the one-paragraph mechanism

Speculation converts decision latency into throughput only where (a)
there is serial think-time to hide behind and (b) the decisions are
resolvable without the evaluation itself. In WALNUTS the think-time is
0.2–5.5% of runtime (W-29), so there is no shadow; and of the decisions,
the ones that gate further orbit work (tolerance, reversibility) are
*functions of the evaluations themselves* — the only way to know what
the orbit does is to integrate it — while the one bit resolvable without
evaluation (the direction coin) is i.i.d. fair, giving expected
lookahead of one doubling. What remains is the dyadic redundancy
(fw+bl): genuinely parallel, genuinely bit-identical, and only 17.2% of
the settled kernel — a ceiling of 1.21x that no amount of engineering
overhead budget can turn into a win against a 2.77–3.43x alternative
already shipped. Picard maps thrive on the opposite structure (cheap
state-light increments, tolerant threshold bits, diffusive contraction);
WALNUTS's ballistic, stiff, evaluation-is-the-update orbit is the worst
case for the method.

## 4. Prototype status

**Not built — the pre-registered gate failed before the worktree was
created** (no `external/walnutpie_w49` exists; walnutpie untouched).
For the record, the gates that would have applied (pre-registered in
W-49): bit-identity canary 12/12 with speculation OFF and ON — ON must
still be bit-identical because speculation computes the same doubles,
just earlier, and the RNG stream stays main-thread-only (helpers only
integrate; the initial normal draw, per-depth `uniform_binary`, and
per-combine `uniform_real_01` all remain on the main thread in
unchanged order); then wall on hier_2pl + blr vs serial and
4-chain-parallel baselines. The numerics would have been sound; the
ceiling is not.

## 5. What would reopen this (park conditions)

1. **m ≫ 1 regimes.** At m=1 (100% of steps today, W-38-E1) the dyadic
   redundancy is one eval deep. If W-38-E4's grow-m lands m=8+, the
   fw+bl share AND the per-attempt parallel grain grow together —
   recompute this table from E4's joint (m, h) traces before believing
   any of the negatives above transfer.
2. **A single-chain-constrained deployment** (cores ≫ chains wanted,
   e.g. streaming) on a model with structurally deep refinement and no
   E2/E4 fix available — the honest ceiling there is ~2–2.9x (Split B),
   still with the +10–25% contention class priced in.
3. **Within-logp_grad data parallelism** is the actual single-chain
   parallel lane (row-parallel likelihoods, stan-math/GPU territory,
   W-29's 81.6–99.4% share) — that is where >1 core per chain has to
   come from; it composes with everything and needs no speculation.
4. Walnutpie watchers that change the accounting, not the verdict:
   issue #34 (gradient caching) and PR #77 (leapfrog unroll) reduce or
   restructure eval counts but leave the serial dependency structure
   (micro-chain, endpoint chaining, fair coin) untouched; the paper's
   R2P randomized-ℓ variant, if walnutpie ever adopts it, adds one more
   unguessable bit per macro step and makes speculation strictly harder.

## Sources

arXiv:2506.09762 (Grazzi et al., Biometrika 2026 — abstract + full HTML
v2: Picard-map formulation, Theorem 3.1 wrong-guess O(i/d), K/√d
rounds, G_hat 4.37 → effective 2.52). arXiv:2506.18746 (WALNUTS, JMLR
27(113) 2026 — abstract + full HTML: Algorithm 3 with backward
micro-computations, §4.1's "different processor" statement). Local:
`runs/w38/accounting.json`, `results/grad_accounting_w38.md`,
`results/session_benchmark_w36.md`, `results/hotspot_atlas_w29.md`,
`results/proposals_fewer_gradients.md` §source anatomy,
`results/upstream_scan_2026-08.md` §7,
`external/walnutpie/include/walnutpie/walnuts.hpp` @ 43b6435.
