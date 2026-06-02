"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ChatTurn,
  FamilyContext,
  createCloudMemory,
  deleteChatSession,
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

type IconName = "brand" | "journey" | "home" | "family" | "records" | "history" | "voice" | "settings" | "calendar" | "search" | "play" | "chevron";

const pageSize = 4;

const timeFilterLabels: Record<TimeFilter, string> = {
  all: "全部",
  today: "今天",
  "7d": "近 7 天",
  "30d": "近 30 天",
};

const sidebarItems: { href: string; label: string; icon: IconName }[] = [
  { href: "/elder", label: "旅程", icon: "journey" },
  { href: "/", label: "首页", icon: "home" },
  { href: "/family", label: "家庭空间", icon: "family" },
  { href: "/records", label: "档案与记忆", icon: "records" },
  { href: "/history", label: "对话历史", icon: "history" },
  { href: "/voices", label: "音色管理", icon: "voice" },
  { href: "/family", label: "系统设置", icon: "settings" },
];

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

  const now = new Date();
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const clock = parsed.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  if (parsed >= today) return `今天 ${clock}`;
  if (parsed >= yesterday) return `昨天 ${clock}`;
  return `${String(parsed.getMonth() + 1).padStart(2, "0")}-${String(parsed.getDate()).padStart(2, "0")} ${clock}`;
}

function estimateDuration(turn: ChatTurn) {
  const chars = `${turn.user_text || ""}${turn.assistant_text || ""}`.length;
  const seconds = Math.max(35, Math.min(540, Math.round(chars * 1.6)));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function displayId(value?: string) {
  if (!value) return "未绑定";
  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
}

function displayName(name?: string, id?: string) {
  return name || displayId(id);
}

function getConversationName(turn: ChatTurn) {
  return displayName(turn.elder_display_name || turn.persona_display_name, turn.elder_id || turn.persona_id);
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
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinTags(value?: string[]) {
  return (value ?? []).join("，");
}

function Icon({ name }: { name: IconName }) {
  if (name === "brand") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8 6.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm8 0a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
        <path d="M3.5 21V12.5L8 8l4 4 4-4 4.5 4.5V21h-6v-4.5h-5V21h-6Z" />
      </svg>
    );
  }
  if (name === "play") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8 5.5v13l10-6.5-10-6.5Z" />
      </svg>
    );
  }
  if (name === "search") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m20 20-4.2-4.2M18 10.5A7.5 7.5 0 1 1 3 10.5a7.5 7.5 0 0 1 15 0Z" />
      </svg>
    );
  }
  if (name === "calendar") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 3v4m10-4v4M4 9h16M5 5h14a1 1 0 0 1 1 1v15H4V6a1 1 0 0 1 1-1Z" />
      </svg>
    );
  }
  if (name === "chevron") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m9 6 6 6-6 6" />
      </svg>
    );
  }

  const paths: Record<Exclude<IconName, "brand" | "play" | "search" | "calendar" | "chevron">, string> = {
    journey: "M4 17 8.5 8l4 7 2.5-4 5 6H4Zm5-9a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
    home: "M4 11.5 12 4l8 7.5V21h-5v-6H9v6H4v-9.5Z",
    family: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3 21c.5-4 2.4-6 5-6s4.5 2 5 6m-2.5-5c.9-.7 2-1 3.5-1 2.6 0 4.5 2 5 6",
    records: "M6 4h12v18H6V4Zm3 5h6M9 13h6",
    history: "M6 7h12a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3h-5l-4 3v-3H6a3 3 0 0 1-3-3v-4a3 3 0 0 1 3-3Zm2 5h.01M12 12h.01M16 12h.01",
    voice: "M8 9a4 4 0 0 1 8 0v3a4 4 0 0 1-8 0V9Zm4 9v3m-5-3h10M5 11v1a7 7 0 0 0 14 0v-1",
    settings: "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm0-13 1.2 2.5 2.8.5.6 2.7 2.4 1.6-1 2.7 1 2.7-2.4 1.6-.6 2.7-2.8.5L12 22l-1.2-2.5-2.8-.5-.6-2.7L5 14.7l1-2.7-1-2.7 2.4-1.6.6-2.7 2.8-.5L12 2.5Z",
  };

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  );
}

