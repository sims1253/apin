#!/usr/bin/env python
"""Phase 1: localize nutpie's win — warmup vs sampling phase timing, and
per-gradient wall vs cmdstan, same models. (Quality-neutral timing probes:
t(tune,draws) factorial on a subset.)"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'results/profile'; OUT.mkdir(parents=True, exist_ok=True)

def probe(nutpie, model, tune, draws, cache, reps=2):
    if model not in cache:
        data = json.loads((ROOT / f'data/{model}.json').read_text())
        cache[model] = nutpie.compile_stan_model(filename=str(ROOT / f'models/{model}.stan')).with_data(**data)
    ts = []
    for r in range(reps):
        t0 = time.time()
        nutpie.sample(cache[model], chains=4, tune=tune, draws=draws,
                      seed=20260819 + r, cores=4, save_warmup=False, progress_bar=False)
        ts.append(time.time() - t0)
    return sorted(ts)[len(ts)//2]

if __name__ == '__main__':
    models = sys.argv[1].split(',') if len(sys.argv) > 1 else \
        ['diamonds', 'radon_partially_pooled_noncentered', 'hier_2pl', 'accel_gp', 'lsat_model', 'pilots']
    import nutpie, os
    os.environ['OMP_NUM_THREADS'] = '1'
    cache = {}
    results = {}
    for m in models:
        try:
            t1000_100 = probe(nutpie, m, 1000, 100, cache)
            t100_100  = probe(nutpie, m, 100, 100, cache)
            t100_1000 = probe(nutpie, m, 100, 1000, cache)
            warmup_s = t1000_100 - t100_100
            per_draw = (t100_1000 - t100_100) / 900
            results[m] = dict(t1000_100=t1000_100, t100_100=t100_100, t100_1000=t100_1000,
                              warmup_s_900_extra=round(warmup_s, 3),
                              sampling_ms_per_draw_per_chain=round(per_draw * 1000 / 4, 4))
            print(f"[nutpie-attr] {m}: warmup(900 extra iters)={warmup_s:.2f}s, "
                  f"sampling={per_draw*1000/4:.2f} ms/draw/chain", flush=True)
        except Exception as e:
            print(f'[nutpie-attr] {m}: FAILED {e}', flush=True)
    (OUT / 'nutpie_attribution.json').write_text(json.dumps(results, indent=2))
