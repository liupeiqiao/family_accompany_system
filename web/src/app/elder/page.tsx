"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ChatHistoryMessage,
  FamilyContext,
  ElderVoiceChatResponse,
  fetchChatHistory,
  fetchCloudElder,
  fetchCloudPersonas,
  fetchCurrentFamily,
  fetchVoiceProfiles,
  sendElderVoiceChat,
} from "../../lib/backend-api";
import { getAuthToken } from "../../lib/auth";

type CallState =
  | "idle"
  | "recording"
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
  const storageKey = "elder_voice_session_id";
  if (typeof window !== "undefined") {
    const existing = window.sessionStorage.getItem(storageKey);
    if (existing) return existing;
  }
  let sessionId = "";
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    sessionId = crypto.randomUUID();
  } else {
    sessionId = `elder-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(storageKey, sessionId);
  }
  return sessionId;
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
  const [clientSessionId] = useState(createClientSessionId);
  const [recentTurns, setRecentTurns] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState("");
  const [continuousMode, setContinuousMode] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [showAllTurns, setShowAllTurns] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const sendRecordingAfterStopRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!getAuthToken()) {
      router.replace("/login");
      return;
    }
    void loadInitialState();
    return () => {
      sendRecordingAfterStopRef.current = false;
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
      // 从聊天历史恢复上次使用的角色
      const history = await fetchChatHistory(context.family.id);
      setRecentTurns(buildRecentTurns(history));
      const lastTurnPersonaId = [...history].reverse().find((msg) => msg.persona_id)?.persona_id;
      const lastPersona = lastTurnPersonaId
        ? personas.find((p) => String(p.id) === String(lastTurnPersonaId))
        : null;
      const activePersona = lastPersona || firstPersona;
      const personaId = String(activePersona.id);
      const boundVoice = voiceProfiles.find(
        (profile) => String(profile.persona_id ?? "") === personaId && profile.status === "ready",
      );
      setCurrentPersonaId(personaId);
      setCurrentPersonaName(String(activePersona.role_label || "家人"));
      setSetupState("ready");
    } catch {
      setFamilyContext(null);
      setSetupState("missing");
      setRecentTurns([]);
    }
  }

  const statusText = useMemo(() => {
    switch (callState) {
      case "recording":
        return "正在听你说";
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
        return "⏹ 发送";
      case "understanding":
        return "⏳ 正在理解";
      case "replying":
        return "⏳ 正在回复";
      case "playing":
        return "⏹ 打断说话";
      default:
        return "🎤 开始说话";
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
      stopRecordingAndSend();
      return;
    }
    await startRecording();
  }

  async function startRecording() {
    setError("");
    sendRecordingAfterStopRef.current = false;
    if (!familyContext) {
      setError("陪伴资料还没准备好，请家人先完成设置。");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("这个手机不能说话聊天，让家人帮你换一个手机试试。");
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
        const shouldSend = sendRecordingAfterStopRef.current;
        sendRecordingAfterStopRef.current = false;
        mediaRecorderRef.current = null;
        if (shouldSend) {
          void sendVoiceBlob(new Blob(chunks, { type: mimeType }), audioFormatFromMimeType(mimeType));
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setCallState("recording");
    } catch {
      setError("还没打开话筒，让家人帮你设置一下。");
      setCallState("error");
    }
  }

  function stopRecordingAndSend() {
    if (mediaRecorderRef.current?.state === "recording") {
      sendRecordingAfterStopRef.current = true;
      setCallState("understanding");
      mediaRecorderRef.current.stop();
    }
  }

  async function sendVoiceBlob(audioBlob: Blob, audioFormat: string) {
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
        audio_file: audioBlob,
      });
      handleVoiceChatResponse(response);
    } catch {
      setError("刚才没听清楚，你再说一遍就好。");
      setCallState("error");
    }
  }

  function handleVoiceChatResponse(response: ElderVoiceChatResponse) {
    if (response.status === "asr_empty") {
      setError("没听清，大点声再说一遍吧。");
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
      <section className={`elderPhone`} data-call-state={callState} aria-label="老人端语音陪伴">
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
          {setupState === "ready" && showMore ? (
            <button
              className={continuousMode ? "button" : "buttonSecondary"}
              onClick={() => setContinuousMode((enabled) => !enabled)}
              type="button"
            >
              {continuousMode ? "连续对话：开" : "连续对话：关"}
            </button>
          ) : null}
          {callState === "playing" && showMore ? (
            <button className="buttonSecondary" onClick={() => { stopPlayback(); setCallState("idle"); }} type="button">
              停止播放
            </button>
          ) : null}
          {callState === "idle" && recentTurns.some((turn) => turn.audioUrl) ? (
            <button className="buttonSecondary" onClick={replayLatest} type="button">
              重播上一条
            </button>
          ) : null}
          {setupState === "ready" ? (
            <button className="moreActions" onClick={() => setShowMore((v) => !v)} type="button">
              {showMore ? "收起 ▲" : "更多 ▾"}
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
            <a className="button" href="/family">家属去设置</a>
          </section>
        ) : null}

        <div className="recentTurns" aria-label="最近对话">
          {recentTurns.length ? (
            <>
              {(showAllTurns ? recentTurns : recentTurns.slice(0, 1)).map((turn) => (
                <article className="recentTurn" key={turn.id}>
                  <p><strong>您说：</strong>{turn.userText || "刚才那句话没有听清"}</p>
                  <p><strong>{currentPersonaName}：</strong>{turn.assistantText}</p>
                  {turn.audioUrl ? (
                    <button className="buttonSecondary" onClick={() => playAudio(turn.audioUrl as string)} type="button">
                      重播
                    </button>
                  ) : null}
                </article>
              ))}
              {recentTurns.length > 1 ? (
                <button className="moreActions" onClick={() => setShowAllTurns((v) => !v)} type="button">
                  {showAllTurns ? "收起 ▲" : `看更多（还有 ${recentTurns.length - 1} 条）▾`}
                </button>
              ) : null}
            </>
          ) : (
            <p className="emptyState">还没有最近对话。</p>
          )}
        </div>
      </section>
    </main>
  );
}
