# Stream筛选、映射与归约

课程：Java｜讲义编号：java-10-streams｜整理日期：2026-10-31

## 实验情境与目标

从成绩列表计算通过者平均分可以用普通循环，也可以用流式管道。Stream 的价值是把筛选、转换和汇总的意图串起来，但它不意味着所有操作都更快，更不意味着写上 parallel 就自动得到正确并行程序。

## 概念与设计步骤

示例先过滤未通过成绩，再映射成基本整数流，最后求平均。空结果用 OptionalDouble 表示没有平均值，不能未经检查就取值。管道执行需要终止操作，一条流也不能反复消费。先保留原列表，便于核对流操作是否按预期只产生汇总，而没有在外部累加器里留下难以理解的副作用。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
import java.util.*;
import java.util.stream.*;
public class Main {
    public static void main(String[] args) {
        List<Integer> scores = Arrays.asList(45, 60, 80, 100);
        OptionalDouble mean = scores.stream()
            .filter(score -> score >= 60)
            .mapToInt(Integer::intValue)
            .average();
        String shown = mean.isPresent() ?
            String.valueOf(mean.getAsDouble()) : "暂无成绩";
        int total = scores.stream().reduce(0, Integer::sum);
        List<Integer> passed = scores.stream()
            .filter(score -> score >= 60)
            .collect(Collectors.toList());
        System.out.println(shown);
        System.out.println(total + ":" + passed);
    }
}
```

## 逐步验证与结果解释

通过者为六十、八十、一百，平均为八十；全体总分为二百八十五。两种统计使用不同筛选口径，因此不能把总分直接除以通过人数。reduce 的零是求和的单位元，空流求和结果为零；平均分则没有可用值，所以需要 OptionalDouble 的存在性检查。

## 常见误区

不要在 forEach 中给共享整数变量累加后再开启并行，那可能导致竞争或让代码难以编译。修改流的数据源会破坏非干扰假设。浮点加法还可能受组合顺序影响。对于简单循环，优先可读与可验证，不需要为了使用新语法把每一行都改成流。

## 练习

把数据改成全部未通过，预测平均值提示与总分。再按成绩是否通过分组，输出两组名单。设计只取最高两项成绩的管道，并解释排序与 limit 调换顺序为什么可能改变结果。

## 验收要点与思路

验收包括空列表、全部未通过和同分样本。报告需要写出每条统计的筛选口径，确认原列表未被修改。若采用并行归约，必须说明操作满足的结合性与状态约束，不能仅凭一次运行得到正确数字作为证据。

## 官方来源与内容说明

- [Reduction](https://docs.oracle.com/javase/tutorial/collections/streams/reduction.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
