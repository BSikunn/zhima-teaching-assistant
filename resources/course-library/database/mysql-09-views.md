# 视图、接口字段与更新边界

课程：数据库｜讲义编号：mysql-09-views｜整理日期：2026-10-31

## 实验情境与目标

课程系统要给助教展示成绩概览，却不需要在每个查询中重复计算通过标记。视图可以把稳定的查询封装成有名字的关系，让调用方围绕字段契约使用它。本讲义强调视图定义与权限配置是两件事，不能把隐藏字段当成已经完成访问控制。

## 概念与设计步骤

先建立一张独立成绩表，再创建只包含学生编号、成绩和通过标记的视图。视图通常保存查询定义，查询时反映底层数据，并不是自动维护的历史快照。能否更新视图受其定义限制；带聚合或某些复杂表达式的视图不可直接作为通用写入接口。正式系统还应显式考虑 SQL SECURITY、定义者和授权。

## 可运行示例

运行环境：MySQL 8.0。建表型实验只在专用 library_lab 库运行；已有数据先备份，避免与其他作业表混用。

```sql
CREATE DATABASE IF NOT EXISTS library_lab CHARACTER SET utf8mb4;
USE library_lab;
CREATE TABLE IF NOT EXISTS lab_grade (
 student_id INT PRIMARY KEY,score INT NOT NULL,private_note VARCHAR(100)
) ENGINE=InnoDB;
INSERT INTO lab_grade VALUES(1,59,'需要单独辅导')
 ON DUPLICATE KEY UPDATE score=59;
CREATE OR REPLACE VIEW lab_grade_public AS
 SELECT student_id,score,(score>=60) AS passed FROM lab_grade;
SELECT * FROM lab_grade_public;
UPDATE lab_grade SET score=75 WHERE student_id=1;
SELECT * FROM lab_grade_public;
```

## 逐步验证与结果解释

第一次查询中 passed 为零，更新底表后第二次变为一。视图没有复制一份固定的五十九分记录，而是重新呈现当前查询结果。private_note 没有出现在视图字段中，但如果同一数据库账号仍能查询底表，它仍然可以读到备注。因此限制视图字段只有在配合适当授权时才成为有效的数据访问边界。

## 常见误区

SELECT * 会让接口字段随底表变化，稳定的数据契约应显式列出列名。不要为了让聚合视图可写而绕过约束。修改视图列名时需要检查依赖报表。创建视图时还要考虑定义者账号的生命周期，避免账号删除后依赖它的视图突然不可访问。

## 练习

创建按班级显示平均分与人数的汇总视图，并讨论它为什么不适合直接 INSERT 一条班级平均分。设计只授予某个教学账号访问指定视图的权限清单，说明哪些底表权限不应同时授予。

## 验收要点与思路

验收需要验证视图查询结果会随底层更新而变化、暴露字段符合约定，以及使用目标教学账号实际尝试读取底表时被拒绝。仅在管理员会话里查看视图字段无法证明权限配置成功。

## 官方来源与内容说明

- [Using Views](https://dev.mysql.com/doc/refman/8.0/en/views.html)；发布方：Oracle；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
