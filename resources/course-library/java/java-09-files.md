# NIO文件、字符编码与写入策略

课程：Java｜讲义编号：java-09-files｜整理日期：2026-10-31

## 实验情境与目标

导出中文课程名单时，必须明确路径、编码和覆盖策略。系统默认编码与当前工作目录经常随运行方式变化，不能只在编辑器中打开正常就判断交付可靠。本实验在独立练习目录写出 UTF-8 文件，再读回并核对完整内容。

## 概念与设计步骤

Path 表达路径，Files 提供常用文件操作，StandardCharsets.UTF_8 把编码契约写在代码中。示例明确使用 CREATE 与 TRUNCATE_EXISTING，因此会覆盖同名练习文件；这个行为需要与业务要求一致。读回相等验证的是本次字节与文本往返，不自动证明生产导出文件权限、容量与并发写入都已正确。

## 可运行示例

运行环境：JDK 8 或更高版本；将代码保存为 Main.java，使用 javac -encoding UTF-8 Main.java 与 java Main 在独立练习目录运行。

```java
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public class Main {
    public static void main(String[] args) throws Exception {
        Path folder = Paths.get("course-output");
        Files.createDirectories(folder);
        Path file = folder.resolve("names.txt");
        List<String> names = Arrays.asList("数据库", "Python", "Java");
        Files.write(file, names, StandardCharsets.UTF_8,
            StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
        List<String> restored = Files.readAllLines(file, StandardCharsets.UTF_8);
        if (!restored.equals(names)) throw new IllegalStateException("往返失败");
        System.out.println(file.toAbsolutePath());
        System.out.println(restored);
    }
}
```

## 逐步验证与结果解释

保存为 Main.java 后编译运行，当前练习目录下出现 course-output/names.txt，输出绝对路径与三门课程名称。再次运行时文件仍为三行，因为覆盖选项与代码目标一致。若改为 APPEND，连续运行会累积重复内容，因此调用方必须先决定导出是快照还是追加日志。

## 常见误区

readAllLines 会一次读取整个文件，大文件需要流式处理，并及时关闭流。用户提供的相对路径必须验证，避免通过父目录访问其他文件。先检查文件存在再写入不能消除竞争；需要根据要求使用 CREATE_NEW 或其他原子操作。临时文件加替换的方案也要考虑文件系统是否支持原子移动。

## 练习

把文件内容增加一条含中文标点和空格的课程名称，验证完整往返。再改成 CREATE_NEW 并连续执行，观察第二次为什么失败。设计导出目标已经存在时的用户提示与保留旧文件方案。

## 验收要点与思路

验收时记录绝对路径、实际行数、第二次运行行为与编码。错误处理不能把写入失败报告成成功下载。若练习中修改覆盖策略，应在报告中明确旧文件是否保留以及用户如何找到新文件。

## 官方来源与内容说明

- [Reading, Writing, and Creating Files](https://docs.oracle.com/javase/tutorial/essential/io/file.html)；发布方：Oracle；访问核对日期：2026-10-31。

Oracle Java Tutorials 标明以 JDK 8 为基础，本讲义只采用该版本已有的核心语法与标准库，未将页面当作最新 Java 特性的说明。教学情境、中文讲解、练习与代码为本项目原创整理，不是官方手册的逐段翻译或全文复制。文档保留可打开的原始页面，供继续学习和核对。
