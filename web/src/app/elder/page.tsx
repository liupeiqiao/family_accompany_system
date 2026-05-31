"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  ChatHistoryMessage,
  FamilyContext,
  fetchChatHistory,
  fetchCurrentFamily,
  sendElderVoiceChat,
} from "../../lib/backend-api";

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
  const [callState, setCallState] = useState<CallState>("idle");
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [currentPersonaId, setCurrentPersonaId] = useState("");
  const [currentPersonaName, setCurrentPersonaName] = useState("家人");
  const [clientSessionId] = useState(createClientSessionId);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [audioFormat, setAudioFormat] = useState("webm");
  const [recentTurns, setRecentTurns] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState("");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    void loadInitialState();
    return () => {
      stopPlayback();
      mediaRecorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadInitialState() {
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      const history = await fetchChatHistory(context.family.id);
      setRecentTurns(buildRecentTurns(history));
    } catch {
      setFamilyContext(null);
      setRecentTurns([]);
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

  const primaryDisabled = callState === "understanding" || callState === "replying";

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
    setError("");
    setCallState("understanding");
    try {
      setCallState("replying");
      const response = await sendElderVoiceChat({
        family_id: familyContext?.family.id ?? "local",
        client_session_id: clientSessionId,
        persona_id: currentPersonaId,
        audio_format: audioFormat,
        audio_file: recordedBlob,
      });
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
      setRecordedBlob(null);
      if (response.audio_url) {
        playAudio(response.audio_url);
      } else {
        setCallState("idle");
      }
    } catch {
      setError("我这边有点卡住了，请稍等一下再说。");
      setCallState("error");
    }
  }

  function playAudio(url: string) {
    stopPlayback();
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => setCallState("idle");
    audio.onerror = () => setCallState("idle");
    setCallState("playing");
    void audio.play().catch(() => setCallState("idle"));
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

        {error ? <p className="errorText">{error}</p> : null}

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
