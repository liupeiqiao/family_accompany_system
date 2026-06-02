"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  CloudRecord,
  DraftObject,
  FamilyContext,
  ParsedDraft,
  createCloudFamilyProfile,
  createCloudMemory,
  createCloudPersona,
  deleteCloudElder,
  deleteCloudFamilyProfile,
  deleteCloudMemory,
  deleteCloudPersona,
  fetchCloudElder,
  fetchCloudFamilyProfiles,
  fetchCloudMemories,
  fetchCloudPersonas,
  fetchCurrentFamily,
  parseProfileText,
  saveCloudElder,
  updateCloudFamilyProfile,
  updateCloudMemory,
  updateCloudPersona,
} from "../../lib/backend-api";
import { getAuthToken } from "../../lib/auth";

const emptyDraft: ParsedDraft = {
  persona: {},
  personas: [],
  elder_profile: {},
  elder_profiles: [],
  family_profiles: [],
  memories: [],
  dedup: {},
};

const elderFields = [
  ["full_name", "姓名"],
  ["gender", "性别"],
  ["personality", "性格"],
  ["preferences", "偏好"],
  ["habits", "习惯"],
  ["health_notes", "健康备注"],
  ["speech_traits", "说话特点"],
  ["life_experiences", "人生经历"],
  ["important_memories", "重要记忆"],
  ["notes", "备注"],
] as const;

const personaFields = [
  ["role_label", "角色名"],
  ["relation", "与老人关系"],
  ["appellation", "对老人称呼"],
  ["personality", "性格"],
  ["speech_style", "说话风格"],
  ["comfort_style", "陪伴方式"],
] as const;

const familyFields = [
  ["name", "姓名"],
  ["gender", "性别"],
  ["relation", "关系"],
  ["personality", "性格"],
  ["preferences", "偏好"],
  ["habits", "习惯"],
  ["relations", "家庭关系"],
  ["notes", "备注"],
] as const;

const memoryFields = [
  ["content", "记忆内容"],
  ["memory_type", "类型"],
  ["subject", "主语"],
  ["family_members", "相关家人"],
  ["emotion_tags", "情感标签"],
  ["topic_tags", "话题标签"],
  ["intimacy_weight", "亲密权重"],
] as const;

const arrayFields = new Set([
  "personality",
  "preferences",
  "habits",
  "health_notes",
  "speech_traits",
  "life_experiences",
  "important_memories",
  "speech_style",
  "comfort_style",
  "relations",
  "family_members",
  "emotion_tags",
  "topic_tags",
]);

function cloneDraft(draft: ParsedDraft): ParsedDraft {
  return {
    persona: { ...draft.persona },
    personas: (draft.personas ?? []).map((item) => ({ ...item })),
    elder_profile: { ...draft.elder_profile },
    elder_profiles: (draft.elder_profiles ?? []).map((item) => ({ ...item })),
    family_profiles: draft.family_profiles.map((item) => ({ ...item })),
    memories: draft.memories.map((item) => ({ ...item })),
    dedup: draft.dedup ?? {},
    merge_preview: draft.merge_preview ?? [],
  };
}

function valueToText(value: unknown): string {
  if (Array.isArray(value)) return value.join("、");
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  return "";
}

