The BYM2 ICAR prior writes `target += -0.5 * dot_self(phi[node1] - phi[node2])`. The generated code gathers both endpoint vectors into dense matrices, subtracts them elementwise, and scatters adjoints back through the same plumbing. On the NYC example (1,921 nodes, 5,461 edges) this chain is about 43% of the gradient.

This adds `dot_self_gathered_diff(phi, node1, node2)`. It reads the coefficients through the index arrays directly, and the reverse pass is one callback with the same per-edge scatter order as stock.

Development found a real hazard here: on GCC the two gathers register their callbacks in the opposite order to the source order, so the scatter must run node2 before node1. The shipped order matches stock bit for bit.

Gates: 59,178 bitwise checks over the real graph and randomized graphs, clean; same-seed sampler draws identical to stock; 100-point parity exact. The whole gather complex leaves the profile, and the gradient loses 17% of its instructions.
