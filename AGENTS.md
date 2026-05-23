## 工作约定

- 尽量使用中文沟通和编写项目说明。
- 安装依赖时优先使用 `pnmp`；仅安装 Python 依赖时使用 `python -m pip install -r requirements.txt`。
- 不要把真实 API Key 写入文档、日志或新代码；优先通过环境变量配置。
- 禁止自主执行 `git commit`，所有提交都要经过用户明确允许。

## 项目认知

本项目是“亲情陪伴系统”，目标是做面向老年人的 AI 亲情陪伴产品。核心思路是让家人共同维护老人画像、家人档案、家庭记忆和 AI 角色信息，再由系统结合意图情绪识别、记忆评分、陪伴策略和安全校验，生成更像家人说话的共情回复。

当前仓库处于原型验证到产品化拆分阶段：`app.py` 是 Streamlit 原型；`engine/` 和 `llm/` 承载核心对话能力；`api/`、`web/`、`supabase/`、`productization/` 是面向 Next.js + FastAPI + Supabase 产品化方向的基础。

## 常用命令

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8501
python -m pytest tests/ -v
```

PowerShell 配置运行环境：

```powershell
后端：
$env:DEEPSEEK_API_KEY="your-key"
$env:DEEPSEEK_BASE_URL="https://api.deepseek.com"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
前端：cd web
$env:NEXT_PUBLIC_COMPANION_API_URL="http://localhost:8000"
npm run dev -- --hostname 127.0.0.1 --port 3000
```

## 开发注意事项

- `app.py` 较大，修改前先用 `rg` 定位相关区块，避免无关重构。
- 侧边栏表单、智能解析预览和 `st.session_state` 强耦合，改导入、编辑、删除逻辑时要同步检查测试。
- LLM 调用失败应优雅降级，不应让页面崩溃。
- 安全逻辑涉及适老表达、医疗边界、敏感话题和虚假承诺，改动后要运行相关测试。
- 数据库迁移逻辑在 `engine/db.py` 的 `init_db()` 中，新增字段时要兼容旧库。


## 对话收尾与 Git 提交规范
- **自动生成提交信息**：每次对话及完成一个阶段性任务后，请主动根据本次的代码变更，为我生成一条清晰、符合 Conventional Commits 规范的 Commit Message。
- **格式要求**：
  - 格式：`<type>(<scope>): <subject>`
  - type 常用类型：`feat` (新功能), `fix` (修复bug), `refactor` (重构), `docs` (文档), `chore` (杂项/配置) 等。
  - 示例：`feat(auth): 实现用户 JWT 登录功能`
- **提供复制命令**：生成信息后，请直接给我提供一条完整的、我可以直接复制粘贴到终端执行的 Git 提交命令。


