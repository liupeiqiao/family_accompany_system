"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  CloudRecord,
  FamilyContext,
  createFamily,
  fetchCloudFamilyProfiles,
  fetchCloudMemories,
  fetchCurrentFamily,
} from "../../lib/backend-api";
import { getAuthToken } from "../../lib/auth";

type IconName =
  | "brand"
  | "journey"
  | "home"
  | "house"
  | "records"
  | "history"
  | "voice"
  | "settings"
  | "members"
  | "memory"
  | "care"
  | "plus"
  | "chevron"
  | "role";

const navItems: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "首页", icon: "home" },
  { href: "/family", label: "家庭空间", icon: "house" },
  { href: "/records", label: "档案与记忆", icon: "records" },
  { href: "/history", label: "对话历史", icon: "history" },
  { href: "/voices", label: "音色管理", icon: "voice" },
  { href: "/family", label: "系统设置", icon: "settings" },
];

const fallbackMembers = [
  { name: "林奶奶", relation: "家庭核心", tone: "warm" },
  { name: "爸爸", relation: "家人", tone: "blue" },
  { name: "妈妈", relation: "家人", tone: "rose" },
  { name: "女儿", relation: "家人", tone: "peach" },
  { name: "儿子", relation: "家人", tone: "green" },
];

const roleRows = [
  { title: "陪伴者", body: "主要陪伴者，可创建记忆、发起对话", count: "2 人", icon: "records" as IconName },
  { title: "协助者", body: "可管理部分记忆与信息，协助维护家庭空间", count: "2 人", icon: "members" as IconName },
  { title: "观察者", body: "可查看部分内容，接收陪伴报告", count: "1 人", icon: "care" as IconName },
];

function valueToText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function roleLabel(role?: string): string {
  if (role === "owner") return "管理员";
  if (role === "editor") return "协助者";
  if (role === "viewer") return "观察者";
  return "管理员";
}

function profileName(profile: CloudRecord): string {
  return valueToText(profile.name) || valueToText(profile.display_name) || "家人";
}

function profileRelation(profile: CloudRecord): string {
  return valueToText(profile.relation) || "家人";
}

