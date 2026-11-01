"""Course-owned resources are content, never student activity."""
RUBRIC = [{"name": "逻辑正确性", "max_score": 60}, {"name": "语法与规范", "max_score": 20}, {"name": "边界与表达", "max_score": 20}]
COURSES = {
    1: {"title": "数据库原理与应用", "code": "DB-2026", "subtitle": "用 SQL 连接知识与实践", "description": "通过查询、索引和事务理解关系数据库，以执行计划和边界样例验证。",
        "topics": ["NULL 判断", "索引失效", "事务处理", "JOIN 与聚合"],
        "lessons": [
            ("联合索引与最左前缀原则", "联合索引 (name, age, city) 从最左列开始连续匹配。WHERE name = '张三' AND age = 20 可以使用索引前缀；跳过 name 直接查询 age 通常不能使用该前缀。范围条件可能影响后续列的利用，必须结合 EXPLAIN 验证。"),
            ("索引失效的常见情形", "对索引列使用函数、隐式类型转换、LIKE 以通配符开头或不满足最左前缀条件，可能影响索引利用。记录原查询与数据分布，用 EXPLAIN 比较优化前后的执行计划，避免仅凭 SQL 外观下结论。"),
            ("NULL 值的正确判断", "NULL 表示未知或缺失，与 NULL 进行 = 或 != 比较得到 UNKNOWN，WHERE 只保留 TRUE。查找邮箱缺失的学生应写 SELECT * FROM students WHERE email IS NULL; 非空使用 IS NOT NULL。空字符串与 NULL 不同。"),
            ("事务与 ACID", "事务将一组操作作为逻辑单元。ACID 为原子性、一致性、隔离性、持久性。BEGIN 开始，COMMIT 提交，ROLLBACK 回滚。转账须让扣款与入账一起成功或失败，并检查余额、更新行数和并发条件。"),
            ("JOIN 与聚合", "INNER JOIN 返回匹配记录，LEFT JOIN 保留左表记录。GROUP BY 形成分组，HAVING 过滤聚合结果。COUNT(*) 统计行数，COUNT(column) 忽略该列的 NULL。连接前确认主外键关系，避免重复行导致汇总错误。")],
        "assignments": [
            ("练习 01 · 找出邮箱为空的学生", "NULL 判断", "查询 students 表中 email 为 NULL 的全部学生，返回所有列；解释 NULL 与空字符串的区别，给出验证样例。", "null_check", "SELECT * FROM students\nWHERE email = NULL;"),
            ("练习 02 · 联合索引的使用", "索引失效", "students 有联合索引 (name, age)。按姓名和年龄查询学生，并解释最左前缀原则及如何用 EXPLAIN 验证。", "index_prefix", "SELECT * FROM students\nWHERE age = 20;"),
            ("练习 03 · 用事务完成转账", "事务处理", "将账户 A 的 100 元转入账户 B，编写事务，说明余额不足、更新失败和并发时的处理。", "transaction", "BEGIN;\n-- 编写检查与更新语句\nCOMMIT;")]},
    2: {"title": "Python 程序设计", "code": "PY-2026", "subtitle": "用函数和数据结构解决问题", "description": "学习 Python 容器、函数、异常与文件处理，重视可读性和边界测试。",
        "topics": ["列表与字典", "函数与边界", "异常与文件"],
        "lessons": [
            ("列表、字典与可变对象", "列表按顺序保存元素，字典把唯一键映射到值。for item in items 遍历列表；counts[word] = counts.get(word, 0) + 1 可统计频次。赋值不会复制可变对象，浅复制仍共享嵌套元素。修改容器时注意别名和迭代安全。"),
            ("函数与边界测试", "def 定义函数，参数接收输入，return 返回结果。避免使用可变默认参数；可用 None 作为默认值，在函数内创建列表。为正常、空输入、重复值与非法输入写断言；将计算与输入输出分离，便于复用和测试。"),
            ("异常、文件与资源管理", "with open(path, encoding='utf-8') as f 会在离开块时关闭文件。except 仅捕获预期异常，例如 ValueError 或 FileNotFoundError，不用空 except 吞掉故障。逐行读取适合大文件；说明空行和无效数据如何处理。")],
        "assignments": [
            ("Python 练习 01 · 词频统计", "列表与字典", "实现 word_counts(words)，返回各单词次数的字典。不修改原列表；验证空列表、重复单词和大小写策略。", "manual", "def word_counts(words):\n    pass"),
            ("Python 练习 02 · 安全计算平均值", "函数与边界", "实现 average(values)；空列表抛出 ValueError，正常返回平均值。写出正数、负数与空输入断言，说明契约。", "manual", "def average(values):\n    pass"),
            ("Python 练习 03 · 读取成绩文件", "异常与文件", "实现 read_scores(path)，用 with 读取 UTF-8 文本中逐行整数。忽略空行，对无效行报告行号，说明文件不存在时的行为。", "manual", "def read_scores(path):\n    pass")]},
    3: {"title": "Java 程序设计", "code": "JAVA-2026", "subtitle": "用类型和对象组织程序", "description": "学习 Java 类型、封装、集合与异常，建立清晰可验证的程序结构。",
        "topics": ["类与封装", "集合与泛型", "异常与资源"],
        "lessons": [
            ("类型、类与封装", "Java 基本类型存储值，引用类型指向对象。类用字段保存状态、方法表达行为；private 字段与公开方法维护不变量。构造器初始化对象。用 equals 比较字符串内容，== 比较引用身份。实例方法操作对象，static 方法属于类。"),
            ("集合与泛型", "List<String> 按顺序保存字符串，Map<String, Integer> 表示词频。泛型在编译期约束类型。用 getOrDefault(word, 0) + 1 更新计数；遍历时避免直接结构性修改集合，可用迭代器的 remove。测试空集合、重复值与 null 策略。"),
            ("异常与资源管理", "异常表达调用失败。非法参数可抛出 IllegalArgumentException；捕获具体异常并保留原因。用 try-with-resources 管理实现 AutoCloseable 的文件资源，确保关闭。不要用空 catch 掩盖失败；在方法契约中说明边界与错误行为。")],
        "assignments": [
            ("Java 练习 01 · 封装银行账户", "类与封装", "实现 BankAccount：私有余额，构造器禁止负数，deposit 与 withdraw 验证金额，余额不足抛出异常。说明边界测试与封装作用。", "manual", "public class BankAccount {\n    // 实现字段、构造器与方法\n}"),
            ("Java 练习 02 · 集合词频统计", "集合与泛型", "实现 countWords(List<String>) 返回 Map<String, Integer>。不修改输入，明确 null 与空集合策略，给出重复单词测试。", "manual", "public Map<String, Integer> countWords(List<String> words) {\n    return new HashMap<>();\n}"),
            ("Java 练习 03 · 安全读取文件", "异常与资源", "用 try-with-resources 读取 UTF-8 成绩文件，跳过空行，非法整数报告行号；保留 I/O 异常原因，说明资源释放。", "manual", "public List<Integer> readScores(Path path) throws IOException {\n    return new ArrayList<>();\n}")]},
}


def course_topics(course_id):
    return COURSES.get(course_id, {}).get("topics", [])
