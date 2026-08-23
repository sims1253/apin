import bridgestan, os, sys
BASE = "/home/m0hawk/Documents/apin/stan/scratch/w53"
for m in ["hier_2pl", "kronecker_gp", "gp_regr", "accel_gp"]:
    for arm, bs in [("stock", "/home/m0hawk/.bridgestan/bridgestan-2.9.0"),
                    ("patched", BASE + "/bs_w53")]:
        d = f"{BASE}/model_{m}_{arm}"
        if os.path.exists(f"{d}/{m}_model.so"):
            print(f"skip {m} {arm} (cached)", flush=True)
            continue
        os.environ["BRIDGESTAN"] = bs
        print(f"building {m} {arm} with {bs}", flush=True)
        bridgestan.compile_model(f"{d}/{m}.stan")
        print(f"done {m} {arm}", flush=True)
