#!/usr/bin/env python
"""W-38 (E1) runner: per-macro-step gradient accounting.

Two stages (both serialized, 1 process at a time, OMP_NUM_THREADS=1):
  canary  2 models (blr, pilots) x 4 chains, warmup=100 samples=100,
          seeds 20260819+c, deterministic DEFAULT inits, same binary run
          with WALNUTPIE_GRAD_ACCOUNTING=1 vs unset -> chain CSVs must be
          md5-identical (bit-identity gate).
  runs    1 chain, seed 20260819, warmup=100 samples=100, fixed inits
          (inits_w25 pf for blr/hier_2pl, inits_w36 for kronecker_gp/
          pilots, rep0/chain_0) on blr, hier_2pl, kronecker_gp, pilots;
          plus hier_2pl at warmup=1000 samples=1000 (production check);
          plus blr-default-init companion (the pf-init blr chain pins at
          100 warmup iters - pre-existing, see report).
Outputs: runs/w38/<stage>/..., runs/w38/accounting.json (raw parsed
counters per run).
"""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / 'external/walnutpie_w38/build/examples/stan_cli'
RUNS = ROOT / 'runs/w38'
BASE_SEED = 20260819
MODELS_SO = ROOT / 'bs_models_threads'

KV = re.compile(r'(\S+)=(\S+)')


def run_cli(model, out_csv, seed, warmup, samples, init_file=None,
            accounting=False):
    """Run stan_cli once; return parsed (stdout text, per-phase logp calls)."""
    Path(out_csv).unlink(missing_ok=True)  # CLI11 refuses existing outputs
    env = {**os.environ, 'OMP_NUM_THREADS': '1'}
    if accounting:
        env['WALNUTPIE_GRAD_ACCOUNTING'] = '1'
    else:
        env.pop('WALNUTPIE_GRAD_ACCOUNTING', None)
    cmd = [str(CLI), str(MODELS_SO / f'model_{model}.so'),
           str(ROOT / f'data/{model}.json'), '--seed', str(seed),
           '--output', str(out_csv),
           '--warmup', str(warmup), '--samples', str(samples)]
    if init_file is not None:
        cmd += ['--init-file', str(init_file)]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError(f'{model} rc={p.returncode}: {p.stderr[-2000:]}')
    calls = [int(m) for m in re.findall(r'logp_grad calls: (\d+)', p.stdout)]
    return p.stdout, calls


def parse_accounting(text):
    """Parse [grad-accounting] records into {phase: {...}}."""
    out = {}
    phase = None
    for line in text.splitlines():
        if not line.startswith('[grad-accounting]'):
            continue
        payload = line[len('[grad-accounting]'):].strip()
        if payload.startswith('phase='):
            phase = payload.split('=', 1)[1]
            out[phase] = {}
        elif phase is not None:
            out[phase].update(
                {k: int(v) for k, v in KV.findall(payload)})
    return out


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def canary():
    d = RUNS / 'canary'
    d.mkdir(parents=True, exist_ok=True)
    results = {}
    ok_all = True
    for model in ['blr', 'pilots']:
        for c in range(4):
            seed = BASE_SEED + c
            md5s = {}
            for arm in ['off', 'on']:
                csv = d / f'{model}_c{c}_{arm}.csv'
                text, _ = run_cli(model, csv, seed, 100, 100,
                                  accounting=(arm == 'on'))
                (d / f'{model}_c{c}_{arm}.log').write_text(text)
                md5s[arm] = md5(csv)
            same = md5s['off'] == md5s['on']
            ok_all &= same
            results[f'{model}_c{c}'] = {'off': md5s['off'], 'on': md5s['on'],
                                        'identical': same}
            print(f'canary {model} c{c}: {"IDENTICAL" if same else "MISMATCH"}')
    results['all_identical'] = ok_all
    (d / 'canary.json').write_text(json.dumps(results, indent=1))
    print(f'CANARY: {"PASS" if ok_all else "FAIL"}')
    return ok_all


def init_for(model):
    sub = 'inits_w25' if model in ('blr', 'hier_2pl') else 'inits_w36'
    p = ROOT / sub / model / 'rep0' / 'chain_0.txt'
    return p if p.exists() else None


def measurement():
    d = RUNS / 'meas'
    d.mkdir(parents=True, exist_ok=True)
    # (model, warmup, samples, use_fixed_init, seed, init_file_override, note)
    # kronecker_gp deviation: seed 20260819/chain_0 aborts deterministically
    # ("macro_time must be in (0, inf)" after nan logp grads) — the known
    # pre-existing W-36 failure mode (W-41's target). Use chain-1 seed/init.
    jobs = [('blr', 100, 100, True, BASE_SEED, None,
             'w25 pf init — chain pins at short warmup (pre-existing)'),
            ('hier_2pl', 100, 100, True, BASE_SEED, None, ''),
            ('kronecker_gp', 100, 100, True, BASE_SEED + 1,
             ROOT / 'inits_w36/kronecker_gp/rep0/chain_1.txt',
             'seed/init deviation: chain_0 aborts (W-36 known failure)'),
            ('pilots', 100, 100, True, BASE_SEED, None, ''),
            ('hier_2pl', 1000, 1000, True, BASE_SEED, None,
             'production settings'),
            ('blr', 100, 100, False, BASE_SEED, None,
             'default-init companion (healthy-chain reference)')]
    out = {}
    for model, wu, ns, use_init, seed, init_override, note in jobs:
        tag = f'{model}_w{wu}_s{ns}' + ('' if use_init else '_defaultinit')
        init = init_override if init_override is not None else (
            init_for(model) if use_init else None)
        csv = d / f'{tag}.csv'
        print(f'run {tag} ...', flush=True)
        try:
            text, calls = run_cli(model, csv, seed, wu, ns,
                                  init_file=init, accounting=True)
        except RuntimeError as e:
            out[tag] = {'model': model, 'error': str(e)[:500], 'note': note}
            print(f'  FAILED (recorded): {str(e)[:200]}')
            continue
        (d / f'{tag}.log').write_text(text)
        acc = parse_accounting(text)
        out[tag] = {'model': model, 'warmup': wu, 'samples': ns, 'seed': seed,
                    'init': str(init) if init else 'default', 'note': note,
                    'logp_calls': calls, 'accounting': acc}
        # consistency: kernel_total + 2 boundary == warmup calls; +0 sampling
        for ph, extra in (('warmup', 2), ('sampling', 0)):
            kt = acc.get(ph, {}).get('kernel_total')
            if kt is not None:
                print(f'  {ph}: kernel_total+{extra}={kt + extra}')
        print(f'  logp_calls per phase: {calls}')
    (RUNS / 'accounting.json').write_text(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'canary':
        sys.exit(0 if canary() else 1)
    if len(sys.argv) > 1 and sys.argv[1] == 'meas':
        measurement()
        sys.exit(0)
    ok = canary()
    if not ok:
        sys.exit(1)
    measurement()