function textToValue(key: string, value: string): unknown {
  if (key === "intimacy_weight") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0.5;
  }
  if (arrayFields.has(key)) {
    return value
      .split(/[、，,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return value;
}

function hasImportableValue(item: DraftObject): boolean {
  return Object.values(item).some((value) => {
    if (Array.isArray(value)) return value.length > 0;
    return value !== "" && value !== null && value !== undefined;
  });
}

function hasDraft(draft: ParsedDraft): boolean {
  return (
    hasImportableValue(draft.persona) ||
    (draft.personas ?? []).some(hasImportableValue) ||
    hasImportableValue(draft.elder_profile) ||
    (draft.elder_profiles ?? []).some(hasImportableValue) ||
    draft.family_profiles.some(hasImportableValue) ||
    draft.memories.some(hasImportableValue)
  );
}

function cloudRecordsToDraft(records: {
  elder: CloudRecord;
  personas: CloudRecord[];
  familyProfiles: CloudRecord[];
  memories: CloudRecord[];
}): ParsedDraft {
  const elderProfiles = records.elder && Object.keys(records.elder).length > 0 ? [records.elder] : [];
  return {
    persona: records.personas[0] ?? {},
    personas: records.personas,
    elder_profile: elderProfiles[0] ?? {},
    elder_profiles: elderProfiles,
    family_profiles: records.familyProfiles,
    memories: records.memories,
    dedup: {},
  };
}

function payloadWithFamily(item: DraftObject, familyId: string): CloudRecord & { family_id: string } {
  return { ...item, family_id: familyId };
}

function displayRecordName(item: DraftObject, fallback: string): string {
  return (
    valueToText(item.full_name) ||
    valueToText(item.role_label) ||
    valueToText(item.name) ||
    valueToText(item.content).slice(0, 32) ||
    fallback
  );
}

export default function RecordsPage() {
  const router = useRouter();
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [sourceText, setSourceText] = useState("");
  const [perspective, setPerspective] = useState<"family" | "elder">("family");
  const [draft, setDraft] = useState<ParsedDraft>(emptyDraft);
  const [savedDraft, setSavedDraft] = useState<ParsedDraft>(emptyDraft);
  const [isParsing, setIsParsing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingRecords, setIsLoadingRecords] = useState(true);
  const [isSavingRecords, setIsSavingRecords] = useState(false);
  const [expandedKey, setExpandedKey] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [recordsError, setRecordsError] = useState("");
  const [recordsSuccess, setRecordsSuccess] = useState("");
  const [syncPersonaToFamily, setSyncPersonaToFamily] = useState(true);
  const [importExpanded, setImportExpanded] = useState(true);
  const [managementExpanded, setManagementExpanded] = useState(true);

  useEffect(() => {
    if (!getAuthToken()) {
      router.replace("/login");
      return;
    }
    void loadSavedRecords();
  }, [router]);

  async function loadSavedRecords() {
    setIsLoadingRecords(true);
    setRecordsError("");
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      const [elder, personas, familyProfiles, memories] = await Promise.all([
        fetchCloudElder(context.family.id),
        fetchCloudPersonas(context.family.id),
        fetchCloudFamilyProfiles(context.family.id),
        fetchCloudMemories(context.family.id),
      ]);
      setSavedDraft(cloneDraft(cloudRecordsToDraft({ elder, personas, familyProfiles, memories })));
      setExpandedKey("");
    } catch (err) {
      setFamilyContext(null);
      setRecordsError(err instanceof Error ? err.message : "无法加载当前家庭空间的云端档案。");
    } finally {
      setIsLoadingRecords(false);
    }
  }

  async function onParse() {
    if (!sourceText.trim()) {
      setError("请先粘贴需要导入的家庭资料。");
      return;
    }
    if (!familyContext) {
      setError("请先创建或进入家庭空间。");
      return;
    }

    setIsParsing(true);
    setError("");
    setSuccess("");
    try {
      const parsed = await parseProfileText({
        family_id: familyContext.family.id,
        text: sourceText,
        perspective,
      });
      setDraft(parsed);
      if (!hasDraft(parsed)) {
        setError("暂时没有解析出可导入内容，请补充资料后再试。");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "智能解析失败。");
    } finally {
      setIsParsing(false);
    }
  }

  async function saveDraftToCloud(nextDraft: ParsedDraft, syncPersona: boolean) {
    if (!familyContext) throw new Error("请先创建或进入家庭空间。");
    const familyId = familyContext.family.id;
    const counts = { persona: 0, elder_profile: 0, family_profiles: 0, memories: 0 };

    const elderPayloads = nextDraft.elder_profiles?.length ? nextDraft.elder_profiles : [nextDraft.elder_profile];
    for (const elder of elderPayloads) {
      if (!hasImportableValue(elder)) continue;
      await saveCloudElder(payloadWithFamily(elder, familyId));
      counts.elder_profile += 1;
    }

    const personaPayloads = nextDraft.personas?.length ? nextDraft.personas : [nextDraft.persona];
    for (const persona of personaPayloads) {
      if (!hasImportableValue(persona)) continue;
      await createCloudPersona(payloadWithFamily(persona, familyId));
      counts.persona += 1;
    }

    // 同步：AI 角色 → 家人档案
    if (syncPersona) {
      for (const persona of personaPayloads) {
        if (!hasImportableValue(persona)) continue;
        const existingFamilyNames = new Set(
          nextDraft.family_profiles.map((fp) => valueToText(fp.name)).filter(Boolean)
        );
        const personaName = valueToText(persona.role_label) || valueToText(persona.relation);
        if (personaName && !existingFamilyNames.has(personaName)) {
          const familyFromPersona = {
            name: personaName,
            gender: valueToText(persona.gender) || "",
            relation: valueToText(persona.relation),
            personality: Array.isArray(persona.personality) ? persona.personality : [],
            preferences: [],
            habits: [],
            relations: [],
            notes: "",
          };
          await createCloudFamilyProfile(payloadWithFamily(familyFromPersona, familyId));
          counts.family_profiles += 1;
        }
      }
    }

    for (const profile of nextDraft.family_profiles) {
      if (!hasImportableValue(profile)) continue;
      await createCloudFamilyProfile(payloadWithFamily(profile, familyId));
      counts.family_profiles += 1;
    }

    for (const memory of nextDraft.memories) {
      if (!valueToText(memory.content).trim()) continue;
      await createCloudMemory(payloadWithFamily(memory, familyId));
      counts.memories += 1;
    }

    return counts;
  }

  async function onSave() {
    if (!hasDraft(draft)) {
      setError("当前没有可保存的档案或记忆。");
      return;
    }
    setIsSaving(true);
    setError("");
    setSuccess("");
    try {
      const result = await saveDraftToCloud(draft, syncPersonaToFamily);
      setSuccess(
        `已保存到云端：角色 ${result.persona} 个，老人画像 ${result.elder_profile} 个，家人档案 ${result.family_profiles} 条，记忆 ${result.memories} 条。`,
      );
      setDraft(emptyDraft);
      await loadSavedRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败，请稍后重试。");
    } finally {
      setIsSaving(false);
    }
  }

  async function onSaveRecords() {
    if (!familyContext) {
      setRecordsError("请先创建或进入家庭空间。");
      return;
    }
    const familyId = familyContext.family.id;
    setIsSavingRecords(true);
    setRecordsError("");
    setRecordsSuccess("");
    try {
      for (const elder of savedDraft.elder_profiles ?? []) {
        if (hasImportableValue(elder)) await saveCloudElder(payloadWithFamily(elder, familyId));
      }
      for (const persona of savedDraft.personas ?? []) {
        const id = valueToText(persona.id);
        if (!id || !hasImportableValue(persona)) continue;
        await updateCloudPersona(id, payloadWithFamily(persona, familyId));
      }
      for (const profile of savedDraft.family_profiles) {
        const id = valueToText(profile.id);
        if (!id || !hasImportableValue(profile)) continue;
        await updateCloudFamilyProfile(id, payloadWithFamily(profile, familyId));
      }
      for (const memory of savedDraft.memories) {
        const id = valueToText(memory.id);
        if (!id || !hasImportableValue(memory)) continue;
        await updateCloudMemory(id, payloadWithFamily(memory, familyId));
      }
      setRecordsSuccess("云端档案修改已保存。");
      await loadSavedRecords();
    } catch (err) {
      setRecordsError(err instanceof Error ? err.message : "保存修改失败，请稍后重试。");
    } finally {
      setIsSavingRecords(false);
    }
  }

  function updateTopLevel(section: "elder_profile" | "persona", key: string, value: string) {
    setDraft((current) => ({
      ...current,
      [section]: { ...current[section], [key]: textToValue(key, value) },
    }));
  }

  function updateListItem(
    target: "draft" | "saved",
    section: "personas" | "elder_profiles" | "family_profiles" | "memories",
    index: number,
    key: string,
    value: string,
  ) {
    const updater = target === "draft" ? setDraft : setSavedDraft;
    updater((current) => ({
      ...current,
      [section]: (current[section] ?? []).map((item, itemIndex) =>
        itemIndex === index ? { ...item, [key]: textToValue(key, value) } : item,
      ),
    }));
  }

  async function deleteSavedRecord(section: "elder" | "persona" | "family" | "memory", index: number) {
    if (!familyContext) return;
    const sectionLabels: Record<string, string> = { elder: "老人画像", persona: "AI 角色", family: "家人档案", memory: "家庭记忆" };
    const item = section === "elder"
      ? savedDraft.elder_profiles?.[0]
      : section === "persona"
        ? savedDraft.personas?.[index]
        : section === "family"
          ? savedDraft.family_profiles[index]
          : savedDraft.memories[index];
    const itemName = item ? displayRecordName(item, sectionLabels[section]) : sectionLabels[section];
    if (!window.confirm(`确定要删除「${itemName}」吗？\n\n删除后将无法恢复，请确认后再操作。`)) {
      return;
    }
    const familyId = familyContext.family.id;
    setRecordsError("");
    setRecordsSuccess("");
    try {
      if (section === "elder") {
        await deleteCloudElder(familyId);
      } else if (section === "persona") {
        const id = valueToText(savedDraft.personas?.[index]?.id);
        if (!id) throw new Error("这条角色缺少 id，无法删除。");
        await deleteCloudPersona(id, familyId);
      } else if (section === "family") {
        const id = valueToText(savedDraft.family_profiles[index]?.id);
        if (!id) throw new Error("这条家人档案缺少 id，无法删除。");
        await deleteCloudFamilyProfile(id, familyId);
      } else {
        const id = valueToText(savedDraft.memories[index]?.id);
        if (!id) throw new Error("这条记忆缺少 id，无法删除。");
        await deleteCloudMemory(id, familyId);
      }
      setRecordsSuccess("已删除云端记录。");
      await loadSavedRecords();
    } catch (err) {
      setRecordsError(err instanceof Error ? err.message : "删除失败，请稍后重试。");
    }
  }

  return (
    <main className="shell">
      <section className="sectionHeader">
        <h1>档案与记忆</h1>
        <p>资料会保存到当前登录用户所在的家庭空间，供老人端对话、音色绑定和后续长期记忆检索使用。</p>
        {familyContext ? <p className="helperText">当前家庭：{familyContext.family.name}</p> : null}
      </section>

      <section className="collapsible" style={{ marginBottom: 24 }}>
        <button
          className={`collapsibleHeader ${importExpanded ? "" : "collapsed"}`}
          onClick={() => setImportExpanded((v) => !v)}
          type="button"
        >
          智能导入家庭资料
        </button>
        <div className={`collapsibleBody ${importExpanded ? "" : "collapsed"}`}>
        <div className="importSource">
          <label htmlFor="sourceText">家庭资料</label>
          <div className="segmentedControl" aria-label="描述视角">
            <button className={perspective === "family" ? "segmentActive" : ""} type="button" onClick={() => setPerspective("family")}>
              家人视角
            </button>
            <button className={perspective === "elder" ? "segmentActive" : ""} type="button" onClick={() => setPerspective("elder")}>
              老人视角
            </button>
          </div>
          <textarea
            id="sourceText"
            value={sourceText}
            onChange={(event) => setSourceText(event.target.value)}
            placeholder="例如：老人叫宋桂兰，女儿小雨每周都会打电话。去年中秋，小雨陪妈妈在院子里赏月。"
          />
          <div className="actions">
            <button type="button" onClick={onParse} disabled={isParsing || !familyContext}>
              {isParsing ? "解析中..." : "智能解析"}
            </button>
            <button className="button buttonSecondary" type="button" onClick={onSave} disabled={isSaving || !hasDraft(draft)}>
              {isSaving ? "保存中..." : "保存到云端"}
            </button>
            <Link className="button buttonSecondary" href="/family">
              返回家庭空间
            </Link>
          </div>
          {error ? <p className="errorText">{error}</p> : null}
          {success ? <p className="successText">{success}</p> : null}
        </div>

        {hasDraft(draft) ? (
          <div className="previewGrid">
            <EditableObject title="老人画像" data={draft.elder_profile} fields={elderFields} onChange={(key, value) => updateTopLevel("elder_profile", key, value)} />
            <EditableObject title="AI 扮演角色" data={draft.persona} fields={personaFields} onChange={(key, value) => updateTopLevel("persona", key, value)} />
            <label className="voiceConsent" style={{ marginTop: -8, marginBottom: 8 }}>
              <input
                checked={syncPersonaToFamily}
                onChange={(e) => setSyncPersonaToFamily(e.target.checked)}
                type="checkbox"
              />
              <span>同步创建为家人档案（将角色姓名、关系、性格自动填入家人档案）</span>
            </label>
            <EditableList title="家人档案" items={draft.family_profiles} fields={familyFields} onChange={(index, key, value) => updateListItem("draft", "family_profiles", index, key, value)} />
            <EditableList title="家庭记忆" items={draft.memories} fields={memoryFields} onChange={(index, key, value) => updateListItem("draft", "memories", index, key, value)} />
          </div>
        ) : (
          <p className="emptyState">解析后会在这里显示可编辑预览。</p>
        )}
        </div>
      </section>

      <hr className="sectionDivider" data-title="已保存数据" />

      <section className="collapsible">
        <button
          className={`collapsibleHeader ${managementExpanded ? "" : "collapsed"}`}
          onClick={() => setManagementExpanded((v) => !v)}
          type="button"
        >
          已保存的云端档案与记忆
        </button>
        <div className={`collapsibleBody ${managementExpanded ? "" : "collapsed"}`}>
        <div className="sectionHeader">
          <h2>已保存的云端档案与记忆</h2>
          <p>这里展示当前家庭空间的数据。修改后点击保存，删除会同步删除云端记录。</p>
        </div>
        <div className="actions">
          <button type="button" onClick={onSaveRecords} disabled={isSavingRecords || !hasDraft(savedDraft)}>
            {isSavingRecords ? "保存中..." : "保存修改"}
          </button>
          <button className="button buttonSecondary" type="button" onClick={loadSavedRecords} disabled={isLoadingRecords}>
            {isLoadingRecords ? "加载中..." : "刷新"}
          </button>
        </div>
        {recordsError ? <p className="errorText">{recordsError}</p> : null}
        {recordsSuccess ? <p className="successText">{recordsSuccess}</p> : null}

        {isLoadingRecords ? (
          <p className="emptyState">正在加载云端档案...</p>
        ) : hasDraft(savedDraft) ? (
          <div className="previewGrid">
            <SavedList
              title="老人画像"
              section="elder"
              items={savedDraft.elder_profiles ?? []}
              fields={elderFields}
              expandedKey={expandedKey}
              setExpandedKey={setExpandedKey}
              onChange={(index, key, value) => updateListItem("saved", "elder_profiles", index, key, value)}
              onDelete={deleteSavedRecord}
            />
            <SavedList
              title="AI 扮演角色"
              section="persona"
              items={savedDraft.personas ?? []}
              fields={personaFields}
              expandedKey={expandedKey}
              setExpandedKey={setExpandedKey}
              onChange={(index, key, value) => updateListItem("saved", "personas", index, key, value)}
              onDelete={deleteSavedRecord}
            />
            <SavedList
              title="家人档案"
              section="family"
              items={savedDraft.family_profiles}
              fields={familyFields}
              expandedKey={expandedKey}
              setExpandedKey={setExpandedKey}
              onChange={(index, key, value) => updateListItem("saved", "family_profiles", index, key, value)}
              onDelete={deleteSavedRecord}
            />
            <SavedList
              title="家庭记忆"
              section="memory"
              items={savedDraft.memories}
              fields={memoryFields}
              expandedKey={expandedKey}
              setExpandedKey={setExpandedKey}
              onChange={(index, key, value) => updateListItem("saved", "memories", index, key, value)}
              onDelete={deleteSavedRecord}
            />
          </div>
        ) : (
          <p className="emptyState">暂无已保存的云端档案或记忆。</p>
        )}
        </div>
      </section>
    </main>
  );
}

function EditableObject({
  title,
  data,
  fields,
  onChange,
}: {
  title: string;
  data: DraftObject;
  fields: readonly (readonly [string, string])[];
  onChange: (key: string, value: string) => void;
}) {
  return (
    <section className="importSection">
      <h2>{title}</h2>
      <div className="fieldGrid">
        {fields.map(([key, label]) => (
          <label key={key}>
            <span>{label}</span>
            <input value={valueToText(data[key])} onChange={(event) => onChange(key, event.target.value)} />
          </label>
        ))}
      </div>
    </section>
  );
}

function EditableList({
  title,
  items,
  fields,
  onChange,
}: {
  title: string;
  items: DraftObject[];
  fields: readonly (readonly [string, string])[];
  onChange: (index: number, key: string, value: string) => void;
}) {
  return (
    <section className="importSection wide">
      <h2>{title}</h2>
      {items.length === 0 ? <p className="emptyState">暂无内容。</p> : null}
      <div className="importList">
        {items.map((item, index) => (
          <article className="importListItem" key={`${title}-${index}`}>
            <strong>{displayRecordName(item, `${title} ${index + 1}`)}</strong>
            <div className="fieldGrid">
              {fields.map(([key, label]) => (
                <label key={key}>
                  <span>{label}</span>
                  <input value={valueToText(item[key])} onChange={(event) => onChange(index, key, event.target.value)} />
                </label>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function SavedList({
  title,
  section,
  items,
  fields,
  expandedKey,
  setExpandedKey,
  onChange,
  onDelete,
}: {
  title: string;
  section: "elder" | "persona" | "family" | "memory";
  items: DraftObject[];
  fields: readonly (readonly [string, string])[];
  expandedKey: string;
  setExpandedKey: (key: string) => void;
  onChange: (index: number, key: string, value: string) => void;
  onDelete: (section: "elder" | "persona" | "family" | "memory", index: number) => void;
}) {
  return (
    <section className="importSection wide">
      <h2>{title}</h2>
      {items.length === 0 ? <p className="emptyState">暂无内容。</p> : null}
      <div className="profileList">
        {items.map((item, index) => {
          const itemKey = `${section}-${index}`;
          const isExpanded = expandedKey === itemKey;
          return (
            <article className="profileSummary" key={itemKey}>
              <div className="profileSummaryHeader">
                <strong>{displayRecordName(item, `${title} ${index + 1}`)}</strong>
                <div className="memoryActions">
                  <button className="button buttonSecondary" type="button" onClick={() => setExpandedKey(isExpanded ? "" : itemKey)}>
                    {isExpanded ? "收起" : "展开编辑"}
                  </button>
                  <button className="button buttonDanger" type="button" onClick={() => onDelete(section, index)}>
                    删除
                  </button>
                </div>
              </div>
              {isExpanded ? (
                <div className="fieldGrid profileEditor">
                  {fields.map(([key, label]) => (
                    <label key={key}>
                      <span>{label}</span>
                      <input value={valueToText(item[key])} onChange={(event) => onChange(index, key, event.target.value)} />
                    </label>
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
