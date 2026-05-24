# Voice Provider Setup

后端默认使用 `MockVoiceProvider`，不需要外部服务。要测试真实语音合成，当前 provider 方向统一为豆包语音服务/火山引擎。

## 豆包语音合成 TTS

当前接入的是 HTTP SSE 单向流式接口：

```text
https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse
```

需要你在火山引擎控制台准备：

- `appid`
- `access_token`
- `cluster`，通常为 `volcano_tts`
- `resource_id`，默认配置为 `volc.service_type.10029`，以控制台实际值为准
- 默认 `voice_type`

PowerShell 示例：

```powershell
$env:VOICE_PROVIDER="doubao"
$env:DOUBAO_TTS_APP_ID="your-appid"
$env:DOUBAO_TTS_ACCESS_TOKEN="your-access-token"
$env:DOUBAO_TTS_CLUSTER="volcano_tts"
$env:DOUBAO_TTS_RESOURCE_ID="volc.service_type.10029"
$env:DOUBAO_TTS_DEFAULT_VOICE_TYPE="your-voice-type"
$env:DOUBAO_TTS_MODEL="seed-tts-1.1"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

不要把真实 key 写入仓库、文档或日志。

## 运行方式

- `/api/tts` 和 `/api/chat` 的语音回复会在 `VOICE_PROVIDER=doubao` 时调用豆包 TTS。
- 数据库里的 `voice_profiles.provider_voice_id` 会作为豆包 `voice_type` 使用。
- 如果 `provider_voice_id` 为空，后端会使用 `DOUBAO_TTS_DEFAULT_VOICE_TYPE`。
- 后端当前会读取完整 SSE 响应并合并音频分片，再返回浏览器可播放的 `data:audio/mpeg;base64,...`。前端真正边播边收可以后续再做。

## 当前边界

- 已接入：语音合成 TTS。
- 未接入：真实声音复刻。
- 未接入：语音识别 ASR。

真实声音复刻需要另接豆包声音复刻 API，并补后端从私有 Storage 读取声音样本的能力。语音识别需要单独选择 ASR 接口和前端录音上传/流式输入方案。
