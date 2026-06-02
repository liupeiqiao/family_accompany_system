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

type SavedSection = "elder" | "persona" | "family" | "memory";

const savedSectionMeta: Record<SavedSection, {
  title: string;
  description: string;
  icon: string;
  tone: string;
}> = {
  elder: {
    title: "老人画像",
    description: "关于老人的性格、习惯、健康状况等关键信息",
    icon: "person",
    tone: "warm",
  },
  persona: {
    title: "AI 扮演角色",
    description: "AI 在聊天中扮演的家人角色及沟通风格",
    icon: "smile",
    tone: "green",
  },
  family: {
    title: "家人档案",
    description: "家庭成员的基本信息、性格特点与关系",
    icon: "group",
    tone: "blue",
  },
  memory: {
    title: "家庭记忆",
    description: "家庭中重要的事件、经历与温暖回忆",
    icon: "notebook",
    tone: "orange",
  },
};

function sectionItems(section: SavedSection, draft: ParsedDraft): DraftObject[] {
  if (section === "elder") return draft.elder_profiles ?? [];
  if (section === "persona") return draft.personas ?? [];
  if (section === "family") return draft.family_profiles;
  return draft.memories;
}

function sectionFields(section: SavedSection) {
  if (section === "elder") return elderFields;
  if (section === "persona") return personaFields;
  if (section === "family") return familyFields;
  return memoryFields;
}

function listSectionName(section: SavedSection): "elder_profiles" | "personas" | "family_profiles" | "memories" {
  if (section === "elder") return "elder_profiles";
  if (section === "persona") return "personas";
  if (section === "family") return "family_profiles";
  return "memories";
}

function countItems(items: DraftObject[]): number {
  return items.filter(hasImportableValue).length;
}

function firstTag(item: DraftObject, keys: string[]): string {
  for (const key of keys) {
    const value = item[key];
    if (Array.isArray(value) && value.length > 0) return valueToText(value[0]);
    const text = valueToText(value);
    if (text) return text;
  }
  return "";
}

function recordTags(section: SavedSection, item: DraftObject): string[] {
  const candidates = section === "elder"
    ? [firstTag(item, ["health_notes"]), firstTag(item, ["preferences"])]
    : section === "persona"
      ? [firstTag(item, ["relation"]), firstTag(item, ["appellation"])]
      : section === "family"
        ? [firstTag(item, ["relation"]), firstTag(item, ["personality"])]
        : [firstTag(item, ["memory_type"]), firstTag(item, ["topic_tags"]), firstTag(item, ["emotion_tags"])];
  return candidates.filter(Boolean).slice(0, 2);
}

