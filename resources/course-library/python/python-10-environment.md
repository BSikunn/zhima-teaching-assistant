# 虚拟环境、依赖与浮点精度

课程：Python｜讲义编号：python-10-environment｜整理日期：2026-10-31

## 实验情境与目标

把作业交给同学运行时，源代码相同但结果不同，问题可能来自解释器、依赖版本或数字处理方式。本讲义把可复现环境与金额计算放在一个交付小实验中：先确保使用指定解释器，再让程序展示二进制浮点与十进制金额的差别。

## 概念与设计步骤

虚拟环境隔离第三方包，不会自动给出完整部署说明。项目仍需记录 Python 版本、依赖文件和运行入口。通过 python -m pip 调用包管理器，能让 pip 与当前解释器对应。金额实验只用标准库 Decimal，避免为了一个简单任务额外安装依赖；从字符串构造金额保留原始十进制含义。

## 可运行示例

运行环境：Python 3.12；仅使用标准库；在独立练习目录运行，避免覆盖已有文件。

```powershell
# 在独立练习目录的 PowerShell 中执行，所有文件留在该目录。
python -m venv .venv-lab
& ./.venv-lab/Scripts/python.exe --version
& ./.venv-lab/Scripts/python.exe -m pip --version
# 保存下面 Python 代码为 money.py，然后执行：
# & ./.venv-lab/Scripts/python.exe ./money.py

```

## 逐步验证与结果解释

money.py 的内容如下：from decimal import Decimal；再写 total = Decimal('0.10') + Decimal('0.20')，最后 print(total, 0.1 + 0.2)，每条语句各占一行。输出的十进制结果为零点三零，而浮点结果可能显示尾部误差。这个现象属于数字表示，重装 Python 或换虚拟环境并不能消除它。

## 金额实验完整源码

```python
from decimal import Decimal
import math
total = Decimal("0.10") + Decimal("0.20")
print(total, 0.1 + 0.2)
print(f"{total:.2f}")
assert total == Decimal("0.30")
assert math.isclose(0.1 + 0.2, 0.3)
```

## 常见误区

不要复制整份虚拟环境到另一台机器后假定可直接使用，应根据依赖说明重建。pip freeze 是当前环境的包快照，不自动说明哪些是直接业务依赖。Decimal(0.1) 会把已有浮点近似值带进十进制对象，应从原始文字构造。浮点误差也不能只靠展示四舍五入来解释业务比较规则。

## 练习

补全 money.py 为可直接执行的文件，加入两位小数的金额展示，再用 math.isclose 比较浮点和零点三。记录解释器路径与 pip 路径，说明它们是否位于同一虚拟环境。将依赖文件为空的理由写进交付说明。

## 验收要点与思路

验收无需安装任何第三方包。解释器应来自 .venv-lab，金额计算由 Decimal 完成，浮点近似比较用合理容差。依赖文件为空可以是因为只使用标准库，但仍应写出支持的 Python 版本与运行命令。

## 官方来源与内容说明

- [虚拟环境和包](https://docs.python.org/zh-cn/3.12/tutorial/venv.html)；发布方：Python Software Foundation；访问核对日期：2026-10-31。
- [浮点算术：争议和限制](https://docs.python.org/zh-cn/3.12/tutorial/floatingpoint.html)；发布方：Python Software Foundation；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
