# 接口、策略与依赖替换

课程：Java｜讲义编号：java-05-interfaces｜整理日期：2026-10-31

## 实验情境与目标

课程成绩可以采用百分制，也可以采用通过与未通过标签。让报表直接依赖一种具体格式，会把展示规则写死。本实验用接口表达格式化行为，报表只调用接口，具体策略由外部传入，从而让规则变更集中在单一实现。

## 概念与设计步骤

接口声明调用方需要的能力，而不是暴露实现细节。示例用传统类实现接口，便于清楚看到 implements 与方法签名；后续可以再学习 lambda。参数与返回值的含义仍需约定，例如接口接收的成绩是否已经验证。为了缩小演示范围，这里在报表入口检查零到一百的边界，格式化器只负责文字表现。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
public class Main {
    interface GradeFormat { String format(int score); }
    static class NumberFormat implements GradeFormat {
        public String format(int score) { return score + "分"; }
    }
    static class PassFormat implements GradeFormat {
        public String format(int score) {
            return score >= 60 ? "通过" : "未通过";
        }
    }
    static String report(int score, GradeFormat format) {
        if (score < 0 || score > 100) throw new IllegalArgumentException();
        return "成绩：" + format.format(score);
    }
    public static void main(String[] args) {
        System.out.println(report(75, new NumberFormat()));
        System.out.println(report(75, new PassFormat()));
    }
}
```

## 逐步验证与结果解释

同一个七十五分分别输出数字成绩与通过标签，report 的代码没有改变。实现接口方法时使用 public，不能降低接口要求的可见性。调用方持有的是 GradeFormat 契约，因此可以在测试中提供简单的确定性实现，而不需要启动界面或连接外部服务。

## 常见误区

接口不能自动保证实现没有副作用，需要通过约定与测试约束。为了每个类都建一个接口会增加无效间接层，应围绕真实替换点设计。不要把接口参数声明成 Object 后在内部强转，那会失去编译期类型信息。默认方法能提供实现，但不能随意改变既有调用方对行为的预期。

## 练习

增加优秀、良好、通过、未通过四档格式实现。写一个只在教师报告中使用的带前缀格式，并验证学生报告仍可使用原实现。讨论格式化与授权为什么是不同职责。

## 验收要点与思路

验收需要两个实现产生不同展示，而核心成绩与合法范围保持一致。接口的价值体现在替换策略时调用路径稳定；如果每增加一种格式都要修改 report 的类型判断，说明这个替换点还没有真正封装好。

## 官方来源与内容说明

- [Interfaces](https://docs.oracle.com/javase/tutorial/java/IandI/createinterface.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
