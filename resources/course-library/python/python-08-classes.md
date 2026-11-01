# 类、实例状态与不变量

课程：Python｜讲义编号：python-08-classes｜整理日期：2026-10-31

## 实验情境与目标

选课管理中，一个课程对象同时保存容量与已选学生，并提供报名行为，比在多个函数间传递散乱变量更容易维护。本实验的重点是让对象在每次成功操作之后都保持已选人数不超过容量的规则，而不是为了使用 class 关键字把所有代码包起来。

## 概念与设计步骤

构造器建立每个实例独立的学生集合，报名方法集中检查重复与满额规则，再修改状态。把集合放在实例属性中，是为了确保不同课程之间不共享学生。Python 的下划线命名主要是约定，不能替代授权边界；对象设计仍应围绕调用方需要的稳定方法与可检查结果。

## 可运行示例

运行环境：Python 3.12；仅使用标准库；在独立练习目录运行，避免覆盖已有文件。

```python
class Course:
    def __init__(self, title, capacity):
        if capacity < 1:
            raise ValueError("容量必须为正数")
        self.title = title
        self.capacity = capacity
        self.students = set()

    def enroll(self, student_id):
        if student_id in self.students:
            return False
        if len(self.students) >= self.capacity:
            raise ValueError("名额已满")
        self.students.add(student_id)
        return True

first = Course("数据库", 1)
second = Course("Python", 2)
assert first.enroll("001") is True
assert first.enroll("001") is False
assert not second.students
print(first.title, len(first.students))
```

## 逐步验证与结果解释

第一门课程报名一次成功，重复报名返回 False，第二门课程仍然没有学生。返回 False 是本例对重复操作的约定，满额则抛出异常，调用方应据此给出不同提示。程序只在单进程对象内维护规则；如果课程保存在数据库中并被多个请求并发访问，还需要数据库约束与事务，不能把这个教学对象当成完整并发方案。

## 常见误区

把 students=set() 写在类体中会让实例共享可变状态。直接允许外部修改集合会绕过报名方法，正式设计可提供只读快照。继承不是复用的唯一方式，课程与报名服务之间也可以通过组合协作。打印对象地址不能证明两个对象内容是否相同。

## 练习

增加退课方法：不存在的学生返回 False，已报名者退课后释放名额。测试容量一的课程先满额、退课、再报名的路径。说明退课后是否要保留历史记录，以及历史事件为什么不应简单塞进当前学生集合。

## 验收要点与思路

验收时不同实例互不干扰，重复报名不占新名额，退课后能再次报名。历史可以保存在独立事件列表或持久化记录中，与当前占用状态分开；这反映了当前状态与历史事实的不同职责。

## 官方来源与内容说明

- [类](https://docs.python.org/zh-cn/3.12/tutorial/classes.html)；发布方：Python Software Foundation；访问核对日期：2026-10-31。

上述来源用于核对主题、语法与使用边界；本文按课堂问题重新编排。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
