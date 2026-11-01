# 备份恢复与可验证的数据演练

课程：数据库｜讲义编号：mysql-10-backup｜整理日期：2026-10-31

## 实验情境与目标

课程项目常见的风险是有一个备份文件，却从未验证能否恢复。备份的目标不是生成文件，而是在规定的恢复范围内重建可用数据。本讲义以独立练习数据库为对象，设计从备份到新库恢复再核对的完整流程，所有输出留在项目目录。

## 概念与设计步骤

逻辑备份记录建表与数据写入语句，便于审阅和跨环境恢复，但其一致性取决于数据库引擎、选项及备份期间的操作。示例的 single-transaction 面向事务表，并不意味着可以无视同时进行的结构变更。备份前写下服务器版本、数据库名、备份时间和校验方式，恢复时再核对这些信息。

## 可运行示例

```powershell
# 在项目根目录的 PowerShell 中执行；先有独立的 library_lab 练习库。
New-Item -ItemType Directory -Force .cache/course-backup | Out-Null
mysqldump -u root -p --single-transaction --routines --triggers --no-tablespaces --set-gtid-purged=OFF --result-file=.cache/course-backup/library-lab.sql library_lab
Get-FileHash .cache/course-backup/library-lab.sql -Algorithm SHA256
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS library_restore CHARACTER SET utf8mb4"
mysql -u root -p library_restore -e "source .cache/course-backup/library-lab.sql"
```

## 逐步验证与结果解释

命令中的密码由客户端提示输入，不应写进脚本或提交仓库。使用 result-file 避免某些 PowerShell 版本的重定向编码改变 SQL 文件。恢复目标是独立的新库，练习前应确认其中没有需要保留的数据。恢复结束后比较表清单、行数、关键业务汇总和约束，不以命令退出码为唯一证据。

## 常见误区

包含 CREATE DATABASE 或 USE 原库语句的转储会影响恢复目标，因此本例不用 databases 选项，也不把整个服务器盲目导出。混合非事务表时需另外设计一致性措施。文件哈希只能证明两份文件字节相同，不能证明里面的数据完整或能恢复。备份还可能包含个人信息，应使用项目私有缓存目录保存。

## 练习

在原练习库插入一条带中文的新记录，重新备份后恢复到另一新库；对比记录数与具体内容。故意只恢复表结构，观察哪些校验能发现遗漏。写出一次恢复演练记录，说明恢复耗时与尚未覆盖的对象。

## 验收要点与思路

合格记录应包含备份哈希、工具版本、目标库、表及行数对照、至少一条中文记录校验和异常说明。如果未测试存储过程或权限，应明确记录覆盖范围；不要从一次小库成功推断生产全量恢复一定满足时限。

## 官方来源与内容说明

- [mysqldump — A Database Backup Program](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html)；发布方：Oracle；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
