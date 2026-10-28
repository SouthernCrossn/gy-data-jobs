-- 用 DBeaver 打开 data/jobs.db，然后逐条运行。
-- 每条查完，把结果抄进 README，别只截图不写字。

-- Q1 样本概况：总条数、贵阳占比、薪资可解析率
SELECT COUNT(*) AS 总数,
       SUM(region = '贵阳') AS 贵阳,
       SUM(salary_med IS NOT NULL) AS 有薪资,
       ROUND(1.0 * SUM(salary_med IS NOT NULL) / COUNT(*), 3) AS 薪资解析率
FROM jobs;

-- Q2 技能提及率 TOP10（全样本）
SELECT skill AS 技能,
       COUNT(*) AS 提及数,
       ROUND(1.0 * COUNT(*) / (SELECT COUNT(*) FROM jobs), 3) AS 提及率
FROM job_skills
GROUP BY skill
ORDER BY 提及数 DESC
LIMIT 10;

-- Q3 贵阳 vs 其他：技能差异（只看提及率差 10 个百分点以上的）
SELECT skill AS 技能,
       ROUND(1.0 * SUM(region = '贵阳') / (SELECT SUM(region = '贵阳') FROM jobs), 3) AS 贵阳率,
       ROUND(1.0 * SUM(region <> '贵阳') / (SELECT SUM(region <> '贵阳') FROM jobs), 3) AS 其他率
FROM job_skills
GROUP BY skill
ORDER BY 贵阳率 DESC;

-- Q4 薪资：贵阳 vs 其他（中位数与样本量）
SELECT region AS 地区,
       COUNT(salary_med) AS 样本量,
       ROUND(AVG(salary_med), 1) AS 均值,
       MIN(salary_med) AS 最低, MAX(salary_med) AS 最高
FROM jobs
WHERE salary_med IS NOT NULL
GROUP BY region;

-- Q5 ★命门：要求"业务/沟通"的岗位，薪资是不是更高？
-- soft_skill=1 表示 JD 里出现了"业务理解"或"沟通表达"类词
SELECT soft_skill AS 提及业务或沟通,
       COUNT(*) AS 样本量,
       ROUND(AVG(salary_med), 1) AS 薪资均值,
       ROUND(AVG(n_skill), 1) AS 平均技能数
FROM jobs
WHERE salary_med IS NOT NULL
GROUP BY soft_skill;

-- Q6 经验门槛分布（回答"大一有没有机会"）
SELECT CASE
         WHEN exp_max = 0 THEN '经验不限/应届'
         WHEN exp_max <= 1 THEN '1年以内'
         WHEN exp_max <= 3 THEN '1-3年'
         ELSE '3年以上'
       END AS 经验段,
       COUNT(*) AS 岗位数,
       ROUND(AVG(salary_med), 1) AS 薪资均值
FROM jobs
GROUP BY 经验段
ORDER BY 岗位数 DESC;
