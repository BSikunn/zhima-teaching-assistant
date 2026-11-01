# 事务、回滚与并发扣库存

课程：数据库｜讲义编号：mysql-06-transactions｜整理日期：2026-10-31

## 实验情境与目标

两名同学同时报名最后一个课程名额时，先查询剩余数量、在程序中减一、再更新的流程可能让双方都认为报名成功。本实验先理解单个事务的原子性，再讨论为什么原子事务仍然需要正确的并发写法。代码只操作专门的练习表，不修改业务课程。

## 概念与设计步骤

把一次报名相关的名额扣减与报名记录写入放在同一个事务中，能够让成功一起提交、失败一起回滚。减少库存时使用带条件的 UPDATE，把名额大于零的检查与扣减放进同一条写入语句，然后检查受影响行数。隔离级别影响事务观察到的数据，但不能替代对业务约束的清晰设计。

## 可运行示例

运行环境：MySQL 8.0。建表型实验只在专用 library_lab 库运行；已有数据先备份，避免与其他作业表混用。

```sql
CREATE DATABASE IF NOT EXISTS library_lab CHARACTER SET utf8mb4;
USE library_lab;
CREATE TABLE IF NOT EXISTS lab_seat (
 course_id INT PRIMARY KEY,remaining INT NOT NULL
) ENGINE=InnoDB;
INSERT INTO lab_seat VALUES(41,1)
 ON DUPLICATE KEY UPDATE remaining=1;
START TRANSACTION;
UPDATE lab_seat SET remaining=remaining-1
 WHERE course_id=41 AND remaining>0;
SELECT ROW_COUNT() AS changed;
SELECT remaining FROM lab_seat WHERE course_id=41;
ROLLBACK;
SELECT remaining FROM lab_seat WHERE course_id=41;
```

## 逐步验证与结果解释

事务内剩余数量为零，ROLLBACK 之后恢复为一；changed 应为一。把条件改成 remaining>1 时更新零行，不能继续插入成功报名。实际应用应在同一连接中处理事务，在扣减成功后写报名记录，并为学生与课程组合设置唯一约束。这样既防止超卖，也防止同一人重复报名占用两个名额。

## 常见误区

不要把 DDL 当成可随意回滚的普通业务更新，本实验在 START TRANSACTION 之前建表。事务不应跨用户等待或长时间网络调用。遇到死锁时需要回滚并按有限重试策略重新执行整个业务事务，不能只补执行最后一条语句。

## 练习

把回滚改为提交并再次查询；随后从两个数据库会话同时尝试扣减一份名额，记录哪次更新零行、哪次可能等待。设计报名记录写入失败时的回滚处理，并解释为什么必须复用同一事务连接。

## 验收要点与思路

验收要求剩余数量从不为负，只有受影响一行的请求获得报名资格，报名记录写入失败后名额恢复。并发实验应记录两个会话各自的提交顺序，不能仅凭最终库存为零就断言没有重复报名。

## 官方来源与内容说明

- [InnoDB Transaction Model](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-model.html)；发布方：Oracle；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
