# 基本类型、字符串与数值转换

课程：Java｜讲义编号：java-01-types｜整理日期：2026-10-31

## 实验情境与目标

课程系统需要同时保存学号、成绩和学时。虽然学号看起来是数字，但它的意义是身份标识，前导零不能丢；成绩需要参与运算，适合数值类型。先写清每个字段的业务含义，再选类型，可以减少后期把错误格式一路传到界面的情况。

## 概念与设计步骤

本实验采用字符串保存学号，整数保存百分制成绩，double 展示平均值。整数相除会先进行整数除法，因此平均值计算要在除法发生之前转换类型。String 是对象类型，比较内容通常使用 equals；等号比较对象引用不能表达业务上的文字相同。演示不依赖新版语言语法，可在 JDK 8 或更高版本运行。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
public class Main {
    public static void main(String[] args) {
        String studentId = "0018";
        int sum = 87 + 88;
        double wrong = sum / 2;
        double average = sum / 2.0;
        String input = new String("0018");
        System.out.println(studentId.equals(input));
        System.out.println(wrong + " / " + average);
        int parsed = Integer.parseInt("90");
        System.out.println(studentId + ":" + parsed);
    }
}
```

## 逐步验证与结果解释

把代码保存为 Main.java，执行 javac -encoding UTF-8 Main.java，再执行 java Main。输出首先是 true，然后是八十七点零与八十七点五，最后保留学号的前导零。wrong 虽然声明为 double，仍不能挽回前面整数除法已经丢失的小数；赋值转换发生在表达式求值之后。

## 常见误区

不要把 char 当成任意长度字符串，单个 char 也不总能代表完整的用户可见字符。整数计算可能溢出，涉及较大累计值应考虑 long 并检查边界。Double 与 double 的自动拆箱遇到 null 会失败。字符串转整数的格式错误应在输入边界处理，不能默认变成零。

## 练习

把总分和人数改成变量，加入人数为零的检查；比较先转换为 double 再除与除完再转换的差别。为学号输入增加去除两端空白的规则，解释为什么转换成整数后无法可靠恢复原始长度。

## 验收要点与思路

验收数据应至少包括奇数总分、零人数和带前导零学号。输出平均分正确保留小数，非法人数有明确处理。每次演练在独立目录编译，避免旧 Main.class 导致误以为修改后的源码已经运行。

## 官方来源与内容说明

- [Primitive Data Types](https://docs.oracle.com/javase/tutorial/java/nutsandbolts/datatypes.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
