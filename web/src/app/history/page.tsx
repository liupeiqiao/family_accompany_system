"use client";

import { useEffect, useMemo, useState } from "react";

import { ChatTurn, FamilyContext, fetchChatTurns, fetchCurrentFamily } from "../../lib/backend-api";

type TimeFilter = "all" | "today" | "7d" | "30d";

const timeFilterLabels: Record<TimeFilter, string> = {
  all: "全部时间",
  today: "今天",
  "7d": "最近 7 天",
  "30d": "最近 30 天",
};

function uniqueValues(turns: ChatTurn[], key: "persona_id" | "elder_id") {
  return Array.from(new Set(turns.map((turn) => turn[key] ?? "").filter(Boolean)));
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

export default function HistoryPage() {
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [personaFilter, setPersonaFilter] = useState("all");
  const [elderFilter, setElderFilter] = useState("all");
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void loadHistory();
  }, []);

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

  const personaOptions = useMemo(() => uniqueValues(turns, "persona_id"), [turns]);
  const elderOptions = useMemo(() => uniqueValues(turns, "elder_id"), [turns]);

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
              {personaOptions.map((personaId) => (
                <option key={personaId} value={personaId}>
                  {displayId(personaId)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>老人</span>
            <select value={elderFilter} onChange={(event) => setElderFilter(event.target.value)}>
              <option value="all">全部老人</option>
              {elderOptions.map((elderId) => (
                <option key={elderId} value={elderId}>
                  {displayId(elderId)}
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

        <div className="historyList" aria-label="对话轮次">
          {!isLoading && filteredTurns.length === 0 ? (
            <p className="emptyState">还没有符合条件的对话。</p>
          ) : null}
          {filteredTurns.map((turn) => (
            <article className="historyTurn" key={turn.id}>
              <div className="turnMeta">
                <span>{formatTime(turn.created_at)}</span>
                <span>角色：{displayId(turn.persona_id)}</span>
                <span>老人：{displayId(turn.elder_id)}</span>
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
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
