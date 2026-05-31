"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { FamilyContext, createFamily, fetchCurrentFamily } from "../../lib/backend-api";
import { getAuthToken } from "../../lib/auth";

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

  async function loadFamily() {
    setIsLoading(true);
    setError("");
    setSuccess("");

    try {
      const current = await fetchCurrentFamily();
      setFamilyContext(current);
      setFamilyName(current.family.name || "我的家庭");
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
