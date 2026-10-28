# -*- coding: utf-8 -*-
import csv

rows = list(csv.DictReader(open("data/jobs.csv", encoding="utf-8-sig")))
print("入库 %d 条\n" % len(rows))
for i, r in enumerate(rows, 1):
    print("%2d. %-20s %5s-%-5sK  %s  %s" % (
        i, r["title"][:20], r["salary_min"], r["salary_max"], r["city"], r["skills"]))