export default function FamilyPage() {
  const router = useRouter();
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [familyName, setFamilyName] = useState("林家小院");
  const [members, setMembers] = useState<CloudRecord[]>([]);
  const [memories, setMemories] = useState<CloudRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const displayMembers = useMemo(() => {
    if (members.length === 0) return fallbackMembers;
    return members.slice(0, 5).map((profile, index) => ({
      name: profileName(profile),
      relation: profileRelation(profile),
      tone: fallbackMembers[index % fallbackMembers.length].tone,
    }));
  }, [members]);

  const memberCount = members.length || fallbackMembers.length;
  const memoryCount = memories.length || 128;

  async function loadFamily() {
    setIsLoading(true);
    setError("");
    setSuccess("");

    try {
      const current = await fetchCurrentFamily();
      setFamilyContext(current);
      setFamilyName(current.family.name || "林家小院");

      try {
        const [familyProfiles, familyMemories] = await Promise.all([
          fetchCloudFamilyProfiles(current.family.id),
          fetchCloudMemories(current.family.id),
        ]);
        setMembers(familyProfiles);
        setMemories(familyMemories);
      } catch {
        setMembers([]);
        setMemories([]);
      }
    } catch {
      setFamilyContext(null);
      setMembers([]);
      setMemories([]);
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
      await loadFamily();
    } catch {
      setError("创建家庭空间失败，请稍后重试。");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="familySpace">
      <aside className="familySidebar">
        <Link className="familyBrand" href="/">
          <Icon name="brand" />
          <strong>亲情陪伴系统</strong>
        </Link>

        <nav className="familyNav" aria-label="家庭空间导航">
          <Link className="familyJourney" href="/">
            <Icon name="journey" />
            <span>首页 / 产品入口</span>
          </Link>
          {navItems.map((item) => (
            <Link
              className={item.label === "家庭空间" ? "familyNavItem familyNavItemActive" : "familyNavItem"}
              href={item.href}
              key={item.label}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        <div className="familyUserCard">
          <span className="familyUserAvatar" aria-hidden="true" />
          <span>
            <strong>小美</strong>
            <small>{roleLabel(familyContext?.membership.role)}</small>
          </span>
          <Icon name="settings" />
        </div>
      </aside>

      <section className="familyMain">
        <header className="familyTop">
          <div>
            <h1>家庭空间</h1>
            <p>家人携手守护，让陪伴更温暖、更有力量</p>
          </div>
          <div className="familyTopActions">
            <button className="familyGhostButton" type="button">
              <Icon name="members" />
              邀请家人
            </button>
            <Link className="familyPrimaryButton" href="/records">
              <Icon name="plus" />
              新建记忆
            </Link>
          </div>
        </header>

        {isLoading ? <p className="familyNotice">正在加载家庭空间...</p> : null}
        {error ? <p className="familyNotice familyNoticeError">{error}</p> : null}
        {success ? <p className="familyNotice familyNoticeSuccess">{success}</p> : null}

        {!isLoading && !familyContext ? (
          <section className="familyCreateCard">
            <div>
              <h2>尚未创建家庭空间</h2>
              <p>创建后，家人档案、家庭记忆和陪伴音色都会归属于同一个家庭空间。</p>
            </div>
            <label>
              <span>家庭空间名称</span>
              <input value={familyName} onChange={(event) => setFamilyName(event.target.value)} />
            </label>
            <button className="familyPrimaryButton" type="button" onClick={onCreateFamily} disabled={isCreating}>
              <Icon name="plus" />
              {isCreating ? "创建中..." : "创建家庭空间"}
            </button>
          </section>
        ) : null}

        {!isLoading && familyContext ? (
          <>
            <section className="familyStats" aria-label="家庭空间概览">
              <StatCard icon="house" label="家庭名称" value={familyContext.family.name || familyName} suffix="" action="" />
              <StatCard icon="members" label="家庭成员" value={String(memberCount)} suffix="人" action="查看成员" />
              <StatCard icon="memory" label="家庭记忆" value={String(memoryCount)} suffix="条" action="查看记忆" />
              <StatCard icon="care" label="本周陪伴" value="23" suffix="次" action="查看统计" />
            </section>

            <section className="familyHeroPhoto" aria-label="家人围绕老人陪伴的温馨照片" />

            <section className="familyLowerGrid">
              <div className="familyPanel familyMembersPanel">
                <h2>家庭成员</h2>
                <div className="familyMemberList">
                  {displayMembers.map((member) => (
                    <article className="familyMember" key={`${member.name}-${member.relation}`}>
                      <span className={`familyMemberPhoto tone-${member.tone}`} aria-hidden="true">
                        {member.name.slice(0, 1)}
                      </span>
                      <strong>{member.name}</strong>
                      <small className={member.relation === "家庭核心" ? "familyCoreTag" : ""}>{member.relation}</small>
                    </article>
                  ))}
                  <Link className="familyAddMember" href="/records">
                    <Icon name="plus" />
                    <span>添加成员</span>
                  </Link>
                </div>
              </div>

              <div className="familyPanel familyRolesPanel">
                <div className="familyPanelTitleRow">
                  <div>
                    <h2>家庭角色设置</h2>
                    <p>自定义每个家庭成员在陪伴中的角色与权限</p>
                  </div>
                  <button className="familyTinyButton" type="button">管理角色</button>
                </div>

                <div className="familyRoleList">
                  {roleRows.map((role) => (
                    <div className="familyRoleRow" key={role.title}>
                      <Icon name={role.icon} />
                      <span>
                        <strong>{role.title}</strong>
                        <small>{role.body}</small>
                      </span>
                      <em>{role.count}</em>
                      <Icon name="chevron" />
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}

function StatCard(props: { icon: IconName; label: string; value: string; suffix: string; action: string }) {
  return (
    <article className="familyStatCard">
      <Icon name={props.icon} />
      <div>
        <span>{props.label}</span>
        <strong>
          {props.value}
          {props.suffix ? <em>{props.suffix}</em> : null}
        </strong>
        {props.action ? (
          <small>
            {props.action}
            <Icon name="chevron" />
          </small>
        ) : (
          <small>
            <Icon name="chevron" />
          </small>
        )}
      </div>
    </article>
  );
}

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, string> = {
    brand: "M12 3 4 7.6v8.8L12 21l8-4.6V7.6L12 3Zm0 4.2 4.4 2.5v5L12 17.2 7.6 14.7v-5L12 7.2Zm0 3.3a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Z",
    journey: "M4 12.5 12 5l8 7.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-7.5Z",
    home: "M4 11.5 12 4l8 7.5V20a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1v-8.5Z",
    house: "M3 11.2 12 3l9 8.2-1.5 1.6L18 11.4V21h-5v-6h-2v6H6v-9.6l-1.5 1.4L3 11.2Z",
    records: "M7 3h10a2 2 0 0 1 2 2v16H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm2 5h6M9 12h6M9 16h4",
    history: "M12 5a7 7 0 1 1-6.2 3.8M5 5v4h4M12 8v5l3 2",
    voice: "M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3Zm6 8a6 6 0 0 1-12 0M12 17v4M9 21h6",
    settings: "M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm8 4a7.8 7.8 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a8 8 0 0 0-1.7-1L15.5 3h-4l-.3 3.1a8 8 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.5a7.8 7.8 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a8 8 0 0 0 1.7 1l.3 3.1h4l.3-3.1a8 8 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1Z",
    members: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3 21c.5-4 2.4-6 5-6s4.5 2 5 6m-2.5-5c.9-.7 2-1 3.5-1 2.6 0 4.5 2 5 6",
    memory: "M6 4h12v16H6V4Zm3 4h6M9 12h6M9 16h4",
    care: "M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.7A4 4 0 0 1 19 11c0 5.5-7 10-7 10Zm-8-1c0-3 2-5 5-5M20 20c0-3-2-5-5-5",
    plus: "M12 5v14M5 12h14",
    chevron: "m9 6 6 6-6 6",
    role: "M8 4h8v4H8V4Zm-2 8h12v8H6v-8Z",
  };

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d={paths[name]} />
    </svg>
  );
}
