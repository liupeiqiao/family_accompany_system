"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import {
  FamilyContext,
  VoiceProfile,
  VoiceStatusResponse,
  VoiceSample,
  cloneVoice,
  createVoiceUploadIntent,
  fetchCurrentFamily,
  fetchVoiceProfiles,
  fetchVoiceSamples,
  deleteVoiceProfile,
  queryVoiceStatus,
  upgradeVoice,
} from "../../lib/backend-api";

type VoiceManagementState = {
  isLoading?: boolean;
  error?: string;
  result?: VoiceStatusResponse;
};

export default function VoicesPage() {
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [samples, setSamples] = useState<VoiceSample[]>([]);
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [filename, setFilename] = useState("");
  const [displayName, setDisplayName] = useState("我的声音");
  const [sampleSource, setSampleSource] = useState<"upload" | "recording">("upload");
  const [selectedAudioFile, setSelectedAudioFile] = useState<File | null>(null);
  const [speakerMode, setSpeakerMode] = useState<"custom" | "prepaid">("custom");
  const [speakerId, setSpeakerId] = useState("");
  const [prepaidDisplayName, setPrepaidDisplayName] = useState("妈妈音色");
  const [customSpeakerId, setCustomSpeakerId] = useState("");
  const [promptText, setPromptText] = useState("");
  const [demoText, setDemoText] = useState("妈，我在呢。");
  const [language, setLanguage] = useState(0);
  const [enableAudioDenoise, setEnableAudioDenoise] = useState(false);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [postpaidCostConfirmed, setPostpaidCostConfirmed] = useState(false);
  const [selectedSampleId, setSelectedSampleId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingSample, setIsCreatingSample] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [isCreatingPreset, setIsCreatingPreset] = useState(false);
  const [presetDisplayName, setPresetDisplayName] = useState("预置音色");
  const [presetConsentConfirmed, setPresetConsentConfirmed] = useState(false);
  const [demoAudioUrl, setDemoAudioUrl] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [voiceManagement, setVoiceManagement] = useState<Record<string, VoiceManagementState>>({});

  useEffect(() => {
    void loadVoiceSpace();
  }, []);

  async function loadVoiceSpace() {
    setIsLoading(true);
    setError("");
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      const [nextSamples, nextProfiles] = await Promise.all([
        fetchVoiceSamples(context.family.id),
        fetchVoiceProfiles(context.family.id),
      ]);
      setSamples(nextSamples);
      setProfiles(nextProfiles);
      setSelectedSampleId((current) => current || nextSamples[0]?.id || "");
    } catch (err) {
      setFamilyContext(null);
      setError(err instanceof Error ? err.message : "声音空间加载失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function onCreateSample(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!familyContext || !filename.trim()) {
      return;
    }
    setIsCreatingSample(true);
    setError("");
    setMessage("");
    try {
      const sample = await createVoiceUploadIntent({
        family_id: familyContext.family.id,
        filename: filename.trim(),
        sample_source: sampleSource,
      });
      setSamples((current) => [sample, ...current]);
      setSelectedSampleId(sample.id);
      setFilename("");
      setMessage("声音样本路径已创建，当前为 pending_upload 状态。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建声音样本失败");
    } finally {
      setIsCreatingSample(false);
    }
  }

  async function onCloneVoice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!familyContext || !selectedAudioFile) {
      return;
    }
    setIsCloning(true);
    setError("");
    setMessage("");
    try {
      if (selectedAudioFile.size > 10 * 1024 * 1024) {
        throw new Error("声音样本不能超过 10MB。");
      }
      const audioDataBase64 = await readFileAsBase64(selectedAudioFile);
      const audioFormat = audioFormatFromFilename(selectedAudioFile.name);
      const nextCustomSpeakerId = customSpeakerId.trim();
      if (!isValidCustomSpeakerId(nextCustomSpeakerId)) {
        throw new Error("后付费自定义音色 ID 必须至少 8 位，以字母开头，只能包含字母、数字、-、_，且不能以 - 或 _ 结尾。");
      }
      if (!postpaidCostConfirmed) {
        throw new Error("请先确认已了解后付费音色可能产生额外成本。");
      }
      const confirmed = window.confirm(
        "后付费音色在正式激活或使用后可能产生较高费用。请确认你已了解火山引擎/豆包官方计费规则，并愿意继续创建。",
      );
      if (!confirmed) {
        return;
      }
      const profile = await cloneVoice({
        family_id: familyContext.family.id,
        display_name: displayName.trim() || "我的声音",
        sample_ids: selectedSampleId ? [selectedSampleId] : [],
        consent_confirmed: consentConfirmed,
        sample_source: sampleSource,
        audio_data_base64: audioDataBase64,
        audio_format: audioFormat,
        speaker_id: "custom_speaker_id",
        custom_speaker_id: nextCustomSpeakerId,
        prompt_text: promptText.trim(),
        language,
        demo_text: demoText.trim(),
        enable_audio_denoise: enableAudioDenoise,
      });
      setProfiles((current) => [profile, ...current]);
      setDemoAudioUrl(profile.demo_audio_url ?? "");
      setSamples((current) =>
        current.map((sample) =>
          sample.id === selectedSampleId
            ? { ...sample, status: "ready", voice_profile_id: profile.id }
            : sample,
        ),
      );
      setMessage("豆包声音复刻已创建，可用于语音回复。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建声音档案失败");
    } finally {
      setIsCloning(false);
    }
  }

  async function onCreatePrepaidSpeaker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!familyContext) {
      return;
    }
    const nextSpeakerId = speakerId.trim();
    if (!isValidPrepaidSpeakerId(nextSpeakerId)) {
      setError("预付费 Speaker ID 通常应为 S_ 或 icl_ 开头。后付费音色请切换到后付费复刻模式。");
      return;
    }
    setIsCloning(true);
    setError("");
    setMessage("");
    try {
      const profile = await cloneVoice({
        family_id: familyContext.family.id,
        display_name: prepaidDisplayName.trim() || nextSpeakerId,
        sample_ids: [],
        consent_confirmed: false,
        sample_source: "prepaid",
        speaker_id: nextSpeakerId,
      });
      setProfiles((current) => [profile, ...current]);
      setSpeakerId("");
      setPrepaidDisplayName("妈妈音色");
      setDemoAudioUrl("");
      setMessage("预付费 Speaker ID 已保存为声音档案，可用于语音回复。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存预付费 Speaker ID 失败");
    } finally {
      setIsCloning(false);
    }
  }

  async function onCreatePresetVoice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!familyContext) {
      return;
    }
    setIsCreatingPreset(true);
    setError("");
    setMessage("");
    try {
      const profile = await cloneVoice({
        family_id: familyContext.family.id,
        display_name: presetDisplayName.trim() || "预置音色",
        sample_ids: [],
        consent_confirmed: presetConsentConfirmed,
        sample_source: "preset",
      });
      setProfiles((current) => [profile, ...current]);
      setMessage("预置音色档案已创建，可用于语音回复。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建预置音色失败");
    } finally {
      setIsCreatingPreset(false);
    }
  }

  async function onQueryVoiceStatus(profile: VoiceProfile) {
    if (!familyContext) {
      return;
    }
    setVoiceManagement((current) => ({
      ...current,
      [profile.id]: { ...current[profile.id], isLoading: true, error: "" },
    }));
    try {
      const result = await queryVoiceStatus({
        family_id: familyContext.family.id,
        voice_profile_id: profile.id,
      });
      setVoiceManagement((current) => ({
        ...current,
        [profile.id]: { isLoading: false, result },
      }));
    } catch (err) {
      setVoiceManagement((current) => ({
        ...current,
        [profile.id]: {
          ...current[profile.id],
          isLoading: false,
          error: err instanceof Error ? err.message : "查询音色状态失败",
        },
      }));
    }
  }

  async function onUpgradeVoice(profile: VoiceProfile) {
    if (!familyContext) {
      return;
    }
    setVoiceManagement((current) => ({
      ...current,
      [profile.id]: { ...current[profile.id], isLoading: true, error: "" },
    }));
    try {
      const result = await upgradeVoice({
        family_id: familyContext.family.id,
        voice_profile_id: profile.id,
      });
      setVoiceManagement((current) => ({
        ...current,
        [profile.id]: { isLoading: false, result },
      }));
      setMessage("音色升级请求已完成。");
    } catch (err) {
      setVoiceManagement((current) => ({
        ...current,
        [profile.id]: {
          ...current[profile.id],
          isLoading: false,
          error: err instanceof Error ? err.message : "升级音色失败",
        },
      }));
    }
  }

  async function onHideVoiceProfile(profile: VoiceProfile) {
    if (!familyContext) {
      return;
    }
    const confirmed = window.confirm(`从本地列表隐藏音色「${profile.display_name}」？这不会删除豆包后付费音色。`);
    if (!confirmed) {
      return;
    }
    setVoiceManagement((current) => ({
      ...current,
      [profile.id]: { ...current[profile.id], isLoading: true, error: "" },
    }));
    try {
      await deleteVoiceProfile(profile.id, familyContext.family.id);
      setProfiles((current) => current.filter((item) => item.id !== profile.id));
      setMessage("音色已从本地列表隐藏，豆包后付费音色仍保留在服务端。");
    } catch (err) {
      setVoiceManagement((current) => ({
        ...current,
        [profile.id]: {
          ...current[profile.id],
          isLoading: false,
          error: err instanceof Error ? err.message : "隐藏音色失败",
        },
      }));
    }
  }

  const canWrite = familyContext?.membership.role === "owner" || familyContext?.membership.role === "editor";

  return (
    <main className="shell">
      <section className="sectionHeader">
        <h1>声音克隆</h1>
        <p>上传或录制本人的授权声音样本，调用豆包 V3 声音复刻训练接口创建可合成音色。</p>
      </section>

      <div className="actions">
        <button className="button buttonSecondary" type="button" onClick={loadVoiceSpace}>
          刷新
        </button>
        <Link className="button buttonSecondary" href="/family">家庭空间</Link>
        <Link className="button buttonSecondary" href="/">返回首页</Link>
      </div>

      {isLoading ? <p className="helperText">正在加载声音空间...</p> : null}
      {error && !familyContext ? (
        <section className="importSection">
          <h2>尚未创建家庭空间</h2>
          <p className="errorText">{error}</p>
          <Link className="button" href="/family">去创建家庭空间</Link>
        </section>
      ) : null}

      {familyContext ? (
        <div className="voiceWorkspace">
          <section className="importSection">
            <h2>{familyContext.family.name}</h2>
            <p className="helperText">成员角色：{familyContext.membership.role}</p>
            {!canWrite ? <p className="errorText">只读成员不能上传声音样本或创建声音档案。</p> : null}
          </section>

          <form className="importSection" onSubmit={onCreateSample}>
            <h2>声音样本</h2>
            <label>
              <span>文件名</span>
              <input
                value={filename}
                onChange={(event) => setFilename(event.target.value)}
                placeholder="例如 hello.wav"
              />
            </label>
            <div className="segmentedControl">
              <button
                className={sampleSource === "upload" ? "segmentActive" : ""}
                type="button"
                onClick={() => setSampleSource("upload")}
              >
                上传
              </button>
              <button
                className={sampleSource === "recording" ? "segmentActive" : ""}
                type="button"
                onClick={() => setSampleSource("recording")}
              >
                录制
              </button>
            </div>
            <div>
              <label htmlFor="prompt-text" style={{ display: "block", marginBottom: 6 }}>朗读文本</label>
              <textarea
                id="prompt-text"
                onChange={(event) => setPromptText(event.target.value)}
                placeholder="可选；如果用户按固定文本朗读，在这里填写用于 WER 校验。"
                rows={3}
                value={promptText}
              />
            </div>
            <button type="submit" disabled={!canWrite || isCreatingSample || !filename.trim()}>
              {isCreatingSample ? "上传中..." : "创建上传路径"}
            </button>
          </form>

          <form className="importSection" onSubmit={onCreatePresetVoice}>
            <h2>预置音色</h2>
            <p className="helperText">无需上传样本，直接使用豆包内置音色创建声音档案，立即体验语音回复。</p>
            <label>
              <span>声音档案名</span>
              <input
                value={presetDisplayName}
                onChange={(event) => setPresetDisplayName(event.target.value)}
              />
            </label>
            <label className="voiceConsent">
              <input
                checked={presetConsentConfirmed}
                onChange={(event) => setPresetConsentConfirmed(event.target.checked)}
                type="checkbox"
              />
              <span>我确认此声音将用于本家庭空间的语音陪伴。</span>
            </label>
            <button type="submit" disabled={!canWrite || isCreatingPreset || !presetConsentConfirmed}>
              {isCreatingPreset ? "创建中..." : "创建预置音色档案"}
            </button>
          </form>

          <form
            className="importSection"
            onSubmit={speakerMode === "prepaid" ? onCreatePrepaidSpeaker : onCloneVoice}
          >
            <h2>真实声音复刻</h2>
            <label>
              <span>音色创建方式</span>
              <select
                onChange={(event) => setSpeakerMode(event.target.value as "custom" | "prepaid")}
                value={speakerMode}
              >
                <option value="custom">后付费音色复刻</option>
                <option value="prepaid">预付费 Speaker ID</option>
              </select>
            </label>
            {speakerMode === "custom" ? (
              <>
                <p className="errorText">
                  后付费音色在正式激活或使用后可能产生较高费用。创建前请先了解火山引擎/豆包官方计费规则，确认预算和使用边界。
                </p>
                <p className="helperText">建议上传 14-30 秒、低噪声、单人、单轨 wav/mp3 音频，文件不超过 10MB。</p>
                <label>
                  <span>自定义音色名称</span>
                  <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
                </label>
                <label>
                  <span>声音文件</span>
                  <input
                    accept=".wav,.mp3,.ogg,.m4a,.aac,.pcm,audio/*"
                    onChange={(event) => setSelectedAudioFile(event.target.files?.[0] ?? null)}
                    type="file"
                  />
                </label>
                <label>
                  <span>后付费自定义音色 ID</span>
                  <input
                    onChange={(event) => setCustomSpeakerId(event.target.value)}
                    placeholder="例如 family_voice_001"
                    value={customSpeakerId}
                  />
                </label>
                <p className="helperText">
                  至少 8 位，以字母开头，只能包含字母、数字、-、_，且不能以 - 或 _ 结尾。
                  {customSpeakerId.trim() && !isValidCustomSpeakerId(customSpeakerId.trim()) ? (
                    <span className="errorText"> 当前输入不符合规则。</span>
                  ) : null}
                </p>
                <label>
                  <span>试听文本</span>
                  <input
                    onChange={(event) => setDemoText(event.target.value)}
                    placeholder="4-300 字，建议贴近陪伴场景"
                    value={demoText}
                  />
                </label>
                <label>
                  <span>语种</span>
                  <select onChange={(event) => setLanguage(Number(event.target.value))} value={language}>
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
                  <input
                    checked={enableAudioDenoise}
                    onChange={(event) => setEnableAudioDenoise(event.target.checked)}
                    type="checkbox"
                  />
                  <span>样本噪声较大时启用降噪；音频质量好时建议关闭以保留相似度。</span>
                </label>
                <label>
                  <span>关联样本记录</span>
                  <select value={selectedSampleId} onChange={(event) => setSelectedSampleId(event.target.value)}>
                    <option value="">不关联</option>
                    {samples.map((sample) => (
                      <option key={sample.id} value={sample.id}>
                        {sample.storage_path}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="voiceConsent">
                  <input
                    checked={consentConfirmed}
                    onChange={(event) => setConsentConfirmed(event.target.checked)}
                    type="checkbox"
                  />
                  <span>我确认这是我本人的声音，并用于本家庭空间的语音陪伴。</span>
                </label>
                <label className="voiceConsent">
                  <input
                    checked={postpaidCostConfirmed}
                    onChange={(event) => setPostpaidCostConfirmed(event.target.checked)}
                    type="checkbox"
                  />
                  <span>我已了解后付费音色激活或使用后可能产生额外成本，并会以火山引擎/豆包官方计费规则为准。</span>
                </label>
              </>
            ) : (
              <>
                <p className="helperText">预付费 Speaker ID 已在豆包侧购买或开通；这里仅保存系统内部配置，不上传音频，也不会创建复刻任务。</p>
                <label>
                  <span>Speaker ID</span>
                  <input
                    onChange={(event) => setSpeakerId(event.target.value)}
                    placeholder="例如 S_xxxxxxxxx"
                    value={speakerId}
                  />
                </label>
                <label>
                  <span>音色名称</span>
                  <input
                    onChange={(event) => setPrepaidDisplayName(event.target.value)}
                    placeholder="例如 妈妈音色"
                    value={prepaidDisplayName}
                  />
                </label>
                <p className="helperText">音色名称仅用于系统内部展示和管理，不会影响实际 Speaker ID。</p>
              </>
            )}
            <button
              type="submit"
              disabled={
                !canWrite ||
                isCloning ||
                (speakerMode === "custom"
                  ? !selectedAudioFile || !consentConfirmed || !postpaidCostConfirmed || !customSpeakerId.trim()
                  : !speakerId.trim() || !prepaidDisplayName.trim())
              }
            >
              {isCloning ? "处理中..." : speakerMode === "custom" ? "创建后付费复刻音色" : "保存预付费 Speaker ID"}
            </button>
            {speakerMode === "custom" && demoAudioUrl ? (
              <div style={{ marginTop: 12 }}>
                <p className="helperText">试听复刻效果：</p>
                <audio controls src={demoAudioUrl} style={{ width: "100%" }}>
                  当前浏览器不支持音频播放。
                </audio>
              </div>
            ) : null}
          </form>

          {message ? <p className="successText">{message}</p> : null}
          {error ? <p className="errorText">{error}</p> : null}

          <section className="importSection wide">
            <h2>声音状态</h2>
            <div className="voiceGrid">
              <VoiceList title="样本" emptyText="还没有声音样本" items={samples} />
              <VoiceProfileList
                canWrite={Boolean(canWrite)}
                emptyText="还没有声音档案"
                items={profiles}
                management={voiceManagement}
                onHide={onHideVoiceProfile}
                onQuery={onQueryVoiceStatus}
                onUpgrade={onUpgradeVoice}
                title="档案"
              />
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

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

function VoiceList({
  title,
  emptyText,
  items,
}: {
  title: string;
  emptyText: string;
  items: VoiceSample[];
}) {
  return (
    <div className="profileList">
      <h3>{title}</h3>
      {items.length === 0 ? <p className="emptyState">{emptyText}</p> : null}
      {items.map((item) => (
        <article className="profileSummary" key={item.id}>
          <strong>{item.storage_path}</strong>
          <div className="profileMeta">
            <span>{item.status}</span>
            <span>{item.sample_source}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function VoiceProfileList({
  title,
  emptyText,
  items,
  canWrite,
  management,
  onHide,
  onQuery,
  onUpgrade,
}: {
  title: string;
  emptyText: string;
  items: VoiceProfile[];
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  onHide: (profile: VoiceProfile) => void;
  onQuery: (profile: VoiceProfile) => void;
  onUpgrade: (profile: VoiceProfile) => void;
}) {
  return (
    <div className="profileList">
      <h3>{title}</h3>
      {items.length === 0 ? <p className="emptyState">{emptyText}</p> : null}
      {items.map((profile) => {
        const state = management[profile.id] ?? {};
        const cloudStatus = state.result?.voice_status;
        return (
          <article className="profileSummary" key={profile.id}>
            <strong>{profile.display_name}</strong>
            <div className="profileMeta">
              <span>{profile.status}</span>
              <span>{profile.provider}</span>
              <span>{profile.provider_voice_id}</span>
              {profile.sample_source ? <span>{profile.sample_source}</span> : null}
            </div>
            <div className="actions">
              <button disabled={state.isLoading} onClick={() => onQuery(profile)} type="button">
                {state.isLoading ? "查询中..." : "查询状态"}
              </button>
              <button disabled={!canWrite || state.isLoading} onClick={() => onUpgrade(profile)} type="button">
                升级统一管理
              </button>
              <button
                className="buttonSecondary"
                disabled={!canWrite || state.isLoading}
                onClick={() => onHide(profile)}
                type="button"
              >
                本地隐藏
              </button>
            </div>
            {cloudStatus ? (
              <div className="profileMeta">
                <span>豆包状态：{formatDoubaoVoiceStatus(cloudStatus.status)}</span>
                {cloudStatus.available_training_times !== undefined ? (
                  <span>剩余训练次数：{cloudStatus.available_training_times}</span>
                ) : null}
                {(cloudStatus.speaker_status ?? []).map((item, index) => (
                  <span key={`${profile.id}-model-${index}`}>
                    model_type {item.model_type ?? "-"}
                    {item.demo_audio ? " · 有试听音频" : ""}
                  </span>
                ))}
              </div>
            ) : null}
            {state.error ? <p className="errorText">{state.error}</p> : null}
          </article>
        );
      })}
    </div>
  );
}

function formatDoubaoVoiceStatus(status: number | undefined): string {
  if (status === 0) {
    return "NotFound";
  }
  if (status === 1) {
    return "Training";
  }
  if (status === 2) {
    return "Success";
  }
  if (status === 3) {
    return "Failed";
  }
  if (status === 4) {
    return "Active";
  }
  return "Unknown";
}
