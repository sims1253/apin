#!/usr/bin/env python
"""W-45: subsampled observation-row data JSONs (+ lsat_model modified .stan).

Deterministic (seed 'w45-<model>-<alpha>'). Output: scratch/w45/data/.
  hier_2pl  random alpha*N row subset of (y, ii, jj); I/J unchanged;
            unconstrained dims identical to full (671).
  blr       random alpha*N aligned rows of (X, y); D unchanged.
  lsat_model  aligned unit = STUDENT. Parameter block (alpha[T], theta[N],
            beta) must stay dimension-identical, so the subsample .stan is
            a data-block-modified COPY: likelihood over the M=alpha*N
            retained students (pattern ids in data), dropped thetas keep
            only their normal(0,1) prior. Written to
            scratch/w45/data/lsat_model_sub.stan; full .so stays stock.
  arma11    CONTROL: random row drops are invalid for a lag model;
            contiguous PREFIX of length round(alpha*T) (pre-registered
            deviation).
"""
import json, random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data'
OUT = ROOT / 'scratch' / 'w45' / 'data'
ALPHAS = [0.25, 0.1]
MODELS = ['hier_2pl', 'blr', 'lsat_model', 'arma11']

# Subsampled lsat_model: parameters IDENTICAL to stock (alpha[T], theta[N],
# beta) so the unconstrained dimension matches the full model (1006) and the
# adapted state transplants 1:1; likelihood over the M retained students,
# dropped thetas prior-only. Written by this script (self-contained method).
LSAT_SUB_STAN = '''// W-45 subsampled variant of lsat_model (Rasch). Parameters are IDENTICAL
// to stock (alpha[T], theta[N], beta) so the unconstrained dimension
// matches the full model (1006) and an adapted state transplants 1:1.
// The likelihood sees only the M = alpha*N retained students; dropped
// thetas keep their normal(0,1) prior (prior-only components).
data {
  int<lower=0> N; // 1000, total students (UNCHANGED parameter anchor)
  int<lower=0> M; // retained students (alpha * N)
  int<lower=0> T; // 5, number of questions
  array[M] int<lower=1, upper=N> student; // retained student indices
  array[M, T] int<lower=0, upper=1> resp; // their response patterns
}
transformed data {
  array[T, M] int r;
  vector[M] ones;
  for (j in 1 : M) {
    for (k in 1 : T) {
      r[k, j] = resp[j, k];
    }
  }
  for (j in 1 : M) {
    ones[j] = 1.0;
  }
}
parameters {
  array[T] real alpha;
  vector[N] theta;
  real<lower=0> beta;
}
model {
  vector[M] theta_sub;
  theta_sub = theta[student];
  alpha ~ normal(0, 100.);
  theta ~ normal(0, 1);
  beta ~ normal(0.0, 100.);
  for (k in 1 : T) {
    r[k] ~ bernoulli_logit(beta * theta_sub - alpha[k] * ones);
  }
}
generated quantities {
  real mean_alpha;
  array[T] real a;
  mean_alpha = mean(alpha);
  for (t in 1 : T) {
    a[t] = alpha[t] - mean_alpha;
  }
}
'''


def sample_rows(n, k, tag):
    idx = sorted(random.Random(tag).sample(range(n), k))
    return idx


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'lsat_model_sub.stan').write_text(LSAT_SUB_STAN)
    for m in MODELS:
        d = json.loads((DATA / f'{m}.json').read_text())
        for a in ALPHAS:
            tag = f'w45-{m}-{a}'
            if m in ('hier_2pl', 'blr'):
                n = d['N']
                k = round(a * n)
                idx = sample_rows(n, k, tag)
                s = dict(d)
                s['N'] = k
                if m == 'hier_2pl':
                    for col in ('y', 'ii', 'jj'):
                        s[col] = [d[col][i] for i in idx]
                else:
                    s['y'] = [d['y'][i] for i in idx]
                    s['X'] = [d['X'][i] for i in idx]
            elif m == 'arma11':
                t = d['T']
                k = round(a * t)
                s = dict(d)
                s['T'] = k
                s['y'] = d['y'][:k]  # contiguous prefix (time series)
            elif m == 'lsat_model':
                n = d['N']
                k = round(a * n)
                # map student index -> pattern via culm
                pat_of = []
                for i in range(d['R']):
                    lo = d['culm'][i - 1] if i else 0
                    pat_of += [i + 1] * (d['culm'][i] - lo)
                assert len(pat_of) == n
                idx = sample_rows(n, k, tag)
                s = {'N': n, 'M': k, 'T': d['T'],
                     'student': [i + 1 for i in idx],
                     'resp': [d['response'][pat_of[i] - 1] for i in idx]}
            p = OUT / f'{m}_a{round(a * 100)}.json'
            p.write_text(json.dumps(s))
            print(p.relative_to(ROOT), 'N/M keys:',
                  {kk: (len(v) if isinstance(v, list) else v)
                   for kk, v in s.items() if kk in ('N', 'M', 'T')})


if __name__ == '__main__':
    main()
