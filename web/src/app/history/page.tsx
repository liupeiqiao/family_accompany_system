"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ChatTurn,
  FamilyContext,
  createCloudMemory,
  fetchChatTurns,
  fetchCurrentFamily,
  generateMemoryCandidate,
} from "../../lib/backend-api";
import { getAuthToken } from "../../lib/auth";

type TimeFilter = "all" | "today" | "7d" | "30d";
type MemoryDraft = {
  content: string;
  memory_type: string;
  subject: string;
  family_members: string;
  emotion_tags: string;
  topic_tags: string;
};

const timeFilterLabels: Record<TimeFilter, string> = {
  all: "全部时间",
  today: "今天",
  "7d": "最近 7 天",
  "30d": "最近 30 天",
};

function uniqueOptions(turns: ChatTurn[], idKey: "persona_id" | "elder_id", labelKey: "persona_display_name" | "elder_display_name") {
  const options = new Map<string, string>();
  turns.forEach((turn) => {
    const id = turn[idKey] ?? "";
    if (!id) return;
    options.set(id, turn[labelKey] || displayId(id));
  });
  return Array.from(options, ([id, label]) => ({ id, label }));
}

function isWithinTimeFilter(turn: ChatTurn, timeFilter: TimeFilter) {
  if (timeFilter === "all") return true;
  const createdAt = parseCreatedAt(turn.created_at);
  if (!createdAt) return true;
  const now = new Date();
  const start = new Date(now);
  if (timeFilter === "today") {
    start.setHours(0, 0, 0, 0);
  } else {
    start.setDate(now.getDate() - (timeFilter === "7d" ? 7 : 30));
  }
  return createdAt >= start;
}

function parseCreatedAt(value?: string) {
  if (!value) return null;
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) return parsed;
  return null;
}

