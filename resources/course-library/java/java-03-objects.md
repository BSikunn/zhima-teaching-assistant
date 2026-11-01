# 类、封装与课程容量规则

课程：Java｜讲义编号：java-03-objects｜整理日期：2026-10-31

## 实验情境与目标

课程对象把名称、容量与当前报名人数放在一起，可以在一个地方维护不超额的规则。相比公开几个字段让任意代码修改，封装通过可理解的方法暴露行为。本实验只演示内存对象的规则，不把它当作数据库并发控制的替代品。

## 概念与设计步骤

构造器检查初始容量，private 字段阻止外部直接改写报名人数，enroll 方法在容量未满时增加人数并返回成功。调用方只需要知道报名成功与否，不需要了解字段如何存储。类应表达稳定业务规则，不能为了封装而机械生成允许任意写入的 setter，否则仍可能把人数直接设成负数。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
public class Main {
    static class Course {
        private final String title;
        private final int capacity;
        private int enrolled;
        Course(String title, int capacity) {
            if (capacity < 1) throw new IllegalArgumentException("容量无效");
            this.title = title;
            this.capacity = capacity;
        }
        boolean enroll() {
            if (enrolled >= capacity) return false;
            enrolled++;
            return true;
        }
        int remaining() { return capacity - enrolled; }
    }
    public static void main(String[] args) {
        Course course = new Course("Java", 1);
        System.out.println(course.enroll());
        System.out.println(course.enroll());
        System.out.println(course.remaining());
    }
}
```

## 逐步验证与结果解释

编译运行后依次输出 true、false、零。初始 enrolled 默认为零；第一次报名修改同一个对象的状态，第二次观察到名额已经用完。final 表示构造后字段引用或值不能被重新赋值，不意味着被引用的任何复杂对象都自动不可变。本例对整数容量使用 final，意图是课程创建后不通过此接口改变容量。

## 常见误区

把 enrolled 声明为 static 会让所有课程共享一个人数，破坏每门课程独立状态。公开所有字段会让外部绕开规则。多个线程同时调用时，这个简单方法仍有竞争，真实系统需要同步或数据库事务。不能凭 private 就声称整个应用已经完成权限控制。

## 练习

创建两门不同容量的课程，确认报名一门不影响另一门。再增加取消报名方法，约定人数为零时如何处理。讨论当前模型没有学生身份时，为什么无法判断同一学生是否重复报名。

## 验收要点与思路

验收中应同时有独立实例、满额和取消后重新报名路径。若加入学生编号集合，人数可以由集合大小得到，避免维护两个容易不一致的数据源。解释类的职责与模型仍未覆盖的问题，也是实验报告的一部分。

## 官方来源与内容说明

- [Classes](https://docs.oracle.com/javase/tutorial/java/javaOO/classes.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
