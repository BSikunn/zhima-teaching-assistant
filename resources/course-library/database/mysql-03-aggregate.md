# 分组统计与统计口径

课程：数据库｜讲义编号：mysql-03-aggregate｜整理日期：2026-10-31

## 实验情境与目标

教学看板需要展示每班报名人数、已出分人数与平均成绩。这三个数字看起来相关，却不能共用一个未经说明的统计口径。报名人数包含未出分学生，平均成绩通常只基于已出分记录；如果把未知值替换成零，得到的是另一种指标。

## 概念与设计步骤

可以把分组理解为先把记录放进写有班名的袋子，再分别计算每袋的摘要。WHERE 过滤原始行，HAVING 过滤已经计算出的分组。使用严格分组习惯：展示字段要么是分组键，要么有明确聚合表达式，避免让数据库随意选取某个学生的姓名来代表整个班。指标名称应尽量写出分子、分母与时间范围。

## 可运行示例

运行环境：MySQL 8.0。建表型实验只在专用 library_lab 库运行；已有数据先备份，避免与其他作业表混用。

```sql
WITH marks AS (
 SELECT '一班' AS cls,90 AS score
 UNION ALL SELECT '一班',NULL
 UNION ALL SELECT '一班',60
 UNION ALL SELECT '二班',80
)
SELECT cls, COUNT(*) AS enrolled,
       COUNT(score) AS graded,
       AVG(score) AS mean_score,
       SUM(CASE WHEN score >= 60 THEN 1 ELSE 0 END) AS passed
FROM marks
GROUP BY cls
HAVING COUNT(*) >= 2
ORDER BY cls;
```

## 逐步验证与结果解释

结果只剩一班：报名三人，出分两人，平均七十五分，通过两人。二班被 HAVING 排除，原因是报名人数不足二，而不是因为成绩低。把 HAVING 改成 WHERE COUNT(*) >= 2 会产生错误，因为行筛选阶段没有当前分组的人数。先算后筛的直觉可以帮助检查条件放在哪里。

## 常见误区

COUNT(*) 与 COUNT(score) 在有空值时并不相同。AVG(COALESCE(score,0)) 会把未出分者纳入零分计算，必须先得到业务授权。连接其他明细表后再分组可能重复放大学生人数，不能靠 DISTINCT 掩盖不明原因的行数增长。

## 练习

增加一班一条四十分记录，手算新的平均分与通过率。再把看板改为只展示已经出分至少三人的班级，写出 HAVING 条件。最后说明按学生平均与按班级平均再平均为什么可能不同。

## 验收要点与思路

验收应保留空值与不同班级人数的样本；正确解答需要给出一班新平均值约六十三点三三，已出分三人，通过率为三分之二，并明确保留的小数位是展示要求。

## 官方来源与内容说明

- [Aggregate Function Descriptions](https://dev.mysql.com/doc/refman/8.0/en/aggregate-functions.html)；发布方：Oracle；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
