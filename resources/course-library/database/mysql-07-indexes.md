# 索引选择与执行计划入门

课程：数据库｜讲义编号：mysql-07-indexes｜整理日期：2026-10-31

## 实验情境与目标

教务系统经常按班级筛选并按成绩排序展示学生。数据量小的时候任何查询都很快，但不能据此决定是否需要索引。本讲义把查询条件和索引列顺序放在一起分析，并明确区分预测、优化器估计和实际运行结果。

## 概念与设计步骤

联合索引应围绕真实查询设计。这里索引的列顺序是班级、成绩、编号，目的是支持按班级定位后读取有序成绩与稳定编号。索引也会占空间并增加写入维护成本，因此不是字段越多越好。执行计划是观察优化器选择的窗口；小表可能选择扫描，即使已经建立了看似匹配的索引也属于合理结果。

## 可运行示例

运行环境：MySQL 8.0。建表型实验只在专用 library_lab 库运行；已有数据先备份，避免与其他作业表混用。

```sql
CREATE DATABASE IF NOT EXISTS library_lab CHARACTER SET utf8mb4;
USE library_lab;
CREATE TABLE IF NOT EXISTS lab_score (
 id INT PRIMARY KEY,cls VARCHAR(30) NOT NULL,score INT NOT NULL,
 INDEX ix_class_score(cls,score,id)
) ENGINE=InnoDB;
INSERT INTO lab_score VALUES
 (1,'一班',70),(2,'二班',88),(3,'一班',95)
 ON DUPLICATE KEY UPDATE score=VALUES(score);
EXPLAIN SELECT id,score FROM lab_score
 WHERE cls='一班' ORDER BY score,id;
SELECT id,score FROM lab_score
 WHERE cls='一班' ORDER BY score,id;
```

## 逐步验证与结果解释

结果应为编号一的七十分和编号三的九十五分。查看 EXPLAIN 的 key、rows、Extra，记录实际值而不是预先规定必须出现某种访问类型。VALUES(score) 是本例兼容 MySQL 8.0 早期版本的重复键更新写法，在较新小版本会有弃用提示；正式项目应按部署版本调整，课堂只借它保持样本可重复执行。

## 常见误区

只看有没有索引名称不能判断性能；返回大量记录时扫描可能更便宜。对索引列套函数或发生隐式类型转换，可能改变可用访问路径。LIKE 前置通配符与后置通配符的访问特征也不同。优化前后必须比较结果一致性，不能为了少扫数据把条件改错。

## 练习

把筛选改为只按 score 查询，预测能否像按 cls 一样利用索引前缀。再增加按 cls、score、id 的范围条件，比较计划。设计一个更大但可控的数据集，记录索引前后耗时与记录数。

## 验收要点与思路

提交查询、实际计划以及解释。小样本耗时不足以证明收益时应如实写出这一限制；如果 EXPLAIN 显示扫描，也应先检查行数和成本，再决定是否需要修改索引，而不是强制优化器迎合答案。

## 官方来源与内容说明

- [Optimization and Indexes](https://dev.mysql.com/doc/refman/8.0/en/optimization-indexes.html)；发布方：Oracle；访问核对日期：2026-10-31。
- [EXPLAIN Statement](https://dev.mysql.com/doc/refman/8.0/en/explain.html)；发布方：Oracle；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
