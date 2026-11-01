# 继承、多态与可替换行为

课程：Java｜讲义编号：java-04-inheritance｜整理日期：2026-10-31

## 实验情境与目标

系统需要发送不同类型的学习提醒，调用方只关心生成提醒文本，不应在每个位置都根据对象类型写分支。继承与重写可以让同一方法调用表现出不同实现，但前提是子类仍然满足父类对外承诺的含义。

## 概念与设计步骤

本实验的基类表达通知文本行为，子类只改变文本内容。使用基类变量保存子类对象，再调用实例方法，就能观察动态分派。构造器负责建立必要的标题状态，子类通过 super 调用父类构造器。选择继承应基于可替换关系；如果只是想复用几行字符串拼接，组合一个格式化器往往更合适。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
public class Main {
    static class Notice {
        protected final String title;
        Notice(String title) { this.title = title; }
        String text() { return "课程提醒：" + title; }
    }
    static class DeadlineNotice extends Notice {
        DeadlineNotice(String title) { super(title); }
        @Override String text() { return "截止提醒：" + title; }
    }
    public static void main(String[] args) {
        Notice[] notices = {new Notice("阅读讲义"),
                            new DeadlineNotice("提交作业")};
        for (Notice notice : notices) {
            System.out.println(notice.text());
        }
    }
}
```

## 逐步验证与结果解释

运行后两行分别显示普通课程提醒与截止提醒。数组声明类型是 Notice，第二个对象的实际类型是 DeadlineNotice，因此调用重写后的 text。增加 @Override 后，如果拼错方法名或参数，就能在编译期发现未真正重写的问题。字段访问与 static 方法不遵循相同的动态实例方法规则，不能机械套用。

## 常见误区

构造器不会被子类继承，子类仍需建立自己的初始化路径。重载由参数列表区分，与重写是两种机制。不能通过子类悄悄加强调用前置条件或随意改变异常含义，导致原先合法的父类用法突然失败。深层继承链也会让行为来源难以追踪。

## 练习

新增考试提醒子类，在不修改循环的情况下输出第三种文本。再用一个接收 Notice 参数的方法统一输出。最后给出一个不适合继承的例子，例如课程包含教师，而课程不是一种教师，说明应该怎样用字段组合表达。

## 验收要点与思路

验收要求通过父类引用调用到子类实现，调用方不用 instanceof 分支。报告应区分重载与重写，并说明如果把 text 改成 static，为什么就无法继续用本例证明动态多态。

## 官方来源与内容说明

- [Inheritance](https://docs.oracle.com/javase/tutorial/java/IandI/subclasses.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
