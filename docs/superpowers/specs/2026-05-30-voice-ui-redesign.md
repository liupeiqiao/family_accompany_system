# 声音复刻页面 UI 重构 & 音色类型区分

## 目标

将声音复刻页面从技术视角的单页平铺结构，重构为以"音色资源管理"为中心的用户视角页面，同时支持区分预置音色、预付费音色、后付费音色，并为不同类型提供对应的删除/隐藏操作。

## 整体布局

```
┌─────────────────────────────────────────────────────────┐
│ 顶部提示栏：使用豆包语音进行声音复刻与音色管理。          │
│           [打开豆包语音控制台]                            │
├──────────────┬──────────────────────────────────────────┤
│ 音色管理      │  右侧主区域（根据左侧选中项切换）          │
│              │                                          │
│ ▸ 家人音色库  │  ← 默认首页                               │
│   导入已有音色 │                                          │
│   创建复刻音色 │                                          │
│              │                                          │
└──────────────┴──────────────────────────────────────────┘
```

- 左侧垂直导航栏，右侧内容区单页切换
- 默认进入"家人音色库"
- 顶部豆包提示栏三个页面共享
- 整体风格参考现代 SaaS 管理后台，突出"管理家人声音资产"

---

## 页面一：家人音色库（默认首页）

卡片网格布局展示所有音色档案。

### 卡片信息

```
┌─────────────────────────────────────────┐
│ 🎤 妈妈的声音                    [预置音色]│
│ 创建时间: 2026-05-20                     │
│ Speaker ID        [展开]          [删除] │
└─────────────────────────────────────────┘
```

- 类型标签：预置音色（蓝灰）/ 已导入（绿色）/ 已复刻（橙色）
- Speaker ID 默认折叠，点击 `[展开]` 显示完整值，再点击 `[收起]`
- Speaker ID 展开/收起和删除按钮在同一行底部

### 删除逻辑

| voice_type | 按钮文案 | 确认弹窗 | 行为 |
|---|---|---|---|
| preset / prepaid | 本地删除 | "永久删除音色「xxx」及其关联样本？" | 调用 `deleteVoiceProfile()`，后端物理删除档案 + 级联删除关联 VoiceSample |
| postpaid | 本地隐藏 | "从本地列表隐藏音色「xxx」？豆包后付费音色仍保留在服务端。" | 调用 `deleteVoiceProfile()`，后端软删除（status → "hidden"）|

### 工具栏

- 搜索框：按音色名称模糊搜索
- 类型筛选下拉：全部 / 预置音色 / 已导入 / 已复刻

---

## 页面二：导入已有音色

### 表单

```
┌─────────────────────────────────────────┐
│ 导入已有音色                              │
│                                          │
│ 如果您已经拥有豆包语音中的音色，可直接导入  │
│ 已有 Speaker ID，无需重新进行声音复刻。     │
│                                          │
│ 音色类型:  [预置音色 ▼]                    │
│            [预付费 Speaker ID]            │
│                                          │
│ 音色名称:  [________________]            │
│                                          │
│ Speaker ID: [________________]  ← 仅选"预付费"时显示 │
│                                          │
│ 确认勾选:  □ 我确认此声音将用于本家庭空间    │
│                                          │
│            [添加音色]                      │
└─────────────────────────────────────────┘
```

- 选择"预置音色"时：Speaker ID 输入框隐藏，后端自动使用默认豆包音色
- 选择"预付费 Speaker ID"时：显示 Speaker ID 输入框，校验 `S_` / `icl_` 前缀
- 提交后 voice_type：`"preset"` / `"prepaid"`
- 固定 sample_source = `"preset"` 或 `"imported"`

---

## 页面三：创建复刻音色

### 表单

```
┌──────────────────────────────────────────────────┐
│ 创建复刻音色                                       │
│                                                   │
│ ⚠ 后付费声音复刻可能产生额外费用，请提前查看        │
│   官方计费规则。                                    │
│                                                   │
│ 音色名称:  [________________]                      │
│                                                   │
│ 音频上传:  [选择文件]  ← 支持 wav/mp3/ogg/m4a       │
│   建议 14-30 秒、低噪声、单人单轨，不超过 10MB       │
│                                                   │
│ ▼ 复刻参数（可折叠，默认展开）                       │
│   音色创建方式: [后付费自定义音色 ID ▼]              │
│                [预付费 speaker_id]                 │
│   音色 ID:     [________________]                 │
│   试听文本:    [________________]                 │
│   语种:        [中文 ▼]                            │
│   □ 样本噪声较大时启用降噪                           │
│                                                   │
│ □ 我确认这是我本人的声音，用于本家庭空间的语音陪伴     │
│                                                   │
│             [创建复刻音色]                          │
└──────────────────────────────────────────────────┘
```

