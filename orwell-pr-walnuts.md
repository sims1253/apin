# walnuts adaptation knobs (default-off): step batching, chop, clip, shrink

## Problem

The vendored walnutpie sampler under-mixes on the fused stack: with pathfinder inits it still lands kidscore at rhat 1.014 / ESS-per-draw 0.093, and the failure tracks the step-size adaptation loop (stock Adam receives one observation per micro-step — hundreds per iteration — and never converges).

## Evidence

- Vendored config gains six knobs, all default-off, vendored structure preserved: --w-chop (window chop), --w-clip-k (Winsorized score clip), --w-var-floor, --w-shrink-kappa, --w-smooth, --w-batch N (Adam mean-batching over N observations).
- kidscore ladder (3 reps x 4 chains, pf inits): --w-batch 10 alone fixes the gate — rhat 1.014 -> 1.008, ESS/draw 0.093 -> 0.108 (b25/b50 and chop variants also pass; D0 arm reproduces the pre-change result exactly).
- Coupled-calibration finding: batched (denoised) Adam converges to the true E[alpha]=0.8 root, landing 4x smaller frozen steps than stock's accidentally-large 0.22 — ESS/draw +7..41% at 1.5-3.5x wall on blr/esnc/logmesq. The stock accept-target and step-scale are a coupled calibration; any adapter change needs a joint (target, step) re-tune — recorded as follow-up, not tuned past here.
- Mass-side knobs (chop/clip/floor/kappa) moved nothing or hurt on this stack (kappa=5: ESS/draw 0.058); carried config is --w-batch 10.

## Validation

All-off path draws byte-identical vs the pre-pick binary (esnc+blr x 2 seeds x {u,pf} inits, 8/8 at 85a8f11 and 4/4 within-rebase; the CSV header gains an f112(...) provenance tag, values all-default); ctest green incl. test_walnuts_adapt property suite (gaussian convergence per knob, stride-1 Adam bitwise stock, off-config == stock-config); --w-batch 10 one-chain kidscore smoke. All quality gates here are draw-based (rhat, ESS/draw, byte-identity) and load-immune; no instruction-count instrument needed.

## References

apin WORKLOG F-11.2; logs/fortk-f112.md; kidscore ladder raw in bench/fortk_f112/.

Rebased onto 33f79dea; all measurements taken at the 85a8f11 base (pre-rebase); re-gated at the rebased tip.
