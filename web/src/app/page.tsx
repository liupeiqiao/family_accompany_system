"use client";

import { useEffect, useState } from "react";

import { AuthUser, clearAuthSession, getAuthUser } from "../lib/auth";

const familyNodes = [
  { name: "奶奶", role: "AI 陪伴中", className: "grandma" },
  { name: "爸爸", role: "AI 陪伴中", className: "dad" },
  { name: "妈妈", role: "AI 陪伴中", className: "mom" },
  { name: "女儿 · 小美", role: "AI 陪伴中", className: "daughter" },
  { name: "儿子 · 小明", role: "AI 陪伴中", className: "son" },
];

const features = [
  {
    title: "AI 家人陪伴",
    body: "7x24 小时温暖陪伴",
    href: "/elder",
    icon: "chat",
    className: "companion",
  },
  {
    title: "家庭空间",
    body: "共同维护家人档案",
    href: "/family",
    icon: "home-family",
    className: "family",
  },
  {
    title: "家庭记忆库",
    body: "珍藏每一刻美好回忆",
    href: "/records",
    icon: "book",
    className: "records",
  },
  {
    title: "家人声音复刻",
    body: "留住最熟悉的声音",
    href: "/voices",
    icon: "voice",
    className: "voices",
  },
];

export default function HomePage() {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    setUser(getAuthUser());
  }, []);

  function logout() {
    clearAuthSession();
    setUser(null);
  }

  return (
    <main className="productHome">
      <div className="homeBackdrop" aria-hidden="true" />
      <header className="homeTopBar">
        <a className="homeBrand" href="/">
          <span className="homeLogo" aria-hidden="true">
            <Icon name="brand" />
          </span>
          <strong>亲情陪伴系统</strong>
          <small>Beta</small>
        </a>

        <div className="homeAuthArea">
          {user ? (
            <button className="homeLoginButton" onClick={logout} type="button">
              <Icon name="chevron" />
              <span>{user.phone} · 退出</span>
            </button>
          ) : (
            <a className="homeLoginButton" href="/login">
              <Icon name="family" />
              <span>登录 / 注册</span>
            </a>
          )}
        </div>
      </header>

      <section className="homeHero" aria-label="首页产品入口">
        <div className="homeHeroContent">
          <h1>
            即使相隔千里，<em>爱</em>也从未离开。
          </h1>
          <p>AI 陪伴家人左右，让记忆永不褪色</p>
        </div>

        <div className="familyTreeStage" aria-label="家庭成员陪伴状态">
          <div className="treeCrown" aria-hidden="true" />
          <div className="treeTrunk" aria-hidden="true" />
          {familyNodes.map((node) => (
            <article className={`familyNode ${node.className}`} key={node.name}>
              <span className="familyNodePhoto" aria-hidden="true" />
              <strong>{node.name}</strong>
              <small>
                <i />
                {node.role}
              </small>
            </article>
          ))}
        </div>

        <section className="homeFeatureGrid" aria-label="核心能力">
          {features.map((panel) => (
            <a className={`homeFeatureCard ${panel.className}`} href={panel.href} key={panel.title}>
              <span>
                <strong>{panel.title}</strong>
                <small>{panel.body}</small>
                <b>
                  进入界面
                  <Icon name="arrow" />
                </b>
              </span>
              <Icon name={panel.icon} />
            </a>
          ))}
        </section>
      </section>
    </main>
  );
}

function Icon({ name }: { name: string }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.9,
    viewBox: "0 0 24 24",
  };

  if (name === "brand") {
    return (
      <svg {...common}>
        <path d="M4.5 13.5V9.6L12 4l7.5 5.6v3.9" />
        <path d="M8 14.5a4 4 0 0 1 8 0v1.8a3 3 0 0 1-3 3h-1" />
        <path d="M8 14.5v2.1a2 2 0 0 0 2 2" />
        <path d="M9.5 14.3h.01M14.5 14.3h.01" />
      </svg>
    );
  }
  if (name === "home" || name === "home-family") {
    return (
      <svg {...common}>
        <path d="M3.5 11.3 12 4.5l8.5 6.8" />
        <path d="M6.5 10.8v8h11v-8" />
        {name === "home-family" ? <path d="M9.5 16a2.5 2.5 0 0 1 5 0M9.7 13h.01M14.3 13h.01" /> : <path d="M10 18.8v-5h4v5" />}
      </svg>
    );
  }
  if (name === "family") {
    return (
      <svg {...common}>
        <path d="M9 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM17 11a2.4 2.4 0 1 0 0-4.8 2.4 2.4 0 0 0 0 4.8Z" />
        <path d="M3.8 19a5.2 5.2 0 0 1 10.4 0M14.7 18.2a4.1 4.1 0 0 1 5.5 0" />
      </svg>
    );
  }
  if (name === "folder") {
    return (
      <svg {...common}>
        <path d="M4 7.5h6l1.5 2H20v10H4z" />
      </svg>
    );
  }
  if (name === "history" || name === "clock") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="8.5" />
        <path d="M12 7.5v5l3.4 2" />
      </svg>
    );
  }
  if (name === "voice") {
    return (
      <svg {...common}>
        <path d="M4 13v-2M8 17V7M12 20V4M16 17V7M20 13v-2" />
      </svg>
    );
  }
  if (name === "settings") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="3" />
        <path d="M19 12a7.8 7.8 0 0 0-.1-1.2l2-1.5-2-3.4-2.4 1a7.8 7.8 0 0 0-2-1.1L14 3h-4l-.5 2.8a7.8 7.8 0 0 0-2 1.1l-2.4-1-2 3.4 2 1.5A7.8 7.8 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.4-1a7.8 7.8 0 0 0 2 1.1L10 21h4l.5-2.8a7.8 7.8 0 0 0 2-1.1l2.4 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2Z" />
      </svg>
    );
  }
  if (name === "chat") {
    return (
      <svg {...common}>
        <path d="M5 18.5V19l3.3-2H17a5.5 5.5 0 0 0 0-11H8a5.5 5.5 0 0 0-3 10.1" />
        <path d="M9 12h.01M12 12h.01M15 12h.01" />
      </svg>
    );
  }
  if (name === "book") {
    return (
      <svg {...common}>
        <path d="M5 5.5h6a3 3 0 0 1 3 3V20a3 3 0 0 0-3-3H5z" />
        <path d="M14 8.5a3 3 0 0 1 3-3h2v11.5h-2a3 3 0 0 0-3 3" />
      </svg>
    );
  }
  if (name === "shield") {
    return (
      <svg {...common}>
        <path d="M12 3.5 19 6v5.5c0 4.2-2.7 7.3-7 8.5-4.3-1.2-7-4.3-7-8.5V6z" />
        <path d="M10 12.5h4M12 10.5v4" />
      </svg>
    );
  }
  if (name === "memory") {
    return (
      <svg {...common}>
        <path d="M6 4.5h12v15H6z" />
        <path d="M9 8h6M9 12h6M9 16h3" />
      </svg>
    );
  }
  if (name === "chevron") {
    return (
      <svg {...common}>
        <path d="m9 6 6 6-6 6" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}
