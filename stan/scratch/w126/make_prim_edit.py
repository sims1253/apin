#!/usr/bin/env python3
"""W-126 hand-edit: the gpcm hpp's REV-mode likelihood loop -> the primitive.
Reproducible: asserts the replaced block verbatim (the bundle stanc's output).
The double-mode instantiation and write_array keep the stock loop (W-112 idiom).
"""
import sys

SRC = ("/home/m0hawk/Documents/apin/stan/scratch/w126/model_gpcm_stock/"
       "gpcm.hpp")
DST = ("/home/m0hawk/Documents/apin/stan/scratch/w126/model_gpcm_prim/"
       "gpcm.hpp")

OLD_LOOP = """        current_statement__ = 17;
        for (int n = 1; n <= N; ++n) {
          current_statement__ = 15;
          lp_accum__.add(pcm(
                           stan::model::rvalue(y, "y",
                             stan::model::index_uni(n)),
                           (stan::model::rvalue(theta, "theta",
                              stan::model::index_uni(
                                stan::model::rvalue(jj, "jj",
                                  stan::model::index_uni(n)))) *
                           stan::model::rvalue(alpha, "alpha",
                             stan::model::index_uni(
                               stan::model::rvalue(ii, "ii",
                                 stan::model::index_uni(n))))),
                           stan::math::segment(beta,
                             stan::model::rvalue(pos, "pos",
                               stan::model::index_uni(
                                 stan::model::rvalue(ii, "ii",
                                   stan::model::index_uni(n)))),
                             stan::model::rvalue(m, "m",
                               stan::model::index_uni(
                                 stan::model::rvalue(ii, "ii",
                                   stan::model::index_uni(n))))), pstream__));
        }"""

NEW_LOOP = """        current_statement__ = 17;
        {
          current_statement__ = 15;
          auto pcm_terms__ = stan::math::pcm_lpdf_gathered<propto__>(
              y, theta, jj, alpha, ii, beta, pos, m);
          for (const auto& pcm_term__ : pcm_terms__) {
            lp_accum__.add(pcm_term__);
          }
        }"""

OLD_INC = "#include <stan/model/model_header.hpp>"
NEW_INC = ("#include <stan/model/model_header.hpp>\n"
           "#include <stan/math/rev/prob/pcm_lpdf_gathered.hpp>")

src = open(SRC).read()
assert src.count(OLD_LOOP) == 2, "expected exactly two identical pcm loops (double + var)"
first = src.index("log_prob_impl")
var_impl_start = src.index("log_prob_impl", first + 20)
# sanity: both loop occurrences; we replace the SECOND (the var-mode impl)
loop_pos = [i for i in range(len(src)) if src.startswith(OLD_LOOP, i)]
assert len(loop_pos) == 2 and loop_pos[1] > var_impl_start > loop_pos[0]
assert src.count(OLD_INC) == 1, "model_header include not found"
# Only the SECOND log_prob_impl (the var-mode one) has this loop; the
# double-mode one (line ~564) calls pcm too -- verify which blocks contain it.
src = (src[:loop_pos[1]] + NEW_LOOP
       + src[loop_pos[1] + len(OLD_LOOP):])
src = src.replace(OLD_INC, NEW_INC, 1)
open(DST, "w").write(src)
print("edited ->", DST)
