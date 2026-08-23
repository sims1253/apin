#!/usr/bin/env python
"""W-42 gate runner: init-protocol guard (never start a chain at
non-finite logp).

Arms:
  pre   exp/safe-adapt-defaults binary @ 43b6435 (build_w36exp) — the
        pre-change reference for every md5 comparison
  post  exp/init-guard binary (walnutpie_w42/build_w42) — the guard
  w41   exp/freeze-clamp binary (walnutpie_w41/build_w41) — the pinned
        1000-iter "recovery" baseline for the wall-saved comparison

Gates (pre-registered in WORKLOG W-42):
  (a) canary bit-identity: 12 file-init cells (hier_2pl + lsat_model rep0
      inits_w25 pf, radon_partially_pooled_noncentered rep0 inits_w36,
      chains 0-3, seeds 20260819+c) + 4 random-init cells (radon, no
      --init-file) — post md5 == pre md5, 16/16, zero WALNUTS warnings.
  (b) fail-fast: kronecker_gp rep0 c0 seed 20260819 + lotka_volterra
      rep1 c0 seed 20261819, inits_w36 chain_0.txt — post errors
      immediately (rc != 0, guard banner, no warmup stanza); record wall
      vs the w41 pinned completion and the pre freeze-abort.
  (c) random-init recovery: kronecker_gp seed 20260820 --init 2.2 (first
      draw -inf, retry accepted — found by seed trial) completes rc=0;
      two identical invocations md5-identical with identical retry
      counts; plus the exhaustion case (seed 20260819 --init 2.5: 100/100
      rejected -> loud error).
  (d) no collateral: eight_schools_centered rep1 c2 (20261821) + diamonds
      rep2 c1 (20262820) post md5 == pre md5.

All runs: 4 SEQUENTIAL single-chain invocations semantics (one chain
process at a time), OMP_NUM_THREADS=1, warmup=1000 samples=1000 unless
noted. Raw logs under runs/w42/<arm>/ (untracked).
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w42'
PRE_CLI = ROOT / 'external/walnutpie/build_w36exp/examples/stan_cli'
POST_CLI = ROOT / 'external/walnutpie_w42/build_w42/examples/stan_cli'
W41_CLI = ROOT / 'external/walnutpie_w41/build_w41/examples/stan_cli'
SO = ROOT / 'bs_models_threads'
WARMUP, DRAWS = 1000, 1000


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def run(arm, cli, model, seed, tag, init=None, warmup=WARMUP, samples=DRAWS,
        extra=()):
    out_dir = RUNS / arm
    out_dir.mkdir(parents=True, exist_ok=True)
    csv = out_dir / f'{tag}.csv'
    log = out_dir / f'{tag}.log'
    cmd = [str(cli), str(SO / f'model_{model}.so'),
           str(ROOT / f'data/{model}.json'), '--seed', str(seed),
           '--output', str(csv), '--warmup', str(warmup),
           '--samples', str(samples)]
    if init:
        cmd += ['--init-file', str(init)]
    cmd += list(extra)
    env = {**__import__('os').environ, 'OMP_NUM_THREADS': '1'}
    t0 = time.time()
    with log.open('w') as lf:
        p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env)
    wall = time.time() - t0
    text = log.read_text()
    rec = dict(arm=arm, tag=tag, rc=p.returncode, wall=round(wall, 2),
               retries=len(re.findall(r'random init draw rejected', text)),
               guard_error='WALNUTS ERROR (init guard)' in text,
               warnings=len(re.findall(r'WALNUTS WARNING', text)),
               warmup_calls=None, csv_md5=md5(csv) if csv.exists() else None,
               log=str(log))
    for m in re.finditer(r'logp_grad calls: (\d+)', text):
        rec['warmup_calls'] = int(m.group(1))  # first stanza = warmup
        break
    return rec


def gate_a():
    cells = []
    for model, sub in [('hier_2pl', 'inits_w25'), ('lsat_model', 'inits_w25'),
                       ('radon_partially_pooled_noncentered', 'inits_w36')]:
        for c in range(4):
            cells.append((model, 20260819 + c,
                          ROOT / sub / model / 'rep0' / f'chain_{c}.txt',
                          f'canary_file_{model}_c{c}'))
    for c in range(4):  # random-init cells
        cells.append(('radon_partially_pooled_noncentered', 20260819 + c,
                      None, f'canary_rand_radon_c{c}'))
    out = []
    for model, seed, init, tag in cells:
        pre = run('pre', PRE_CLI, model, seed, tag, init=init)
        post = run('post', POST_CLI, model, seed, tag, init=init)
        ok = (pre['rc'] == 0 and post['rc'] == 0 and
              pre['csv_md5'] == post['csv_md5'] and
              post['warnings'] == 0 and not post['guard_error'])
        out.append(dict(cell=tag, ok=ok, pre_md5=pre['csv_md5'],
                        post_md5=post['csv_md5'],
                        pre_calls=pre['warmup_calls'],
                        post_calls=post['warmup_calls'],
                        post_warnings=post['warnings'],
                        pre_wall=pre['wall'], post_wall=post['wall']))
        print(f"[a] {tag}: {'OK' if ok else 'FAIL'} "
              f"(calls {pre['warmup_calls']}->{post['warmup_calls']}, "
              f"wall {pre['wall']}/{post['wall']}s)", flush=True)
    n_ok = sum(r['ok'] for r in out)
    print(f'[a] CANARY: {n_ok}/{len(out)}', flush=True)
    return dict(cells=out, passed=n_ok, total=len(out),
                gate=n_ok == len(out))


def gate_b():
    out = []
    for model, rep, seed in [('kronecker_gp', 0, 20260819),
                             ('lotka_volterra', 1, 20261819)]:
        init = ROOT / 'inits_w36' / model / f'rep{rep}' / 'chain_0.txt'
        tag = f'failfast_{model}_rep{rep}_c0'
        post = run('post', POST_CLI, model, seed, tag, init=init)
        w41 = run('w41', W41_CLI, model, seed, tag, init=init)
        pre = run('pre', PRE_CLI, model, seed, tag, init=init)
        banner = ''
        log = Path(post['log']).read_text()
        m = re.search(r'WALNUTS ERROR \(init guard\): (.*)', log)
        if m:
            banner = m.group(1)
        ok = (post['rc'] != 0 and post['guard_error'] and
              post['warmup_calls'] is None and
              post['wall'] < min(w41['wall'], pre['wall']))
        out.append(dict(cell=tag, ok=ok, post_rc=post['rc'],
                        post_wall=post['wall'], w41_rc=w41['rc'],
                        w41_wall=w41['wall'], pre_rc=pre['rc'],
                        pre_wall=pre['wall'],
                        wall_saved_vs_w41=round(w41['wall'] - post['wall'], 2),
                        wall_saved_vs_pre=round(pre['wall'] - post['wall'], 2),
                        banner=banner))
        print(f"[b] {model} rep{rep} c0: post rc={post['rc']} "
              f"wall={post['wall']}s | w41 rc={w41['rc']} "
              f"wall={w41['wall']}s | pre rc={pre['rc']} "
              f"wall={pre['wall']}s | saved {w41['wall']-post['wall']:.1f}s "
              f"vs pinned", flush=True)
    ok = all(r['ok'] for r in out)
    print(f'[b] FAIL-FAST: {"PASS" if ok else "FAIL"}', flush=True)
    return dict(cells=out, gate=ok)


def gate_c():
    # Recovery: first draw -inf at --init 2.2, retry accepted (seed trial).
    r1 = run('post', POST_CLI, 'kronecker_gp', 20260820, 'recovery_run1',
             extra=['--init', '2.2'])
    r2 = run('post', POST_CLI, 'kronecker_gp', 20260820, 'recovery_run2',
             extra=['--init', '2.2'])
    # Exhaustion: all 100 draws -inf at --init 2.5 -> loud error.
    ex = run('post', POST_CLI, 'kronecker_gp', 20260819, 'exhaust_run',
             extra=['--init', '2.5'])
    det = (r1['rc'] == 0 and r2['rc'] == 0 and
           r1['csv_md5'] == r2['csv_md5'] and
           r1['retries'] == r2['retries'] and r1['retries'] >= 1)
    exh = (ex['rc'] != 0 and ex['guard_error'] and ex['retries'] == 100)
    print(f"[c] recovery: rc={r1['rc']}/{r2['rc']} retries={r1['retries']}/"
          f"{r2['retries']} md5_match={r1['csv_md5'] == r2['csv_md5']} | "
          f"exhaustion: rc={ex['rc']} retries={ex['retries']}", flush=True)
    return dict(recovery_run1=r1, recovery_run2=r2, exhaustion=ex,
                deterministic=det, exhaustion_ok=exh,
                gate=det and exh)


def gate_d():
    out = []
    for model, rep, c, seed in [('eight_schools_centered', 1, 2, 20261821),
                                ('diamonds', 2, 1, 20262820)]:
        init = ROOT / 'inits_w36' / model / f'rep{rep}' / f'chain_{c}.txt'
        tag = f'collat_{model}_rep{rep}_c{c}'
        pre = run('pre', PRE_CLI, model, seed, tag, init=init)
        post = run('post', POST_CLI, model, seed, tag, init=init)
        ok = (pre['rc'] == 0 and post['rc'] == 0 and
              pre['csv_md5'] == post['csv_md5'] and post['warnings'] == 0)
        out.append(dict(cell=tag, ok=ok, pre_md5=pre['csv_md5'],
                        post_md5=post['csv_md5']))
        print(f"[d] {tag}: {'OK' if ok else 'FAIL'}", flush=True)
    ok = all(r['ok'] for r in out)
    print(f'[d] NO-COLLATERAL: {"PASS" if ok else "FAIL"}', flush=True)
    return dict(cells=out, gate=ok)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'abcd'
    res = {}
    if 'a' in which:
        res['a'] = gate_a()
    if 'b' in which:
        res['b'] = gate_b()
    if 'c' in which:
        res['c'] = gate_c()
    if 'd' in which:
        res['d'] = gate_d()
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results/w42_gates.json').write_text(json.dumps(res, indent=1))
    print('W42 GATES DONE:', {k: v.get('gate') for k, v in res.items()},
          flush=True)


if __name__ == '__main__':
    main()
