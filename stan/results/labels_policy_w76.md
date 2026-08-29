# W-76 policy-outcome labels (ground truth for the Fisher-ratio selector test)

Compiled from measured experiments (3-rep medians): W-63/W-70 (metric-window
chop 100/250/500), W-64 (step-optimizer belief vs adam), W-73 (lr_hi 0.15),
W-66 (low-rank metric direction). Aggressive-policy responsiveness per model:

| model | window-chop | belief opt | lr_hi | rank | LABEL |
|---|---|---|---|---|---|
| diamonds | +43/+55/−23% | +71.6% | +89.1% | (n/a) | **WINNER** |
| radon_pp_nc | +7/+37/+60% | +21.3% | +42.2% | (n/a) | **WINNER** |
| bym2_offset_only | +29/+12/−3% | +35.1% | +30.2% | harmed | **WINNER** |
| lsat_model | +36/+25/+28% | +22.5% | +6.9% | harmed | winner-leaning |
| eight_schools_c | +22/+33/−25% | +28.6% | +1.4% | harmed | MIXED |
| hier_2pl | +9/+2/+0% | −1.7% | +2.7% | harmed | NEUTRAL |
| pilots | −90/−16/−16% | −4.7% | −10.7% | (n/a) | harmed-leaning |
| kronecker_gp | −11/−4/−5% | −16.4% | −16.6% | harmed | **HARMED** |
| accel_gp | −63/−69/−64% | −35.9% | −33.8% | (n/a) | **HARMED** |
| lotka_volterra | −51/−44/−9% | −43.2% | −53.1% | harmed | **HARMED** |

(Naked-DA aborts in W-64 excluded as instability, not policy response.)

## Clean separation task for the selector

Primary classes: {diamonds, radon_pp_nc, bym2} vs {lotka_volterra,
kronecker_gp, accel_gp}. Secondary: lsat→winner side, pilots→harmed side,
eight_schools_c and hier_2pl = declared mixed/neutral (not counted as
errors either way).

Prior selector failures to beat: lp lag-1 autocorr (W-28: hier 0.71–0.91
vs blr 0.62–0.74 — no separation), windowed warmup stats (W-37: 0/18
boundaries), window_cross_ratio (W-66: ordering INVERTED — models it
certified "spread" were the ones rank harmed).

Selector signal under test (W-76): per-coordinate log(Var_draw·Var_score)
at end of warmup — mean, spread (IQR/std), quantiles, frac |log|>1,
max-|log|. All computed from #11 warmup-tracer dumps under NORMAL inits
(selector must work without pf).
