PR #7 taught the compiler one pattern: the 2PL bernoulli likelihood over indexed coefficients. This turns that pass into a registry and adds two families.

Entry two matches the ICAR prior: `dot_self(phi[node1] - phi[node2])` becomes `dot_self_gathered_diff`. Entry three matches the stereotyped normal loop: a local mean vector assigned from indexed coefficients, one scalar `normal_lpdf` per element. The rewrite covers both predictor shapes, `alpha[c[n]]` and `alpha[c[n]] + x[n] * beta[c[n]]`, and reproduces the per-term push loop that the accumulator's chunk buffer requires.

The pass fires only on the exact patterns. Fourteen negative controls stay silent, including loops whose sigma varies and means read after the loop.

Gates: regenerated programs are byte-identical to the gated hand edits; end-to-end draws match stock exactly at the same optimization level; models without the patterns compile unchanged; the test suite passes. One in-repo ICAR model now gets the rewrite, as intended.

Requires the three math-side primitives. An upstream submission would gate this behind `--Oexperimental` until they land.
