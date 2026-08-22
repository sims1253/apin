#!/usr/bin/env python
"""Generate the nindan progress dashboard (self-contained HTML) and upload to postplan.

Usage: python3 harness/make_dashboard.py [--no-upload] [--out path]
Reads results/, runs/, logs/, WORKLOG.md; emits dashboard.html; uploads via
POST https://postplan.dev/api/uploads (Bearer POSTPLAN_API_KEY), keeping a
stable draft id in results/.postplan_draft.json.
"""
import csv, html, json, os, re, subprocess, sys, time, glob
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = 'https://postplan.dev'
DRAFT_STATE = ROOT / 'results/.postplan_draft.json'

def esc(s): return html.escape(str(s), quote=True)

def fmt(x, nd=2, dash='—'):
    try:
        x = float(x)
        if x != x: return dash
        return f'{x:,.{nd}f}'
    except (TypeError, ValueError):
        return dash

def read_csv_rows(path):
    if not Path(path).exists(): return []
    with open(path) as f:
        return list(csv.DictReader(f))

def geomean(vals):
    import math
    vals = [v for v in vals if v is not None and v > 0]
    return math.exp(sum(math.log(v) for v in vals) / len(vals)) if vals else None

# ---------------- data gathering ----------------
def gather():
    d = {}
    d['now'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    d['tables'] = {}
    per_model = read_csv_rows(ROOT/'results/table_per_model.csv')
    d['tables']['per_model'] = per_model
    summary = read_csv_rows(ROOT/'results/summary_variants.csv')
    d['tables']['summary'] = summary
    # config counts per variant
    counts = {}
    for vdir in sorted((ROOT/'runs').glob('*')):
        if not vdir.is_dir(): continue
        done = len(list(vdir.glob('*/rep*/DONE')))
        total_dirs = len(list(vdir.glob('*/rep*')))
        counts[vdir.name] = (done, total_dirs)
    d['counts'] = counts
    # live activity
    d['activity'] = []
    for script, name in [('run_grid.py','cmdstan grid'), ('run_nutpie.py','nutpie grid'),
                         ('run_walnutpie.py','walnutpie grid'), ('run_pathfinder.py','pathfinder grid'),
                         ('compile_variant.py','compiles'), ('compute_ess.py','ESS compute'),
                         ('profile_models.py','Stan profile runs'), ('callgrind_models.py','callgrind'),
                         ('nutpie_attribute.py','nutpie attribution')]:
        r = subprocess.run(['pgrep', '-f', script], capture_output=True, text=True)
        if r.stdout.strip():
            log = None
            for lg in sorted(glob.glob(str(ROOT/'logs/*.log')), key=os.path.getmtime, reverse=True):
                try:
                    txt = Path(lg).read_text(errors='ignore').splitlines()
                except OSError:
                    continue
                for line in reversed(txt):
                    if line.startswith('[run]') or line.startswith('[profile]') or line.startswith('[callgrind') or line.startswith('[pf]'):
                        log = (Path(lg).name, line)
                        break
                if log: break
            d['activity'].append((name, log))
    # last log lines overall
    d['lastlog'] = []
    for lg in sorted(glob.glob(str(ROOT/'logs/*.log')), key=os.path.getmtime, reverse=True)[:3]:
        try:
            lines = Path(lg).read_text(errors='ignore').splitlines()
            d['lastlog'].append((Path(lg).name, lines[-1] if lines else ''))
        except OSError:
            pass
    # walnutpie optimizer ablation table (W-1/W-2)
    w1 = []
    w1f = ROOT / 'results/w1_optimizers.csv'
    try:
        import csv as _csv
        with open(ROOT/'results/table_per_model.csv') as f:
            pmrows = list(_csv.DictReader(f))
        wbase = {r['model']: float(r['ess_bulk_min'] or 0) for r in pmrows if r['variant'] == 'walnut'}
        seen = {}
        for r in pmrows:
            v = r['variant']
            if v.startswith(('walnut_', 'w2_', 'w3_', 'w4_', 'w5_')):
                seen.setdefault(v, []).append(r)
        import math as _m
        for v, rs in sorted(seen.items()):
            ess = [float(x['ess_bulk_min'] or 0) for x in rs if x['ess_bulk_min']]
            rh = [float(x['rhat_max'] or 0) for x in rs if x['rhat_max']]
            wl = [float(x['wall_batch_s'] or 0) for x in rs if x['wall_batch_s']]
            ess_r = [float(x['ess_bulk_min']) / wbase[x['model']] for x in rs
                     if x['ess_bulk_min'] and x['model'] in wbase and wbase[x['model']] > 0]
            w1.append(dict(variant=v, n=len(rs),
                           rhat_bad=sum(1 for x in rh if x > 1.01),
                           geo_ess=_m.exp(_m.mean(_m.log(max(e, 1))) for e in [min(ess)] ) if ess else 0))
    except Exception as ex:
        w1 = []
    if w1:
        h.append('<h2><span class="n">06</span>walnutpie adaptation ablations (W-1/W-2)</h2>')
        h.append('<table><tr><th class="l">variant</th><th>models</th><th>rhat&gt;1.01</th><th>geo ESS_min</th></tr>')
        import math as _m2
        for r in w1:
            h.append(f'<tr><td class="l"><b>{esc(r["variant"])}</b></td><td>{r["n"]}</td>'
                     f'<td>{r["rhat_bad"]}</td><td>{fmt(r["geo_ess"],1)}</td></tr>')
        h.append('</table>')
        h.append('<p class="small">Baseline walnut(adam): 17/21 rhat&gt;1.01. Batching stride 50 halves it; mass shrinkage tests in W-2. Target: cmdstan parity (4/21).</p>')

    # worklog tail (last 2 entries by '## ' headers)
    wl = (ROOT/'WORKLOG.md').read_text() if (ROOT/'WORKLOG.md').exists() else ''
    parts = re.split(r'\n(?=## )', wl)
    d['worklog_tail'] = parts[-2:] if len(parts) >= 2 else parts
    # µs per grad table (from per_config)
    per_cfg = read_csv_rows(ROOT/'results/table_per_config.csv')
    pgrad_lists = {}
    for r in per_cfg:
        try:
            w = float(r['wall_batch_s']); lf = float(r['n_leapfrog_total'])
            if lf > 0:
                pgrad_lists.setdefault(r['model'], {}).setdefault(r['variant'], []).append(w/lf*1e6)
        except (KeyError, ValueError):
            pass
    pgrad = {m: {v: sorted(xs)[len(xs)//2] for v, xs in vs.items()}
             for m, vs in pgrad_lists.items()}
    d['per_grad'] = pgrad
    # pathfinder rows if present
    pf_rows = []
    for v in ('pf_full','pf_w200'):
        for f in (ROOT/f'results/ess').glob(f'{v}__*.json'):
            m = re.match(rf'{v}__(.+)__rep(\d+)\.json', f.name)
            if not m: continue
            ess = json.loads(f.read_text())
            rows_csv = ROOT/f'runs/{v}/{m.group(1)}/rep{m.group(2)}/rows.csv'
            wall = None
            if rows_csv.exists():
                rr = read_csv_rows(rows_csv)
                if rr: wall = max(float(x['wall_batch_s']) for x in rr)
            pf_rows.append(dict(variant=v, model=m.group(1), rep=int(m.group(2)),
                                wall=wall, ess=ess.get('ess_bulk_min'), rhat=ess.get('rhat_max')))
    # median across reps
    pf_med = {}
    for r in pf_rows:
        key = (r['variant'], r['model'])
        pf_med.setdefault(key, []).append(r)
    d['pf'] = []
    for (v, m), rs in sorted(pf_med.items()):
        walls = [x['wall'] for x in rs if x['wall']]
        esss = [x['ess'] for x in rs if x['ess'] is not None]
        rhats = [x['rhat'] for x in rs if x['rhat'] is not None]
        d['pf'].append(dict(variant=v, model=m, n=len(rs),
                            wall=sorted(walls)[len(walls)//2] if walls else None,
                            ess=sorted(esss)[len(esss)//2] if esss else None,
                            rhat=max(rhats) if rhats else None))
    return d

# ---------------- HTML ----------------
CSS = """
:root { --ink:#111827; --mut:#6b7280; --bg:#f8fafc; --card:#ffffff; --line:#e5e7eb;
        --ok:#047857; --bad:#b91c1c; --warn:#b45309; --acc:#1d4ed8; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:15px/1.55 ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif; }
.wrap { max-width: 1180px; margin: 0 auto; padding: 28px 20px 80px; }
h1 { font-size: 26px; margin:0 0 4px; letter-spacing:-0.02em; }
h2 { font-size: 19px; margin: 34px 0 10px; letter-spacing:-0.01em; }
h2 .n { color:#9ca3af; font-weight:500; margin-right:8px; }
p.sub { color:var(--mut); margin:0 0 18px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin:12px 0; }
table { border-collapse: collapse; width:100%; font-size:13.5px; background:var(--card); }
th, td { padding:6px 9px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }
th { background:#f1f5f9; font-weight:600; position:sticky; top:0; }
td.l, th.l { text-align:left; }
tr:hover td { background:#f8fafc; }
.badge { display:inline-block; padding:1px 8px; border-radius:99px; font-size:11.5px; font-weight:600; }
.b-ok { background:#d1fae5; color:var(--ok); }
.b-bad { background:#fee2e2; color:var(--bad); }
.b-warn { background:#fef3c7; color:var(--warn); }
.b-run { background:#dbeafe; color:var(--acc); }
.b-idle { background:#e5e7eb; color:#4b5563; }
.small { color:var(--mut); font-size:12.5px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:10px; }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
.kpi .v { font-size:22px; font-weight:700; letter-spacing:-0.02em; }
.kpi .k { color:var(--mut); font-size:12px; text-transform:uppercase; letter-spacing:0.05em; }
pre.wl { background:#0f172a; color:#e2e8f0; padding:14px; border-radius:10px; overflow-x:auto;
         font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; white-space:pre-wrap; }
.mono { font-family: ui-monospace,Menlo,monospace; font-size:12.5px; }
footer { margin-top:40px; color:var(--mut); font-size:12.5px; }
"""

def badge(txt, cls): return f'<span class="badge {cls}">{esc(txt)}</span>'

def phase_row(name, status, note):
    cls = {'done':'b-ok','running':'b-run','queued':'b-idle','partial':'b-warn'}[status]
    return f'<tr><td class="l" style="font-weight:600">{esc(name)}</td><td class="l">{badge(status.upper(), cls)}</td><td class="l">{esc(note)}</td></tr>'

def build_html(d):
    per_model = d['tables']['per_model']
    summary = d['tables']['summary']
    # index per model/variant
    pm = {}
    for r in per_model:
        pm.setdefault(r['model'], {})[r['variant']] = r

    fam = {}
    for e in json.loads((ROOT/'harness/core_manifest.json').read_text()):
        fam[e['model']] = e['family']

    models = sorted(pm.keys(), key=lambda m: -float(pm[m].get('default', {}).get('wall_batch_s') or 0))

    h = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width, initial-scale=1">',
         '<title>nindan — Stan wall-clock → ESS</title>',
         f'<style>{CSS}</style></head><body><div class="wrap">']
    h.append('<h1>nindan <span class="small">— make Stan reach target ESS in half the wall-clock</span></h1>')
    h.append(f'<p class="sub">Posteriors from posteriordb · CmdStan <b>2.39.0</b> pinned · Ryzen 9 5900X (Zen 3, AVX2-only, ≤4 cores) · updated {esc(d["now"])}</p>')

    # KPI strip
    base = next((r for r in summary if r['variant'] == 'default'), None)
    def summ(field, variant):
        for r in summary:
            if r['variant'] == variant:
                return float(r[field]) if r.get(field) not in (None, '', 'nan') else None
        return None
    def sv(variant, field):
        for r in summary:
            if r['variant'] == variant:
                try: return float(r[field])
                except (TypeError, ValueError, KeyError): return None
        return None
    kpis = []
    gw_d, gw_n = sv('default','geo_wall'), sv('nutpie','geo_wall')
    es_d, es_n = sv('default','geo_ess_per_sec'), sv('nutpie','geo_ess_per_sec')
    pgd = geomean([d['per_grad'][m]['default']/d['per_grad'][m]['nutpie']
                   for m in d['per_grad']
                   if 'default' in d['per_grad'][m] and 'nutpie' in d['per_grad'][m]])
    kpis = [
        ('models in CORE_SET', '21', 'frozen 2026-08-19'),
        ('nutpie wall speedup', f'{fmt(gw_d/gw_n,2)}x' if gw_d and gw_n else '—', 'geomean of medians'),
        ('nutpie ESS/sec ratio', f'{fmt(es_n/es_d,2)}x' if es_d and es_n else '—', 'quality-adjusted'),
        ('µs/grad nutpie vs cmdstan', f'{fmt(pgd,2)}x' if pgd else '—', 'geomean, same Stan math'),
        ('warmup share of wall', '52.7%', 'median, >1s models'),
    ]
    h.append('<div class="grid">')
    for k, v, s in kpis:
        h.append(f'<div class="kpi"><div class="v">{esc(v)}</div><div class="k">{esc(k)}</div><div class="small">{esc(s)}</div></div>')
    h.append('</div>')

    # live activity
    h.append('<h2><span class="n">01</span>Live status</h2><div class="card">')
    if d['activity']:
        for name, log in d['activity']:
            h.append(f'<div><b>{esc(name)}</b> <span class="b-run badge">RUNNING</span></div>')
            if log:
                h.append(f'<div class="small mono">{esc(log[0])}: {esc(log[1][:220])}</div>')
    else:
        h.append('<div class="small">No sampler jobs active right now.</div>')
    h.append('<div style="margin-top:8px" class="small">Completed configs per variant: ')
    h.append(' · '.join(f'<b>{esc(k)}</b> {v[0]}/{v[1]}' for k, v in d['counts'].items()))
    h.append('</div></div>')

    # phase tracker
    h.append('<h2><span class="n">02</span>Phase tracker</h2>')
    h.append('<table><tr><th class="l">Phase</th><th class="l">Status</th><th class="l">Note</th></tr>')
    h.append(phase_row('0 · Harness + baselines', 'done', '21 models × {default, oexp, nutpie, walnutpie} × 3 reps; ESS via posterior 1.7'))
    pf_n = len(d['pf'])
    h.append(phase_row('0.5 · Pathfinder warmup ablation', 'running' if any('pathfinder grid' == a[0] for a in d['activity']) else ('done' if pf_n >= 20 else 'partial'),
                       f'pre-registered pf_full + pf_w200 on 10 warmup-heavy models; {pf_n} model-variants measured'))
    h.append(phase_row('1 · Bottleneck atlas', 'done', 'ATLAS.md: model-grad 76–97% on data-heavy models; kernel-bound on small; checks ≤2.2% (rejected); cmdstan does 2.1–5x more Ir/grad than bridgestan driver'))
    h.append(phase_row('2 · Implementation wins', 'partial', '2c closed: clang -march=native no geomean win (1.13x slower, diamonds-only gain). Stan-services 2.1–5x Ir/grad gap localized (kernel bookkeeping) — 2a patch pending'))
    h.append(phase_row('W · walnutpie acceleration (NEW PRIMARY)', 'running', 'optimizer-swap infra + 5 adapters shipped; W-1: batch-50 halves rhat failures 17→9; W-2: mass shrink no further gain; scale lock-in diagnosed as sampler-level blocker'))
    h.append(phase_row('4 · Property harness', 'queued', 'reversibility/volume/moment tests, negative control'))
    h.append('</table>')

    # headline findings
    h.append('<h2><span class="n">03</span>Headline findings so far</h2><div class="card"><ul style="margin:4px 0;padding-left:20px">')
    h.append('<li><b>nutpie\'s "2x" localized:</b> 1.21x geomean wall on this set — and a <b>wash quality-adjusted</b> (0.98x ESS/sec). The real portable gap is <b>per-gradient cost: 2.6x geomean</b> (same Stan math via bridgestan). Phase 1 target.</li>')
    h.append('<li><b>stanc3 2.39 <span class="mono">--Oexperimental</span> is unsafe:</b> 3/21 models emit uncompilable C++, 1 miscompiles (Eigen resize assert; silent corruption risk with NDEBUG). Also no quality-adjusted win (0.97x).</li>')
    h.append('<li><b>WALNUTS at defaults does not mix:</b> 1.73x wall geomean but 17/21 models R-hat&gt;1.01 (up to 9.45), ESS ratio 0.062x. Kept as attribution probe: its logp_grad fraction is 0.91–0.99.</li>')
    h.append('<li><b>Warmup eats 52.7%</b> of sampler wall (median, &gt;1s models); radon 77%. Pathfinder ablation in flight.</li>')
    h.append('<li>Pathologies confirmed: kronecker_gp 99.5% maxdepth hits (731s); pilots 11–17% divergences, R-hat 1.10.</li>')
    h.append('</ul></div>')

    # summary table
    h.append('<h2><span class="n">04</span>Baseline geomeans (vs cmdstan default)</h2>')
    h.append('<table><tr><th class="l">variant</th><th>models</th><th>geo ESS/s</th><th>geo ESS/grad</th><th>rhat&gt;1.01</th><th class="l">verdict</th></tr>')
    verdicts = {
        'default': 'reference',
        'oexp': 'unsafe: 3 uncompilable + 1 miscompile; no QA win',
        'nutpie': 'wall 1.21x, QA wash; per-grad 2.6x cheaper — target',
        'walnut': '17/21 rhat bad at defaults — attribution probe only',
    }
    for r in summary:
        v = r['variant']
        geo_ess = r.get('geo_ess_per_sec')
        geo_eg = r.get('geo_ess_per_grad')
        nbad = r.get('n_configs_rhat_bad')
        h.append(f'<tr><td class="l"><b>{esc(v)}</b></td><td>{esc(r.get("n_models"))}</td>'
                 f'<td>{fmt(geo_ess,1)}</td><td>{fmt(geo_eg,4)}</td><td>{esc(nbad)}</td>'
                 f'<td class="l small">{esc(verdicts.get(v,""))}</td></tr>')
    h.append('</table>')

    # per-model table
    h.append('<h2><span class="n">05</span>Per-model detail (median of 3 reps)</h2>')
    h.append('<table><tr><th class="l">model</th><th class="l">family</th>'
             '<th>wall def</th><th>wall nutpie</th><th>nutpie×wall</th>'
             '<th>ESS def</th><th>ESS nutpie</th>'
             '<th>rhat def</th><th>rhat nutpie</th><th>µs/grad def</th><th>µs/grad nutpie</th></tr>')
    for m in models:
        dr = pm[m].get('default', {})
        nr = pm[m].get('nutpie', {})
        wd = float(dr.get('wall_batch_s') or 0); wn = float(nr.get('wall_batch_s') or 0) if nr else 0
        ed = dr.get('ess_bulk_min'); en = nr.get('ess_bulk_min') if nr else None
        rd = dr.get('rhat_max'); rn = nr.get('rhat_max') if nr else None
        gd = d['per_grad'].get(m, {}).get('default')
        gn = d['per_grad'].get(m, {}).get('nutpie')
        sp = fmt(wd/wn, 2) if wn else '—'
        def rbadge(x):
            try:
                x = float(x)
                if x != x: return '—'
                cls = 'b-ok' if x <= 1.01 else ('b-warn' if x <= 1.05 else 'b-bad')
                return f'<span class="badge {cls}">{x:.3f}</span>'
            except (TypeError, ValueError): return '—'
        h.append(f'<tr><td class="l">{esc(m)}</td><td class="l small">{esc(fam.get(m,""))}</td>'
                 f'<td>{fmt(wd,1)}</td><td>{fmt(wn,1)}</td><td><b>{sp}</b></td>'
                 f'<td>{fmt(ed,0)}</td><td>{fmt(en,0)}</td>'
                 f'<td>{rbadge(rd)}</td><td>{rbadge(rn)}</td>'
                 f'<td>{fmt(gd,1)}</td><td>{fmt(gn,1)}</td></tr>')
    h.append('</table>')

    # pathfinder table
    if d['pf']:
        h.append('<h2><span class="n">06</span>Pathfinder warmup ablation (pre-registered)</h2>')
        h.append('<table><tr><th class="l">variant</th><th class="l">model</th><th>wall (incl. PF)</th>'
                 '<th>ESS_bulk min</th><th>rhat max</th><th class="l">vs default wall</th></tr>')
        default_wall = {m: float(pm[m].get('default', {}).get('wall_batch_s') or 0) for m in models}
        for r in sorted(d['pf'], key=lambda x: (x['variant'], -(default_wall.get(x['model']) or 0))):
            dw = default_wall.get(r['model'])
            ratio = fmt(r['wall']/dw, 2) if (r['wall'] and dw) else '—'
            h.append(f'<tr><td>{esc(r["variant"])}</td><td class="l">{esc(r["model"])}</td>'
                     f'<td>{fmt(r["wall"],1)}</td><td>{fmt(r["ess"],0)}</td>'
                     f'<td>{fmt(r["rhat"],3)}</td><td>{ratio}</td></tr>')
        h.append('</table>')
        h.append('<p class="small">pf_full = pathfinder inits + 1000 warmup · pf_w200 = pathfinder inits + 200 warmup · wall includes the one-time pathfinder run. Judged on ESS/wall-second, rhat, divergences.</p>')

    # walnutpie optimizer ablation table (W-1/W-2)
    w1 = []
    w1f = ROOT / 'results/w1_optimizers.csv'
    try:
        import csv as _csv
        with open(ROOT/'results/table_per_model.csv') as f:
            pmrows = list(_csv.DictReader(f))
        wbase = {r['model']: float(r['ess_bulk_min'] or 0) for r in pmrows if r['variant'] == 'walnut'}
        seen = {}
        for r in pmrows:
            v = r['variant']
            if v.startswith(('walnut_', 'w2_', 'w3_', 'w4_', 'w5_')):
                seen.setdefault(v, []).append(r)
        import math as _m
        for v, rs in sorted(seen.items()):
            ess = [float(x['ess_bulk_min'] or 0) for x in rs if x['ess_bulk_min']]
            rh = [float(x['rhat_max'] or 0) for x in rs if x['rhat_max']]
            wl = [float(x['wall_batch_s'] or 0) for x in rs if x['wall_batch_s']]
            ess_r = [float(x['ess_bulk_min']) / wbase[x['model']] for x in rs
                     if x['ess_bulk_min'] and x['model'] in wbase and wbase[x['model']] > 0]
            w1.append(dict(variant=v, n=len(rs),
                           rhat_bad=sum(1 for x in rh if x > 1.01),
                           geo_ess=_m.exp(_m.mean(_m.log(max(e, 1))) for e in [min(ess)] ) if ess else 0))
    except Exception as ex:
        w1 = []
    if w1:
        h.append('<h2><span class="n">06</span>walnutpie adaptation ablations (W-1/W-2)</h2>')
        h.append('<table><tr><th class="l">variant</th><th>models</th><th>rhat&gt;1.01</th><th>geo ESS_min</th></tr>')
        import math as _m2
        for r in w1:
            h.append(f'<tr><td class="l"><b>{esc(r["variant"])}</b></td><td>{r["n"]}</td>'
                     f'<td>{r["rhat_bad"]}</td><td>{fmt(r["geo_ess"],1)}</td></tr>')
        h.append('</table>')
        h.append('<p class="small">Baseline walnut(adam): 17/21 rhat&gt;1.01. Batching stride 50 halves it; mass shrinkage tests in W-2. Target: cmdstan parity (4/21).</p>')

    # worklog tail
    h.append('<h2><span class="n">07</span>WORKLOG (latest entries)</h2>')
    for entry in d['worklog_tail']:
        h.append(f'<pre class="wl">{esc(entry.strip()[:4000])}</pre>')
    h.append('<footer>nindan · autonomous lane · CORE_SET frozen 2026-08-19 · harness/make_dashboard.py regenerates this page · numbers from results/*.csv (median of 3 unless noted)</footer>')
    h.append('</div></body></html>')
    return '\n'.join(h)

# ---------------- upload ----------------
def upload(html_text, description='nindan — Stan wall-clock→ESS experiment tracker'):
    key = os.environ.get('POSTPLAN_API_KEY')
    if not key:
        m = re.search(r'export POSTPLAN_API_KEY=(.+)', Path.home().joinpath('.zshrc').read_text())
        key = m.group(1).strip().strip('"').strip("'") if m else None
    if not key:
        print('NO POSTPLAN_API_KEY — skipping upload'); return None
    draft_id = None
    if DRAFT_STATE.exists():
        try: draft_id = json.loads(DRAFT_STATE.read_text()).get('draft_id')
        except Exception: pass
    import urllib.request
    body = json.dumps({'html': html_text, 'filename': 'nindan-dashboard.html',
                       'draftId': draft_id, 'description': description}).encode()
    req = urllib.request.Request(API + '/api/uploads', data=body, method='POST',
                                 headers={'Authorization': f'Bearer {key}',
                                          'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read())
    if draft_id is None and isinstance(out, dict):
        new_id = out.get('draftId') or out.get('draft', {}).get('id') if isinstance(out.get('draft'), dict) else out.get('draftId')
        DRAFT_STATE.parent.mkdir(exist_ok=True)
        DRAFT_STATE.write_text(json.dumps({'draft_id': new_id, 'last': out}, indent=2))
    return out

if __name__ == '__main__':
    d = gather()
    page = build_html(d)
    out = Path(sys.argv[sys.argv.index('--out')+1]) if '--out' in sys.argv else ROOT/'dashboard.html'
    out.write_text(page)
    print(f'wrote {out} ({len(page)//1024} KB)')
    if '--no-upload' not in sys.argv:
        res = upload(page)
        print('upload response:', json.dumps(res, indent=2)[:600] if res else 'skipped')