function recordSummary(section: SavedSection, item: DraftObject): string {
  if (section === "memory") return valueToText(item.content) || "暂未填写记忆内容";
  if (section === "elder") return valueToText(item.notes) || firstTag(item, ["personality", "habits", "health_notes"]) || "暂未填写摘要";
  if (section === "persona") return valueToText(item.comfort_style) || valueToText(item.speech_style) || "暂未填写沟通风格";
  return valueToText(item.notes) || firstTag(item, ["relations", "preferences", "habits"]) || "暂未填写档案摘要";
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

  const savedSections: SavedSection[] = ["elder", "persona", "family", "memory"];
  const totalCounts = {
    elder: countItems(sectionItems("elder", savedDraft)),
    persona: countItems(sectionItems("persona", savedDraft)),
    family: countItems(sectionItems("family", savedDraft)),
    memory: countItems(sectionItems("memory", savedDraft)),
  };

  return (
    <main className="recordsApp">
      <RecordsSidebar />
      <section className="recordsMain">
        <header className="recordsHeader">
          <div>
            <h1>档案与记忆</h1>
            <p>当前家庭空间的资料与记忆库</p>
            {familyContext ? <span className="recordsFamilyTag">当前家庭：{familyContext.family.name}</span> : null}
          </div>
          <div className="recordsHeaderActions">
            <button className="recordsButton recordsButtonGhost" type="button" onClick={loadSavedRecords} disabled={isLoadingRecords}>
              <span aria-hidden="true">↻</span>
              {isLoadingRecords ? "加载中" : "刷新"}
            </button>
            <button className="recordsButton recordsButtonPrimary" type="button" onClick={onSaveRecords} disabled={isSavingRecords || !hasDraft(savedDraft)}>
              <span aria-hidden="true">▣</span>
              {isSavingRecords ? "保存中" : "保存修改"}
            </button>
          </div>
        </header>

        <section className="recordsStats" aria-label="档案统计">
          <RecordsStat title="老人画像" value={totalCounts.elder} unit="条" icon="person" tone="warm" />
          <RecordsStat title="AI 角色" value={totalCounts.persona} unit="个" icon="smile" tone="green" />
          <RecordsStat title="家人档案" value={totalCounts.family} unit="条" icon="group" tone="blue" />
          <RecordsStat title="家庭记忆" value={totalCounts.memory} unit="条" icon="notebook" tone="orange" />
        </section>

        <div className="recordsWorkspace">
          <section className="recordsLibrary">
            <div className="recordsSectionHeading">
              <h2>已保存的云端档案与记忆</h2>
              <p>修改后点击保存，删除会同步删除云端记录。</p>
            </div>
            {recordsError ? <p className="errorText">{recordsError}</p> : null}
            {recordsSuccess ? <p className="successText">{recordsSuccess}</p> : null}

            {isLoadingRecords ? (
              <p className="recordsEmpty">正在加载云端档案...</p>
            ) : hasDraft(savedDraft) ? (
              <div className="recordsSavedGroups">
                {savedSections.map((section) => (
                  <SavedGroup
                    key={section}
                    section={section}
                    items={sectionItems(section, savedDraft)}
                    fields={sectionFields(section)}
                    expandedKey={expandedKey}
                    setExpandedKey={setExpandedKey}
                    onChange={(index, key, value) => updateListItem("saved", listSectionName(section), index, key, value)}
                    onDelete={deleteSavedRecord}
                  />
                ))}
              </div>
            ) : (
              <p className="recordsEmpty">暂无已保存的云端档案或记忆。</p>
            )}
          </section>

          <aside className="recordsImportPanel">
            <div className="recordsPanelTitle">
              <h2>智能导入家庭资料</h2>
              <span aria-hidden="true">⌃</span>
            </div>
            <p>粘贴或输入家人的文字资料，AI 将自动解析整理。</p>
            <label className="recordsTextareaLabel" htmlFor="sourceText">
              <textarea
                id="sourceText"
                value={sourceText}
                maxLength={2000}
                onChange={(event) => setSourceText(event.target.value)}
                placeholder="请输入或粘贴家庭资料..."
              />
              <span>{sourceText.length} / 2000</span>
            </label>
            <div className="recordsPerspective">
              <span>选择视角</span>
              <div className="recordsSegmented" aria-label="描述视角">
                <button className={perspective === "family" ? "active" : ""} type="button" onClick={() => setPerspective("family")}>
                  家人视角
                </button>
                <button className={perspective === "elder" ? "active" : ""} type="button" onClick={() => setPerspective("elder")}>
                  老人视角
                </button>
              </div>
            </div>
            <label className="recordsCheckbox">
              <input
                checked={syncPersonaToFamily}
                onChange={(e) => setSyncPersonaToFamily(e.target.checked)}
                type="checkbox"
              />
              <span>同步创建为家人档案</span>
            </label>
            <button className="recordsButton recordsButtonPrimary recordsParseButton" type="button" onClick={onParse} disabled={isParsing || !familyContext}>
              {isParsing ? "解析中..." : "✦ 智能解析"}
            </button>
            <button className="recordsButton recordsButtonGhost recordsSaveDraftButton" type="button" onClick={onSave} disabled={isSaving || !hasDraft(draft)}>
              {isSaving ? "保存中..." : "保存到云端"}
            </button>
            <Link className="recordsBackLink" href="/family">
              返回家庭空间
            </Link>
            {error ? <p className="errorText">{error}</p> : null}
            {success ? <p className="successText">{success}</p> : null}

            {hasDraft(draft) ? (
              <section className="recordsDraftPreview">
                <h3>解析预览</h3>
                <EditableObject title="老人画像" data={draft.elder_profile} fields={elderFields} onChange={(key, value) => updateTopLevel("elder_profile", key, value)} />
                <EditableObject title="AI 扮演角色" data={draft.persona} fields={personaFields} onChange={(key, value) => updateTopLevel("persona", key, value)} />
                <EditableList title="家人档案" items={draft.family_profiles} fields={familyFields} onChange={(index, key, value) => updateListItem("draft", "family_profiles", index, key, value)} />
                <EditableList title="家庭记忆" items={draft.memories} fields={memoryFields} onChange={(index, key, value) => updateListItem("draft", "memories", index, key, value)} />
              </section>
            ) : (
              <p className="recordsImportHint">解析后可在页面查看与编辑</p>
            )}
          </aside>
        </div>
      </section>
    </main>
  );
}

