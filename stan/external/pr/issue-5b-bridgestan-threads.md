# Default (non-`STAN_THREADS`) model `.so` silently corrupts memory when used from multiple threads

**Versions:** BridgeStan 2.9.0, Stan 2.39.0 (stan-math as vendored),
Linux x86-64, gcc 16.2.1.

## Summary

A model `.so` built by default `bridgestan.compile_model` (i.e. without
`make_args=["STAN_THREADS=True"]`) crashes the process when one model
library is used concurrently from multiple threads — reproduced
deterministically (3/3): `free(): double free detected in tcache 2` or
SIGSEGV. The requirement is documented and visible in `model_info()`, but
**nothing signals it at the point of misuse**; the failure is a heap
corruption far from the cause.

## Mechanism

Without `-DSTAN_THREADS`, stan-math uses a process-global autodiff
arena/chain stack. Concurrent `logp`/`logp_grad` calls from several
threads into the same `.so` are therefore undefined by construction — this
is a build-configuration hazard, not a code bug in BridgeStan.

## Reproduction

Build the same model twice:

```python
import bridgestan
m_default  = bridgestan.compile_model("m.stan")                       # STAN_THREADS=false
m_threads  = bridgestan.compile_model("m.stan",
                                      make_args=["STAN_THREADS=True"]) # STAN_THREADS=true
# NOTE: build in separate source dirs — see the companion issue about
# compile_model silently returning the cached .so regardless of make_args;
# that gotcha is how we shipped default binaries while believing otherwise.
print(m_default.model_info(), m_threads.model_info())  # STAN_THREADS: false vs true
```

Then run 4 chains over one `.so` from 4 threads (one `StanModel` instance
per thread, all `dlopen`-ing the same library), fixed seeds and init
files, warmup 400 / samples 200:

| `.so` build | execution | result |
|---|---|---|
| `STAN_THREADS=true` | 4 threads | rc = 0, clean exit |
| `STAN_THREADS=false` (default) | 4 threads | `free(): double free detected in tcache 2` / SIGSEGV, rc = 139 — **3/3 runs** |
| `STAN_THREADS=false` (default) | serialized | rc = 0 **and draws md5-identical to the threaded `STAN_THREADS=true` run** |

The third row is the useful nuance: the hazard is precisely *concurrency*
into a default build, not the default build itself — serialized use is
correct and bit-identical to the threaded build's output.

## Ask

The information exists (`model_info()["STAN_THREADS"]`, plus the docs),
but the misuse is silent until it corrupts the heap. Some options, in
increasing order of invasiveness:

1. A debug/cheap runtime guard: e.g. a `std::once_flag`-style thread-count
   assertion in the bridge entry points that trips when the library is
   entered concurrently without a `STAN_THREADS` build (the build mode is
   knowable at compile time inside the generated code).
2. A loud warning in the Python/Rust/Julia bindings when a model object
   is shared across threads (documented opt-in to silence).
3. At minimum, a "thread safety" section in the compile_model docstring
   stating the failure mode explicitly (heap corruption, not an error).

Happy to prototype (1) or (3) as a PR.

## Relation to the compile_model cache issue

This compounds with the silent-cache behavior filed separately: building
"with `STAN_THREADS=True`" against an already-built default pair returns
the default `.so` without warning — the two together produce a workflow
that believes it is thread-safe and crashes at runtime.
