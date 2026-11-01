# 标准库组合与可复现统计

课程：Python｜讲义编号：python-09-stdlib｜整理日期：2026-10-31

## 实验情境与目标

课程作业的每日完成情况常常只需要标准库就能生成摘要。先查标准库能否解决问题，可以减少依赖数量与环境冲突。本实验组合日期、计数器和统计模块，把完成事件转换为每日数量及平均分，同时通过固定输入让结果可复现。

## 概念与设计步骤

记录中日期与成绩有不同处理规则：日期用于分组，缺失成绩不进入平均分。Counter 表达按键计数，statistics.mean 表达数值平均，datetime.date 表达日历日期而不是随意拼接的文字。标准库函数虽然简洁，仍要明确输入是否为空、日期是否合法、时区是否影响一天的划分。

## 可运行示例

运行环境：Python 3.12；仅使用标准库；在独立练习目录运行，避免覆盖已有文件。

```python
from collections import Counter
from datetime import date
from statistics import mean

records = [("2026-10-29", 80), ("2026-10-29", None),
           ("2026-10-30", 100), ("2026-10-30", 60)]
days = [date.fromisoformat(day) for day, _ in records]
daily = Counter(days)
grades = [score for _, score in records if score is not None]
for day, count in sorted(daily.items()):
    print(day.isoformat(), count)
average = mean(grades) if grades else None
print("平均成绩：", average)
assert average == 80
```

## 逐步验证与结果解释

两个日期各有两条完成事件，已评分的三条成绩平均为八十。未评分事件仍计入完成数量，因此两个统计各自有明确分母。排序用于稳定展示，与 Counter 如何积累计数无关。若来源是带时区的时间戳，应先转换为业务时区再截取日期，不能直接按字符串前十位分组后声称是本地日统计。

## 常见误区

mean 遇到空序列会失败，示例显式返回 None 表示暂无平均分。随机示例若不固定条件，截图之间难比较；测试应优先使用确定输入。日期字符串排序只有在统一规范格式时才可能与时间顺序一致，正式程序宜先解析。

## 练习

增加一个新日期和一条未评分事件，重新计算每日数量与平均分。再加入非法日期，记录解析异常。将平均分展示保留一位小数，同时保证计算阶段保留原数值而不是先转成字符串。

## 验收要点与思路

验收应同时给出完成事件总数、已评分数量与均分，保证三者没有混用。空记录时每天没有输出、平均分为 None。对无效日期应报错或进入明确的错误列表，不能静默放进一个无法辨认的分组。

## 官方来源与内容说明

- [标准库简介](https://docs.python.org/zh-cn/3.12/tutorial/stdlib.html)；发布方：Python Software Foundation；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