function RecordsSidebar() {
  const navItems = [
    { href: "/", label: "首页", icon: "home" },
    { href: "/family", label: "家庭空间", icon: "house" },
    { href: "/records", label: "档案与记忆", icon: "archive" },
    { href: "/history", label: "对话历史", icon: "chat" },
    { href: "/voices", label: "音色管理", icon: "person" },
    { href: "/family", label: "系统设置", icon: "settings" },
  ];

  return (
    <aside className="recordsSidebar">
      <div className="recordsBrand">
        <RecordsIcon name="brand" />
        <strong>亲情陪伴系统</strong>
      </div>
      <nav className="recordsNav" aria-label="档案与记忆导航">
        {navItems.map((item) => (
          <Link
            className={item.href === "/records" ? "recordsNavItem active" : "recordsNavItem"}
            href={item.href}
            key={`${item.href}-${item.label}`}
          >
            <RecordsIcon name={item.icon} />
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
      <div className="recordsUser">
        <span className="recordsAvatar" aria-hidden="true" />
        <span>
          <strong>小美</strong>
          <small>管理员</small>
        </span>
        <RecordsIcon name="settings" />
      </div>
    </aside>
  );
}

function RecordsStat({
  title,
  value,
  unit,
  icon,
  tone,
}: {
  title: string;
  value: number;
  unit: string;
  icon: string;
  tone: string;
}) {
  return (
    <article className="recordsStat">
      <span className={`recordsIconBubble ${tone}`}>
        <RecordsIcon name={icon} />
      </span>
      <div>
        <span>{title}</span>
        <strong>
          {value}
          <small>{unit}</small>
        </strong>
      </div>
    </article>
  );
}

function SavedGroup({
  section,
  items,
  fields,
  expandedKey,
  setExpandedKey,
  onChange,
  onDelete,
}: {
  section: SavedSection;
  items: DraftObject[];
  fields: readonly (readonly [string, string])[];
  expandedKey: string;
  setExpandedKey: (key: string) => void;
  onChange: (index: number, key: string, value: string) => void;
  onDelete: (section: SavedSection, index: number) => void;
}) {
  const meta = savedSectionMeta[section];
  return (
    <section className="recordsSavedGroup">
      <div className="recordsSavedIntro">
        <span className={`recordsIconBubble ${meta.tone}`}>
          <RecordsIcon name={meta.icon} />
        </span>
        <div>
          <h3>{meta.title}</h3>
          <p>{meta.description}</p>
        </div>
      </div>
      <div className="recordsSavedList">
        {items.length === 0 ? <p className="recordsEmpty compact">暂无内容</p> : null}
        {items.map((item, index) => {
          const itemKey = `${section}-${index}`;
          const isExpanded = expandedKey === itemKey;
          const tags = recordTags(section, item);
          return (
            <article className="recordsSavedItem" key={itemKey}>
              <div className="recordsItemContent">
                <span className={`recordsDot ${meta.tone}`} aria-hidden="true" />
                <div>
                  <strong>{displayRecordName(item, `${meta.title} ${index + 1}`)}</strong>
                  <p>{recordSummary(section, item)}</p>
                  {tags.length > 0 ? (
                    <div className="recordsTags">
                      {tags.map((tag) => <span key={tag}>{tag}</span>)}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="recordsItemActions">
                <button className="recordsMiniButton" type="button" onClick={() => setExpandedKey(isExpanded ? "" : itemKey)}>
                  {isExpanded ? "收起" : "展开编辑"}
                </button>
                <button className="recordsMiniButton danger" type="button" onClick={() => onDelete(section, index)}>
                  删除
                </button>
              </div>
              {isExpanded ? (
                <div className="fieldGrid recordsInlineEditor">
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

function RecordsIcon({ name }: { name: string }) {
  if (name === "brand") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M4 10.7 12 4l8 6.7v7.1a2.2 2.2 0 0 1-2.2 2.2h-3.1v-5.5H9.3V20H6.2A2.2 2.2 0 0 1 4 17.8z" />
        <path d="M9.3 20v-5.5h5.4V20" />
      </svg>
    );
  }
  const paths: Record<string, string[]> = {
    home: ["M4 11.5 12 5l8 6.5V20H6v-8.5", "M10 20v-5h4v5"],
    house: ["M4 11.5 12 5l8 6.5V20H6v-8.5", "M8 20v-7h8v7"],
    archive: ["M5 6h14v14H5z", "M8 4h8", "M9 11h6", "M12 8v6"],
    chat: ["M5 6h14v10H9l-4 4z"],
    person: ["M12 12a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z", "M5.5 20a6.5 6.5 0 0 1 13 0"],
    settings: ["M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z", "M12 3v3M12 18v3M4.2 7.5l2.6 1.5M17.2 15l2.6 1.5M4.2 16.5 6.8 15M17.2 9l2.6-1.5"],
    smile: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M8.5 10h.01M15.5 10h.01", "M8.8 14a4.2 4.2 0 0 0 6.4 0"],
    group: ["M9 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6z", "M17 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z", "M3.8 20a5.2 5.2 0 0 1 10.4 0", "M13.5 19a4.5 4.5 0 0 1 6.7 0"],
    notebook: ["M6 4h11a2 2 0 0 1 2 2v14H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z", "M8 4v16", "M11 8h5M11 12h5M11 16h4"],
  };

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      {(paths[name] ?? paths.archive).map((d) => (
        <path d={d} key={d} />
      ))}
    </svg>
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
