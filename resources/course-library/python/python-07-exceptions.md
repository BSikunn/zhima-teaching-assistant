# 异常处理与失败信息保留

课程：Python｜讲义编号：python-07-exceptions｜整理日期：2026-10-31

## 实验情境与目标

成绩导入程序遇到一条坏记录时，是停止全部导入、跳过这条记录还是提示用户修正，应由业务决定。本讲义通过一个小型解析函数区分缺失、格式错误和范围错误，并保留足够上下文，让失败能够被解释和复现。

## 概念与设计步骤

把可预期的输入问题转换为明确的 ValueError，调用方按记录处理并收集错误。捕获异常的范围应尽量小，避免把后续程序缺陷也伪装成用户输入错误。异常链使用 raise ... from ... 保留底层原因；对用户显示简短业务说明，对调试日志保留更详细的上下文，两者承担不同职责。

## 可运行示例

运行环境：Python 3.12；仅使用标准库；在独立练习目录运行，避免覆盖已有文件。

```python
def parse_score(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError("成绩必须是整数文本") from error
    if not 0 <= value <= 100:
        raise ValueError("成绩必须介于零和一百之间")
    return value

values, errors = [], []
for index, raw in enumerate(["90", "abc", "105", "60"], start=1):
    try:
        values.append(parse_score(raw))
    except ValueError as error:
        errors.append(f"第 {index} 条：{error}")
print(values)
print(errors)
assert values == [90, 60]
```

## 逐步验证与结果解释

结果保留九十与六十两条有效成绩，并记录第二条格式错误、第三条超范围。循环继续是本实验明确选择的策略，不代表所有导入都应部分成功。涉及跨记录一致性时，可能必须先验证整批，再一次提交；否则用户会误以为全部失败，重新上传后又产生重复。

## 常见误区

except Exception 后直接 pass 会丢失错误信息。用 return 放在 finally 中还可能覆盖原本的返回值或异常，应避免。不要捕获 BaseException 来吞掉键盘中断和退出信号。异常信息中包含文件路径或原始敏感数据时，展示与日志需要按使用场景筛选。

## 练习

把空字符串、None、负数和边界一百分加入输入，预测成功与错误数量。再把策略改为遇到任何坏记录就整批拒绝，要求返回所有错误而不是只报第一条。比较两种策略下用户修复与重试的体验。

## 验收要点与思路

验收时九十与六十仍可正确解析，非法值不能作为零分进入成绩表。整批拒绝版本应先收集验证结果，仅在错误列表为空时写入，不能一边验证一边留下部分永久变更。

## 官方来源与内容说明

- [错误和异常](https://docs.python.org/zh-cn/3.12/tutorial/errors.html)；发布方：Python Software Foundation；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
