# 泛型、类型安全与通配符

课程：Java｜讲义编号：java-07-generics｜整理日期：2026-10-31

## 实验情境与目标

一份课程容器不应在运行很久之后才发现混进了错误类型。泛型让许多类型约束在编译阶段表达清楚，减少强制转换与运行时错误。本实验用同一个 Box 类型分别保存课程名和人数，再通过数字通配符示例讨论读取与写入权限。

## 概念与设计步骤

Box<T> 把内容类型交给调用方选择，get 的返回类型随参数变化。泛型类型参数不是运行时为每种 T 复制一份独立类。对 List<? extends Number>，可以把元素当 Number 读取，但不能随意写入某个具体数字类型，因为实际列表可能是整数列表或浮点列表。示例只进行读取求和，避免假定其具体元素类型。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
import java.util.*;
public class Main {
    static class Box<T> {
        private final T value;
        Box(T value) { this.value = value; }
        T get() { return value; }
    }
    static double total(List<? extends Number> values) {
        double sum = 0;
        for (Number value : values) sum += value.doubleValue();
        return sum;
    }
    public static void main(String[] args) {
        Box<String> title = new Box<>("Java");
        Box<Integer> people = new Box<>(28);
        System.out.println(title.get() + ":" + people.get());
        System.out.println(total(Arrays.asList(10, 20, 30)));
    }
}
```

## 逐步验证与结果解释

输出课程名与二十八人，再输出六十点零。尝试把 people.get() 赋给 String 变量，编译器应拒绝，而不是等到运行时才发现错误。这里使用 Integer 作为泛型参数，基本类型 int 不能直接作为类型实参；自动装箱帮助完成部分转换，但不消除 null 的风险。

## 常见误区

不要为了消除报错而退回原始类型 List，这会失去类型检查。List<Integer> 不能直接赋给 List<Number>，否则后者加入小数会破坏前者的整数承诺。不能用 new T() 任意实例化类型参数，创建策略需要显式传入。擦除带来的运行时限制也应与编译期安全区分。

## 练习

编写把整数复制到 Number 目标列表的方法，思考读取源适合 extends、写入目标适合 super 的原因。再创建 Box<List<String>>，验证外层 final 不会禁止内部列表追加。

## 验收要点与思路

验收应展示一个正确编译案例和一个刻意编译失败的错误案例，失败源码独立保存，避免影响成功示例运行。说明通配符限制来自不知道实际元素类型，而不是把泛型规则简单背成几个符号。

## 官方来源与内容说明

- [Generic Types](https://docs.oracle.com/javase/tutorial/java/generics/types.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
