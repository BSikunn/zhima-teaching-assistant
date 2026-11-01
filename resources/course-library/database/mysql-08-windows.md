# 窗口函数与分组前几名

课程：数据库｜讲义编号：mysql-08-windows｜整理日期：2026-10-31

## 实验情境与目标

老师需要每个班级成绩最高的两位学生，同时还要显示每个学生与本班平均分的差距。普通 GROUP BY 会把学生明细合并，无法直接同时保留个人信息。窗口计算适合在明细行上附加组内统计，但排名规则必须先说明同分如何处理。

## 概念与设计步骤

ROW_NUMBER 给每一行一个顺序位置，RANK 与 DENSE_RANK 则表达不同的并列名次规则。本例选择每班严格两行，因此使用 ROW_NUMBER，并加入编号作为同分时的稳定顺序。班级平均分用 AVG 加 PARTITION BY 计算，保留各个学生明细。先在公共表表达式中计算排名，再在外层筛选，查询结构更容易逐步验证。

## 可运行示例

运行环境：MySQL 8.0。建表型实验只在专用 library_lab 库运行；已有数据先备份，避免与其他作业表混用。

```sql
WITH marks AS (
 SELECT 1 AS id,'一班' AS cls,90 AS score
 UNION ALL SELECT 2,'一班',90
 UNION ALL SELECT 3,'一班',80
 UNION ALL SELECT 4,'二班',70
), ranked AS (
 SELECT id,cls,score,
 ROW_NUMBER() OVER(PARTITION BY cls ORDER BY score DESC,id) AS rn,
 AVG(score) OVER(PARTITION BY cls) AS class_mean
 FROM marks
)
SELECT id,cls,score,rn,ROUND(score-class_mean,2) AS gap
FROM ranked WHERE rn<=2 ORDER BY cls,rn;
```

## 逐步验证与结果解释

结果是一班编号一和二，以及二班编号四，共三行。一班平均约八十六点六七，因此两位九十分学生各比均值高约三点三三。二班只有一人，其差值为零。窗口内的排序用于计算排名，最终展示仍有独立的 ORDER BY；不能假设窗口排序自动决定整张结果的输出顺序。

## 常见误区

在同一层 WHERE 中直接使用刚计算的排名别名通常不成立，应使用外层查询。把 ROW_NUMBER 改成 DENSE_RANK 之后，前两名可能超过两个人，这是业务定义变化。滚动累计要明确 ROWS 或 RANGE 的窗口范围，同分排序键会影响默认窗口的含义。

## 练习

增加一班另一位八十分学生，分别使用三种排名函数输出全部排名，再讨论前两行与前两名的差别。写出保留所有并列冠军的查询，并预测冠军人数。最后把平均分改成班级最高分，计算距最高分的差。

## 验收要点与思路

并列冠军仍为两位九十分学生；如果按不同分值的前两名筛选，则八十分的两位也应保留。验收重点是解释人数变化的原因，并用包含同分的样本证明查询符合已经声明的排名规则。

## 官方来源与内容说明

- [Window Function Concepts and Syntax](https://dev.mysql.com/doc/refman/8.0/en/window-functions-usage.html)；发布方：Oracle；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
