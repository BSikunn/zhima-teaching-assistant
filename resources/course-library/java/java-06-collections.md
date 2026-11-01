# 集合选择、去重与计数

课程：Java｜讲义编号：java-06-collections｜整理日期：2026-10-31

## 实验情境与目标

学习访问事件需要保留原顺序，也要统计每门课程访问次数。List 表达有序且允许重复的记录，Set 表达唯一成员，Map 表达键到值的对应关系。本实验把原始事件与汇总结果分开保存，避免为了去重而丢失访问频率。

## 概念与设计步骤

示例用 ArrayList 保存事件，用 LinkedHashMap 统计次数并保留首次见到的课程顺序。实际系统应以课程编号作为键，名称只用于展示；同名课程不能被错误合并。集合的选择取决于是否需要顺序、重复、按键定位与更新，而不只是哪一个类名最熟悉。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
import java.util.*;
public class Main {
    public static void main(String[] args) {
        List<String> visits = new ArrayList<>(
            Arrays.asList("数据库", "Python", "数据库", "Java"));
        Map<String,Integer> counts = new LinkedHashMap<>();
        for (String course : visits) {
            counts.put(course, counts.getOrDefault(course, 0) + 1);
        }
        for (Map.Entry<String,Integer> entry : counts.entrySet()) {
            System.out.println(entry.getKey() + ":" + entry.getValue());
        }
        List<String> copy = new ArrayList<>(visits);
        copy.remove("Java");
        System.out.println(visits.size() + "/" + copy.size());
    }
}
```

## 逐步验证与结果解释

汇总依次显示数据库二次、Python 一次、Java 一次，原列表仍为四条，副本为三条。new ArrayList<>(visits) 复制外层列表结构；如果里面装的是可变课程对象，两个列表中的对应元素仍可能指向同一个对象。这个区别在修改课程名称时尤其需要通过实验验证。

## 常见误区

Arrays.asList 返回的列表长度固定，直接调用增加或删除会失败，所以示例再包一层 ArrayList。HashMap 不承诺首次插入展示顺序。增强 for 中直接结构性删除原集合可能触发并发修改异常，应使用迭代器、removeIf 或构造新集合。不能把集合类名中的 concurrent 当作所有复合操作都自动原子的保证。

## 练习

把事件改成课程编号列表，再维护编号到名称的映射，加入同名不同编号的两门课程。接着输出访问次数从高到低的结果，并为同次数规定编号升序。

## 验收要点与思路

验收包含重复事件、空列表与同名课程。保持原始事件数量不变，并说明不同集合的顺序契约。只打印一个集合看似有序，不能证明它在所有运行中都提供稳定顺序保证。

## 官方来源与内容说明

- [The List Interface](https://docs.oracle.com/javase/tutorial/collections/interfaces/list.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
