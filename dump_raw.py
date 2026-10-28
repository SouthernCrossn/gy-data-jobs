# -*- coding: utf-8 -*-
"""看某个 raw 文件里到底粘了些什么。

用法:  python dump_raw.py 51job_贵阳.txt
"""
import sys
import re

import importlib.util
spec = importlib.util.spec_from_file_location("p", "01_build_db.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

name = sys.argv[1]
txt = open("raw/" + name, encoding="utf-8", errors="ignore").read()
blocks = re.split(r"\n\s*#{3,}\s*\n", txt)
print("文件: %s   字符数: %d   块数: %d\n" % (name, len(txt), len(blocks)))

for i, b in enumerate(blocks, 1):
    r = p.parse_block(b, name)
    if not r:
        continue
    keep = p.KEEP_TITLE.search(r["title"]) and not p.BAD_TITLE.search(r["title"])
    head, body = p.split_detail(b)
    print("%2d. [%s] %s" % (i, "收" if keep else "剔", r["title"][:34]))
    print("     薪资 %s-%s | %s | 经验 %s-%s | %s | 正文 %d 字" % (
        r["salary_min"], r["salary_max"], r["city"] or "?",
        r["exp_min"], r["exp_max"], r["edu"] or "?", len(body)))
    print("     技能 %s" % (r["skills"] or "(无)"))
