# -*- coding: utf-8 -*-
"""
把 raw/*.txt 里的岗位文本块，解析成 CSV + SQLite。

用法:  python 01_build_db.py
依赖:  仅标准库（不需要联网、不需要 pip）

输入格式:
  raw/ 下放若干 .txt 文件，岗位之间用一行 ### 分隔（见 README 的正则替换技巧）。
"""

import csv
import hashlib
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
DATA = ROOT / "data"

# ============ 改这里：技能词典 ============
# 命中任一关键词即算"提及"，不区分大小写。想加技能就往对应类别里加词组。
SKILLS = {
    "SQL": ["sql", "mysql", "hive sql", "oracle"],
    "Python": ["python", "pandas", "numpy", "scrapy"],
    "Excel": ["excel", "透视表", "vlookup"],
    "BI可视化": ["tableau", "power bi", "powerbi", "帆软", "finebi", "fine report", "bi工具", "可视化"],
    "R/SPSS": [" r语言", "r语言", "spss", "sas"],
    "大数据组件": ["hadoop", "hive", "spark", "flink", "clickhouse", "linux", "shell"],
    "建模算法": ["机器学习", "建模", "算法", "深度学习", "xgboost", "预测模型"],
    "统计分析": ["统计学", "回归", "a/b", "ab测试", "假设检验", "描述统计"],
    "数据仓库": ["数据仓库", "数仓", "etl", "数据建模规范"],
    "报表自动化": ["报表", "自动化", "定时任务", "看板"],
    # 注意：这里刻意不用裸的"业务"二字——"业务部门""支持业务"几乎每份 JD 都有，
    # 用了它会让"业务溢价"的对比失效。只认真正的分析能力词。
    "业务分析": ["指标体系", "用户画像", "运营分析", "业务分析", "商业分析", "数据驱动", "业务建模"],
    "沟通表达": ["沟通", "表达", "汇报", "演讲", "对接"],
}

# 两类：给图 3 用
SOFT = {"业务分析"}

SALARY = re.compile(
    r"(\d+(?:\.\d+)?)\s*([Kk千万]?)\s*[-~—至]\s*(\d+(?:\.\d+)?)\s*([Kk千万Ww元]?)"
    r"(?![\d\-])(?![人名个年天月岁次条周])"
)
EXP = re.compile(r"(\d+)\s*[-~—]\s*(\d+)\s*年")
EXP_OPEN = re.compile(r"(\d+)\s*年以上")
CITIES = ["贵阳", "遵义", "六盘水", "安顺", "毕节", "铜仁", "黔东南", "黔南", "黔西南",
          "北京", "上海", "深圳", "广州", "杭州", "成都", "重庆", "武汉", "西安",
          "南京", "长沙", "昆明", "天津", "苏州"]
GUIZHOU = {"贵阳", "遵义", "六盘水", "安顺", "毕节", "铜仁", "黔东南", "黔南", "黔西南"}
EDUS = ["本科", "大专", "硕士", "博士", "学历不限", "不限"]


def to_k(v: float, unit: str) -> float:
    """把薪资统一换算成 千元/月"""
    if unit in ("万", "W", "w"):
        return v * 10.0
    if unit == "元" or (unit == "" and v >= 200):
        return v / 1000.0
    return v


HEAD_MARKS = ("职位描述", "岗位职责", "工作职责", "职位信息", "职位详情")
TAIL_MARKS = ("职位发布者", "公司信息", "公司介绍", "相似职位", "看了又看",
              "竞争分析", "热门职位", "工商信息")

# 岗位类型把关：只留"分析"类岗位
KEEP_TITLE = re.compile(r"数据分析|商业分析|数据运营|BI|数据专员")
BAD_TITLE = re.compile(r"标注|采集|录入|销售|讲师|老师|实施|运维|开发|客服|运营经理")


