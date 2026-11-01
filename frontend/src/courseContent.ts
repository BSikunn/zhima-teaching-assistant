export const courseContent: Record<number, { language: string; label: string; topics: string; starter: string; prompts: string[] }> = {
  1: { language: 'sql', label: 'SQL', topics: '查询与关联、索引与事务', starter: 'SELECT * FROM students;', prompts: ['什么是最左前缀原则？', '为什么不能用 = NULL 判断空值？', '事务的 ACID 分别指什么？', 'LEFT JOIN 和 INNER JOIN 有什么区别？'] },
  2: { language: 'python', label: 'Python', topics: '函数、集合与异常处理', starter: 'def solve():\n    pass\n\nsolve()', prompts: ['列表和字典分别适合什么场景？', '如何理解函数参数与返回值？', '怎样处理文件读取中的异常？', '为什么循环中修改列表容易出错？'] },
  3: { language: 'java', label: 'Java', topics: '面向对象、集合与异常处理', starter: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, Java");\n    }\n}', prompts: ['接口与抽象类有什么区别？', '如何理解封装、继承与多态？', 'ArrayList 和 HashMap 适合什么场景？', '受检异常应该如何处理？'] },
}
