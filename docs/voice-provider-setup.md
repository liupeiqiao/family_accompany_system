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
- 默认 `speaker`，也就是音色列表里的发音人 ID

PowerShell 示例：

```powershell
$env:VOICE_PROVIDER="doubao"
$env:DOUBAO_TTS_API_KEY="your-api-key"
$env:DOUBAO_TTS_RESOURCE_ID="seed-tts-2.0"
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
- 后端当前会读取完整 SSE 响应并合并音频分片，再返回浏览器可播放的 `data:audio/mpeg;base64,...`。前端真正边播边收可以后续再做。

## 当前边界

- 已接入：语音合成 TTS。
- 未接入：真实声音复刻。
- 未接入：语音识别 ASR。

真实声音复刻需要另接豆包声音复刻 API，并补后端从私有 Storage 读取声音样本的能力。语音识别需要单独选择 ASR 接口和前端录音上传/流式输入方案。
