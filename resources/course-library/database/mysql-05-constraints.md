# 主外键与数据完整性实验

课程：数据库｜讲义编号：mysql-05-constraints｜整理日期：2026-10-31

## 实验情境与目标

图书借阅系统不能出现借阅记录指向不存在的读者。仅在界面下拉框中限制选择还不够，因为脚本、导入或并发操作都可能绕过界面。本实验在数据库层声明关系，让错误数据在写入时被拒绝，并观察应用应该怎样处理这一类失败。

## 概念与设计步骤

父表保存读者身份，子表保存借阅事件；子表的 reader_id 引用父表主键。外键负责引用存在性，不会替你判断读者是否有借阅权限、是否达到借阅上限。删除规则也是业务决定：历史借阅常常需要保留，因此示例显式采用 RESTRICT，要求先处理引用关系再删除读者，而不是为了让删除成功就级联抹掉历史。

## 可运行示例

运行环境：MySQL 8.0。建表型实验只在专用 library_lab 库运行；已有数据先备份，避免与其他作业表混用。

```sql
CREATE DATABASE IF NOT EXISTS library_lab CHARACTER SET utf8mb4;
USE library_lab;
CREATE TABLE IF NOT EXISTS lab_reader (
 id INT PRIMARY KEY,name VARCHAR(40) NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS lab_loan (
 id INT PRIMARY KEY,reader_id INT NOT NULL,book VARCHAR(80) NOT NULL,
 CONSTRAINT fk_lab_reader FOREIGN KEY(reader_id)
 REFERENCES lab_reader(id) ON DELETE RESTRICT
) ENGINE=InnoDB;
INSERT INTO lab_reader VALUES(21,'小禾');
INSERT INTO lab_loan VALUES(301,21,'数据库练习册');
SELECT * FROM lab_loan;
```

## 逐步验证与结果解释

先完成成功路径，确认借阅记录确实关联到已有读者。再单独执行 INSERT INTO lab_loan VALUES(302,999,'孤立记录')，预期外键拒绝；此失败语句不放在可直接运行的成功代码块里。最后尝试删除编号二十一的读者，也应因仍有子表引用被阻止。这两个错误验证了不同方向的完整性保护。

## 常见误区

外键字段与被引用字段应保持兼容的类型定义，并检查数据库引擎是否支持所需行为。不能把关闭外键检查当作日常修复手段。允许为空的外键意味着关系可以缺失，和填入一个不存在编号不是一回事；本例通过 NOT NULL 明确要求每条借阅必须有读者。

## 练习

为借阅表增加归还日期，讨论日期为空的业务含义。提出停用读者但保留借阅历史的方案，再解释为何删除读者记录并不是唯一选择。测试重复主键、未知读者和合法借阅三种输入。

## 验收要点与思路

可采用独立的状态字段表示停用，并让借阅接口检查状态。验收重点是非法引用无法落库，原有借阅仍能查到，同时应用把约束异常转成用户能理解的提示，而不是把整段数据库堆栈展示出来。

## 官方来源与内容说明

- [FOREIGN KEY Constraints](https://dev.mysql.com/doc/refman/8.0/en/constraint-foreign-key.html)；发布方：Oracle；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
