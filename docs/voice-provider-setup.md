# Voice Provider Setup

后端默认使用 `MockVoiceProvider`，不需要外部服务。要测试真实语音合成，当前 provider 方向统一为豆包语音服务/火山引擎。

## 豆包语音合成 TTS

当前接入的是 HTTP SSE 单向流式接口：

```text
https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse
```

需要你在火山引擎控制台准备：

- 新版控制台的 `API Key`
- `resource_id`，用于选择 TTS/ICL 模型版本与计费方式，默认配置为 `seed-tts-2.0`
- 声音复刻合成用的 `clone_resource_id`，默认配置为 `seed-icl-2.0`
- 默认 `speaker`，也就是音色列表里的发音人 ID

PowerShell 示例：

```powershell
$env:VOICE_PROVIDER="doubao"
$env:DOUBAO_TTS_API_KEY="your-api-key"
$env:DOUBAO_TTS_RESOURCE_ID="seed-tts-2.0"
$env:DOUBAO_TTS_CLONE_RESOURCE_ID="seed-icl-2.0"
$env:DOUBAO_TTS_DEFAULT_VOICE_TYPE="your-speaker-id"
$env:DOUBAO_TTS_ENCODING="mp3"
$env:DOUBAO_TTS_SAMPLE_RATE="24000"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

不要把真实 key 写入仓库、文档或日志。

## 运行方式

- `/api/tts` 和 `/api/chat` 的语音回复会在 `VOICE_PROVIDER=doubao` 时调用豆包 TTS。
- 后端使用新版控制台鉴权 Header：`X-Api-Key`、`X-Api-Resource-Id`、`X-Api-Request-Id`。
- 后端请求体使用 V3 `req_params` 结构，数据库里的 `voice_profiles.provider_voice_id` 会作为豆包 `speaker` 使用。
- 如果 `provider_voice_id` 为空，后端会使用 `DOUBAO_TTS_DEFAULT_VOICE_TYPE`。
- 如果 `provider_voice_id` 以 `S_` 或 `icl_` 开头，后端会自动使用 `DOUBAO_TTS_CLONE_RESOURCE_ID`，用于已复刻音色的合成。
- 后端当前会读取完整 SSE 响应并合并音频分片，再返回浏览器可播放的 `data:audio/mpeg;base64,...`。前端真正边播边收可以后续再做。

## 下一步服务商处理

真实声音复刻需要你在新版控制台确认：

- 已开通豆包声音复刻大模型，对应资源 ID 通常为 `seed-icl-2.0` 或控制台展示的 ICL 资源。
- 已完成声音复刻训练或创建，并拿到可用于合成的 `speaker`，常见形式为 `S_...` 或 `icl_...`。
- 该 `speaker` 对当前 API Key 有授权，否则合成接口会返回音色权限错误。

## Web 端真实复刻

声音页现在可以直接提交音频样本给豆包 V3 训练接口：

- 接口：`https://openspeech.bytedance.com/api/v3/tts/voice_clone`
- 鉴权：新版控制台 `X-Api-Key` 和 `X-Api-Request-Id`
- 音频：前端读取文件为 base64，后端传入 `audio.data` 和 `audio.format`
- 预付费：填写控制台给出的 `S_...` speaker。
- 后付费：填写自定义音色 ID，例如 `custom_family_voice_001`，后端会用 `speaker_id="custom_speaker_id"` 提交。
- 训练成功后，`voice_profiles.provider_voice_id` 保存返回的 `speaker_id`，后续 `/api/tts` 和聊天语音会直接使用该音色。

样本建议：

- 14-30 秒，优先 wav；文件不超过 10MB。
- 单人、单轨、低噪声，人声清晰。
- 情绪尽量平稳，适合陪伴场景。
- 如按固定文本朗读，可填写朗读文本用于服务端 WER 校验。
- 噪声较大时开启降噪；高质量音频建议关闭降噪以保留相似度。

## 当前边界

- 已接入：语音合成 TTS。
- 已接入：已复刻音色的合成资源自动切换。
- 已接入：通过 Web 上传样本并发起豆包 V3 真实声音复刻训练。
- 未接入：语音识别 ASR。

后续可以把前端 base64 直传改成对象存储上传后由后端读取，减少大请求体压力。语音识别需要单独选择 ASR 接口和前端录音上传/流式输入方案。
