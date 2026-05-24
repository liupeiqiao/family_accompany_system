"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { FamilyContext, createFamily, fetchCurrentFamily } from "../../lib/backend-api";

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

export default function FamilyPage() {
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
    } catch (loadError) {
      if (loadError instanceof Error && loadError.message.includes("404")) {
        setFamilyContext(null);
      } else {
        setError("无法加载家庭空间，请确认 API 服务已启动。");
      }
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadFamily();
  }, []);

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
              维护档案与记忆
            </Link>
            <button className="button buttonSecondary" type="button" onClick={loadFamily}>
              刷新
            </button>
            <Link className="button buttonSecondary" href="/">
              返回首页
            </Link>
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
