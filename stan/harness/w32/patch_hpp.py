#!/usr/bin/env python3
"""W-32: patch a stanc-generated kronecker_gp hpp so each matrix's eigenvalues
AND eigenvectors come from ONE decomposition via the w32::eigh helper
(scratch/w32/w32_eigh.hpp). Idempotent. Usage: patch_hpp.py <hpp>"""
import sys
from pathlib import Path

hpp = Path(sys.argv[1])
src = hpp.read_text()

OLD = """\
      stan::model::assign(Q1, stan::math::eigenvectors_sym(Sigma1),
        "assigning variable Q1");
      current_statement__ = 17;
      stan::model::assign(R1, stan::math::eigenvalues_sym(Sigma1),
        "assigning variable R1");
      current_statement__ = 18;
      stan::model::assign(Q2, stan::math::eigenvectors_sym(Lambda),
        "assigning variable Q2");
      current_statement__ = 19;
      stan::model::assign(R2, stan::math::eigenvalues_sym(Lambda),
        "assigning variable R2");
"""

NEW = """\
      const auto w32_eigh_Sigma1_ = stan::math::w32_eigh(Sigma1);
      stan::model::assign(Q1, w32_eigh_Sigma1_.vectors,
        "assigning variable Q1");
      stan::model::assign(R1, w32_eigh_Sigma1_.values,
        "assigning variable R1");
      const auto w32_eigh_Lambda_ = stan::math::w32_eigh(Lambda);
      stan::model::assign(Q2, w32_eigh_Lambda_.vectors,
        "assigning variable Q2");
      stan::model::assign(R2, w32_eigh_Lambda_.values,
        "assigning variable R2");
"""

n = src.count(OLD)
if n == 0 and "w32_eigh" in src:
    print("already patched")
    sys.exit(0)
assert n == 3, f"expected 3 call-site blocks, found {n}"
src = src.replace(OLD, NEW)

INC_OLD = "#include <stan/model/model_header.hpp>\n"
INC_NEW = INC_OLD + '#include "w32_eigh.hpp"\n'
assert src.count(INC_OLD) == 1
src = src.replace(INC_OLD, INC_NEW)

hpp.write_text(src)
print(f"patched {hpp}: 3 blocks -> w32::eigh, include added")
