# 智码助教源码

面向数据库、Python、Java课程的教学智能体。本仓库对应Vue与FastAPI本机完整实现，包含容器部署配置。

产品能力、操作截图、账号和已验证边界见[产品说明](产品说明.md)。

## 首次使用

1. 准备已有Python 3.11或3.12、Node.js与npm。
2. 在项目根目录运行安装脚本，替换为本机实际Python路径：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Python "C:\Python312\python.exe"
Copy-Item -LiteralPath .env.example -Destination .env
```

3. 双击`启动智码助教.cmd`，打开http://127.0.0.1:8765。用完双击`停止智码助教.cmd`。
4. 默认demo模式不产生付费模型调用。需要真实AI时在私有.env配置AI_MODE=deepseek、DEEPSEEK_API_KEY及DEEPSEEK_MODEL，重启并核对页面模式。

初始体验账号：student、student2、student3、teacher、admin；初始密码Demo12345!。正式开放前请完成真实身份、课程授权及账号管理设计。

## 文件与数据

真实密钥、数据库、上传文件、备份、日志、依赖目录、模型权重和本机运行工具没有放入仓库。新安装由seed创建基础课程，30份扩充讲义在resources/course-library，需要使用导入脚本显式入库。不要直接上传原电脑整个项目目录。

本机完整服务和容器备份、迁移、恢复步骤见[运行维护](docs/运行维护.md)。当前源码包不包含Sites云端适配；原项目中该版本使用Worker、D1、R2与全文检索，运行架构与本机不同。

## 验证

```powershell
. .\scripts\env.ps1
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-check
npm.cmd run build --prefix frontend
```

2026年11月1日本机重新验证：139项后端测试通过；前端类型检查和生产构建通过。外部API、容量、生产容器与教学效果应在对应环境另行验收。未声明新的开源许可；依赖与课程资料的权利遵从各自来源。
