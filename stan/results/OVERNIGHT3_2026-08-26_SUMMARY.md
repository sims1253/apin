# Overnight-3 session summary — 2026-08-26 (for review on return)

Three pre-registered experiments + two diagnoses, all closed with gates.
Machine coordination held throughout (sibling W-83/W-81 streams respected).

## The promote package is now fully validated (your decision)

**W-75: robustness stack × pf inits = +84.66% aggregate geoESS, 30/30
cells, healthy paths bit-identical.** Branch `exp/robust-stack-w75`
(local, external_w75/ worktree) = exp tip + #7/#8/#9/#10 fixes. The two
accel_gp abort cells from W-74 now complete — and the NaN-alpha guard
(#10) prevents the poisoning upstream so the freeze clamp (#8) never even
fires. Package for you: merge walnutpie PRs #7/#8/#9/#10 + adopt the
pf-init workflow (one-time ~5% wall cost, see results/pf_init_w74.md).

## Pilots: mechanism solved, discriminator run, fix direction known

- **Diagnosis:** exact likelihood-null ridge in the model (a/b additive
  shift invariance); all 4 chains lock at different ridge points;
  log-mass is invariant along the ridge, which is why every lp-based
  rescue ever tried (W-11/14/15, pf inits) was blind. Precise detector
  defined: ridgeF = cross-chain dispersion of chain-mean positions
  (observed 26–30 on pilots, <2 on healthy models).
- **W-85:** forcing CmdStan-scale trajectory budget traverses the ridge
  (ESS(mu_a) 1–14 → 12–1000, rhat 3.37 → 1.02) at ~80× gradient cost —
  i.e., LENGTH-binding, not metric-binding; the metric variance-floor
  idea is refuted for this class. Fix direction (W-86 design candidate,
  territory handed to orchestrator #2's W-82-guarded lane):
  ridgeF-gated conditional min-micro-steps increase. Third independent
  validation of the robustness stack along the way (stock binary
  aborted 2/3 reps of this very experiment; stack completed 3/3).

## Selector program: closed for good

**W-76: Fisher-ratio selector KILLED** (strict gate: best statistic 1/8
misclassifications, 5 rep violations, direction inverted). Fourth dead
selector on the same labels (W-28/W-37/W-66/W-76). The conditional-policy
program — routing aggressive settings to easy models — has no cheap
end-of-warmup signal and closes. Real byproduct: the spread stats map a
genuine tight-vs-broad posterior axis, orthogonal to policy response.

## Net position after three nights

- Measured and adopted-candidate: pf-init workflow + robustness PRs
  (+84.7% aggregate; your merge decision).
- Measured and closed: every adaptation knob (optimizer, windows,
  min-micro, hyperparameters), four selectors, low-rank direction,
  partial refresh, DEER, subsampled-warmup transplant.
- Root-caused: accel finalize abort (NaN→Adam→freeze ctor), kronecker
  dead-init (LKJ boundary), pilots ridge lock (this night).
- Open lanes owned by others: W-82-guarded (pin detection — now has the
  W-85 input), W-83 init-quality study, two-phase warmup (design doc
  recommends expect-REJECT), SoA batches, walnuts-ai port.

Artifacts: results/{pf_init_w74, fisher_selector_w76}.md, results/
w74/w75/w76/w85 JSONs, runs/w74|w75|w76|w85, external_w75|w76 worktrees,
inits_w74/. WORKLOG entries W-74..W-76, W-85 (+ pilots diagnosis entry).
