# apin — portable setup

> Fresh session? Read **HANDOFF.md** first (queued work + gates + gotchas).
> This file is environment/build setup only.

```bash
git clone --recurse-submodules git@github.com:sims1253/apin.git
cd apin/stan

# python env (harness): uv-managed
uv venv && uv pip install pandas numpy "bridgestan==2.9.0" cmdstanpy nutpie
# R: needs posterior (>=1.7) for harness/ess.R

# model libraries: regenerable, not tracked (~19MB of .so)
#   bs_models/model_<name>.so — build all from models/ + posteriordb data:
python3 harness/compile_variant.py --all   # or per-model
#   (pin: posteriordb submodule @ 28f8d3d6 = CORE_SET freeze)

# walnutpie CLI (submodule @ dev/init-robustness):
cmake -S external/walnutpie -B external/walnutpie/build && cmake --build external/walnutpie/build -j4
# cmdstan variant (submodule @ nindan/mixed-build-guard): see harness/run_grid.py header

# Pathfinder init draws land in /tmp/winit/<model>/rep*/chain_*.txt (see
# harness/run_pathfinder.py); runs/ is NOT tracked — regenerate with
# harness/run_{grid,walnutpie}.py. results/ IS tracked (all tables + ess json).
```

## What lives where
- `stan/WORKLOG.md` — append-only experiment log (W-1 … W-22): the canonical record.
- `stan/results/FINAL_REPORT.md` — consolidated findings (phase 0 → session 2 addendum).
- `stan/ATLAS.md` — callgrind instruction atlas.
- `stan/patches/stan-2a2-scratch-hoist-PLAN.md` — pre-planned next cmdstan patch (gates included).
- `stan/external/*.md` — optimizer research (Muon/Aurora/SOAP), upstream audit, ESS/grad evidence.
