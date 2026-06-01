"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ChatHistoryMessage,
  createCloudPersona,
  createFamily,
  FamilyContext,
  ElderVoiceChatResponse,
  fetchChatHistory,
  fetchCloudElder,
  fetchCloudPersonas,
  fetchCurrentFamily,
  fetchVoiceProfiles,
  saveCloudElder,
  sendElderVoiceChat,
} from "../../lib/backend-api";
import { getAuthToken } from "../../lib/auth";

type CallState =
  | "idle"
  | "recording"
  | "recorded"
  | "understanding"
  | "replying"
  | "playing"
  | "error";

type ConversationTurn = {
  id: string;
  userText: string;
  assistantText: string;
  audioUrl?: string;
};

type SetupState = "loading" | "ready" | "missing";

function createClientSessionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `elder-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function audioFormatFromMimeType(mimeType: string) {
  if (mimeType.includes("mp3") || mimeType.includes("mpeg")) return "mp3";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}

function buildRecentTurns(messages: ChatHistoryMessage[]): ConversationTurn[] {
  const turns: ConversationTurn[] = [];
  for (let index = 0; index < messages.length; index += 1) {
    const current = messages[index];
    const next = messages[index + 1];
    if (current.role !== "user" || !next || next.role !== "assistant") {
      continue;
    }
    turns.push({
      id: `${current.id}-${next.id}`,
      userText: current.text,
      assistantText: next.text,
      audioUrl: next.audio_storage_path,
    });
    index += 1;
  }
  return turns.slice(-3).reverse();
}

export default function ElderChatPage() {
  const router = useRouter();
  const [callState, setCallState] = useState<CallState>("idle");
  const [setupState, setSetupState] = useState<SetupState>("loading");
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [currentPersonaId, setCurrentPersonaId] = useState("");
  const [currentPersonaName, setCurrentPersonaName] = useState("家人");
  const [currentVoiceProfileId, setCurrentVoiceProfileId] = useState("");
  const [currentVoiceName, setCurrentVoiceName] = useState("");
  const [elderName, setElderName] = useState("");
  const [personaRole, setPersonaRole] = useState("女儿");
  const [setupError, setSetupError] = useState("");
  const [isSettingUp, setIsSettingUp] = useState(false);
  const [clientSessionId] = useState(createClientSessionId);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [audioFormat, setAudioFormat] = useState("webm");
  const [recentTurns, setRecentTurns] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState("");
  const [continuousMode, setContinuousMode] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!getAuthToken()) {
      router.replace("/login");
      return;
    }
    void loadInitialState();
    return () => {
      stopPlayback();
      mediaRecorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function loadInitialState() {
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      const [elder, personas, voiceProfiles] = await Promise.all([
        fetchCloudElder(context.family.id),
        fetchCloudPersonas(context.family.id),
        fetchVoiceProfiles(context.family.id),
      ]);
      const firstPersona = personas[0];
      if (!elder.id || !firstPersona?.id) {
        setSetupState("missing");
        return;
      }
      const personaId = String(firstPersona.id);
      const boundVoice = voiceProfiles.find(
        (profile) => String(profile.persona_id ?? "") === personaId && profile.status === "ready",
      );
      setCurrentPersonaId(personaId);
      setCurrentPersonaName(String(firstPersona.appellation || firstPersona.role_label || "家人"));
      setCurrentVoiceProfileId(boundVoice?.id ?? "");
      setCurrentVoiceName(boundVoice?.display_name ?? "");
      const history = await fetchChatHistory(context.family.id);
      setRecentTurns(buildRecentTurns(history));
      setSetupState("ready");
    } catch {
      setFamilyContext(null);
      setSetupState("missing");
      setRecentTurns([]);
    }
  }

  async function handleSetupSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSetupError("");
    setIsSettingUp(true);
    try {
      const context = familyContext ?? await createFamily({ name: "我的家庭" });
      setFamilyContext(context);
      const familyId = context.family.id;
      const cleanElderName = elderName.trim() || "老人";
      const cleanPersonaRole = personaRole.trim() || "家人";
      await saveCloudElder({
        family_id: familyId,
        full_name: cleanElderName,
        appellation: cleanElderName,
      });
      const persona = await createCloudPersona({
        family_id: familyId,
        role_label: cleanPersonaRole,
        relation: cleanPersonaRole,
        appellation: cleanPersonaRole,
        personality: [],
        speech_style: ["语气温和", "表达简单"],
        comfort_style: ["先回应情绪", "少讲复杂道理"],
        topic_affinity: [],
        sensitivity_map: {},
      });
      setCurrentPersonaId(String(persona.id ?? ""));
      setCurrentPersonaName(String(persona.appellation || persona.role_label || cleanPersonaRole));
      setCurrentVoiceProfileId("");
      setCurrentVoiceName("");
      setRecentTurns([]);
      setSetupState("ready");
      setCallState("idle");
    } catch (err) {
      setSetupError(err instanceof Error ? err.message : "创建陪伴资料失败，请稍后再试。");
    } finally {
      setIsSettingUp(false);
    }
  }

  const statusText = useMemo(() => {
    switch (callState) {
      case "recording":
        return "正在听你说";
      case "recorded":
        return "说完啦，可以发送";
      case "understanding":
        return "正在理解你说的话";
      case "replying":
        return "正在回复";
      case "playing":
        return "正在播放回复";
      case "error":
        return "刚才有点卡住了";
      default:
        return "可以开始说话啦";
    }
  }, [callState]);

  const primaryLabel = useMemo(() => {
    switch (callState) {
      case "recording":
        return "结束并发送";
      case "recorded":
        return "发送";
      case "understanding":
        return "正在理解";
      case "replying":
        return "正在回复";
      case "playing":
        return "打断说话";
      default:
        return "开始说话";
    }
  }, [callState]);

  const primaryDisabled = setupState !== "ready" || callState === "understanding" || callState === "replying";

  async function handlePrimaryAction() {
    if (primaryDisabled) return;
    if (callState === "playing") {
      stopPlayback();
      await startRecording();
      return;
    }
    if (callState === "recording") {
      stopRecording();
      return;
    }
    if (callState === "recorded") {
      await sendRecordedAudio();
      return;
    }
    await startRecording();
  }

  async function startRecording() {
    setError("");
    setRecordedBlob(null);
    if (!familyContext) {
      setError("陪伴资料还没准备好，请家人先完成设置。");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("当前浏览器暂时不能录音，请换一个浏览器再试。");
      setCallState("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const mimeType = recorder.mimeType || "audio/webm";
        setRecordedBlob(new Blob(chunks, { type: mimeType }));
        setAudioFormat(audioFormatFromMimeType(mimeType));
        setCallState("recorded");
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setCallState("recording");
    } catch {
      setError("没有打开麦克风权限，暂时不能语音聊天。");
      setCallState("error");
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }

  function cancelRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder?.state === "recording") {
      recorder.onstop = () => {
        recorder.stream.getTracks().forEach((track) => track.stop());
      };
      recorder.stop();
    }
    setRecordedBlob(null);
    setCallState("idle");
  }

  async function sendRecordedAudio() {
    if (!recordedBlob) return;
    if (!familyContext) {
      setError("陪伴资料还没准备好，请家人先完成设置。");
      setCallState("error");
      return;
    }
    setError("");
    setCallState("understanding");
    try {
      setCallState("replying");
      const response = await sendElderVoiceChat({
        family_id: familyContext.family.id,
        client_session_id: clientSessionId,
        persona_id: currentPersonaId,
        voice_profile_id: currentVoiceProfileId,
        audio_format: audioFormat,
        audio_file: recordedBlob,
      });
      handleVoiceChatResponse(response);
    } catch {
      setError("我这边有点卡住了，请稍等一下再说。");
      setCallState("error");
    }
  }

  function handleVoiceChatResponse(response: ElderVoiceChatResponse) {
    setRecordedBlob(null);
    if (response.status === "asr_empty") {
      setError("刚才没有听清，您可以再说一遍。");
      setCallState("idle");
      return;
    }
    if (response.status === "context_error") {
      setError(response.reply_text || "陪伴资料暂时没有读到，请家人稍后检查。");
      setCallState("idle");
      return;
    }
    if (response.matched_persona.persona_id) {
      setCurrentPersonaId(response.matched_persona.persona_id);
    }
    if (response.matched_persona.display_name) {
      setCurrentPersonaName(response.matched_persona.display_name);
    }
    const nextTurn: ConversationTurn = {
      id: `${response.session_id}-${Date.now()}`,
      userText: response.recognized_text,
      assistantText: response.reply_text,
      audioUrl: response.audio_url ?? undefined,
    };
    setRecentTurns((turns) => [nextTurn, ...turns].slice(0, 3));
    if (response.audio_url) {
      playAudio(response.audio_url);
      return;
    }
    setError("这次没有生成语音回复，文字已经显示出来了。");
    setCallState("idle");
  }

  function playAudio(url: string) {
    stopPlayback();
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => {
      void handlePlaybackEnded();
    };
    audio.onerror = () => setCallState("idle");
    setCallState("playing");
    void audio.play().catch(() => setCallState("idle"));
  }

  async function handlePlaybackEnded() {
    audioRef.current = null;
    if (continuousMode && setupState === "ready") {
      await startRecording();
      return;
    }
    setCallState("idle");
  }

  function stopPlayback() {
    audioRef.current?.pause();
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
  }

  function replayLatest() {
    const latest = recentTurns.find((turn) => turn.audioUrl);
    if (latest?.audioUrl) {
      playAudio(latest.audioUrl);
    }
  }

  return (
    <main className="shell">
      <section className="elderPhone" aria-label="老人端语音陪伴">
        <header className="callTarget">
          <p className="eyebrow">正在和</p>
          <h1>{currentPersonaName} 说话</h1>
          <p className="helperText">
            {currentVoiceName ? `已使用绑定音色：${currentVoiceName}` : "还没有给这个家人绑定音色"}
          </p>
          <p className="callStatus">{statusText}</p>
        </header>

        <button
          className={`callButton ${callState}`}
          disabled={primaryDisabled}
          onClick={() => void handlePrimaryAction()}
          type="button"
        >
          {primaryLabel}
        </button>

        <div className="callActions" aria-label="辅助操作">
          {setupState === "ready" ? (
            <button
              className={continuousMode ? "button" : "buttonSecondary"}
              onClick={() => setContinuousMode((enabled) => !enabled)}
              type="button"
            >
              {continuousMode ? "连续对话：开" : "连续对话：关"}
            </button>
          ) : null}
          {callState === "recording" ? (
            <button className="buttonSecondary" onClick={cancelRecording} type="button">
              取消本轮
            </button>
          ) : null}
          {callState === "recorded" ? (
            <button className="buttonSecondary" onClick={() => void startRecording()} type="button">
              重新说
            </button>
          ) : null}
          {callState === "playing" ? (
            <button className="buttonSecondary" onClick={() => { stopPlayback(); setCallState("idle"); }} type="button">
              停止播放
            </button>
          ) : null}
          {callState === "idle" && recentTurns.some((turn) => turn.audioUrl) ? (
            <button className="buttonSecondary" onClick={replayLatest} type="button">
              重播上一条
            </button>
          ) : null}
        </div>

        {setupState === "ready" && continuousMode ? (
          <p className="helperText">播放完会继续听你说。</p>
        ) : null}

        {error ? <p className="errorText">{error}</p> : null}

        {setupState === "missing" ? (
          <section className="elderSetupNotice" aria-label="陪伴资料设置提示">
            <h2>陪伴资料还没准备好</h2>
            <p>请家人先完成设置，再把这个页面交给老人使用。</p>
            <form className="elderSetupForm" onSubmit={(event) => void handleSetupSubmit(event)}>
              <label>
                <span>老人称呼</span>
                <input
                  onChange={(event) => setElderName(event.target.value)}
                  placeholder="例如：妈妈、奶奶、外公"
                  value={elderName}
                />
              </label>
              <label>
                <span>家人角色</span>
                <input
                  onChange={(event) => setPersonaRole(event.target.value)}
                  placeholder="例如：女儿、儿子、小雨"
                  value={personaRole}
                />
              </label>
              <button className="button" disabled={isSettingUp} type="submit">
                {isSettingUp ? "创建中" : "创建陪伴资料"}
              </button>
              {setupError ? <p className="errorText">{setupError}</p> : null}
            </form>
            <a className="button buttonSecondary" href="/family">家属去设置</a>
          </section>
        ) : null}

        <div className="recentTurns" aria-label="最近对话">
          {recentTurns.length ? (
            recentTurns.map((turn) => (
              <article className="recentTurn" key={turn.id}>
                <p><strong>您说：</strong>{turn.userText || "刚才那句话没有听清"}</p>
                <p><strong>{currentPersonaName}：</strong>{turn.assistantText}</p>
                {turn.audioUrl ? (
                  <button className="buttonSecondary" onClick={() => playAudio(turn.audioUrl as string)} type="button">
                    重播
                  </button>
                ) : null}
              </article>
            ))
          ) : (
            <p className="emptyState">还没有最近对话。</p>
          )}
        </div>
      </section>
    </main>
  );
}
