# `compile_model` returns a cached `<stem>_model.so` even when `make_args` differ

**Versions:** BridgeStan 2.9.0 (Python bindings), Stan 2.39.0, Linux
x86-64, gcc 16.2.1, Python 3.13.

## Summary

`bridgestan.compile_model` checks for `<stem>_model.so` next to the `.stan`
file and returns it if present, **ignoring the requested `make_args`**.
Any workflow that varies `STAN_*` variables or `CXXFLAGS` between builds
against one source directory silently gets the stale binary.

## Reproduction

```python
import bridgestan, os, time

m1 = bridgestan.compile_model("m.stan")                          # default build
so = "m_model.so"
t1, inode1 = os.path.getmtime(so), os.stat(so).st_ino

m2 = bridgestan.compile_model("m.stan",
                              make_args=["STAN_THREADS=True"])   # different build!
t2, inode2 = os.path.getmtime(so), os.stat(so).st_ino

assert (t1, inode1) == (t2, inode2)   # PASSES: same object returned, nothing rebuilt
assert m2.model_info()["stanc_version"]  # no field reflects the requested build mode
```

The second call returns the *default-mode* `.so`: same mtime, same inode,
no warning. (We hit this in practice shipping default binaries into an
experiment that believed it had `STAN_THREADS=True` builds; caught only by
md5-comparing the binaries. Related: requesting different `CXXFLAGS`
against an already-built pair behaves the same.)

## Why it bites

The model `.so`'s name does not encode the build mode at all — in the 2.9.0
Makefile only the *bridge* object gets a `_threads` suffix
(`bridgestan[_threads].o`); the model target is `<stem>_model.so` either
way. So two independent hazards compound:

1. there is nothing in the artifact name distinguishing build modes, and
2. the cache check does not compare the requested `make_args` with what
   produced the cached artifact.

## Suggested directions (any one of these would have caught our case)

- Encode the relevant build mode (at minimum the `STAN_*` variables, or a
  hash of the effective make args) into the `.so` name or a sidecar stamp
  file written at build time.
- On a cache hit, compare the stamp with the requested `make_args` and
  warn (or rebuild) on mismatch.
- At minimum, document the cache-key semantics prominently in
  `compile_model`'s docstring — the current behavior reads as "build with
  these args", not "return whatever is on disk".

Happy to turn any of these into a PR if a direction is preferred.
