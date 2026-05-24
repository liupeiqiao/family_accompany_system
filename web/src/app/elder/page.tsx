"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  FamilyContext,
  VoiceProfile,
  fetchCurrentFamily,
  fetchVoiceProfiles,
  sendChat,
} from "../../lib/backend-api";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  audioUrl?: string;
};

const initialMessages: Message[] = [
  {
    id: 1,
    role: "assistant",
    content: "妈，我在呢。您慢慢说，我陪您聊一会儿。",
  },
];

export default function ElderChatPage() {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [messageText, setMessageText] = useState("");
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [voiceProfiles, setVoiceProfiles] = useState<VoiceProfile[]>([]);
  const [selectedVoiceProfileId, setSelectedVoiceProfileId] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void loadVoiceOptions();
  }, []);

  async function loadVoiceOptions() {
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      const profiles = await fetchVoiceProfiles(context.family.id);
      const readyProfiles = profiles.filter((profile) => profile.status === "ready");
      setVoiceProfiles(readyProfiles);
      setSelectedVoiceProfileId(readyProfiles[0]?.id ?? "");
    } catch {
      setFamilyContext(null);
      setVoiceProfiles([]);
      setSelectedVoiceProfileId("");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = messageText.trim();
    if (!text || isSending) {
      return;
    }

    setError("");
    setMessageText("");
    setIsSending(true);

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: text,
    };
    setMessages((current) => [...current, userMessage]);

    try {
      const reply = await sendChat({
        family_id: familyContext?.family.id ?? "local",
        elder_id: "",
        persona_id: "",
        text,
        voice_profile_id: voiceEnabled ? selectedVoiceProfileId : undefined,
      });
      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: reply.text,
        audioUrl: reply.audio_url ?? undefined,
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch {
      setError("暂时连不上家人回复服务，请稍后再试。");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="shell">
      <section className="chat" aria-label="老人端聊天">
        <h1>老人端</h1>

        <div className="conversation" aria-live="polite">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <strong>{message.role === "user" ? "老人" : "家人回复"}</strong>
              <p>{message.content}</p>
              {message.audioUrl ? (
                <audio controls src={message.audioUrl}>
                  当前浏览器不支持音频播放。
                </audio>
              ) : null}
            </article>
          ))}
        </div>

        {error ? <p className="errorText">{error}</p> : null}

        <form onSubmit={handleSubmit}>
          <label htmlFor="elder-message">想和家人说的话</label>
          <textarea
            id="elder-message"
            name="message"
            rows={4}
            value={messageText}
            onChange={(event) => setMessageText(event.target.value)}
            placeholder="比如：小明，我今天有点想你。"
          />

          <div className="voiceReplyControl">
            <label className="voiceConsent">
              <input
                checked={voiceEnabled}
                disabled={!selectedVoiceProfileId}
                onChange={(event) => setVoiceEnabled(event.target.checked)}
                type="checkbox"
              />
              <span>使用语音回复</span>
            </label>
            <select
              disabled={!voiceProfiles.length}
              value={selectedVoiceProfileId}
              onChange={(event) => setSelectedVoiceProfileId(event.target.value)}
            >
              <option value="">暂无可用声音档案</option>
              {voiceProfiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.display_name}
                </option>
              ))}
            </select>
          </div>

          <button disabled={isSending} type="submit">
            {isSending ? "发送中..." : "发送"}
          </button>
        </form>
      </section>
    </main>
  );
}
