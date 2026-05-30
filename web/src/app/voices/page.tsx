"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  FamilyContext,
  VoiceProfile,
  VoiceStatusResponse,
  cloneVoice,
  fetchCurrentFamily,
  fetchVoiceProfiles,
  deleteVoiceProfile,
  queryVoiceStatus,
  upgradeVoice,
} from "../../lib/backend-api";

type NavTab = "library" | "import" | "clone";
type VoiceManagementState = { isLoading?: boolean; error?: string; result?: VoiceStatusResponse };

export default function VoicesPage() {
  const [activeTab, setActiveTab] = useState<NavTab>("library");
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [voiceManagement, setVoiceManagement] = useState<Record<string, VoiceManagementState>>({});

  useEffect(() => { void loadVoiceSpace(); }, []);

  async function loadVoiceSpace() {
    setIsLoading(true);
    setError("");
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      const nextProfiles = await fetchVoiceProfiles(context.family.id);
      setProfiles(nextProfiles);
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

  async function handleUpgrade(profile: VoiceProfile) {
    if (!familyContext) return;
    setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true } }));
    try {
      const result = await upgradeVoice({
        family_id: familyContext.family.id,
        voice_profile_id: profile.id,
      });
      setVoiceManagement((c) => ({ ...c, [profile.id]: { isLoading: false, result } }));
      setMessage("音色升级请求已完成。");
    } catch (err) {
      setVoiceManagement((c) => ({
        ...c, [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "升级失败" },
      }));
    }
  }

  const canWrite = familyContext?.membership.role === "owner" || familyContext?.membership.role === "editor";

  return (
    <main className="shell">
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
              canWrite={Boolean(canWrite)}
              management={voiceManagement}
              message={message}
              onDelete={handleDelete}
              onQuery={handleQuery}
              onUpgrade={handleUpgrade}
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
    </main>
  );
}

// ====== Sub-components (stubs to be filled in later tasks) ======

function DoubaoBanner() {
  return (
    <div className="doubaoBanner">
      <span>使用豆包语音进行声音复刻与音色管理。</span>
      <a className="button buttonSecondary" href="https://console.volcengine.com/speech/new/voices?ResourceID=volc.seedicl.default&projectName=default" target="_blank" rel="noopener noreferrer">
        打开豆包语音控制台
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
      <h3>音色管理</h3>
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
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  message: string;
  onDelete: (profile: VoiceProfile) => void;
  onQuery: (profile: VoiceProfile) => void;
  onUpgrade: (profile: VoiceProfile) => void;
}) {
  const { profiles, canWrite, management, message, onDelete, onQuery, onUpgrade } = props;
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const filtered = profiles.filter((p) => {
    if (search && !p.display_name.toLowerCase().includes(search.toLowerCase())) return false;
    if (typeFilter !== "all" && p.voice_type !== typeFilter) return false;
    return true;
  });

  return (
    <section className="importSection wide">
      <h2>家人音色库</h2>
      <div className="toolbar">
        <input
          placeholder="搜索音色名称..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="all">全部</option>
          <option value="preset">预置音色</option>
          <option value="prepaid">已导入</option>
          <option value="postpaid">已复刻</option>
        </select>
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
              canWrite={canWrite}
              management={management}
              onDelete={onDelete}
              onQuery={onQuery}
              onUpgrade={onUpgrade}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function VoiceCard(props: {
  profile: VoiceProfile;
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  onDelete: (profile: VoiceProfile) => void;
  onQuery: (profile: VoiceProfile) => void;
  onUpgrade: (profile: VoiceProfile) => void;
}) {
  const { profile, canWrite, management, onDelete, onQuery, onUpgrade } = props;
  const [speakerIdExpanded, setSpeakerIdExpanded] = useState(false);
  const state = management[profile.id] ?? {};
  const cloudStatus = state.result?.voice_status;

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

  return (
    <article className="voiceCard">
      <div className="voiceCardHeader">
        <strong>{profile.display_name}</strong>
        {typeLabel ? <span className={`voiceTag ${typeClass}`}>{typeLabel}</span> : null}
      </div>
      <div className="voiceCardMeta">
        <span>创建时间: {new Date().toLocaleDateString()}</span>
      </div>
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
        <button disabled={!canWrite || state.isLoading} onClick={() => onUpgrade(profile)} type="button">
          升级统一管理
        </button>
      </div>
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
    <section className="importSection">
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
    <section className="importSection">
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
