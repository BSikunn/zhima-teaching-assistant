# 文本文件、JSON与编码契约

课程：Python｜讲义编号：python-06-files｜整理日期：2026-10-31

## 实验情境与目标

一份课程名单在本机显示正常，换到另一台电脑却出现乱码，通常是因为文件编码、读写约定或内容结构没有讲清。本实验使用 UTF-8 和 JSON 保存中文课程数据，并强调文件的字节编码与 JSON 的数据类型是两层不同约定。

## 概念与设计步骤

with 负责在作用域退出时关闭文件，显式 encoding 避免依赖操作系统默认值。json.dump 把列表和字典转换成 JSON 文本，ensure_ascii=False 让中文在文件中保持可读，不代表更换编码。恢复时 json.load 返回 Python 对象，还应根据业务检查字段、类型与范围；解析成功不等于内容一定合法。

## 可运行示例

运行环境：Python 3.12；仅使用标准库；在独立练习目录运行，避免覆盖已有文件。

```python
import json
from pathlib import Path
path = Path("course-records.json")
records = [{"id": 1, "title": "数据库", "hours": 32},
           {"id": 2, "title": "Python", "hours": 48}]
with path.open("w", encoding="utf-8") as handle:
    json.dump(records, handle, ensure_ascii=False, indent=2)
with path.open("r", encoding="utf-8") as handle:
    restored = json.load(handle)
print(restored[0]["title"])
assert restored == records
assert sum(row["hours"] for row in restored) == 80
```

## 逐步验证与结果解释

在独立练习目录运行代码，会生成 course-records.json，中文名称能够恢复为原字符串，总学时为八十。这里以 w 模式写文件会覆盖同名文件，练习时应确认目标文件属于本次实验。若只是追加一份完整 JSON 到文件末尾，通常不再是单个合法 JSON 文档；日志场景可以另行采用每行一条 JSON 的格式。

## 常见误区

不要把 Python 字典的 str 输出当成 JSON，它可能使用单引号、None 或其他不兼容表示。不要用 eval 解析外部文本。相对路径取决于当前工作目录，不能假定总在源文件旁边。读取非常大的文件时应考虑流式格式或分块处理，而不是无条件一次全部载入。

## 练习

为读取结果增加验证：顶层必须为列表，每项必须有整数编号、非空标题和正数学时。分别制造无效 JSON、缺失字段和学时为负的文件，记录它们应该在哪一层被拒绝。最后讨论保存前备份与临时文件替换的必要性。

## 验收要点与思路

验收包括中文往返、缺失文件、格式错误和合法但业务无效的数据。错误提示应区分文件读取失败、JSON 解析失败与业务验证失败，不要用一个空列表悄悄替代所有错误。

## 官方来源与内容说明

- [输入与输出](https://docs.python.org/zh-cn/3.12/tutorial/inputoutput.html)；发布方：Python Software Foundation；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
