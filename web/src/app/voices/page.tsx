"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CloudRecord,
  FamilyContext,
  VoiceProfile,
  VoiceStatusResponse,
  cloneVoice,
  fetchCloudPersonas,
  fetchCurrentFamily,
  fetchVoiceProfiles,
  deleteVoiceProfile,
  previewVoice,
  queryVoiceStatus,
  updateVoiceProfile,
} from "../../lib/backend-api";
import { getAuthToken } from "../../lib/auth";

type NavTab = "library" | "import" | "clone";
type VoiceManagementState = { isLoading?: boolean; error?: string; result?: VoiceStatusResponse };

export default function VoicesPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<NavTab>("library");
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [personas, setPersonas] = useState<CloudRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [voiceManagement, setVoiceManagement] = useState<Record<string, VoiceManagementState>>({});

  useEffect(() => {
    if (!getAuthToken()) {
      router.replace("/login");
      return;
    }
    void loadVoiceSpace();
  }, [router]);

  async function loadVoiceSpace() {
    setIsLoading(true);
    setError("");
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      const [nextProfiles, nextPersonas] = await Promise.all([
        fetchVoiceProfiles(context.family.id),
        fetchCloudPersonas(context.family.id),
      ]);
      setProfiles(nextProfiles);
      setPersonas(nextPersonas);
    } catch (err) {
      setFamilyContext(null);
      setError(err instanceof Error ? err.message : "声音空间加载失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDelete(profile: VoiceProfile) {
    if (!familyContext) return;
    setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true } }));
    try {
      await deleteVoiceProfile(profile.id, familyContext.family.id);
      setProfiles((c) => c.filter((p) => p.id !== profile.id));
      setMessage("音色已删除。");
    } catch (err) {
      setVoiceManagement((c) => ({
        ...c, [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "删除失败" },
      }));
    }
  }

  async function handleBindPersona(profile: VoiceProfile, personaId: string) {
    if (!familyContext) return;
    setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true } }));
    try {
      const updated = await updateVoiceProfile(profile.id, {
        family_id: familyContext.family.id,
        persona_id: personaId,
      });
      setProfiles((c) => c.map((p) => (p.id === profile.id ? updated : p)));
      setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: false } }));
      setMessage(personaId ? "音色已绑定到 AI 角色。" : "音色已取消角色绑定。");
    } catch (err) {
      setVoiceManagement((c) => ({
        ...c, [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "绑定失败" },
      }));
    }
  }

  async function handleQuery(profile: VoiceProfile) {
    if (!familyContext) return;
    setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true } }));
    try {
      const result = await queryVoiceStatus({
        family_id: familyContext.family.id,
        voice_profile_id: profile.id,
      });
      setVoiceManagement((c) => ({ ...c, [profile.id]: { isLoading: false, result } }));
    } catch (err) {
      setVoiceManagement((c) => ({
        ...c, [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "查询失败" },
      }));
    }
  }

  async function handleRename(profile: VoiceProfile, newName: string) {
    if (!familyContext) return;
    if (!newName.trim()) return;
    setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true } }));
    try {
      const updated = await updateVoiceProfile(profile.id, {
        family_id: familyContext.family.id,
        display_name: newName.trim(),
      });
      setProfiles((c) => c.map((p) => (p.id === profile.id ? updated : p)));
      setMessage("音色名称已更新。");
    } catch (err) {
      setVoiceManagement((c) => ({
        ...c, [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "重命名失败" },
      }));
    }
  }

  async function handlePreview(profile: VoiceProfile) {
    if (!familyContext) return;
    setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true, error: "" } }));
    try {
      const audioUrl = profile.demo_audio_url
        ? profile.demo_audio_url
        : (await previewVoice({ family_id: familyContext.family.id, voice_profile_id: profile.id })).audio_url;
      setProfiles((c) => c.map((p) => (p.id === profile.id ? { ...p, demo_audio_url: audioUrl } : p)));
      setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: false } }));
      void new Audio(audioUrl).play();
    } catch (err) {
      setVoiceManagement((c) => ({
        ...c,
        [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "试听失败" },
      }));
    }
  }

  const canWrite = familyContext?.membership.role === "owner" || familyContext?.membership.role === "editor";

  return (
    <main className="voiceApp">
      <VoiceAppSidebar />
      <section className="voiceMain" aria-label="音色管理">
        <DoubaoBanner />
        <div className="voiceLayout">
          <VoiceNav activeTab={activeTab} onSelect={setActiveTab} />
          <div className="voiceContent">
          {isLoading ? <p className="helperText">正在加载声音空间...</p> : null}
          {error && !familyContext ? (
            <section className="importSection">
              <h2>尚未创建家庭空间</h2>
              <p className="errorText">{error}</p>
              <Link className="button" href="/family">去创建家庭空间</Link>
            </section>
          ) : null}
          {familyContext && activeTab === "library" && (
            <FamilyVoiceLibrary
              profiles={profiles}
              personas={personas}
              canWrite={Boolean(canWrite)}
              management={voiceManagement}
              message={message}
              onDelete={handleDelete}
              onBindPersona={handleBindPersona}
              onQuery={handleQuery}
              onRename={handleRename}
              onPreview={handlePreview}
            />
          )}
          {familyContext && activeTab === "import" && (
            <ImportVoice
              familyId={familyContext.family.id}
              canWrite={Boolean(canWrite)}
              onImported={(profile) => {
                setProfiles((c) => [profile, ...c]);
                setMessage("音色导入成功。");
                setActiveTab("library");
              }}
              onError={setError}
            />
          )}
          {familyContext && activeTab === "clone" && (
            <CreateCloneVoice
              familyId={familyContext.family.id}
              canWrite={Boolean(canWrite)}
              onCreated={(profile) => {
                setProfiles((c) => [profile, ...c]);
                setMessage("复刻音色创建成功。");
                setActiveTab("library");
              }}
              onError={setError}
            />
          )}
          </div>
        </div>
      </section>
    </main>
  );
}

