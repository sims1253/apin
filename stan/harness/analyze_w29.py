#!/usr/bin/env python
"""W-29 analyzer: attribute logp_grad-subtree Ir to stan-math functions.

Reads results/profile/w29/<model>/{ann_exclusive,ann_inclusive,ann_tree}.txt +
cli.log (produced by harness/w29_callgrind.py), writes
results/profile/w29/w29_analysis.json and prints per-model tables.

Subtree = inclusive Ir of bs_log_density_gradient (the bridgestan C entry the
sampler calls once per gradient). Attribution of shared callees (libm pow/log,
malloc, operator new) into the subtree uses --tree=both caller-edge costs:
a caller edge counts as inside the gradient when the caller is gradient math
(stan::math / Eigen / log_prob_impl / bs_log_density_gradient), and outside
when it is bridge/IO glue (rapidjson, bridgestan::, istream, sampler).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'results/profile/w29'
MODELS = ['hier_2pl', 'kronecker_gp', 'gp_regr', 'accel_gp', 'diamonds']

COST = re.compile(r'^\s*([\d,]+)(?:\s+\(\s*[\d.,]+%\s*\))?\s+(.*)$')

OUT_G_CALLER = re.compile(
    r'rapidjson|bridgestan|IStreamWrapper|filebuf|xsgetn|sentry|read_data|'
    r'constrain|unconstrain|param_unc|walnutpie|run_walnuts|main|ld-linux|_dl_')


def read_lines(p):
    return p.read_text(errors='replace').splitlines()


def parse_flat(path):
    """exclusive/inclusive annotate -> (total, [(cost, fullname)])."""
    total, funcs = None, []
    for line in read_lines(path):
        m = re.match(r'^\s*([\d,]+)(?:\s*\([\d.,%\s]+\))?\s+PROGRAM TOTALS', line)
        if m:
            total = int(m.group(1).replace(',', ''))
            continue
        m = COST.match(line)
        if m and '???:' in m.group(2):
            funcs.append((int(m.group(1).replace(',', '')), m.group(2).strip()))
    return total, funcs


def norm_tree_name(name):
    n = strip_bin(name)
    return re.sub(r'\s*\(\d+x\)\s*$', '', n)


def parse_tree(path):
    """tree=both -> {normalized_name: dict(self=, callers=[(cost,name,raw)], callees=[(cost,name)])}.

    Layout per block: caller lines '<' precede the '* self' line, callee lines
    '>' follow it -> callers must be buffered and attached to the next block.
    """
    blocks = {}
    cur, pending = None, []
    for line in read_lines(path):
        m = COST.match(line)
        if not m:
            continue
        cost = int(m.group(1).replace(',', ''))
        rest = m.group(2).strip()
        arrow = rest[:1] if rest[:1] in '<>*' else ''
        rest = rest[1:].strip() if arrow else rest
        if arrow == '*':
            cur = blocks.setdefault(norm_tree_name(rest), dict(self=0, callers=[], callees=[]))
            cur['self'] += cost
            cur['callers'].extend(pending)
            pending = []
        elif arrow == '<':
            pending.append((cost, norm_tree_name(rest), rest))
        elif arrow == '>' and cur is not None:
            cur['callees'].append((cost, norm_tree_name(rest)))
    return blocks


def strip_bin(name):
    return re.sub(r'\s*\[[^\]]*\]\s*$', '', name).replace('???:', '')


def find(funcs, *needles):
    out = [(c, n) for c, n in funcs if all(nd in n for nd in needles)]
    return max(out)[0] if out else 0


RET_BOUNDARY = re.compile(
    r'(?:^|\s)(?:type|auto|void|bool|double|long|int|unsigned|char|std::\S+|Eigen::\S+|'
    r'stan::math::\S+|stan::model::\S+|stan::scalar_type<\S*?>|stan::return_type<\S*?>)\s+'
    r'(stan::math::(?:internal::)?(\w+))\s*[<(]')


def shorten(name):
    n = strip_bin(name)
    n = re.sub(r'\s*\(\d+x\)\s*$', '', n)
    m = re.search(r'reverse_pass_callback_vari<stan::math::(\w+)<', n)
    if m:
        return f'revcb:{m.group(1)}'
    if 'unblocked_cholesky_lambda' in n:
        return 'cholesky_decompose::rev_lambda'
    m = re.search(r'stan::model::(\w+)<', n)
    if m:
        return f'stan::model::{m.group(1)}'
    if '::{lambda' in n and 'operator()' in n:
        outer = re.search(r'stan::math::(?:internal::)?(\w+)[<(]', n)
        if outer:
            return f'{outer.group(1)}::rev_lambda'
    m = RET_BOUNDARY.search(n)
    if m:
        return m.group(1)
    m = re.search(r'(?:type|auto|void|bool|double|long)\s+stan::math::(?:internal::)?(\w+)[<(]', n)
    if m:
        return f'stan::math::{m.group(1)}'
    m = re.search(r'stan::math::(?:internal::)?(\w+)[<(]', n)
    if m:
        return f'stan::math::{m.group(1)}'
    if re.search(r'var_value<[^()]*>::var_value[<(]', n) or re.search(r'::var_value[<(]', n):
        return 'var_value::ctor'
    if re.search(r'::vari\(', n) or re.search(r'\bvari\d*\(', n):
        return 'vari::ctor'
    if 'log_prob_impl' in n:
        m2 = re.search(r'(\w+_model_namespace)', n)
        return (m2.group(1) if m2 else '') + '::log_prob_impl'
    if 'Eigen::internal::' in n:
        m2 = re.search(r'Eigen::internal::(\w+)', n)
        return f'Eigen::internal::{m2.group(1)}' if m2 else n[:60]
    if 'Eigen::' in n:
        m2 = re.search(r'Eigen::(\w+(?:::\w+)?)', n)
        return f'Eigen::{m2.group(1)}' if m2 else n[:60]
    if 'walnutpie::' in n:
        m2 = re.search(r'walnutpie::(?:detail::)?(\w+)', n)
        return f'walnutpie::{m2.group(1)}' if m2 else 'walnutpie::*'
    if 'stan::model::' in n:
        m2 = re.search(r'stan::model::(\w+)', n)
        return f'stan::model::{m2.group(1)}' if m2 else 'stan::model::*'
    m2 = re.search(r'(\w+)::chain\(\)', n)
    if m2:
        return f'{m2.group(1)}::chain'
    if re.match(r'^(pow|exp|log|log1p|log2|sqrt|atan|atanh|lgamma|tanh|hypot|cbrt|expm1|log1p|sinh|asinh|__lgammal?)\b', n):
        return f'libm::{n.split("(")[0]}'
    if 'emplace_back' in n:
        m2 = re.search(r'std::vector<(\w+(?:::\w+)?)', n)
        return f'vector<{m2.group(1)}>::emplace_back' if m2 else 'vector::emplace_back'
    if n.startswith('operator new') or n.startswith('operator delete'):
        return n.split('(')[0]
    return n[:70]


BUCKETS = [
    ('rev_sweep',      r'rev_lambda|revcb|::chain\(\)|update_adjoints|set_zero_adj|recover_memory|chainable_stack'),
    ('tape_build',     r'::ctor|emplace_back|stack_alloc|arena_matrix|chainable_alloc|ops_partials'),
    ('eltwise_ops',    r'stan::math::(subtract|elt_multiply|add|multiply|divide|square|abs|negative)\b'),
    ('eigen_sym',      r'eigenvectors_sym|eigenvalues_sym|SelfAdjointEigenSolver|computeFromTridiagonal|tridiagonalization'),
    ('gp_kernel',      r'gp_exp_quad_cov|cov_exp_quad|gp_dot_prod|squared_distance'),
    ('cholesky_llt',   r'cholesky|llt_inplace|triangular_solve|triangular_matrix|TriangularView'),
    ('lpdf_lpmf',      r'_lpdf|_lpmf|_lcdf|_lccdf|lkj_corr|bernoulli|categorical|inv_logit|log1p_exp|log_inv_logit|apply_scalar_unary|plog_impl'),
    ('eigen_linalg',   r'Eigen::|gebp|gemv|gemm|general_matrix|outer_product|redux|selfadjoint|dot_'),
    ('index_glue',     r'rvalue|IndexedView|Holder|index_multi|assign_impl'),
    ('libm',           r'^libm::'),
    ('alloc_mem',      r'^malloc$|^free$|operator new|operator delete|memcpy|memmove|aligned_malloc'),
    ('model_glue',     r'log_prob_impl|bs_log_density|model_base'),
    ('io_checks',      r'check_|validate|bounded<|ostream|csv|rapidjson|istream'),
    ('sampler',        r'walnutpie|run_walnuts|build_span|transition'),
]


def bucket(name):
    for b, pat in BUCKETS:
        if re.search(pat, name):
            return b
    return 'other'


def in_g_frac_of(blk, so_pat):
    """Fraction of a function's caller-edge cost coming from inside the gradient.

    A caller edge is gradient work iff the caller's code lives in the model .so
    (or libm) AND is not IO/bridge glue (rapidjson data read, bridgestan
    constrain/unconstrain setup) — checked on the RAW caller line so signature
    substrings (std::ostream* params) cannot trigger false exclusions.
    """
    if blk is None or not blk['callers']:
        return None
    tot = sum(c for c, _, _ in blk['callers'])
    g = sum(c for c, _, raw in blk['callers']
            if (so_pat in raw or '/libm.so' in raw) and not OUT_G_CALLER.search(raw))
    return g / tot if tot else None


def call_path(tree, name, budget=6):
    """Greedy max-cost caller chain from `name` up to bs_log_density_gradient."""
    path, cur, seen = [name], name, {name}
    for _ in range(budget):
        blk = tree.get(cur)
        if blk is None or not blk['callers']:
            break
        nxt = max(blk['callers'], key=lambda c: c[0])[1]
        if nxt in seen:
            break
        path.append(nxt)
        seen.add(nxt)
        cur = nxt
        if 'bs_log_density_gradient' in nxt or 'log_prob_impl' in nxt:
            break
    return [shorten(p) for p in reversed(path)]


def analyze(m):
    od = OUT / m
    so_pat = f'model_{m}.so'
    T, excl = parse_flat(od / 'ann_exclusive.txt')
    _, incl = parse_flat(od / 'ann_inclusive.txt')
    tree = parse_tree(od / 'ann_tree.txt')

    G = find(incl, 'bs_log_density_gradient')
    F = find(incl, 'log_prob_impl')
    S = find(incl, 'run_walnuts<')

    txt = (od / 'cli.log').read_text(errors='replace')
    stanzas = [dict(total=float(t.group(1)), calls=int(t.group(4)), per_call=float(t.group(5)))
               for t in re.finditer(
                   r'total time: ([\d.eE+-]+)s?\s*\n'
                   r'logp_grad time: ([\d.eE+-]+)s\s*\n'
                   r'logp_grad fraction: ([\d.eE+-]+)\s*\n'
                   r'\s*logp_grad calls: (\d+)\s*\n'
                   r'\s*time per call: ([\d.eE+-]+)s\s*', txt)]
    ncalls = sum(s['calls'] for s in stanzas)
    errors = txt.count('Error in logp_grad')

    rows, buck = [], {}
    alloc_g = 0
    for cost, name in excl[:45]:
        sname = strip_bin(name)
        short = shorten(name)
        blk = tree.get(sname)
        fg = in_g_frac_of(blk, so_pat)
        if fg is None:
            fg = 1.0 if (so_pat in name or '/libm.so' in name) and not OUT_G_CALLER.search(name) else 0.0
        cost_g = cost * fg
        b = bucket(short)
        buck[b] = buck.get(b, 0) + cost_g
        if re.search(r'malloc|operator new|stack_alloc|aligned_malloc|memmove|memcpy', sname):
            alloc_g += cost_g
        rows.append(dict(cost=cost, cost_g=int(cost_g), name=sname, short=short,
                         pct_G=round(100 * cost_g / G, 2) if G else 0,
                         pct_T=round(100 * cost / T, 2),
                         in_g=round(fg, 3), bucket=b,
                         path=call_path(tree, sname)))

    res = dict(model=m, T=T, G=G, F=F, S=S,
               G_over_T=round(G / T, 4), F_over_G=round(F / G, 4),
               rev_over_G=round((G - F) / G, 4),
               grad_calls=ncalls, grad_errors=errors,
               ir_per_grad=G // ncalls if ncalls else None,
               per_call_us=[round(s['per_call'] * 1e6, 1) for s in stanzas],
               sampler_side_frac=round(1 - G / T, 4),
               alloc_share_G=round(alloc_g / G, 4),
               buckets={k: round(v / G, 4) for k, v in sorted(buck.items(), key=lambda x: -x[1])},
               top=rows)
    return res


if __name__ == '__main__':
    models = sys.argv[1:] or MODELS
    allres = {}
    for m in models:
        r = analyze(m)
        allres[m] = r
        print(f"\n== {m}: T={r['T']:,} G={r['G']:,} ({r['G_over_T']:.1%} of T) "
              f"fwd={r['F_over_G']:.1%}G rev+glue={r['rev_over_G']:.1%}G "
              f"alloc={r['alloc_share_G']:.1%}G calls={r['grad_calls']} err={r['grad_errors']} "
              f"Ir/grad={r['ir_per_grad']:,}")
        print('   buckets %ofG:', ', '.join(f'{k}={v:.1%}' for k, v in r['buckets'].items() if v >= 0.005))
        for row in r['top']:
            if row['cost_g'] < 0.01 * r['G']:
                continue
            print(f"   {row['cost_g']:>13,} {row['pct_G']:5.1f}%G [{row['bucket']}] {row['short']}")
            print(f"        path: {' <- '.join(row['path'])[:200]}")
    (OUT / 'w29_analysis.json').write_text(json.dumps(allres, indent=1))
    print('\n->', OUT / 'w29_analysis.json')
