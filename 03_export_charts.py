# -*- coding: utf-8 -*-
"""
从 data/jobs.db 导出"可直接画图"的 CSV，用 WPS 表格出图。

用法:  python 03_export_charts.py
依赖:  仅标准库

为什么画图交给 WPS：
  你的环境里没有 matplotlib，也不需要装。
  Python 负责"算"，WPS 负责"画"，这是真实分析岗也常见的分工。
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "jobs.db"
OUT = ROOT / "charts"

BINS = [(0, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 15), (15, 20), (20, 999)]


def write_csv(name, header, rows):
    OUT.mkdir(exist_ok=True)
    p = OUT / name
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  √ {name}  ({len(rows)} 行)")


def main():
    if not DB.exists():
        print("× 找不到 data/jobs.db，先跑 01_build_db.py")
        return

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    q = lambda s, *a: con.execute(s, a).fetchall()

    total = q("SELECT COUNT(*) n FROM jobs")[0]["n"]
    if not total:
        print("× 库里没数据")
        return
    gy = q("SELECT COUNT(*) n FROM jobs WHERE region='贵阳'")[0]["n"]
    sal_ok = q("SELECT COUNT(*) n FROM jobs WHERE salary_med IS NOT NULL")[0]["n"]
    print(f"样本 {total} 条｜贵阳 {gy}｜薪资可解析 {sal_ok}\n")

    # ---------- 图1：技能提及率 TOP10（条形图） ----------
    rows = q("""SELECT skill, COUNT(*) n FROM job_skills
                GROUP BY skill ORDER BY n DESC LIMIT 10""")
    write_csv("图1_技能提及率.csv", ["技能", "提及条数", "提及率(%)"],
              [[r["skill"], r["n"], round(r["n"] / total * 100, 1)] for r in rows])

    # ---------- 图2：薪资分布（簇状柱形图） ----------
    sal = q("SELECT region, salary_med FROM jobs WHERE salary_med IS NOT NULL")
    counts = {"贵阳": [0] * len(BINS), "其他": [0] * len(BINS)}
    for r in sal:
        v = r["salary_med"]
        for i, (lo, hi) in enumerate(BINS):
            if lo <= v < hi:
                counts[r["region"]][i] += 1
                break
    write_csv("图2_薪资分布.csv",
              ["月薪区间(千元)", "贵阳", "其他"],
              [[f"{lo}-{hi if hi < 999 else '+'}", c1, c2]
               for (lo, hi), c1, c2 in zip(BINS, counts["贵阳"], counts["其他"])])

    # ---------- 图3：★业务溢价（柱形图，全篇命门） ----------
    rows = q("""SELECT soft_skill s, COUNT(*) n, AVG(salary_med) a
                FROM jobs WHERE salary_med IS NOT NULL GROUP BY soft_skill""")
    d = {r["s"]: r for r in rows}
    line = []
    for k, label in [(1, "要求业务/沟通"), (0, "未要求")]:
        r = d.get(k)
        line.append([label, r["n"] if r else 0, round(r["a"], 1) if r else 0])
    write_csv("图3_业务溢价.csv", ["分组", "样本量", "平均月薪(千元)"], line)

    # ---------- 图4：经验门槛（柱形图） ----------
    def seg(r):
        if r["exp_max"] is None:
            return "未标注"
        if r["exp_max"] == 0:
            return "经验不限/应届"
        if r["exp_max"] <= 1:
            return "1年以内"
        if r["exp_max"] <= 3:
            return "1-3年"
        return "3年以上"

    agg = {}
    for r in q("SELECT exp_max, salary_med FROM jobs"):
        s = seg(r)
        a = agg.setdefault(s, [0, []])
        a[0] += 1
        if r["salary_med"] is not None:
            a[1].append(r["salary_med"])
    order = ["经验不限/应届", "1年以内", "1-3年", "3年以上", "未标注"]
    write_csv("图4_经验门槛.csv", ["经验要求", "岗位数", "平均月薪(千元)"],
              [[s, agg[s][0], round(sum(agg[s][1]) / len(agg[s][1]), 1) if agg[s][1] else ""]
               for s in order if s in agg])

    # ---------- 图5：学历分布（饼图） ----------
    rows = q("""SELECT CASE WHEN edu='' THEN '未标注' ELSE edu END e, COUNT(*) n
                FROM jobs GROUP BY e ORDER BY n DESC""")
    write_csv("图5_学历分布.csv", ["学历", "岗位数"], [[r["e"], r["n"]] for r in rows])

    # ---------- 汇总：一行数字，写 PPT 页脚和 README 用 ----------
    med_gy = [r["salary_med"] for r in sal if r["region"] == "贵阳"]
    med_ot = [r["salary_med"] for r in sal if r["region"] != "贵阳"]
    sql_rate = q("""SELECT COUNT(DISTINCT job_id) n FROM job_skills WHERE skill='SQL'""")[0]["n"]
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else ""
    def median(xs):
        if not xs:
            return ""
        s = sorted(xs)
        n = len(s)
        return round((s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2), 1)

    write_csv("汇总.csv", ["指标", "数值"], [
        ["样本总量", total],
        ["贵阳样本", gy],
        ["贵阳薪资均值(千元)", avg(med_gy)],
        ["其他城市薪资均值(千元)", avg(med_ot)],
        ["贵阳薪资中位数(千元)", median(med_gy)],
        ["其他城市薪资中位数(千元)", median(med_ot)],
        ["SQL提及率(%)", round(sql_rate / total * 100, 1)],
        ["业务溢价差额(千元)", round((line[0][2] or 0) - (line[1][2] or 0), 1)],
        ["业务溢价比(%)",
         round((line[0][2] - line[1][2]) / line[1][2] * 100, 1) if line[1][2] else ""],
    ])

    print(f"\n→ 全部导出到 {OUT}")
    print("  接下来：WPS 表格打开 → 选中数据 → 插入图表。见 README「出图」一节。")


if __name__ == "__main__":
    main()
