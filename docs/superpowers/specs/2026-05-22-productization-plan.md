# 亲情陪伴系统产品化实施计划

## Summary

将当前 Streamlit + SQLite 原型渐进式产品化：保留现有 Python 对话逻辑作为服务层参考与过渡，新增正式 `Next.js React Web` 用户端、`Supabase` 云端数据层、家庭空间协作模型，以及基于第三方 API 的声音克隆与语音回复能力。

第一版目标：

- 家人登录家庭空间。
- 家人维护老人画像、家人档案、家庭记忆。
- 家人上传或录制声音样本生成克隆声音。
- 老人端可文字聊天，并播放克隆语音回复。

## Key Changes

- 新建正式 Web 应用：使用 `Next.js + TypeScript`。
- 家人端包含家庭空间、成员邀请、档案管理、记忆管理、声音克隆管理。
- 老人端包含简化聊天界面、文字输入和语音播放。
- 云端同步采用 `Supabase Auth + Postgres + Storage + RLS`。
- 用家庭空间隔离数据，多位家人加入同一空间后共同维护档案和记忆。
- 所有家庭数据表开启行级权限。
- 家庭空间成员角色保留三类：`owner`、`editor`、`viewer`。
- 首版 UI 主要展示创建者和可编辑成员；`viewer` 在数据库和权限中保留，但首版界面不突出。
- 老人不是成员权限角色，而是 `elders` 业务对象。
- 老人聊天入口单独设计为老人端会话入口。
- 保留当前 Python 引擎能力，将 `app.py` 中的核心流程拆为后端服务接口。
- Streamlit 暂时保留为内部调试工具，不作为正式用户端。
- 声音克隆采用 `VoiceProvider` 抽象，首个实现接第三方声音克隆服务。
- 上传音频样本创建 `voice_id`，聊天回复生成文本后调用 TTS 输出音频。
- 授权第一版按“简单提示”实现：上传或录制前展示确认提示。
- 同时保存最小审计字段：创建人、家庭空间、样本来源、创建时间、provider、provider_voice_id。

## Interfaces And Data

Supabase 主要表：

- `families`
- `family_memberships`
- `elders`
- `personas`
- `family_profiles`
- `memories`
- `voice_profiles`
- `voice_samples`
- `chat_sessions`
- `chat_messages`

成员权限：

- `owner`：可邀请成员、删除成员、管理声音。
- `editor`：可新增和编辑档案、记忆、声音样本。
- `viewer`：只读，首版作为预留权限。

Python 服务接口：

- `POST /api/parse`：自然语言解析为档案和记忆草稿。
- `POST /api/chat`：输入家庭空间、老人、当前角色、用户文本，返回回复文本、调试信息和可选音频 URL。
- `POST /api/voices/clone`：提交样本文件引用，返回克隆状态和 `voice_profile_id`。
- `POST /api/tts`：文本 + `voice_profile_id` 生成语音文件。

文件存储：

- 声音样本和生成语音放 Supabase Storage。
- 数据库只保存路径、元数据和权限归属。

## Test Plan

- 后端单元测试：迁移现有评分、策略、解析兜底、安全校验测试。
- 新增家庭空间权限、数据过滤、声音 provider mock 测试。
- 前端测试：登录、加入家庭空间、档案 CRUD、记忆 CRUD、声音上传或录制、聊天播放音频。
- 集成测试：两个家人账号加入同一家庭空间后，一个人新增记忆，另一个人刷新后可见。
- 权限测试：非成员无法读取家庭空间数据。
- 失败场景：LLM 失败返回温和兜底；声音克隆失败显示可重试状态；TTS 失败仍显示文字回复；无授权提示确认时禁止上传样本。
- 安全检查：RLS 覆盖所有家庭数据表和存储路径；服务端不信任前端传入的 `family_id` 权限。

## Assumptions

- 第一版不做完整语音输入，只做文字聊天 + 克隆语音输出。
- 第一版不做复杂冲突合并；多人编辑以最后保存为准，保留 `updated_at` 和 `updated_by`。
- 第一版声音服务通过 `VoiceProvider` 保持可替换。
- 当前 Streamlit 原型不继续扩展为正式应用，只作为业务规则参考和内部调试入口。
