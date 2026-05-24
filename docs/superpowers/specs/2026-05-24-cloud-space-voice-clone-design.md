# 云空间与声音克隆产品级架构设计

## 背景

亲情陪伴系统当前处于原型验证到产品化拆分阶段。仓库已经具备 Streamlit 本地原型、FastAPI 服务雏形、Next.js Web 雏形、Supabase schema、私有 Storage bucket 规划，以及 `VoiceProvider` mock 抽象。

本设计面向产品级架构，但按阶段裁剪实现范围。核心原则是先完成家庭资料云端化和云端资料驱动聊天，再接入声音样本、声音克隆和 TTS。声音能力是陪伴体验增强，不应早于家庭画像、家人档案、家庭记忆和 AI 角色的云端闭环。

## 目标

1. 建立以单家庭空间为主的云端协作模型。
2. 将老人画像、家人档案、家庭记忆和 AI 角色迁移到 Supabase 云端存储。
3. 让老人端聊天读取云端资料，并复用现有 `engine/` 对话能力。
4. 在资料和聊天闭环稳定后，实现声音样本云存储、mock 声音克隆、真实 provider 接入和语音播放。
5. 弱化前端授权感知，但后端保留声音相关最小确认、权限和审计字段。

## 非目标

1. 首版不支持多家庭空间 UI 切换。
2. 首版不支持机构或护理人员管理多个家庭。
3. 首版不支持上传他人声音。
4. 首版不支持已故亲人或历史录音克隆。
5. 首版不做复杂多人编辑冲突合并。
6. 首版不把 Streamlit 作为正式云端数据入口。

## 总体方案

采用 Supabase 优先、FastAPI 业务编排的方案：

- Supabase Auth 负责登录身份。
- Supabase Postgres 负责家庭空间、成员、资料、记忆、角色、声音档案和聊天记录。
- Supabase Storage 负责声音样本和生成语音文件。
- Supabase RLS 负责数据隔离兜底。
- FastAPI 负责权限二次校验、智能导入、聊天上下文组装、声音 provider 调用、TTS 和审计写入。
- Next.js 前端负责交互，不直接承担可信业务判断。

前端传入的 `family_id` 只能作为请求参数，不能作为可信权限依据。FastAPI 需要根据当前登录用户确认其家庭空间成员身份，Supabase RLS 作为最后一道隔离。

## 云空间与权限模型

首版产品体验按单家庭空间设计。用户登录后默认进入一个家庭空间，界面不突出多空间切换。底层仍保留 `families` 和 `family_memberships`，所有业务数据都带 `family_id`，为后续多家庭空间保留扩展能力。

角色保留三类：

- `owner`：创建家庭空间的人。可邀请家人、移除成员、管理声音档案、编辑所有资料。
- `editor`：普通家人。可维护老人画像、家人档案、家庭记忆，并可创建自己的声音。
- `viewer`：只读成员。数据库保留，首版 UI 可以不主动暴露。

首版创建流程：

1. 用户登录。
2. 如果没有家庭空间，引导创建一个家庭空间。
3. 创建者自动成为 `owner`。
4. 邀请家人加入后默认成为 `editor`。
5. 所有业务页面默认使用该家庭空间。

## 云端资料存储与同步

第一阶段优先云端化家庭资料。Supabase Postgres 是正式主存储，当前 SQLite 和 Streamlit 原型保留为内部调试与迁移参考。

核心表沿用现有 schema：

- `elders`：老人画像，包括性格、偏好、习惯、健康备注、人生经历、重要记忆。
- `family_profiles`：家人档案，包括姓名、关系、性格、偏好、习惯、家庭关系。
- `memories`：家庭记忆，包括内容、类型、主体、相关家人、情绪标签、主题标签、亲密权重。
- `personas`：AI 角色，包括扮演关系、称呼、说话风格、安慰方式、敏感偏好。

资料数据流：

1. 家人端登录后进入默认家庭空间。
2. 页面通过 FastAPI 或受控 Supabase 查询读取该 `family_id` 下的资料。
3. 手动编辑保存到云端，记录 `updated_by` 和 `updated_at`。
4. 智能导入走 FastAPI 和 LLM 解析，先返回可编辑草稿。
5. 用户确认后，FastAPI 按 `family_id` 写入云端资料表。
6. 老人端聊天时，FastAPI 从 Supabase 读取云端资料，转换为现有 `engine/` 所需结构，再调用对话引擎生成回复。

