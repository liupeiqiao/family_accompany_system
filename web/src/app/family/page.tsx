"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { FamilyContext, createFamily, fetchCurrentFamily } from "../../lib/backend-api";
import { getAuthToken } from "../../lib/auth";
import { fetchCloudElder, fetchCloudPersonas, fetchCloudMemories, fetchVoiceProfiles } from "../../lib/backend-api";

function roleLabel(role?: string): string {
  if (role === "owner") {
    return "所有者";
  }
  if (role === "editor") {
    return "可编辑成员";
  }
  if (role === "viewer") {
    return "只读成员";
  }
  return "未加入";
}

const nextSteps = [
  {
    title: "完善档案与记忆",
    body: "录入老人画像、AI 角色、家人档案和家庭记忆。",
    href: "/records",
  },
  {
    title: "管理家人音色",
    body: "导入或创建音色，并绑定到对应的 AI 角色。",
    href: "/voices",
  },
  {
    title: "查看对话历史",
    body: "查看文字记录、重播 AI 回复，并把重要内容保存为记忆。",
    href: "/history",
  },
  {
    title: "进入老人端",
    body: "打开电话式语音陪伴界面，开始连续语音对话。",
    href: "/elder",
  },
];

export default function FamilyPage() {
  const router = useRouter();
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [familyName, setFamilyName] = useState("我的家庭");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [completion, setCompletion] = useState<{ elder: boolean; persona: boolean; memory: boolean; voice: boolean } | null>(null);

  async function loadFamily() {
    setIsLoading(true);
    setError("");
    setSuccess("");

    try {
      const current = await fetchCurrentFamily();
      setFamilyContext(current);
      setFamilyName(current.family.name || "我的家庭");
      try {
        const [elder, personas, memories, voices] = await Promise.all([
          fetchCloudElder(current.family.id),
          fetchCloudPersonas(current.family.id),
          fetchCloudMemories(current.family.id),
          fetchVoiceProfiles(current.family.id),
        ]);
        setCompletion({
          elder: !!(elder && (elder.full_name || elder.id)),
          persona: Array.isArray(personas) && personas.length > 0,
          memory: Array.isArray(memories) && memories.length > 0,
          voice: Array.isArray(voices) && voices.length > 0,
        });
      } catch {
        setCompletion(null);
      }
    } catch {
      setFamilyContext(null);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!getAuthToken()) {
      router.replace("/login");
      return;
    }
    void loadFamily();
  }, [router]);

  async function onCreateFamily() {
    if (!familyName.trim()) {
      setError("请填写家庭空间名称。");
      return;
    }

    setIsCreating(true);
    setError("");
    setSuccess("");

    try {
      const created = await createFamily({ name: familyName.trim() });
      setFamilyContext(created);
      setSuccess("家庭空间已创建。");
    } catch {
      setError("创建家庭空间失败，请稍后重试。");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="shell">
      <section className="sectionHeader">
        <h1>家庭空间</h1>
        <p>创建默认家庭空间后，老人画像、家人档案、家庭记忆和 AI 角色都会归属到同一个云端家庭。</p>
      </section>

      {isLoading ? <p className="emptyState">正在加载家庭空间...</p> : null}
      {error ? <p className="errorText">{error}</p> : null}
      {success ? <p className="successText">{success}</p> : null}

      {!isLoading && familyContext ? (
        <section className="panel familyStatus">
          <div>
            <h2>{familyContext.family.name}</h2>
            <p className="helperText">家庭 ID：{familyContext.family.id}</p>
          </div>
          <div className="profileMeta">
            <span>成员角色：{roleLabel(familyContext.membership.role)}</span>
            <span>用户：{familyContext.membership.user_id}</span>
          </div>

          <div className="completionPanel">
            <h3>陪伴资料完成度</h3>
            {completion ? (
              <>
                <div className="statGrid">
                  <Link href="/records" className={`statCard ${completion.elder ? "completed" : "pending"}`}>
                    <div className={`statNumber ${completion.elder ? "done" : "todo"}`}>{completion.elder ? "✓" : "1"}</div>
                    <div className="statLabel">老人画像</div>
                  </Link>
                  <Link href="/records" className={`statCard ${completion.persona ? "completed" : "pending"}`}>
                    <div className={`statNumber ${completion.persona ? "done" : "todo"}`}>{completion.persona ? "✓" : "2"}</div>
                    <div className="statLabel">AI 角色</div>
                  </Link>
                  <Link href="/records" className={`statCard ${completion.memory ? "completed" : "pending"}`}>
                    <div className={`statNumber ${completion.memory ? "done" : "todo"}`}>{completion.memory ? "✓" : "3"}</div>
                    <div className="statLabel">家庭记忆</div>
                  </Link>
                  <Link href="/voices" className={`statCard ${completion.voice ? "completed" : "pending"}`}>
                    <div className={`statNumber ${completion.voice ? "done" : "todo"}`}>{completion.voice ? "✓" : "4"}</div>
                    <div className="statLabel">音色</div>
                  </Link>
                </div>
                {completion.elder && completion.persona && completion.memory && completion.voice ? (
                  <p className="successText" style={{ marginTop: 16 }}>所有资料已就绪，老人可以开始语音聊天了。</p>
                ) : (
                  <p className="helperText" style={{ marginTop: 16 }}>点击上方未完成的项目，直接跳转到对应配置页面。</p>
                )}
              </>
            ) : (
              <p className="helperText">暂未读取到陪伴资料。</p>
            )}
          </div>

          <div className="actions">
            <Link className="button" href="/records">
              完善档案与记忆
            </Link>
            <button className="button buttonSecondary" type="button" onClick={loadFamily}>
              刷新
            </button>
            <Link className="button buttonSecondary" href="/">
              返回首页
            </Link>
          </div>
          <div>
            <h3>下一步</h3>
            <div className="nextStepGrid">
              {nextSteps.map((step) => (
                <Link className="nextStepLink" href={step.href} key={step.href}>
                  <strong>{step.title}</strong>
                  <span>{step.body}</span>
                </Link>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {!isLoading && !familyContext ? (
        <section className="panel familyStatus">
          <h2>尚未创建家庭空间</h2>
          <p className="helperText">首版默认使用单家庭空间；创建者会成为 owner，后续邀请家人默认成为 editor。</p>
          <label className="familyNameField">
            <span>家庭空间名称</span>
            <input value={familyName} onChange={(event) => setFamilyName(event.target.value)} />
          </label>
          <div className="actions">
            <button type="button" onClick={onCreateFamily} disabled={isCreating}>
              {isCreating ? "创建中..." : "创建家庭空间"}
            </button>
            <Link className="button buttonSecondary" href="/">
              返回首页
            </Link>
          </div>
        </section>
      ) : null}
    </main>
  );
}
