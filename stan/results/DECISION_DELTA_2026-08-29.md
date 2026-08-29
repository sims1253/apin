# Decision delta — what changed for the open user decisions (2026-08-29, PI memo)

Companion to the standing guides (results/PR_REVIEW_GUIDE.md, scratch/
w61/PROMOTION_ASSEMBLY_MAP.md). Only the DELTA since those were written.

## 1. Package A — combined-posture promotion (assembly/combined-posture)

- **BLOCKER found (W-110) — and FIXED (W-114):** the v1 assembly's ridge
  guard was unreachable (the W-96 conflict resolution dropped the
  multi-chain dispatch). **assembly/combined-posture-v2 @ 5a797d0** on
  the fork restores it (clean merge of the guard lineage + one surgical
  dispatch commit; canaries: single-chain default path bit-identical to
  v1 on two models; --chains 4 dispatches; the guard fires with the
  graduated budget live). Package A is testable/functional again;
  promotion remains your call.
- **W-96's gates stand otherwise** (48/48 completion; bit-identity fail
  attributed to pin_trace ulp, non-semantic; hier_2pl GMD reproduced at
  0.985x once --metric-window 50 is used — W-107).

## 2. Ridge guard in the recommended posture — quote ESS/s WITHOUT it

- W-110: on the four ridge-locked floor models the guard fires 12/12 and
  buys QUALITY (rhat-max 3.0-4.4 → 1.2-2.0; ESS floors 1.45-2.21x; full
  heals 103/61/23 ESS in the right budget/rep regime) but ESS/s geomean
  0.150x at the graduated budgets. W-109's "composed E/S 2-3x" projection
  is refuted for ESS/s: the honest headline stays 1.485x (E/S, no ridge).
- Budget-rule evidence now: W-102 (accel wants 128, diamonds wants
  graduation) + W-110 diagnostic (pilots F=5.2 graduated to 16 heals to
  ESS 6.4; fixed 128 heals the SAME rep to 103). Three of four fired
  models prefer the full 128. **The curve is now concrete (W-114's
  fire line): budget = 16 × F/5 — so a lock barely past the threshold
  F=5 gets only ~16 micro-steps; the floor near threshold is the
  mechanism of the under-budgeting.** Decision: default the fired class
  to fixed-128 (keeping graduation for diamonds-class), or raise the
  curve's floor/shape. Either way WALNUTPIE_RIDGE_MINMICRO=128 is the
  documented stopgap.
- bym2 rep1-class (F=16k, 128 fails, 4,824s/chain wasted): init-pathology
  class (W-84) — belongs to the init lane, not the budget lane.

## 3. Package B — error-cap default (unchanged, one addendum)

- W-91/92/109 stand: per-model lever (esc/hier_2pl/arma11 winners), no
  all-green default change. W-109's E+/E = 1.438x stacks multiplicatively
  on its subset. No new evidence since; decision still yours.

## 4. The math-side campaign (executing; first two families LANDED)

- W-111 census: radon_pp's scalar-lpdf loop = 90.1% of its gradient Ir
  (the largest unexploited math target in the suite); radon_var 87.4%;
  bym2 ICAR ~43%; lsat confirmed out of scope (0 gathers).
- **LANDED (W-112):** `normal_lpdf_gathered` — radon_pp G **−65.5%**,
  radon_var **−66.4%**, bit-identical (draws md5 digit-for-digit,
  22,360 bitwise unit checks). Branch gathered-normal @ bc00891778.
- **LANDED (W-113):** `dot_self_gathered_diff` (ICAR) — bym2 G **−17.0%**
  bit-identical; no relaxed variant by PI decision. Branch gathered-icar
  @ 3b9ee1b7dd.
- W-115 (in flight): the stanc3 emission REGISTRY (expression matchers +
  the normal loop matcher) — on green, the radon/bym2 class needs no
  manual C++ end-to-end, matching the hier_2pl precedent.
- Next queued: family 3 pcm/ordered (gate model gpcm_latent_reg_irt),
  family 4 additive bernoulli_logit (election88_full).
- Campaign map with admission test + family ranking:
  results/gathered_glm_generalization.md (status stamp included).
- Fork-PR packaging of the two new primitives (math drafts in the
  math#14 style) is prepared on request — user files upstream, never
  agents.

## 5. Filing state (unchanged rules)

math#14 + stanc3#7 (gathered-GLM pair), math#5/#6, stan#2, bridgestan#1,
walnutpie set — all fork-internal drafts; nothing was or will be pushed
upstream by agents. AI-policy disclosure lives in the DCO-signed commits.