首版冲突处理采用最后保存覆盖。所有记录保留 `updated_by` 和 `updated_at`，后续再扩展版本历史或合并提醒。

## 音频对象存储

声音能力使用 Supabase Storage，分两个私有 bucket：

- `voice-samples`：保存用户上传或录制的原始声音样本。
- `generated-audio`：保存聊天回复生成后的语音文件。

数据库只保存路径和元数据，不保存音频二进制。

推荐路径结构：

```text
voice-samples/{family_id}/{user_id}/{sample_id}.{ext}
generated-audio/{family_id}/{chat_session_id}/{message_id}.mp3
```

路径第一段固定为 `family_id`，便于 RLS 判断、删除清理、迁移和成本统计。

## 声音克隆流程与边界

声音能力放在第二阶段之后实现。首版只支持“我的声音”：登录用户只能上传或录制自己的声音样本，并创建自己的 `voice_profile`。

产品表达可以弱化授权意识，例如页面只用轻量确认文案：“我确认这是我本人的声音，并用于本家庭空间的语音陪伴”。技术上仍必须保存最小审计字段。

声音样本与克隆流程：

1. 用户进入“我的声音”页面。
2. 上传或录制 1 到多段声音样本。
3. 前端展示轻量确认。
4. FastAPI 校验当前用户属于家庭空间，并要求 `created_by` 为当前用户。
5. 样本保存到 `voice-samples/{family_id}/{user_id}/...`。
6. FastAPI 调用 `VoiceProvider.create_clone()`。
7. 成功后创建 `voice_profiles`，状态为 `ready`。
8. 失败时标记 `failed`，允许重新提交。

边界：

- 不支持上传他人声音。
- 不支持已故亲人声音。
- 不支持声音跨家庭空间复用。
- 不公开下载原始声音样本。
- 删除声音档案时，应同时清理 provider 侧 voice id、Supabase 样本和相关本地记录。生成音频可按保留策略异步清理。
- provider 不可用时保留 mock 或 fallback，老人端不能崩溃。

声音和角色不强绑定。`personas` 负责文本风格，`voice_profiles` 负责播放声音。首版可以为某个 AI 角色选择默认声音，但数据库层保持松耦合。

## 聊天语音生成

聊天接口优先生成文字。语音生成是附加能力，失败不影响文字回复。

流程：

1. 老人端发起聊天。
2. FastAPI 从云端读取家庭资料和当前角色，生成文字回复。
3. 如果请求带可用 `voice_profile_id`，尝试调用 `VoiceProvider.synthesize()`。
4. TTS 成功后将音频保存到 `generated-audio/{family_id}/{chat_session_id}/...`。
5. 将音频路径写入 `chat_messages.audio_storage_path`。
6. TTS 失败时返回文字回复，并给前端一个轻量状态，例如“语音暂不可用”。

首版 TTS 可以同步调用，并设置超时。后续如果延迟或成本压力明显，再迁移到后台任务队列。

## 后端服务边界与 API

FastAPI 作为业务编排层，不让前端直接拼复杂业务写库。

建议 API：

- `GET /api/family/current`：返回当前用户默认家庭空间、成员角色和基础配置。
- `POST /api/family`：创建默认家庭空间，创建者成为 `owner`。
- `GET /api/elders/current`：读取老人画像。
- `PUT /api/elders/current`：更新老人画像。
- `GET /api/family-profiles`：列出家人档案。
- `POST /api/family-profiles`：创建家人档案。
- `PUT /api/family-profiles/{id}`：更新家人档案。
- `DELETE /api/family-profiles/{id}`：删除家人档案。
- `GET /api/memories`：列出家庭记忆。
- `POST /api/memories`：创建家庭记忆。
- `PUT /api/memories/{id}`：更新家庭记忆。
- `DELETE /api/memories/{id}`：删除家庭记忆。
- `GET /api/personas`：列出 AI 角色。
- `POST /api/personas`：创建 AI 角色。
- `PUT /api/personas/{id}`：更新 AI 角色。
- `POST /api/import/preview`：智能解析自然语言，返回可编辑草稿，不落库。
- `POST /api/import/commit`：用户确认后，把草稿写入云端资料表。
- `POST /api/chat`：读取云端资料，生成文字回复，可选生成语音。
- `POST /api/voices/upload-intent`：创建声音样本上传路径或签名。
- `POST /api/voices/clone`：用已上传样本创建声音档案。
- `POST /api/tts`：为指定文本生成语音，可被聊天接口内部调用，也可独立调试。

