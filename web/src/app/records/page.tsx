"use client";

import Link from "next/link";
import { useState } from "react";

import {
  ParsedDraft,
  importParsedData,
  parseProfileText,
} from "../../lib/backend-api";

type DraftObject = Record<string, unknown>;

const emptyDraft: ParsedDraft = {
  persona: {},
  elder_profile: {},
  family_profiles: [],
  memories: [],
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

function valueToText(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join("，");
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (typeof value === "string") {
    return value;
  }
  return "";
}

function textToValue(key: string, value: string): unknown {
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

  if (key === "intimacy_weight") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0.5;
  }

  if (arrayFields.has(key)) {
    return value
      .split(/[，,]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  return value;
}

function hasDraft(draft: ParsedDraft): boolean {
  return (
    Object.keys(draft.persona).length > 0 ||
    Object.keys(draft.elder_profile).length > 0 ||
    draft.family_profiles.length > 0 ||
    draft.memories.length > 0
  );
}

export default function RecordsPage() {
  const [sourceText, setSourceText] = useState("");
  const [draft, setDraft] = useState<ParsedDraft>(emptyDraft);
  const [isParsing, setIsParsing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function onParse() {
    if (!sourceText.trim()) {
      setError("请先粘贴需要导入的家庭资料。");
      return;
    }

    setIsParsing(true);
    setError("");
    setSuccess("");

    try {
      const parsed = await parseProfileText({
        family_id: "local",
        text: sourceText,
        perspective: "family",
      });
      setDraft(parsed);
      if (!hasDraft(parsed)) {
        setError("暂时没有解析出可导入内容，请补充资料后再试。");
      }
    } catch {
      setError("连不上后端服务，请确认 API 服务已启动。");
    } finally {
      setIsParsing(false);
    }
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
      const result = await importParsedData({
        family_id: "local",
        ...draft,
      });
      setSuccess(
        `已保存：角色 ${result.imported.persona} 个，老人画像 ${result.imported.elder_profile} 个，家人档案 ${result.imported.family_profiles} 条，记忆 ${result.imported.memories} 条。`,
      );
    } catch {
      setError("保存失败，请稍后重试。");
    } finally {
      setIsSaving(false);
    }
  }

  function updateTopLevel(section: "elder_profile" | "persona", key: string, value: string) {
    setDraft((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [key]: textToValue(key, value),
      },
    }));
  }

  function updateListItem(
    section: "family_profiles" | "memories",
    index: number,
    key: string,
    value: string,
  ) {
    setDraft((current) => ({
      ...current,
      [section]: current[section].map((item, itemIndex) =>
        itemIndex === index ? { ...item, [key]: textToValue(key, value) } : item,
      ),
    }));
  }

  function deleteFamilyProfile(index: number) {
    setDraft((current) => ({
      ...current,
      family_profiles: current.family_profiles.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  function deleteMemory(index: number) {
    setDraft((current) => ({
      ...current,
      memories: current.memories.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  return (
    <main className="shell">
      <section className="sectionHeader">
        <h1>档案与记忆</h1>
        <p>粘贴家庭资料，先智能解析，再编辑确认并保存到本地档案库。</p>
      </section>

      <section className="importWorkspace">
        <div className="importSource">
          <label htmlFor="sourceText">家庭资料</label>
          <textarea
            id="sourceText"
            value={sourceText}
            onChange={(event) => setSourceText(event.target.value)}
            placeholder="例如：老人叫宋桂兰，儿子小明每周末来看她。去年中秋，小明陪妈妈在院子里赏月。"
          />
          <div className="actions">
            <button type="button" onClick={onParse} disabled={isParsing}>
              {isParsing ? "解析中..." : "智能解析"}
            </button>
            <button
              className="button buttonSecondary"
              type="button"
              onClick={onSave}
              disabled={isSaving || !hasDraft(draft)}
            >
              {isSaving ? "保存中..." : "一键保存"}
            </button>
            <Link className="button buttonSecondary" href="/">
              返回首页
            </Link>
          </div>
          {error ? <p className="errorText">{error}</p> : null}
          {success ? <p className="successText">{success}</p> : null}
        </div>

        {hasDraft(draft) ? (
          <div className="previewGrid">
            <EditableObject
              title="老人画像"
              data={draft.elder_profile}
              fields={elderFields}
              onChange={(key, value) => updateTopLevel("elder_profile", key, value)}
            />
            <EditableObject
              title="AI 扮演角色"
              data={draft.persona}
              fields={personaFields}
              onChange={(key, value) => updateTopLevel("persona", key, value)}
            />
            <EditableList
              title="家人档案"
              items={draft.family_profiles}
              fields={familyFields}
              onChange={(index, key, value) =>
                updateListItem("family_profiles", index, key, value)
              }
              onDelete={deleteFamilyProfile}
            />
            <EditableList
              title="家庭记忆"
              items={draft.memories}
              fields={memoryFields}
              onChange={(index, key, value) => updateListItem("memories", index, key, value)}
              onDelete={deleteMemory}
            />
          </div>
        ) : (
          <p className="emptyState">解析后会在这里显示可编辑预览。</p>
        )}
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
            <input
              value={valueToText(data[key])}
              onChange={(event) => onChange(key, event.target.value)}
            />
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
  onDelete,
}: {
  title: string;
  items: DraftObject[];
  fields: readonly (readonly [string, string])[];
  onChange: (index: number, key: string, value: string) => void;
  onDelete: (index: number) => void;
}) {
  return (
    <section className="importSection wide">
      <h2>{title}</h2>
      {items.length === 0 ? <p className="emptyState">暂无内容。</p> : null}
      <div className="importList">
        {items.map((item, index) => (
          <article className="importListItem" key={`${title}-${index}`}>
            <div className="itemHeader">
              <strong>{title} {index + 1}</strong>
              <button className="button buttonDanger" type="button" onClick={() => onDelete(index)}>
                删除
              </button>
            </div>
            <div className="fieldGrid">
              {fields.map(([key, label]) => (
                <label key={key}>
                  <span>{label}</span>
                  <input
                    value={valueToText(item[key])}
                    onChange={(event) => onChange(index, key, event.target.value)}
                  />
                </label>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
