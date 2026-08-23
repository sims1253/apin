import sys, time
import numpy as np
import bridgestan
arm = sys.argv[1]
BASE = "/home/m0hawk/Documents/apin/stan/scratch/w53"
so = bridgestan.StanModel(f"{BASE}/model_hier_2pl_{arm}/hier_2pl_model.so",
                          "/home/m0hawk/Documents/apin/stan/data/hier_2pl.json")
D = so.param_unc_num()
rng = np.random.default_rng(20260822)
pts = [rng.standard_normal(D) * 0.5 for _ in range(200)]
for x in pts: so.log_density_gradient(x, propto=True, jacobian=False)