function formatTime(value?: string) {
  const parsed = parseCreatedAt(value);
  if (!parsed) return value || "时间未记录";
  return parsed.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function displayId(value?: string) {
  if (!value) return "未绑定";
  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
}

function displayName(name?: string, id?: string) {
  return name || displayId(id);
}

function createMemoryDraftFromTurn(turn: ChatTurn): MemoryDraft {
  const subject = turn.persona_display_name || turn.elder_display_name || turn.persona_id || turn.elder_id || "老人";
  return {
    content: `老人说：${turn.user_text || "未识别到文字"}\nAI 回复：${turn.assistant_text || "未记录回复"}`,
    memory_type: "对话",
    subject,
    family_members: turn.persona_display_name || "",
    emotion_tags: "",
    topic_tags: "",
  };
}

function splitTags(value: string) {
  return value
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinTags(value?: string[]) {
  return (value ?? []).join("，");
}

export default function HistoryPage() {
  const router = useRouter();
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [personaFilter, setPersonaFilter] = useState("all");
  const [elderFilter, setElderFilter] = useState("all");
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [memoryDrafts, setMemoryDrafts] = useState<Record<string, MemoryDraft>>({});
  const [savedMemoryTurnIds, setSavedMemoryTurnIds] = useState<Record<string, boolean>>({});
  const [memorySaveMessage, setMemorySaveMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getAuthToken()) {
      router.replace("/login");
      return;
    }
    void loadHistory();
  }, [router]);

  async function loadHistory() {
    setIsLoading(true);
    setError("");
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      setTurns(await fetchChatTurns(context.family.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "对话历史加载失败");
      setFamilyContext(null);
      setTurns([]);
    } finally {
      setIsLoading(false);
    }
  }

  function playAudio(audioUrl: string) {
    const audio = new Audio(audioUrl);
    void audio.play();
  }

  function openMemoryDraft(turn: ChatTurn) {
    setMemorySaveMessage("");
    setMemoryDrafts((current) => ({
      ...current,
      [turn.id]: current[turn.id] ?? createMemoryDraftFromTurn(turn),
    }));
  }

  function updateMemoryDraft(turnId: string, key: keyof MemoryDraft, value: string) {
    setMemoryDrafts((current) => ({
      ...current,
      [turnId]: {
        ...current[turnId],
        [key]: value,
      },
    }));
  }

  function closeMemoryDraft(turnId: string) {
    setMemoryDrafts((current) => {
      const next = { ...current };
      delete next[turnId];
      return next;
    });
  }

  async function saveTurnAsMemory(turn: ChatTurn) {
    if (!familyContext) {
      setMemorySaveMessage("请先进入家庭空间后再保存记忆。");
      return;
    }
    const draft = memoryDrafts[turn.id] ?? createMemoryDraftFromTurn(turn);
    if (!draft.content.trim()) {
      setMemorySaveMessage("记忆内容不能为空。");
      return;
    }
    try {
      await createCloudMemory({
        family_id: familyContext.family.id,
        content: draft.content.trim(),
        memory_type: draft.memory_type.trim() || "对话",
        subject: draft.subject.trim() || "老人",
        family_members: splitTags(draft.family_members),
        emotion_tags: splitTags(draft.emotion_tags),
        topic_tags: splitTags(draft.topic_tags),
        intimacy_weight: 0.6,
      });
      setSavedMemoryTurnIds((current) => ({ ...current, [turn.id]: true }));
      closeMemoryDraft(turn.id);
      setMemorySaveMessage("已保存为长期记忆。");
    } catch (err) {
      setMemorySaveMessage(err instanceof Error ? err.message : "保存记忆失败");
    }
  }

  async function generateCandidateForTurn(turn: ChatTurn) {
    if (!familyContext) {
      setMemorySaveMessage("请先进入家庭空间后再生成候选。");
      return;
    }
    try {
      const response = await generateMemoryCandidate({
        family_id: familyContext.family.id,
        user_text: turn.user_text,
        assistant_text: turn.assistant_text,
        persona_display_name: turn.persona_display_name,
        elder_display_name: turn.elder_display_name,
      });
      const candidate = response.candidate;
      setMemoryDrafts((current) => ({
        ...current,
        [turn.id]: {
          content: candidate.content || createMemoryDraftFromTurn(turn).content,
          memory_type: candidate.memory_type || "对话",
          subject: candidate.subject || turn.elder_display_name || turn.persona_display_name || "老人",
          family_members: joinTags(candidate.family_members),
          emotion_tags: joinTags(candidate.emotion_tags),
          topic_tags: joinTags(candidate.topic_tags),
        },
      }));
      setMemorySaveMessage(response.source === "parser" ? "已生成记忆候选，请确认后保存。" : "已生成基础候选，请编辑确认后保存。");
    } catch (err) {
      setMemorySaveMessage(err instanceof Error ? err.message : "生成记忆候选失败");
    }
  }

  const personaOptions = useMemo(() => uniqueOptions(turns, "persona_id", "persona_display_name"), [turns]);
  const elderOptions = useMemo(() => uniqueOptions(turns, "elder_id", "elder_display_name"), [turns]);

  const filteredTurns = useMemo(
    () =>
      turns.filter((turn) => {
        if (personaFilter !== "all" && turn.persona_id !== personaFilter) return false;
        if (elderFilter !== "all" && turn.elder_id !== elderFilter) return false;
        return isWithinTimeFilter(turn, timeFilter);
      }),
    [elderFilter, personaFilter, timeFilter, turns],
  );

  return (
    <main className="shell">
      <section className="sectionHeader">
        <p className="eyebrow">家庭复盘</p>
        <h1>对话历史</h1>
        <p className="helperText">
          {familyContext ? `${familyContext.family.name} 的老人端对话记录` : "查看老人端语音陪伴留下的文字和 AI 回复音频。"}
        </p>
      </section>

      <section className="historyLayout">
        <div className="historyFilters" aria-label="对话筛选">
          <label>
            <span>AI 角色</span>
            <select value={personaFilter} onChange={(event) => setPersonaFilter(event.target.value)}>
              <option value="all">全部角色</option>
              {personaOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>老人</span>
            <select value={elderFilter} onChange={(event) => setElderFilter(event.target.value)}>
              <option value="all">全部老人</option>
              {elderOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>时间</span>
            <select value={timeFilter} onChange={(event) => setTimeFilter(event.target.value as TimeFilter)}>
              {(Object.keys(timeFilterLabels) as TimeFilter[]).map((key) => (
                <option key={key} value={key}>
                  {timeFilterLabels[key]}
                </option>
              ))}
            </select>
          </label>
          <button className="buttonSecondary" onClick={() => void loadHistory()} type="button">
            刷新
          </button>
        </div>

        {isLoading ? <p className="helperText">正在加载对话历史...</p> : null}
        {error ? <p className="errorText">{error}</p> : null}
        {memorySaveMessage ? <p className={memorySaveMessage.includes("已保存") ? "successText" : "errorText"}>{memorySaveMessage}</p> : null}

        <div className="historyList" aria-label="对话轮次">
          {!isLoading && filteredTurns.length === 0 ? (
            <p className="emptyState">还没有符合条件的对话。</p>
          ) : null}
          {filteredTurns.map((turn) => (
            <article className="historyTurn" key={turn.id}>
              <div className="turnMeta">
                <span>{formatTime(turn.created_at)}</span>
                <span>角色：{displayName(turn.persona_display_name, turn.persona_id)}</span>
                <span>老人：{displayName(turn.elder_display_name, turn.elder_id)}</span>
                <span>音色：{displayName(turn.voice_display_name, turn.voice_profile_id)}</span>
              </div>
              <div className="turnDialogue">
                <p>
                  <strong>老人说：</strong>
                  {turn.user_text || "这一轮没有识别到文字"}
                </p>
                <p>
                  <strong>AI 回复：</strong>
                  {turn.assistant_text || "这一轮没有回复文字"}
                </p>
              </div>
              <div className="turnFooter">
                <span>ASR：{turn.asr_provider || "未记录"}</span>
                <span>TTS：{turn.tts_provider || "未记录"}</span>
                {turn.audio_url ? (
                  <button className="buttonSecondary" onClick={() => playAudio(turn.audio_url as string)} type="button">
                    重播
                  </button>
                ) : null}
                {savedMemoryTurnIds[turn.id] ? (
                  <span className="savedBadge">已保存为记忆</span>
                ) : (
                  <>
                    <button className="buttonSecondary" onClick={() => void generateCandidateForTurn(turn)} type="button">
                      生成记忆候选
                    </button>
                    <button className="buttonSecondary" onClick={() => openMemoryDraft(turn)} type="button">
                      保存为记忆
                    </button>
                  </>
                )}
              </div>
              {memoryDrafts[turn.id] ? (
                <div className="memorySavePanel">
                  <label>
                    <span>记忆内容</span>
                    <textarea
                      value={memoryDrafts[turn.id].content}
                      onChange={(event) => updateMemoryDraft(turn.id, "content", event.target.value)}
                      rows={4}
                    />
                  </label>
                  <div className="memorySaveGrid">
                    <label>
                      <span>类型</span>
                      <input
                        value={memoryDrafts[turn.id].memory_type}
                        onChange={(event) => updateMemoryDraft(turn.id, "memory_type", event.target.value)}
                      />
                    </label>
                    <label>
                      <span>主语</span>
                      <input
                        value={memoryDrafts[turn.id].subject}
                        onChange={(event) => updateMemoryDraft(turn.id, "subject", event.target.value)}
                      />
                    </label>
                    <label>
                      <span>相关家人</span>
                      <input
                        placeholder="逗号分隔"
                        value={memoryDrafts[turn.id].family_members}
                        onChange={(event) => updateMemoryDraft(turn.id, "family_members", event.target.value)}
                      />
                    </label>
                    <label>
                      <span>情绪标签</span>
                      <input
                        placeholder="逗号分隔"
                        value={memoryDrafts[turn.id].emotion_tags}
                        onChange={(event) => updateMemoryDraft(turn.id, "emotion_tags", event.target.value)}
                      />
                    </label>
                    <label>
                      <span>主题标签</span>
                      <input
                        placeholder="逗号分隔"
                        value={memoryDrafts[turn.id].topic_tags}
                        onChange={(event) => updateMemoryDraft(turn.id, "topic_tags", event.target.value)}
                      />
                    </label>
                  </div>
                  <div className="callActions">
                    <button onClick={() => void saveTurnAsMemory(turn)} type="button">
                      确认保存
                    </button>
                    <button className="buttonSecondary" onClick={() => closeMemoryDraft(turn.id)} type="button">
                      取消
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
