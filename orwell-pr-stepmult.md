# walnuts step multiplier (default-off): the coupled-calibration instrument

## Problem

F-11.2 (in #4) found walnutpie's accept target and step-noise are a coupled calibration: batched (denoised) Adam converges to the true E[alpha]=0.8 root at frozen steps 1.1-3.0x smaller than stock's accidental regime — ESS/draw up, wall up.

## Evidence

- step_freeze_multiplier K, applied post-freeze: warmup draws bit-identical under any K (property-tested); --w-step-mult flag, default 1.0.
- Dev-set mechanism table (stock -> b10 -> b10xK): kidscore ESS/draw 0.083 -> 0.133 -> 0.457 (K=8; best-in-class, R-hat 1.006); blr 0.149 -> 0.218 -> 0.421; logmesq converges only at K=8 (R-hat 1.026 -> 1.002). esnc peaks at K=4 (1.545) and collapses at K=8 — trajectories U-turn immediately.
- Registered validation FAILED at the global gates (geomean ESS/s 2.93x vs arm C 6.57x; 5/9 R-hat) — no global (target, K) exists: the optimum is model-dependent. All three F-16 silent-failure models IMPROVED (diamonds R-hat 1.108 -> 1.015) without crossing 1.01. b25 < b10 at every K.

## Validation

Default K=1.0 byte-identical (md5). The knob is the instrument for per-model adaptive K (the ranked follow-up), not a config. Stacked on #4. apin WORKLOG F-21; logs/fortk-f21.md; raw bench/fortk_f21/.
