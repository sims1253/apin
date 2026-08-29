# Null-ridge lock — upstream reprex kit

Self-contained reproduction of the walnutpie null-ridge lock against the
STOCK upstream package (v0.0.2, main). No fork code involved.

## Files

- `pilots.stan` — the model (posteriordb pilots, centered hierarchy).
- `null_ridge_reprex.py` — runs both arms via the upstream python API.
- `reprex_output.txt` — captured output (the numbers quoted in the post).
- `DISCOURSE_POST.md` — paste-ready post for the walnutpie Discourse.

## Reproduce

```bash
pip install walnutpie bridgestan arviz   # stock PyPI / main
# BridgeStan needs a STAN_THREADS build of the model:
mkdir build_threads && cp pilots.stan build_threads/ && cd build_threads
python -c "import bridgestan, shutil; shutil.move(bridgestan.compile_model('pilots.stan', make_args=['STAN_THREADS=true']), 'pilots_threads.so')"
cd .. && sed -i 's|build/|build_threads/|' null_ridge_reprex.py
python null_ridge_reprex.py
```

(Expected output matches `reprex_output.txt` up to platform noise; the
pattern — ESS ~1–4 / ridgeF ~8 / rhat ~3.9 at defaults vs ridgeF ~0.2 /
rhat ~1.02 at min_micro_steps=128 — is what matters.)

## Provenance

Diagnosis chain (apin repo WORKLOG): W-85 (length-vs-metric binding),
W-88/W-93/W-95/W-99/W-101/W-102 (detector, composition, calibration,
out-of-sample, cost tuning on the fork), W-105 (this pure-upstream
repro). Full data: results/ridge_guard_w88.md, results/combined_posture_
w93.md, results/w99_ess.json.