def split_detail(block):
    """把整页复制的文本，切成【岗位头部】和【JD 正文】。

    招聘网站详情页整页复制时，前后会混进搜索结果列表、发布者信息、公司信息、
    相似职位——这些地方含大量别的岗位的技能标签。不切掉，词频会被污染成 100%。
    """
    m = re.search("|".join(HEAD_MARKS), block)
    if not m:
        return block[:800], block

    body = block[m.start():]
    for mark in TAIL_MARKS:
        i = body.find(mark)
        if i > 0:
            body = body[:i]
            break
    header = block[:m.start()][-500:]
    return header, body


def last_match(rx, text):
    """取最后一次匹配。详情页头部上方还挂着搜索结果列表，
    用第一次匹配会抓到别人的薪资。"""
    ms = list(rx.finditer(text))
    return ms[-1] if ms else None


TITLE_JUNK = re.compile(r"^(\d+薪|发布|收藏|分享|举报|置顶|热招|急招|更多|查看.*|全职|兼职|实习|欢迎您|登录|注册|搜索|首页)$")
TITLE_WORD = re.compile(r"分析|数据|运营|BI|专员|工程师|经理")


def pick_title(header, fallback):
    """从下往上找离正文最近的那行薪资，岗位名通常就在同一行或上一行。"""
    hlines = [ln.strip() for ln in header.splitlines() if ln.strip()]
    for i in range(len(hlines) - 1, -1, -1):
        if not SALARY.search(hlines[i]):
            continue
        # 情况一：岗位名和薪资同一行，如"大数据开发工程师 1.5-3万"
        rest = SALARY.sub("", hlines[i]).strip(" ·|-—\t")
        if (2 <= len(rest) <= 30 and re.search(r"[\u4e00-\u9fa5]", rest)
                and not TITLE_JUNK.match(rest)):
            return rest
        # 情况二：岗位名在上一行
        for j in range(i - 1, -1, -1):
            cand = hlines[j]
            if 2 <= len(cand) <= 25 and not re.search(r"\d", cand) \
                    and not TITLE_JUNK.match(cand):
                return cand
        break
    # 情况三：版面把岗位名放在别处，按"像岗位名"的词兜底
    for cand in reversed(hlines):
        if (2 <= len(cand) <= 22 and TITLE_WORD.search(cand)
                and not re.search(r"\d", cand) and not TITLE_JUNK.match(cand)):
            return cand
    return fallback[:60]


def parse_block(block: str, source: str):
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if not lines:
        return None

    header, body = split_detail(block)
    title = pick_title(header, lines[0])

    text = header.replace("\n", " ")
    fallback = block.replace("\n", " ")
    low = " " + (body or block).lower() + " "

    s_min = s_max = None
    m = last_match(SALARY, text) or last_match(SALARY, fallback)
    if m:
        # 上下限的单位可能不一样："6千-1万""5000-7000元""8-13K"
        u_min = m.group(2) or m.group(4) or ""
        u_max = m.group(4) or m.group(2) or ""
        s_min = to_k(float(m.group(1)), u_min)
        s_max = to_k(float(m.group(3)), u_max)
        if s_min > s_max:
            s_min, s_max = s_max, s_min

    e_min = e_max = None
    m2 = last_match(EXP, text) or last_match(EXP, fallback)
    if m2:
        e_min, e_max = int(m2.group(1)), int(m2.group(2))
    else:
        m3 = last_match(EXP_OPEN, text) or last_match(EXP_OPEN, fallback)
        if m3:
            # "3年以上" → 记为 3 年起，上限留空用 99 表示"不封顶"
            e_min, e_max = int(m3.group(1)), 99
        elif "应届" in text or "经验不限" in text or "无需经验" in text:
            e_min = e_max = 0

    edu = next((e for e in EDUS if e in text), "")

    city = next((c for c in CITIES if c in text), "")
    if "贵州" in text and city not in GUIZHOU:
        # JD 只写"贵州"没写具体市，按贵阳处理
        city = city or "贵阳"
    region = "贵阳" if city in GUIZHOU else "其他"

    hits = []
    for skill, kws in SKILLS.items():
        if any(kw in low for kw in kws):
            hits.append(skill)

    return {
        "source": source,
        "title": title,
        "city": city,
        "region": region,
        "salary_min": s_min,
        "salary_max": s_max,
        "salary_med": None if s_min is None else round((s_min + s_max) / 2, 1),
        "exp_min": e_min,
        "exp_max": e_max,
        "edu": edu,
        "skills": ";".join(hits),
        "n_skill": len(hits),
        "soft_skill": int(bool(set(hits) & SOFT)),
    }


