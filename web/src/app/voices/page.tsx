"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import {
  FamilyContext,
  VoiceProfile,
  VoiceSample,
  cloneVoice,
  createVoiceUploadIntent,
  fetchCurrentFamily,
  fetchVoiceProfiles,
  fetchVoiceSamples,
} from "../../lib/backend-api";

export default function VoicesPage() {
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [samples, setSamples] = useState<VoiceSample[]>([]);
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [filename, setFilename] = useState("");
  const [displayName, setDisplayName] = useState("我的声音");
  const [sampleSource, setSampleSource] = useState<"upload" | "recording">("upload");
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [selectedSampleId, setSelectedSampleId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingSample, setIsCreatingSample] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [isCreatingPreset, setIsCreatingPreset] = useState(false);
  const [presetDisplayName, setPresetDisplayName] = useState("预置音色");
  const [presetConsentConfirmed, setPresetConsentConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

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
    if (!familyContext || !selectedSampleId) {
      return;
    }
    setIsCloning(true);
    setError("");
    setMessage("");
    try {
      const profile = await cloneVoice({
        family_id: familyContext.family.id,
        display_name: displayName.trim() || "我的声音",
        sample_ids: [selectedSampleId],
        consent_confirmed: consentConfirmed,
        sample_source: sampleSource,
      });
      setProfiles((current) => [profile, ...current]);
      setSamples((current) =>
        current.map((sample) =>
          sample.id === selectedSampleId
            ? { ...sample, status: "ready", voice_profile_id: profile.id }
            : sample,
        ),
      );
      setMessage("Mock 声音档案已创建，可用于后续语音回复接入。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建声音档案失败");
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

  const canWrite = familyContext?.membership.role === "owner" || familyContext?.membership.role === "editor";

  return (
    <main className="shell">
      <section className="sectionHeader">
        <h1>声音克隆</h1>
        <p>上传或录制本人的授权声音样本，先用 mock provider 跑通声音档案流程。</p>
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

          <form className="importSection" onSubmit={onCloneVoice}>
            <h2>Mock 克隆</h2>
            <label>
              <span>声音档案名</span>
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </label>
            <label>
              <span>选择样本</span>
              <select value={selectedSampleId} onChange={(event) => setSelectedSampleId(event.target.value)}>
                <option value="">请选择样本</option>
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
            <button type="submit" disabled={!canWrite || isCloning || !selectedSampleId}>
              {isCloning ? "生成中..." : "创建 mock 声音档案"}
            </button>
          </form>

          {message ? <p className="successText">{message}</p> : null}
          {error ? <p className="errorText">{error}</p> : null}

          <section className="importSection wide">
            <h2>声音状态</h2>
            <div className="voiceGrid">
              <VoiceList title="样本" emptyText="还没有声音样本" items={samples} />
              <VoiceList title="档案" emptyText="还没有声音档案" items={profiles} />
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function VoiceList({
  title,
  emptyText,
  items,
}: {
  title: string;
  emptyText: string;
  items: (VoiceSample | VoiceProfile)[];
}) {
  return (
    <div className="profileList">
      <h3>{title}</h3>
      {items.length === 0 ? <p className="emptyState">{emptyText}</p> : null}
      {items.map((item) => (
        <article className="profileSummary" key={item.id}>
          <strong>{String("storage_path" in item ? item.storage_path : item.display_name)}</strong>
          <div className="profileMeta">
            <span>{item.status}</span>
            {"provider" in item ? <span>{String(item.provider)}</span> : null}
            {"sample_source" in item ? <span>{String(item.sample_source)}</span> : null}
          </div>
        </article>
      ))}
    </div>
  );
}