- 费用提醒在表单顶部显著位置
- 复刻参数区域可折叠（默认展开）
- 创建方式切换：后付费校验自定义 ID 格式（至少8位，字母开头），预付费校验 S_/icl_ 前缀
- 提交后 voice_type：后付费 → `"postpaid"`，预付费 → `"prepaid"`
- 去掉原有的"关联样本记录"下拉（样本管理内部化）

---

## 数据模型

### VoiceProfile 新增字段

```
voice_type: "preset" | "prepaid" | "postpaid"
```

创建时由后端 `handle_clone_voice` 写入，判断逻辑：

| voice_type | 触发条件 |
|---|---|
| `"preset"` | 导入页选"预置音色"（无 Speaker ID，无样本文件） |
| `"prepaid"` | 导入页选"预付费" 或 复刻页选"预付费 speaker_id"（Speaker ID 以 S_ / icl_ 开头） |
| `"postpaid"` | 复刻页选"后付费自定义音色 ID"（使用 custom_speaker_id） |

voice_type 创建后只读，不随后续操作变更。

### TypeScript 类型更新

```typescript
export type VoiceProfile = CloudRecord & {
  id: string;
  display_name: string;
  provider: string;
  provider_voice_id: string;
  status: "creating" | "ready" | "failed";
  consent_confirmed: boolean;
  demo_audio_url?: string;
  sample_source?: string;
  voice_type?: "preset" | "prepaid" | "postpaid";  // 新增
};
```

---

## API 变更

### 删除音色档案（统一入口）

| 方法 | 路径 |
|---|---|
| `DELETE` | `/api/voices/profiles/{profile_id}?family_id=...` |

Handler: `handle_delete_voice_profile()`

后端根据 `voice_type` 自动决定行为：

| voice_type | 行为 |
|---|---|
| preset / prepaid | 物理删除档案 + 级联删除所有 `voice_profile_id` 匹配的 VoiceSample |
| postpaid | 软删除（`status → "hidden"`），豆包服务端数据不受影响 |

前端统一调用 `deleteVoiceProfile()`，不再区分 hide / permanent delete。确认弹窗文案前端根据 `voice_type` 切换。

### 移除的 API

`handle_hide_voice_profile()` 逻辑合并到 `handle_delete_voice_profile()` 中，不再独立暴露。

### CloudRepository 接口新增

```python
def delete_voice_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
    ...
```

实现：
- InMemoryCloudRepository: preset/prepaid → `del self._voice_profiles[profile_id]` + 遍历 `_voice_samples` 删除匹配项；postpaid → `profile["status"] = "hidden"`
- SupabaseCloudRepository: preset/prepaid → DELETE `voice_profiles` 行 + DELETE `voice_samples` WHERE `voice_profile_id = profile_id`；postpaid → PATCH `status = "hidden"`

### 前端 API 函数变更

```typescript
// 新增：统一删除入口，后端根据 voice_type 自动选择硬删除或软隐藏
export function deleteVoiceProfile(profileId: string, familyId: string): Promise<{ ok: boolean }>

// 移除：hideVoiceProfile()，逻辑合并到 deleteVoiceProfile
```

### cloneVoice 接口调整

`cloneVoice()` 入参新增 `voice_type` 字段，由前端根据当前页面上下文传入。

**导入预付费 Speaker ID（无音频）的特殊处理：**

当 `voice_type === "prepaid"` 且未传 `audio_data_base64` 时，后端跳过豆包复刻 API 调用，直接创建档案记录（因为音色已存在于豆包平台）。`provider_voice_id` 设为用户输入的 Speaker ID。

---

## 前端组件结构

```
page.tsx (VoicesPage)
├─ 顶部提示栏 <DoubaoBanner />
├─ 左侧导航 <VoiceNav />  (家人音色库 / 导入已有音色 / 创建复刻音色)
└─ 右侧内容区（条件渲染）
    ├─ <FamilyVoiceLibrary />   — 默认
    ├─ <ImportVoice />          — 导入已有音色
    └─ <CreateCloneVoice />     — 创建复刻音色
```

### 状态管理

- 当前选中页面: `useState<"library" | "import" | "clone">("library")`
- 音色列表: `useState<VoiceProfile[]>([])`
- 数据加载: 进入页面时一次性加载，切换 tab 不重新请求
- 操作后（删除/导入/创建）：局部刷新 profiles 列表

### 不再展示的内容

- 原有的"声音样本"独立管理区（样本创建表单 + 样本列表）移除——样本管理内部化，用户无需直接操作样本记录
- 原有的"声音状态"两个并排列表（样本+档案）合并为单一音色卡片网格

---

## 不在本次范围内

- 音色与角色解耦：角色编辑页关联音色功能（后续独立任务）
- 现有数据迁移脚本（voice_type 回填）
- 声音样本独立管理页面