def main():
    DATA.mkdir(exist_ok=True)
    files = sorted(f for f in RAW.glob("*.txt")
                   if not f.stem.startswith(("_", "命令")))
    if not files:
        print("× raw/ 里没有 txt。先把采集的文本放进去。")
        return

    rows = []
    skipped = []
    seen = set()
    dups = 0
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        blocks = re.split(r"\n\s*#{3,}\s*\n", txt)
        n = 0
        for b in blocks:
            r = parse_block(b, f.stem)
            if not r:
                continue
            # 岗位类型把关：不是"数据分析"类的一律剔除，否则词频会被
            # 数据标注 / 计划运营 / 实施 这类岗位的 Excel 要求带偏
            t = r["title"]
            ok = bool(KEEP_TITLE.search(t)) and not BAD_TITLE.search(t)
            if not ok and "分析" in t and len(t) <= 6 and not BAD_TITLE.search(t):
                # 网站把标题截断了（只剩"分析师"），改看正文里有没有"数据分析"
                if "数据分析" in split_detail(b)[1]:
                    ok = True
            if not ok:
                skipped.append(t)
                continue
            # 去重：同一条岗位被复制了两次（页面详情/正文略有差异，所以
            # 用"岗位名+薪资+经验+学历"做指纹，而不是比对原文）
            key = "%s|%s|%s|%s|%s|%s" % (r["title"], r["salary_min"], r["salary_max"],
                                         r["exp_min"], r["exp_max"], r["edu"])
            if key in seen:
                dups += 1
                continue
            seen.add(key)
            rows.append(r)
            n += 1
        print(f"  {f.name}: {n} 条")

    if skipped:
        print(f"  × 剔除 {len(skipped)} 条（岗位类型不符）：")
        for t in skipped:
            print(f"      - {t}")
    if dups:
        print(f"  × 去重 {dups} 条（同一条被复制了多次）")

    if not rows:
        print("× 没解析出数据，检查 ### 分隔符")
        return

    csv_path = DATA / "jobs.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    db_path = DATA / "jobs.db"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, title TEXT, city TEXT, region TEXT,
            salary_min REAL, salary_max REAL, salary_med REAL,
            exp_min INTEGER, exp_max INTEGER, edu TEXT,
            n_skill INTEGER, soft_skill INTEGER
        )""")
    cur.execute("CREATE TABLE job_skills (job_id INTEGER, skill TEXT)")

    for i, r in enumerate(rows, 1):
        cur.execute(
            "INSERT INTO jobs (id,source,title,city,region,salary_min,salary_max,"
            "salary_med,exp_min,exp_max,edu,n_skill,soft_skill) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (i, r["source"], r["title"], r["city"], r["region"], r["salary_min"],
             r["salary_max"], r["salary_med"], r["exp_min"], r["exp_max"],
             r["edu"], r["n_skill"], r["soft_skill"]),
        )
        for sk in filter(None, r["skills"].split(";")):
            cur.execute("INSERT INTO job_skills VALUES (?,?)", (i, sk))
    con.commit()

    total = len(rows)
    with_salary = sum(1 for r in rows if r["salary_med"] is not None)
    gy = sum(1 for r in rows if r["region"] == "贵阳")
    print(f"\n√ 总条数 {total}｜贵阳 {gy}｜其他 {total - gy}")
    print(f"√ 薪资可解析 {with_salary} 条（{with_salary / total:.0%}）")
    print(f"√ 已写入 {csv_path.name} 与 {db_path.name}")
    if with_salary / total < 0.6:
        print("! 薪资解析率偏低，抽查 raw 里的薪资写法，补一下 SALARY 正则")


if __name__ == "__main__":
    main()
