#!/usr/bin/env python
"""Callgrind the SAME model via walnutpie's stan_cli (bridgestan .so driver):
per-gradient instruction comparison vs cmdstan services, same model math,
same iteration counts (100 warmup + 100 draws, 1 chain).
"""
import json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / 'external/walnutpie/build/examples/stan_cli'
OUT = ROOT / 'results/profile'

def parse_annotate(path):
    txt = path.read_text()
    total = None
    m = re.search(r'^\s*([\d,]+)\s+\(100\.0%\).*PROGRAM TOTALS', txt, re.M)
    if not m:
        m2 = re.findall(r'([\d,]+)\s+\(\s*[\d.]+%\)', next((l for l in txt.splitlines() if 'PROGRAM TOTALS' in l), ''))
        total = int(m2[0].replace(',', '')) if m2 else 0
    else:
        total = int(m.group(1).replace(',', ''))
    return total

def run(model, warmup=100, draws=100):
    od = OUT / model
    od.mkdir(exist_ok=True)
    ann = od / 'bridge_callgrind_annotate.txt'
    if not ann.exists():
        cg = od / 'bridge_callgrind.out'
        so = ROOT / 'bs_models' / f'model_{model}.so'
        cmd = ['valgrind', '--tool=callgrind', '--simulate-cache=yes',
               f'--callgrind-out-file={cg}', str(CLI), str(so),
               str(ROOT / f'data/{model}.json'), '--seed', '20260819',
               '--warmup', str(warmup), '--samples', str(draws),
               '--output', str(od / 'bridge_draws.csv')]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-300:])
        subprocess.run(['callgrind_annotate', str(cg)], stdout=open(ann, 'w'), check=False)
    total = parse_annotate(ann)
    # parse logp_grad calls from the run's stdout — rerun cheap without valgrind? use cached log if present
    log = od / 'bridge_cli.log'
    if not log.exists():
        so = ROOT / 'bs_models' / f'model_{model}.so'
        subprocess.run([str(CLI), str(so), str(ROOT / f'data/{model}.json'),
                        '--seed', '20260819', '--warmup', str(warmup), '--samples', str(draws)],
                       stdout=open(log, 'w'), stderr=subprocess.DEVNULL)
    STANZA = re.compile(r'logp_grad calls: (\d+)')
    calls = [int(m.group(1)) for m in STANZA.finditer(log.read_text())]
    return dict(model=model, total_instructions=total,
                warmup_calls=calls[0] if calls else None,
                sample_calls=calls[1] if len(calls) > 1 else None,
                ir_per_grad_sample=total / sum(calls) if calls else None)

if __name__ == '__main__':
    models = sys.argv[1].split(',') if len(sys.argv) > 1 else ['diamonds', 'lsat_model', 'radon_partially_pooled_noncentered', 'pilots']
    results = {}
    for m in models:
        try:
            r = run(m)
            results[m] = r
            print(f"[cg-bridge] {m}: total={r['total_instructions']:,} calls={r['sample_calls']} "
                  f"Ir/grad={r['ir_per_grad_sample']:,.0f}" if r['ir_per_grad_sample'] else m, flush=True)
        except Exception as e:
            print(f'[cg-bridge] {m}: FAILED {e}', flush=True)
    (OUT / 'bridge_callgrind.json').write_text(json.dumps(results, indent=2))