function VoiceAppSidebar() {
  const items = [
    { href: "/", label: "首页", icon: "home" },
    { href: "/family", label: "家庭空间", icon: "family" },
    { href: "/records", label: "档案与记忆", icon: "folder" },
    { href: "/history", label: "对话历史", icon: "history" },
    { href: "/voices", label: "音色管理", icon: "voice", active: true },
    { href: "/family", label: "系统设置", icon: "settings" },
  ];
  return (
    <aside className="voiceSidebar">
      <a className="voiceBrand" href="/">
        <VoiceIcon name="brand" />
        <span>
          <strong>亲情陪伴系统</strong>
          <small>让陪伴有声，让记忆延续</small>
        </span>
      </a>
      <nav className="voiceSideNav" aria-label="主导航">
        {items.map((item) => (
          <a className={item.active ? "active" : ""} href={item.href} key={item.label}>
            <VoiceIcon name={item.icon} />
            <span>{item.label}</span>
          </a>
        ))}
      </nav>
      <div className="voiceUserCard">
        <span className="voiceUserAvatar" aria-hidden="true" />
        <span>
          <strong>小美</strong>
          <small>管理员</small>
        </span>
        <VoiceIcon name="chevron" />
      </div>
    </aside>
  );
}

function DoubaoBanner() {
  return (
    <div className="doubaoBanner">
      <span><VoiceIcon name="speaker" />使用豆包语音进行声音复刻与音色管理</span>
      <a className="button buttonSecondary" href="https://console.volcengine.com/speech/new/voices?ResourceID=volc.seedicl.default&projectName=default" target="_blank" rel="noopener noreferrer">
        打开豆包语音控制台 <VoiceIcon name="external" />
      </a>
    </div>
  );
}

