# 异常分类与资源自动关闭

课程：Java｜讲义编号：java-08-exceptions｜整理日期：2026-10-31

## 实验情境与目标

读取成绩文本时既可能遇到格式错误，也可能遇到文件读取失败。二者需要不同处理，资源也必须在失败路径被关闭。本实验先用内存字符串模拟逐行读取，让异常行为可复现，再讨论将同样结构迁移到真实文件。

## 概念与设计步骤

try-with-resources 让实现 AutoCloseable 的资源在离开作用域时关闭，包括发生异常的路径。示例每一行单独解析，坏成绩进入错误列表，其他记录继续处理；这种部分成功是本练习明确选择的策略。外层 IOException 表达读取层失败，内层 NumberFormatException 表达内容格式失败，不应把它们统统转换成零分。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
import java.io.*;
import java.util.*;
public class Main {
    public static void main(String[] args) throws IOException {
        List<Integer> scores = new ArrayList<>();
        List<String> errors = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(
                new StringReader("90\nwrong\n60\n"))) {
            String line;
            int number = 0;
            while ((line = reader.readLine()) != null) {
                number++;
                try {
                    scores.add(Integer.parseInt(line));
                } catch (NumberFormatException error) {
                    errors.add("第" + number + "行不是整数");
                }
            }
        }
        System.out.println(scores);
        System.out.println(errors);
    }
}
```

## 逐步验证与结果解释

有效结果为九十和六十，错误列表指出第二行。BufferedReader 在离开资源块后关闭，本例无需手写 finally 再调用 close。main 声明 throws IOException 是为了缩小教学代码；真实用户入口应捕获读取异常并给出可操作提示，同时保留调试所需的原因。

## 常见误区

catch Exception 后什么也不做会让导入结果看似成功。catch 的顺序应把更具体异常放在前面，否则可能出现不可达处理。不要在 finally 中随意 return，它可能覆盖原异常。自动关闭的异常与原异常可能同时出现，排查时要关注 suppressed exceptions，而不是只看最外层一句话。

## 练习

加入一行一百零五分并添加范围校验，保证它不进入有效结果。将策略改成只要存在坏行就整批拒绝。最后把内存字符串替换为项目目录的文件读取，并明确字符编码。

## 验收要点与思路

验收要区分读取失败、格式错误与范围错误，资源关闭发生在成功和失败两种路径。整批拒绝版本不能先永久写入前面的有效记录，再在最后声称整批失败；应先完成验证后统一提交。

## 官方来源与内容说明

- [The try-with-resources Statement](https://docs.oracle.com/javase/tutorial/essential/exceptions/tryResourceClose.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
