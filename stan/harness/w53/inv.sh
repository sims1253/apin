#!/bin/bash
# W-53 Phase 0: pointer-semantics inventory over external/math_soa (develop @344d7167)
# Raw grep batteries -> scratch/w53/inventory/*.txt ; classified in the report.
set -u
M=/home/m0hawk/Documents/apin/stan/external/math_soa/stan/math
O=/home/m0hawk/Documents/apin/stan/scratch/w53/inventory
cd "$M"

G() { grep -rn --include='*.hpp' -E "$2" . ; }

# P1 raw vari*/vari_value<T>* mentioned anywhere (files + counts)
G p1 '\bvari_value<[A-Za-z_:,<> ]+>\s*\*|\bvari\s*\*|\bvari\s+\*|vari\*' \
  | awk -F: '{print $1}' | sort | uniq -c | sort -rn > $O/p1_raw_vari_ptr_byfile.txt
G p1 '\bvari_value<[A-Za-z_:,<> ]+>\s*\*|\bvari\s*\*|\bvari\s+\*|vari\*' | wc -l > $O/p1_total_matches.txt

# P2 vi_ member accessed outside rev/core/var*.hpp and vari.hpp (pointer reach-through)
G p2 '\.vi_|->vi_' | grep -vE 'rev/core/var(_value)?(_fwd_declare)?\.hpp' \
  | awk -F: '{print $1}' | sort | uniq -c | sort -rn > $O/p2_vi_member_byfile.txt
G p2 '\.vi_|->vi_' | wc -l > $O/p2_total.txt

# P3 identity comparisons on var/vari pointers (==, !=) excluding null checks
G p3 'vi_\s*(==|!=)\s*[^;]*vi_|vi_\s*(==|!=)\s*(nullptr|NULL|0)|!=\s*nullptr.*vi_' \
  > $O/p3_identity_cmp.txt
# var-vs-var pointer identity (e.g. &a == &b on var, a.vi_ == b.vi_)
G p3b '(\.vi_|->vi_)\s*==\s*(\.vi_|->vi_|\w+\.vi_)' > $O/p3b_vi_eq_vi.txt

# P4 address-of var / vari (excluding & in function-arg contexts is hard; raw)
G p4 '&\s*\w+\.vi_|&\s*\(?\s*\w+\s*\)?\.vi_|addressof.*vi_' > $O/p4_addrof_vi.txt
G p4b 'std::addressof\(' > $O/p4b_addressof.txt

# P5 casts of vari pointers
G p5 '(static|reinterpret|const|dynamic)_cast<[^>]*vari[^>]*>' > $O/p5_casts.txt
grep -rn --include='*.hpp' -E '(static|reinterpret)_cast<[^>]*>\([^)]*vi_' . > $O/p5b_casts_on_vi.txt

# P6 containers of vari*
G p6 'std::vector<\s*(vari|vari_value|ChainableT)' > $O/p6_vector_vari.txt
G p6b 'alloc_array<\s*vari' > $O/p6b_allocarray_vari.txt
G p6c 'Eigen::Matrix<\s*vari|Matrix<vari\s*,' > $O/p6c_eigen_vari.txt

# P7 dump/serialize/deserialization: save/read/deep_copy/count/collect/accumulate
G p7 'save_varis|read_var|deep_copy_vars|count_vars|collect_adjoints|accumulate_adjoints|filter_var_scalar_types' \
  | awk -F: '{print $1}' | sort -u > $O/p7_serialize_files.txt

# P8 direct chain() invocations
G p8 '->chain\(\)|\.chain\(\)' | grep -vE 'void chain\(\)|inline.*chain\(\)' > $O/p8_direct_chain.txt

# P9 var passed by value / compared / sorted / map-key patterns (public semantics)
G p9 'std::hash<\s*(var|stan::math::var)|std::map<[^;]*var[,\s>]|std::unordered_map<[^;]*\bvar\b' > $O/p9_hash_map_var.txt
G p9b 'std::sort|std::is_sorted' > $O/p9b_sort.txt

# P10 nested / thread / arena storage structural sites
G p10 'start_nested|recover_memory_nested|nested_var|scoped_chainablestack|STAN_THREADS' \
  | awk -F: '{print $1}' | sort | uniq -c | sort -rn > $O/p10_structural_byfile.txt

# P11 opencl (GPU) vari
G p11 'matrix_cl<.*(vari|var)|opencl.*vari|vari.*opencl' > $O/p11_opencl.txt

# P12 callbacks holding raw pointers (reverse_pass_callback / callback_vari / chainable_object)
G p12 'reverse_pass_callback|callback_vari|chainable_object' \
  | awk -F: '{print $1}' | sort | uniq -c | sort -rn > $O/p12_callbacks_byfile.txt

echo "inventory written to $O"
