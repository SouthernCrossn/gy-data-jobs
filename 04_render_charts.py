# -*- coding: utf-8 -*-
"""用 Pillow 直接画PPT用图（不依赖 matplotlib）。

用法:  python 04_render_charts.py
输出:  charts/图1_技能.png / 图2_薪资.png / 图3_溢价.png
"""

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CH = ROOT / "charts"

NAVY = (27, 42, 65)
GOLD = (176, 141, 87)
GREY = (107, 107, 107)
LIGHT = (216, 210, 196)
CREAM = (247, 244, 236)
WHITE = (255, 255, 255)

W, H = 1920, 1080
F = "C:/Windows/Fonts/msyh.ttc"
FB = "C:/Windows/Fonts/msyhbd.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FB if bold else F, size)


def new_canvas():
    img = Image.new("RGB", (W, H), CREAM)
    return img, ImageDraw.Draw(img)


def title(d, text, sub=None):
    d.text((120, 70), text, font=font(52, True), fill=NAVY)
    if sub:
        d.text((120, 140), sub, font=font(26), fill=GREY)
    d.line([(120, 190), (W - 120, 190)], fill=LIGHT, width=2)


def read_csv(name):
    with (CH / name).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def meta():
    """从 汇总.csv 读样本量，避免把 n 写死在图里。"""
    d = {r["指标"]: r["数值"] for r in read_csv("汇总.csv")}
    total = int(d["样本总量"])
    gy = int(d["贵阳样本"])
    return total, gy, total - gy


def save(img, name):
    p = CH / name
    img.save(p)
    print("  OK", p.name)


# ---------------- 图1 技能提及率（横向条形） ----------------
def chart1():
    rows = read_csv("图1_技能提及率.csv")[:8]
    rows = rows[::-1]
    total, gy, sh = meta()
    img, d = new_canvas()
    title(d, "数据分析岗最常要求的能力", f"样本 {total} 条招聘信息 · 提及率 = 提到该能力的岗位占比")

    left, right, top, bottom = 400, 200, 300, 990
    n = len(rows)
    gap = (bottom - top) / n
    barh = gap * 0.55
    vmax = max(float(r["提及率(%)"]) for r in rows)

    for i, r in enumerate(rows):
        y = top + i * gap + (gap - barh) / 2
        v = float(r["提及率(%)"])
        w = (right * 0) + (v / vmax) * (W - left - right)
        d.text((120, y + barh / 2 - 22), r["技能"], font=font(30), fill=NAVY)
        d.rectangle([left, y, left + w, y + barh], fill=GOLD if i >= n - 3 else NAVY)
        d.text((left + w + 16, y + barh / 2 - 20), "%.0f%%" % v, font=font(30, True), fill=NAVY)
    save(img, "图1_技能.png")


# ---------------- 图2 薪资分布（簇状柱形） ----------------
def chart2():
    rows = read_csv("图2_薪资分布.csv")
    total, gy, sh = meta()
    img, d = new_canvas()
    title(d, "月薪分布：贵阳 vs 上海", "单位：千元/月 · 柱高 = 该薪资区间的岗位数")

    top, bottom = 300, 900
    vmax = max(max(int(r["贵阳"]), int(r["其他"])) for r in rows) or 1
    n = len(rows)
    slot = (W - 240) / n
    bw = slot * 0.28

    for i, r in enumerate(rows):
        x = 120 + i * slot + slot * 0.12
        for j, (key, color) in enumerate([("贵阳", GOLD), ("其他", NAVY)]):
            v = int(r[key])
            h = (v / vmax) * (bottom - top)
            bx = x + j * (bw + 8)
            d.rectangle([bx, bottom - h, bx + bw, bottom], fill=color)
            if v:
                d.text((bx + bw / 2 - 10, bottom - h - 40), str(v), font=font(24, True), fill=GREY)
        d.text((x + bw / 2, bottom + 18), r["月薪区间(千元)"], font=font(20), fill=GREY)

    d.line([(120, bottom), (W - 120, bottom)], fill=NAVY, width=3)
    # 图例
    d.rectangle([120, 225, 150, 250], fill=GOLD)
    d.text((165, 220), f"贵阳（n={gy}）", font=font(24), fill=NAVY)
    d.rectangle([420, 225, 450, 250], fill=NAVY)
    d.text((465, 220), f"上海（n={sh}）", font=font(24), fill=NAVY)
    save(img, "图2_薪资.png")


# ---------------- 图3 业务溢价 ----------------
def chart3():
    rows = read_csv("图3_业务溢价.csv")
    vals = {r["分组"]: (int(r["样本量"]), float(r["平均月薪(千元)"])) for r in rows}
    a = vals.get("要求业务/沟通", (0, 0))
    b = vals.get("未要求", (0, 0))

    total, gy, sh = meta()
    img, d = new_canvas()
    title(d, "把「业务分析」写进要求的岗位，薪水更高吗？",
          f"平均月薪，单位千元 · 样本 {total} 条（小样本，仅作方向参考）")

    top, bottom = 360, 880
    vmax = max(a[1], b[1]) * 1.25
    bars = [("要求业务分析", a, GOLD), ("未要求", b, (140, 140, 140))]
    slot = int((W - 400) / 2)

    for i, (label, (n, v), color) in enumerate(bars):
        x = 200 + i * slot + slot * 0.2
        bw = slot * 0.5
        h = (v / vmax) * (bottom - top)
        d.rectangle([x, bottom - h, x + bw, bottom], fill=color)
        d.text((x + bw / 2 - 62, bottom - h - 100), "%.1fK" % v, font=font(48, True), fill=NAVY)
        d.text((x + bw / 2 - 32, bottom - h + 22), "n=%d" % n, font=font(26), fill=WHITE)
        d.text((x + bw / 2 - 100, bottom + 20), label, font=font(28), fill=NAVY)

    gap = a[1] - b[1]
    d.text((W / 2 - 170, 250), "差值 %+.1fK（%+.0f%%）" % (gap, gap / b[1] * 100 if b[1] else 0),
           font=font(34, True), fill=GOLD)
    save(img, "图3_溢价.png")


if __name__ == "__main__":
    chart1()
    chart2()
    chart3()
