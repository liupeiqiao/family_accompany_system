## 工作约定

- 安装依赖时优先使用 `pnmp`；本项目是 Python 项目，若只安装 Python 依赖，使用 `python -m pip install -r requirements.txt`。
- 尽量使用中文沟通和编写项目说明。
- 不要把真实 API Key 写入文档、日志或新代码；优先通过环境变量配置。

## 项目概览

本项目是“亲情陪伴系统”，一个面向老年人的 AI 情感陪伴原型。系统通过家庭记忆、老人画像、家人档案、AI 扮演角色画像、意图情绪识别和安全校验，生成更像家人说话的共情回复。

当前形态是 Streamlit 单页应用，入口为 `app.py`，本地使用 SQLite 持久化数据，LLM 调用采用 DeepSeek 的 OpenAI 兼容接口。

## 技术栈

- Python + Streamlit：页面、侧边栏表单、聊天交互和流程编排。
- SQLite：默认数据库文件为 `companion.db`，由 `engine/db.py` 初始化和迁移。
- OpenAI Python SDK：连接 DeepSeek 兼容 API。
- pytest：单元测试与源码行为约束测试。

## 常用命令

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8501
python -m pytest tests/ -v
```

运行应用通常需要配置：

```bash
set DEEPSEEK_API_KEY=your-key
```

PowerShell 可使用：

```powershell
$env:DEEPSEEK_API_KEY="your-key"
python -m streamlit run app.py --server.port 8501
```

## 目录与模块

- `app.py`：Streamlit 主入口，负责页面样式、侧边栏管理、智能解析导入、聊天流程和调试信息。
- `engine/memory.py`：家庭记忆 `MemoryUnit` 与内存存储。
- `engine/persona.py`：AI 扮演角色 `PersonaProfile`，支持多角色、切换、合并。
- `engine/elder.py`：老人画像 `ElderProfile`，记录性格、偏好、健康备注、人生经历等。
- `engine/family.py`：家人档案 `FamilyProfile`，记录家人与关系网络。
- `engine/db.py`：SQLite 持久化，维护 `persona`、`memories`、`family_profiles`、`elder_profile` 四类数据。
- `engine/scorer.py`：五因子记忆评分，公式为 `alpha*R + beta*E + gamma*C + delta*S - epsilon*M`。
- `engine/strategy.py`：根据意图和情绪选择陪伴策略。
- `engine/adaptation.py`：老年适配与安全检查，包括句子长度、称呼、禁忌词、网络用语、医疗建议和虚假承诺检查。
- `llm/client.py`：DeepSeek API 客户端，默认模型为 `deepseek-chat`。
- `llm/prompts.py`：意图情绪识别、回复生成和策略描述 Prompt。
- `llm/parser.py`：自然语言解析为结构化画像、记忆和家人档案，并做人物去重判断。
- `docs/`：架构、数据模型、算法、安全与 UX 的 HTML 说明文档。
- `tests/`：当前包含 29 个 pytest 测试，覆盖智能解析预览、导入同步、老人视角解析、删除、去重和 API 错误处理。

## 核心流程

每轮聊天大致流程：

1. 老人输入文本。
2. LLM 识别意图、情绪、对话对象和提及人物。
3. 系统按当前角色、提及人物和家庭记忆检索候选上下文。
4. `engine/scorer.py` 对记忆进行相关性、共情度、亲密度、安全性和敏感惩罚评分。
5. `engine/strategy.py` 选择陪伴策略。
6. LLM 根据角色画像、老人画像、家人档案、记忆和策略生成回复。
7. `engine/adaptation.py` 做老年适配和安全校验；失败时构造重试提示。
8. Streamlit 展示最终回复和调试信息。

## 数据模型要点

- 老人画像：姓名、性别、性格、偏好、习惯、健康备注、说话特点、人生经历、重要记忆。
- AI 扮演角色：角色名、与老人关系、对老人称呼、性格、说话风格、陪伴方式。
- 家人档案：姓名、与老人关系、性格、偏好、习惯、家庭关系、备注。
- 家庭记忆：正文、主语、类型、相关家人、情感标签、话题标签、亲密权重。

## 开发注意事项

- `app.py` 较大，修改前先用 `rg` 定位相关区块，避免无关重构。
- 侧边栏表单和 `st.session_state` 强耦合，改导入、编辑、删除逻辑时要同步检查测试。
- 智能解析预览区要求可编辑；一键导入应读取编辑后的 `st.session_state.parsed`。
- LLM 调用失败应优雅降级，不应让页面崩溃。
- 安全相关逻辑涉及老年适配、医疗边界、敏感话题和虚假承诺，改动后要补充或运行相关测试。
- 数据库迁移逻辑在 `engine/db.py` 的 `init_db()` 中，新增字段时要兼容旧库。


## 对话收尾与 Git 提交规范
- **自动生成提交信息**：每次对话或完成一个阶段性任务后，请主动根据本次的代码变更，为我生成一条清晰、符合 Conventional Commits 规范的 Commit Message。
- **格式要求**：
  - 格式：`<type>(<scope>): <subject>`
  - type 常用类型：`feat` (新功能), `fix` (修复bug), `refactor` (重构), `docs` (文档), `chore` (杂项/配置) 等。
  - 示例：`feat(auth): 实现用户 JWT 登录功能`
- **提供复制命令**：生成信息后，请直接给我提供一条完整的、我可以直接复制粘贴到终端执行的 Git 提交命令。