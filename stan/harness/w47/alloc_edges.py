#!/usr/bin/env python3
"""W-47 helper: from ann_tree.txt, attribute stack_alloc::alloc and
chainstack emplace_back exclusive cost to their immediate parent call frame."""
import re
import sys

path = sys.argv[1]
want = sys.argv[2] if len(sys.argv) > 2 else "alloc"

rows = []
num = re.compile(r"^([\d,]+) \([\s\d.]+%\)\s+(.)\s+(.*)$")
with open(path, errors="replace") as fh:
    for line in fh:
        stripped = line.rstrip("\n")
        m = num.match(stripped.lstrip(" "))
        if m:
            ir = int(m.group(1).replace(",", ""))
            marker = m.group(2)
            sig = m.group(3)
            indent = len(stripped) - len(stripped.lstrip(" "))
            rows.append((ir, marker, sig, indent))

# callgrind_annotate --tree: a function block starts with a flush-left '*'
# row (the function), optionally preceded by flush-left '<' caller rows and
# followed by flush-left '>' direct-callee rows; deeper-indented '>' rows are
# callees of the nearest flush-left '>' row above them.
agg = {}
last_star = None
last_callee = None
for ir, marker, sig, indent in rows:
    if marker == "*":
        last_star = sig
        last_callee = None
        continue
    if marker != ">":
        continue
    if indent == 0:
        parent = last_star
        last_callee = sig
    else:
        parent = last_callee or last_star
    if want == "alloc" and "stack_alloc::alloc" not in sig:
        continue
    if want == "emplace" and "emplace_back" not in sig:
        continue
    key = parent or "<top>"
    key = key.split(" [")[0]
    key = re.sub(r"\(.*$", "()", key)
    key = key.replace("???:", "")
    if len(key) > 95:
        key = key[:95]
    a = agg.setdefault(key, [0, 0])
    a[0] += ir
    cc = re.search(r"\(([\d,]+)x\)", sig)
    if cc:
        a[1] += int(cc.group(1).replace(",", ""))
for k, v in sorted(agg.items(), key=lambda kv: -kv[1][0])[:12]:
    print(f"{v[0]:>15,}  calls={v[1]:>13,}  <- {k}")