export default function HistoryPage() {
  const router = useRouter();
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [personaFilter, setPersonaFilter] = useState("all");
  const [elderFilter, setElderFilter] = useState("all");
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [memoryDrafts, setMemoryDrafts] = useState<Record<string, MemoryDraft>>({});
  const [savedMemoryTurnIds, setSavedMemoryTurnIds] = useState<Record<string, boolean>>({});
  const [memorySaveMessage, setMemorySaveMessage] = useState("");
  const [expandedTurnIds, setExpandedTurnIds] = useState<Record<string, boolean>>({});
  const [quickSaveTurnId, setQuickSaveTurnId] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
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

  function playAudio(audioUrl?: string) {
    if (!audioUrl) return;
    const audio = new Audio(audioUrl);
    void audio.play();
  }

  async function deleteTurn(turn: ChatTurn) {
    if (!familyContext) return;
    const name = getConversationName(turn);
    if (!window.confirm(`确定要删除与「${name}」的这段对话记录吗？\n\n删除后无法恢复。`)) {
      return;
    }
    try {
      await deleteChatSession(turn.session_id, familyContext.family.id);
      setTurns((current) => current.filter((t) => t.id !== turn.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
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
      setQuickSaveTurnId("");
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
      setQuickSaveTurnId(turn.id);
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
        if (!isWithinTimeFilter(turn, timeFilter)) return false;
        const query = searchQuery.trim().toLowerCase();
        if (!query) return true;
        return [turn.user_text, turn.assistant_text, turn.persona_display_name, turn.elder_display_name]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      }),
    [elderFilter, personaFilter, searchQuery, timeFilter, turns],
  );

  const totalPages = Math.max(1, Math.ceil(filteredTurns.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const pageTurns = filteredTurns.slice((safePage - 1) * pageSize, safePage * pageSize);

  useEffect(() => {
    setCurrentPage(1);
  }, [elderFilter, personaFilter, searchQuery, timeFilter]);

  return (
    <main className="historyApp">
      <aside className="historySidebar" aria-label="主导航">
        <Link className="historyBrand" href="/">
          <Icon name="brand" />
          <span>亲情陪伴系统</span>
        </Link>
        <nav className="historySideNav">
          {sidebarItems.map((item) => (
            <Link className={item.href === "/history" ? "active" : ""} href={item.href} key={`${item.href}-${item.label}`}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      <section className="historyMain">
        <header className="historyTop">
          <h1>对话历史</h1>
          <p>{familyContext ? `${familyContext.family.name} 的老人端对话记录` : "查看老人端语音陪伴留下的文字和 AI 回复音频"}</p>
        </header>

        <section className="historyToolbar" aria-label="对话筛选">
          <div className="historyTabs" role="tablist" aria-label="时间范围">
            {(Object.keys(timeFilterLabels) as TimeFilter[]).map((key) => (
              <button
                aria-selected={timeFilter === key}
                className={timeFilter === key ? "active" : ""}
                key={key}
                onClick={() => setTimeFilter(key)}
                role="tab"
                type="button"
              >
                {timeFilterLabels[key]}
              </button>
            ))}
          </div>

          <label className="historyDateSelect">
            <Icon name="calendar" />
            <select value={timeFilter} onChange={(event) => setTimeFilter(event.target.value as TimeFilter)}>
              {(Object.keys(timeFilterLabels) as TimeFilter[]).map((key) => (
                <option key={key} value={key}>
                  {timeFilterLabels[key] === "全部" ? "选择日期范围" : timeFilterLabels[key]}
                </option>
              ))}
            </select>
            <Icon name="chevron" />
          </label>

          <label className="historySearch">
            <Icon name="search" />
            <input
              aria-label="搜索对话内容"
              placeholder="搜索对话内容"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </label>
        </section>

        <section className="historyAdvancedFilters" aria-label="对象筛选">
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
          <button className="historyRefresh" onClick={() => void loadHistory()} type="button">
            刷新
          </button>
        </section>

        {isLoading ? <p className="historyNotice">正在加载对话历史...</p> : null}
        {error ? <p className="historyNotice error">{error}</p> : null}
        {memorySaveMessage ? <p className={memorySaveMessage.includes("已保存") ? "historyNotice success" : "historyNotice error"}>{memorySaveMessage}</p> : null}

        <section className="historyTableCard" aria-label="对话轮次">
          <div className="historyTableHeader">
            <span>对话对象</span>
            <span>对话内容摘要</span>
            <span>时长</span>
            <span>时间</span>
            <span>操作</span>
          </div>

          {!isLoading && pageTurns.length === 0 ? (
            <div className="historyEmpty">还没有符合条件的对话。</div>
          ) : null}

          {pageTurns.map((turn, index) => {
            const turnExpanded = !!expandedTurnIds[turn.id];
            const summary = turn.user_text || turn.assistant_text || "这一轮没有记录到对话文字";
            const hasMore = (turn.user_text || "").length > 42 || (turn.assistant_text || "").length > 42;
            const isQuickSave = quickSaveTurnId === turn.id;
            const name = getConversationName(turn);
            return (
              <article className="historyRow" key={turn.id}>
                <button
                  className="historyRowMain"
                  onClick={() => setExpandedTurnIds((current) => ({ ...current, [turn.id]: !turnExpanded }))}
                  type="button"
                >
                  <span className={`historyAvatar avatarTone${index % 4}`} aria-hidden="true">
                    {name.slice(0, 1)}
                  </span>
                  <strong>{name}</strong>
                  <span className="historySummary">{summary}</span>
                  <span>{estimateDuration(turn)}</span>
                  <span>{formatTime(turn.created_at)}</span>
                </button>
                <div className="historyRowAction">
                  <button
                    aria-label={turn.audio_url ? "播放对话音频" : "展开对话详情"}
                    className="historyPlay"
                    onClick={() => (turn.audio_url ? playAudio(turn.audio_url) : setExpandedTurnIds((current) => ({ ...current, [turn.id]: !turnExpanded })))}
                    type="button"
                  >
                    <Icon name="play" />
                  </button>
                </div>

                {turnExpanded ? (
                  <div className="historyDetail">
                    <div className="historyDialogue">
                      <p>
                        <strong>老人说：</strong>
                        {turn.user_text || "这一轮没有识别到文字"}
                      </p>
                      <p>
                        <strong>AI 回复：</strong>
                        {turn.assistant_text || "这一轮没有记录回复文字"}
                      </p>
                      <div className="historyMetaLine">
                        <span>角色：{displayName(turn.persona_display_name, turn.persona_id)}</span>
                        <span>老人：{displayName(turn.elder_display_name, turn.elder_id)}</span>
                        <span>音色：{displayName(turn.voice_display_name, turn.voice_profile_id)}</span>
                        <span>ASR：{turn.asr_provider || "未记录"}</span>
                        <span>TTS：{turn.tts_provider || "未记录"}</span>
                        {hasMore ? <span>已展开完整内容</span> : null}
                      </div>
                    </div>
                    <div className="historyDetailActions">
                      {savedMemoryTurnIds[turn.id] ? (
                        <span className="savedBadge">已保存为记忆</span>
                      ) : (
                        <>
                          <button className="buttonSecondary" onClick={() => void generateCandidateForTurn(turn)} type="button">
                            生成记忆候选
                          </button>
                          {isQuickSave ? (
                            <button className="button buttonSuccess" onClick={() => { openMemoryDraft(turn); void saveTurnAsMemory(turn); }} type="button">
                              一键保存
                            </button>
                          ) : null}
                          <button className="buttonSecondary" onClick={() => openMemoryDraft(turn)} type="button">
                            保存为记忆
                          </button>
                        </>
                      )}
                      <button
                        className="buttonSecondary buttonDanger"
                        onClick={() => void deleteTurn(turn)}
                        style={{ marginLeft: "auto" }}
                        type="button"
                      >
                        删除记录
                      </button>
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
                  </div>
                ) : null}
              </article>
            );
          })}
        </section>

        <footer className="historyPagination">
          <span>共 {filteredTurns.length} 条对话记录</span>
          <div>
            <button disabled={safePage <= 1} onClick={() => setCurrentPage((value) => Math.max(1, value - 1))} type="button" aria-label="上一页">
              <Icon name="chevron" />
            </button>
            {Array.from({ length: Math.min(totalPages, 4) }, (_, index) => index + 1).map((page) => (
              <button className={safePage === page ? "active" : ""} key={page} onClick={() => setCurrentPage(page)} type="button">
                {page}
              </button>
            ))}
            {totalPages > 5 ? <span>...</span> : null}
            {totalPages > 4 ? (
              <button className={safePage === totalPages ? "active" : ""} onClick={() => setCurrentPage(totalPages)} type="button">
                {totalPages}
              </button>
            ) : null}
            <button disabled={safePage >= totalPages} onClick={() => setCurrentPage((value) => Math.min(totalPages, value + 1))} type="button" aria-label="下一页">
              <Icon name="chevron" />
            </button>
          </div>
        </footer>
      </section>
    </main>
  );
}