建议模块：

- `CloudRepository`：封装 Supabase 数据读写。
- `FamilyContextService`：把云端资料转换为现有 `engine/` 对话所需结构。
- `VoiceProvider`：保留现有抽象，真实 provider 和 mock provider 都实现它。
- `AuditService`：记录声音相关创建、删除、失败原因和操作者。

## 阶段拆分

### 阶段 1：家庭云空间与资料云存储

目标是让家庭资料真正云端化。

验收标准：

- 用户登录后能创建或进入默认家庭空间。
- 老人画像、家人档案、家庭记忆、AI 角色都保存到 Supabase。
- 所有表按 `family_id` 隔离。
- `owner` 和 `editor` 可编辑，非成员不能读取。
- 当前本地导入和编辑能力有对应云端版本。
- 不接真实声音克隆。

### 阶段 2：云端资料驱动聊天

目标是让老人端回复读取云端资料，而不是本地 SQLite。

验收标准：

- 老人端聊天接口从 Supabase 读取画像、档案、记忆、角色。
- 现有 `engine/` 记忆评分、策略、安全校验继续复用。
- 智能导入结果确认后写入云端，并能影响后续聊天。
- LLM 失败、云端读取失败都有温和兜底。
- Streamlit 保留为内部调试，不作为正式数据入口。

### 阶段 3：声音样本云存储与 mock 克隆闭环

目标是先跑通声音流程和权限，不急着接真实服务商。

验收标准：

- 登录用户可上传或录制自己的声音样本。
- 样本保存到 `voice-samples` 私有 bucket。
- `voice_samples` 记录路径、来源、创建人、家庭空间。
- `MockVoiceProvider` 能创建 `voice_profiles`。
- 页面能展示声音状态：上传中、生成中、可用、失败。
- 未确认“这是我的声音”时不能创建声音档案，但文案保持轻量。

### 阶段 4：真实声音 provider 与聊天语音播放

目标是接入真实声音克隆和 TTS。

验收标准：

- 新增真实 provider 实现，并保留 mock provider。
- provider key 全部走环境变量，不写入代码或文档。
- 生成音频保存到 `generated-audio` 私有 bucket。
- `chat_messages.audio_storage_path` 记录语音路径。
- 老人端文字回复始终优先展示，语音失败只提示“语音暂不可用”。
- 删除声音档案时能清理本地记录，并尽力清理 provider 侧资源。

## 测试策略

阶段 1 和阶段 2：

- Supabase schema/RLS 静态检查。
- FastAPI 权限测试：非成员不能读取或写入家庭资料。
- 资料 CRUD 测试：老人画像、家人档案、记忆、角色。
- 智能导入 preview/commit 测试。
- 聊天上下文转换测试，确认云端资料能进入 `engine/`。
- LLM 失败和云端读取失败的兜底测试。

阶段 3 和阶段 4：

- `VoiceProvider` mock 单元测试。
- 未确认本人声音时拒绝创建声音档案。
- 声音样本路径必须包含正确 `family_id` 和 `user_id`。
- TTS 失败不影响文字聊天。
- provider key 只从环境变量读取。
- 删除声音档案时验证数据库记录和 provider 清理调用。

## 风险与缓解

1. 权限边界混乱。
   - 缓解：FastAPI 做业务权限判断，Supabase RLS 做兜底，前端不承担可信判断。

2. 过早接声音 provider 导致核心资料闭环滞后。
   - 缓解：阶段 1 和阶段 2 先完成云端资料与聊天闭环。

3. 声音克隆合规风险。
   - 缓解：首版只支持登录用户本人的声音，界面弱化授权感知，后端保留最小确认和审计。

4. TTS 延迟影响老人端聊天。
   - 缓解：文字优先返回，语音作为附加能力；同步 TTS 设置超时，后续可改后台任务。

5. Storage 路径与 RLS 不一致。
   - 缓解：固定路径第一段为 `family_id`，所有上传路径由 FastAPI 生成或校验。

## 待后续确认

1. 真实声音 provider 选择。
2. 声音样本格式、大小、时长和数量限制。
3. 删除声音档案时生成音频的保留策略。
4. 多家庭空间 UI 何时开放。
5. `viewer` 角色在首版 UI 是否完全隐藏。

