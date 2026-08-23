"""W-46: extract the REAL ntheta = (2y-1)*alpha_i*(theta_j - beta_i) distribution
seen by bernoulli_logit_lpmf in hier_2pl, at draws-like positions.

Sets:
  A pfinit : inits_w25/hier_2pl/rep0/chain_{0..3}.txt unconstrained points
             (theta = u[0:600], xi1 = u[600:632], xi2 = u[632:664];
              alpha=exp(xi1), beta=xi2; mu/tau/L_Omega do not enter eta)
  B random : 20 N(0,1) unconstrained points, W-27 deterministic scheme
             (random.Random('20260819-0').gauss(0,1) x 669)
  C cloud  : pf init rep0/chain_0 + 0.25 * N(0,1) (20 draws)
  D draws  : the 50 POSTERIOR draws of results/profile/w34/stock/draws.csv
             (constrained columns theta.1..600, alpha.1..32, beta.1..32)
Outputs scratch/w46/x_<set>.npy (concatenated ntheta values) + stats JSON.
"""
import json, random
import numpy as np

BASE = "/home/m0hawk/Documents/apin/stan"
D = json.load(open(f"{BASE}/data/hier_2pl.json"))
I, J, N = D["I"], D["J"], D["N"]
ii = np.array(D["ii"]) - 1          # 0-based item idx, item-major: ii=0..31 x J
jj = np.array(D["jj"]) - 1          # 0-based person idx, tiled 1..600
y = np.array(D["y"])
signs = 2.0 * y - 1.0
assert N == I * J and (ii == np.repeat(np.arange(I), J)).all()

def eta_of(alpha, beta, theta):
    # eta_n = alpha_i * (theta_j - beta_i) over the complete grid
    m = alpha[None, :] * (theta[:, None] - beta[None, :])   # (J, I)
    return m.reshape(-1)                                     # col-major = item-major? verify

# column-major flatten of (J,I): element (j,i) at i*J+j -> item-major n = i*J+j.
# data order: n-th obs has ii[n]=i repeated J times, jj[n]=j -> n = i*J + j. Same.

sets = {}

# A: pf inits
vals = []
for c in range(4):
    u = np.loadtxt(f"{BASE}/inits_w25/hier_2pl/rep0/chain_{c}.txt")
    assert u.shape == (669,), u.shape
    theta, xi1, xi2 = u[0:J], u[J:J+I], u[J+I:J+2*I]
    vals.append(signs * eta_of(np.exp(xi1), xi2, theta))
sets["pfinit"] = np.concatenate(vals)

# B: random N(0,1) unconstrained (W-27 scheme)
rng = random.Random("20260819-0")
vals = []
for _ in range(20):
    u = np.array([rng.gauss(0, 1) for _ in range(669)])
    theta, xi1, xi2 = u[0:J], u[J:J+I], u[J+I:J+2*I]
    vals.append(signs * eta_of(np.exp(xi1), xi2, theta))
sets["random"] = np.concatenate(vals)

# C: posterior cloud around pf init
u0 = np.loadtxt(f"{BASE}/inits_w25/hier_2pl/rep0/chain_0.txt")
vals = []
for _ in range(20):
    u = u0 + 0.25 * np.array([rng.gauss(0, 1) for _ in range(669)])
    theta, xi1, xi2 = u[0:J], u[J:J+I], u[J+I:J+2*I]
    vals.append(signs * eta_of(np.exp(xi1), xi2, theta))
sets["cloud"] = np.concatenate(vals)

# D: posterior draws (constrained)
raw = np.loadtxt(f"{BASE}/results/profile/w34/stock/draws.csv", delimiter=",", skiprows=1)
hdr = open(f"{BASE}/results/profile/w34/stock/draws.csv").readline().strip().split(",")
col = {n: k for k, n in enumerate(hdr)}
vals = []
for r in range(raw.shape[0]):
    theta = raw[r, col["theta.1"]:col["theta.600"] + 1]
    alpha = raw[r, col["alpha.1"]:col["alpha.32"] + 1]
    beta = raw[r, col["beta.1"]:col["beta.32"] + 1]
    vals.append(signs * eta_of(alpha, beta, theta))
sets["draws"] = np.concatenate(vals)

stats = {}
for name, x in sets.items():
    np.save(f"{BASE}/scratch/w46/x_{name}.npy", x.astype(np.float64))
    band = np.abs(x) <= 20.0
    q = np.quantile(np.abs(x), [0.5, 0.9, 0.99, 0.999, 1.0])
    stats[name] = dict(
        n=int(x.size),
        in_band_frac=float(band.mean()),
        absx_median=float(q[0]), absx_p90=float(q[1]), absx_p99=float(q[2]),
        absx_p999=float(q[3]), absx_max=float(q[4]),
        u_band_min=float(np.exp(-20)),  # by construction
        u_band_min_observed=float(np.exp(-np.abs(x)[band]).min()),
        u_band_max_observed=float(np.exp(-np.abs(x)[band]).max()),
        finite_frac=float(np.isfinite(x).mean()),
    )
    print(name, stats[name])

json.dump(stats, open(f"{BASE}/scratch/w46/x_stats.json", "w"), indent=1)
print("saved scratch/w46/x_*.npy + x_stats.json")