function VoiceNav({ activeTab, onSelect }: { activeTab: NavTab; onSelect: (tab: NavTab) => void }) {
  const tabs: { key: NavTab; label: string }[] = [
    { key: "library", label: "家人音色库" },
    { key: "import", label: "导入已有音色" },
    { key: "clone", label: "创建复刻音色" },
  ];
  return (
    <nav className="voiceNav">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          className={activeTab === tab.key ? "navItemActive" : "navItem"}
          onClick={() => onSelect(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

function FamilyVoiceLibrary(props: {
  profiles: VoiceProfile[];
  personas: CloudRecord[];
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  message: string;
  onDelete: (profile: VoiceProfile) => void;
  onBindPersona: (profile: VoiceProfile, personaId: string) => void;
  onQuery: (profile: VoiceProfile) => void;
  onRename: (profile: VoiceProfile, newName: string) => void;
  onPreview: (profile: VoiceProfile) => void;
}) {
  const { profiles, personas, canWrite, management, message, onDelete, onBindPersona, onQuery, onRename, onPreview } = props;
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const filtered = profiles.filter((p) => {
    if (search && !p.display_name.toLowerCase().includes(search.toLowerCase())) return false;
    if (typeFilter !== "all" && p.voice_type !== typeFilter) return false;
    return true;
  });

  return (
    <section className="voicePanel">
      <div className="voicePanelTop">
        <h2>家人音色库</h2>
        <div className="toolbar">
          <label className="voiceSearch">
            <VoiceIcon name="search" />
            <input
              placeholder="搜索音色名称..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="all">全部</option>
            <option value="preset">预置音色</option>
            <option value="prepaid">已导入</option>
            <option value="postpaid">已复刻</option>
          </select>
        </div>
      </div>
      {message ? <p className="successText">{message}</p> : null}
      {filtered.length === 0 ? (
        <p className="emptyState">还没有音色档案</p>
      ) : (
        <div className="voiceGrid">
          {filtered.map((profile) => (
            <VoiceCard
              key={profile.id}
              profile={profile}
              personas={personas}
              canWrite={canWrite}
              management={management}
              onDelete={onDelete}
              onBindPersona={onBindPersona}
              onQuery={onQuery}
              onRename={onRename}
              onPreview={onPreview}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function VoiceCard(props: {
  profile: VoiceProfile;
  personas: CloudRecord[];
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  onDelete: (profile: VoiceProfile) => void;
  onBindPersona: (profile: VoiceProfile, personaId: string) => void;
  onQuery: (profile: VoiceProfile) => void;
  onRename: (profile: VoiceProfile, newName: string) => void;
  onPreview: (profile: VoiceProfile) => void;
}) {
  const { profile, personas, canWrite, management, onDelete, onBindPersona, onQuery, onRename, onPreview } = props;
  const [speakerIdExpanded, setSpeakerIdExpanded] = useState(false);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editName, setEditName] = useState(profile.display_name);
  const state = management[profile.id] ?? {};
  const cloudStatus = state.result?.voice_status;
  const boundPersona = personas.find((persona) => String(persona.id ?? "") === String(profile.persona_id ?? ""));

  const typeLabel = profile.voice_type === "preset" ? "预置音色"
    : profile.voice_type === "prepaid" ? "已导入"
    : profile.voice_type === "postpaid" ? "已复刻" : "";
  const typeClass = profile.voice_type === "preset" ? "tagPreset"
    : profile.voice_type === "prepaid" ? "tagPrepaid"
    : "tagPostpaid";

  function confirmDelete() {
    const isPostpaid = profile.voice_type === "postpaid";
    const msg = isPostpaid
      ? `确认删除音色「${profile.display_name}」？\n\n该操作仅会将音色从当前系统中移除。\n\n豆包平台中的原始音色不会被删除，\n您仍然可以在豆包控制台中继续使用该音色。`
      : `确认删除音色「${profile.display_name}」？\n\n删除后将从当前家庭空间中永久移除。\n该操作不可恢复。`;
    if (window.confirm(msg)) {
      onDelete(profile);
    }
  }

  function startRename() {
    setEditName(profile.display_name);
    setIsEditingName(true);
  }

  function submitRename() {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== profile.display_name) {
      onRename(profile, trimmed);
    }
    setIsEditingName(false);
  }

  function cancelRename() {
    setEditName(profile.display_name);
    setIsEditingName(false);
  }

  return (
    <article className="voiceCard">
      <div className="voiceCardHeader">
        <span className="voiceCardAvatar" aria-hidden="true" />
        {isEditingName ? (
          <span className="voiceNameEdit">
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") submitRename(); else if (e.key === "Escape") cancelRename(); }}
              onBlur={cancelRename}
              autoFocus
            />
            <button className="linkButton" onMouseDown={(e) => { e.preventDefault(); submitRename(); }}>保存</button>
            <button className="linkButton" onMouseDown={(e) => { e.preventDefault(); cancelRename(); }}>取消</button>
          </span>
        ) : (
          <>
            <strong>{profile.display_name}</strong>
            {canWrite ? <button className="linkButton editNameButton" onClick={startRename} title="编辑名称">✎</button> : null}
          </>
        )}
        {typeLabel ? <span className={`voiceTag ${typeClass}`}>{typeLabel}</span> : null}
      </div>
      <div className="voiceWave">
        {Array.from({ length: 34 }).map((_, index) => (
          <span key={index} style={{ height: `${10 + ((index * 7) % 26)}px` }} />
        ))}
        <button disabled={state.isLoading || profile.status !== "ready"} onClick={() => onPreview(profile)} type="button" aria-label="试听">
          <VoiceIcon name="play" />
        </button>
      </div>
      <div className="voiceCardMeta">
        <span>创建时间: {new Date().toLocaleDateString()}</span>
      </div>
      <label>
        <span>绑定 AI 角色</span>
        <select
          value={profile.persona_id ?? ""}
          disabled={!canWrite || state.isLoading}
          onChange={(event) => onBindPersona(profile, event.target.value)}
        >
          <option value="">暂不绑定，老人端自动选择</option>
          {personas.map((persona) => (
            <option key={String(persona.id ?? "")} value={String(persona.id ?? "")}>
              {String(persona.role_label ?? persona.relation ?? persona.id ?? "未命名角色")}
            </option>
          ))}
        </select>
      </label>
      <p className="helperText">
        当前绑定：{boundPersona ? String(boundPersona.role_label ?? boundPersona.id) : "未绑定"}
      </p>
      <div className="voiceCardFooter">
        <span className="speakerIdRow">
          Speaker ID{" "}
          {speakerIdExpanded ? (
            <span>{profile.provider_voice_id} <button className="linkButton" onClick={() => setSpeakerIdExpanded(false)}>[收起]</button></span>
          ) : (
            <button className="linkButton" onClick={() => setSpeakerIdExpanded(true)}>[展开]</button>
          )}
        </span>
        <button
          className="buttonSecondary"
          disabled={!canWrite || state.isLoading}
          onClick={confirmDelete}
        >
          删除音色
        </button>
      </div>
      {cloudStatus ? (
        <div className="voiceCardStatus">
          <span>豆包状态：{formatDoubaoVoiceStatus(cloudStatus.status)}</span>
          {cloudStatus.available_training_times !== undefined ? (
            <span>剩余训练次数：{cloudStatus.available_training_times}</span>
          ) : null}
        </div>
      ) : null}
      {state.error ? <p className="errorText">{state.error}</p> : null}
      <div className="actions" style={{ marginTop: 8 }}>
        <button disabled={state.isLoading} onClick={() => onQuery(profile)} type="button">
          {state.isLoading ? "查询中..." : "查询状态"}
        </button>
        <button disabled={state.isLoading || profile.status !== "ready"} onClick={() => onPreview(profile)} type="button">
          试听
        </button>
      </div>
      {profile.demo_audio_url ? (
        <audio className="voicePreviewAudio" controls src={profile.demo_audio_url}>
          当前浏览器不支持音频播放。
        </audio>
      ) : null}
    </article>
  );
}

function ImportVoice(props: {
  familyId: string;
  canWrite: boolean;
  onImported: (p: VoiceProfile) => void;
  onError: (e: string) => void;
}) {
  const { familyId, canWrite, onImported, onError } = props;
  const [importType, setImportType] = useState<"preset" | "prepaid">("preset");
  const [displayName, setDisplayName] = useState("");
  const [speakerId, setSpeakerId] = useState("");
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!displayName.trim()) return;
    if (importType === "prepaid" && !isValidPrepaidSpeakerId(speakerId.trim())) {
      onError("预付费 speaker_id 通常应为 S_ 或 icl_ 开头。");
      return;
    }
    setIsSubmitting(true);
    try {
      const profile = await cloneVoice({
        family_id: familyId,
        display_name: displayName.trim(),
        sample_ids: [],
        consent_confirmed: consentConfirmed,
        sample_source: importType === "preset" ? "preset" : "upload",
        speaker_id: importType === "prepaid" ? speakerId.trim() : "",
        voice_type: importType,
      });
      onImported(profile);
    } catch (err) {
      onError(err instanceof Error ? err.message : "导入音色失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="voiceFormPanel voiceImportPanel">
      <h2>导入已有音色</h2>
      <p className="helperText">
        如果您已经拥有豆包语音中的音色，可直接导入已有 Speaker ID，无需重新进行声音复刻。
      </p>
      <form onSubmit={handleSubmit}>
        <label>
          <span>音色类型</span>
          <select value={importType} onChange={(e) => setImportType(e.target.value as "preset" | "prepaid")}>
            <option value="preset">预置音色</option>
            <option value="prepaid">预付费 Speaker ID</option>
          </select>
        </label>
        <label>
          <span>音色名称</span>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="例如：妈妈的声音" />
        </label>
        {importType === "prepaid" ? (
          <label>
            <span>Speaker ID</span>
            <input
              value={speakerId}
              onChange={(e) => setSpeakerId(e.target.value)}
              placeholder="例如 S_example"
            />
          </label>
        ) : null}
        <label className="voiceConsent">
          <input checked={consentConfirmed} onChange={(e) => setConsentConfirmed(e.target.checked)} type="checkbox" />
          <span>我确认此声音将用于本家庭空间的语音陪伴。</span>
        </label>
        <button type="submit" disabled={!canWrite || isSubmitting || !consentConfirmed || !displayName.trim()}>
          {isSubmitting ? "添加中..." : "添加音色"}
        </button>
      </form>
    </section>
  );
}

function CreateCloneVoice(props: {
  familyId: string;
  canWrite: boolean;
  onCreated: (p: VoiceProfile) => void;
  onError: (e: string) => void;
}) {
  const { familyId, canWrite, onCreated, onError } = props;
  const [displayName, setDisplayName] = useState("我的声音");
  const [selectedAudioFile, setSelectedAudioFile] = useState<File | null>(null);
  const [speakerMode, setSpeakerMode] = useState<"custom" | "prepaid">("custom");
  const [customSpeakerId, setCustomSpeakerId] = useState("");
  const [speakerId, setSpeakerId] = useState("");
  const [demoText, setDemoText] = useState("妈，我在呢。");
  const [language, setLanguage] = useState(0);
  const [enableAudioDenoise, setEnableAudioDenoise] = useState(false);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [demoAudioUrl, setDemoAudioUrl] = useState("");
  const [paramsExpanded, setParamsExpanded] = useState(true);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedAudioFile) return;
    setIsSubmitting(true);
    try {
      if (selectedAudioFile.size > 10 * 1024 * 1024) throw new Error("声音样本不能超过 10MB。");
      const audioDataBase64 = await readFileAsBase64(selectedAudioFile);
      const audioFormat = audioFormatFromFilename(selectedAudioFile.name);
      const nextCustomSpeakerId = customSpeakerId.trim();
      const nextSpeakerId = speakerMode === "custom" ? "custom_speaker_id" : speakerId.trim();
      if (speakerMode === "custom" && !isValidCustomSpeakerId(nextCustomSpeakerId)) {
        throw new Error("后付费自定义音色 ID 必须至少 8 位，以字母开头，只能包含字母、数字、-、_，且不能以 - 或 _ 结尾。");
      }
      if (speakerMode === "prepaid" && !isValidPrepaidSpeakerId(nextSpeakerId)) {
        throw new Error("预付费 speaker_id 通常应为 S_ 或 icl_ 开头。后付费请切换到自定义音色 ID。");
      }
      const profile = await cloneVoice({
        family_id: familyId,
        display_name: displayName.trim() || "我的声音",
        sample_ids: [],
        consent_confirmed: consentConfirmed,
        sample_source: "upload",
        audio_data_base64: audioDataBase64,
        audio_format: audioFormat,
        speaker_id: nextSpeakerId,
        custom_speaker_id: speakerMode === "custom" ? nextCustomSpeakerId : "",
        language,
        demo_text: demoText.trim(),
        enable_audio_denoise: enableAudioDenoise,
        voice_type: speakerMode === "prepaid" ? "prepaid" : "postpaid",
      });
      setDemoAudioUrl(profile.demo_audio_url ?? "");
      onCreated(profile);
    } catch (err) {
      onError(err instanceof Error ? err.message : "创建复刻音色失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="voiceFormPanel voiceClonePanel">
      <h2>创建复刻音色</h2>
      <p className="warningText">后付费声音复刻可能产生额外费用，请提前查看官方计费规则。</p>
      <form onSubmit={handleSubmit}>
        <label>
          <span>音色名称</span>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <label>
          <span>音频上传</span>
          <input
            accept=".wav,.mp3,.ogg,.m4a,.aac,.pcm,audio/*"
            onChange={(e) => setSelectedAudioFile(e.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
        <p className="helperText">建议 14-30 秒、低噪声、单人单轨 wav/mp3 音频，文件不超过 10MB。</p>
        <div className="collapsibleSection">
          <button type="button" className="linkButton" onClick={() => setParamsExpanded(!paramsExpanded)}>
            {paramsExpanded ? "▼" : "▶"} 复刻参数
          </button>
          {paramsExpanded ? (
            <>
              <label>
                <span>音色创建方式</span>
                <select value={speakerMode} onChange={(e) => setSpeakerMode(e.target.value as "custom" | "prepaid")}>
                  <option value="custom">后付费自定义音色 ID</option>
                  <option value="prepaid">预付费 speaker_id</option>
                </select>
              </label>
              {speakerMode === "custom" ? (
                <label>
                  <span>后付费自定义音色 ID</span>
                  <input value={customSpeakerId} onChange={(e) => setCustomSpeakerId(e.target.value)} placeholder="例如 family_voice_001" />
                </label>
              ) : (
                <label>
                  <span>预付费 speaker_id</span>
                  <input value={speakerId} onChange={(e) => setSpeakerId(e.target.value)} placeholder="例如 S_example" />
                </label>
              )}
              <label>
                <span>试听文本</span>
                <input value={demoText} onChange={(e) => setDemoText(e.target.value)} placeholder="4-300 字，建议贴近陪伴场景" />
              </label>
              <label>
                <span>语种</span>
                <select value={language} onChange={(e) => setLanguage(Number(e.target.value))}>
                  <option value={0}>中文</option>
                  <option value={1}>英文</option>
                  <option value={2}>日语</option>
                  <option value={3}>西班牙语</option>
                  <option value={4}>印尼语</option>
                  <option value={5}>葡萄牙语</option>
                  <option value={8}>韩语</option>
                </select>
              </label>
              <label className="voiceConsent">
                <input checked={enableAudioDenoise} onChange={(e) => setEnableAudioDenoise(e.target.checked)} type="checkbox" />
                <span>样本噪声较大时启用降噪；音频质量好时建议关闭以保留相似度。</span>
              </label>
            </>
          ) : null}
        </div>
        <label className="voiceConsent">
          <input checked={consentConfirmed} onChange={(e) => setConsentConfirmed(e.target.checked)} type="checkbox" />
          <span>我确认这是我本人的声音，用于本家庭空间的语音陪伴。</span>
        </label>
        <button
          type="submit"
          disabled={!canWrite || isSubmitting || !selectedAudioFile || !consentConfirmed}
        >
          {isSubmitting ? "训练中..." : "创建复刻音色"}
        </button>
        {demoAudioUrl ? (
          <div style={{ marginTop: 12 }}>
            <p className="helperText">试听复刻效果：</p>
            <audio controls src={demoAudioUrl} style={{ width: "100%" }}>当前浏览器不支持音频播放。</audio>
          </div>
        ) : null}
      </form>
    </section>
  );
}

// ====== Utility functions (kept from original file) ======

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("读取声音文件失败"));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",", 2)[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

function audioFormatFromFilename(filename: string): string {
  const extension = filename.split(".").pop()?.toLowerCase() ?? "";
  return extension || "wav";
}

function isValidCustomSpeakerId(value: string): boolean {
  return /^[A-Za-z][A-Za-z0-9_-]{6,254}[A-Za-z0-9]$/.test(value);
}

function isValidPrepaidSpeakerId(value: string): boolean {
  return /^(S_|icl_)/i.test(value);
}

function formatDoubaoVoiceStatus(status: number | undefined): string {
  if (status === 0) return "NotFound";
  if (status === 1) return "Training";
  if (status === 2) return "Success";
  if (status === 3) return "Failed";
  if (status === 4) return "Active";
  return "Unknown";
}

function VoiceIcon({ name }: { name: string }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.9,
    viewBox: "0 0 24 24",
  };
  if (name === "brand") return <svg {...common}><path d="M4.5 13.5V9.6L12 4l7.5 5.6v3.9" /><path d="M8 14.5a4 4 0 0 1 8 0v1.8a3 3 0 0 1-3 3h-1" /><path d="M8 14.5v2.1a2 2 0 0 0 2 2" /></svg>;
  if (name === "home") return <svg {...common}><path d="M3.5 11.2 12 4.5l8.5 6.7" /><path d="M6.5 10.8v8h11v-8" /><path d="M10 18.8v-5h4v5" /></svg>;
  if (name === "family") return <svg {...common}><path d="M9 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM17 11a2.4 2.4 0 1 0 0-4.8 2.4 2.4 0 0 0 0 4.8Z" /><path d="M3.8 19a5.2 5.2 0 0 1 10.4 0M14.7 18.2a4.1 4.1 0 0 1 5.5 0" /></svg>;
  if (name === "folder") return <svg {...common}><path d="M4 7.5h6l1.5 2H20v10H4z" /></svg>;
  if (name === "history") return <svg {...common}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5v5l3.4 2" /></svg>;
  if (name === "voice") return <svg {...common}><path d="M4 13v-2M8 17V7M12 20V4M16 17V7M20 13v-2" /></svg>;
  if (name === "settings") return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="M19 12a7.8 7.8 0 0 0-.1-1.2l2-1.5-2-3.4-2.4 1a7.8 7.8 0 0 0-2-1.1L14 3h-4l-.5 2.8a7.8 7.8 0 0 0-2 1.1l-2.4-1-2 3.4 2 1.5A7.8 7.8 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.4-1a7.8 7.8 0 0 0 2 1.1L10 21h4l.5-2.8a7.8 7.8 0 0 0 2-1.1l2.4 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2Z" /></svg>;
  if (name === "speaker") return <svg {...common}><path d="M5 9v6h3l5 4V5L8 9z" /><path d="M16 9.5a4 4 0 0 1 0 5M18.5 7a7.2 7.2 0 0 1 0 10" /></svg>;
  if (name === "external") return <svg {...common}><path d="M9 5H5v14h14v-4" /><path d="M13 5h6v6M12 12l7-7" /></svg>;
  if (name === "search") return <svg {...common}><circle cx="10.5" cy="10.5" r="5.5" /><path d="m15 15 4 4" /></svg>;
  if (name === "play") return <svg {...common}><path d="m9 6 9 6-9 6z" /></svg>;
  return <svg {...common}><path d="m9 6 6 6-6 6" /></svg>;
}
