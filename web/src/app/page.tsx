"use client";

import { useEffect, useState } from "react";

import { AuthUser, clearAuthSession, getAuthUser } from "../lib/auth";

const navItems = [
  { label: "首页", href: "/", icon: "home", active: true },
  { label: "家庭空间", href: "/family", icon: "family" },
  { label: "档案与记忆", href: "/records", icon: "folder" },
  { label: "对话历史", href: "/history", icon: "history" },
  { label: "音色管理", href: "/voices", icon: "voice" },
  { label: "系统设置", href: "/family", icon: "settings" },
];

const stats = [
  { label: "今日陪伴", value: "2", suffix: "小时 36 分", icon: "clock" },
  { label: "可用亲人音色", value: "5", suffix: "个", icon: "family" },
  { label: "已沉淀家庭记忆", value: "128", suffix: "条", icon: "memory" },
];

const features = [
  {
    title: "AI 语音陪伴",
    body: "自然对话，贴心陪伴\n让长辈畅聊每一天",
    href: "/elder",
    icon: "chat",
  },
  {
    title: "家庭共建空间",
    body: "邀请家人一起建设\n共享温暖与关爱",
    href: "/family",
    icon: "home-family",
  },
  {
    title: "记忆与传承",
    body: "珍藏回忆，传承家风\n留住家庭的故事",
    href: "/records",
    icon: "book",
  },
  {
    title: "安全隐私保障",
    body: "多重守护，隐私无忧\n全方位保护信息安全",
    href: "/records",
    icon: "shield",
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
      <aside className="homeSidebar" aria-label="产品导航">
        <a className="homeBrand" href="/">
          <span className="homeLogo" aria-hidden="true">
            <Icon name="brand" />
          </span>
          <span>
            <strong>亲情陪伴系统</strong>
            <small>让陪伴有声，让记忆延续</small>
          </span>
        </a>

        <nav className="homeNav">
          {navItems.map((item) => (
            <a className={item.active ? "homeNavItem active" : "homeNavItem"} href={item.href} key={item.label}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </a>
          ))}
        </nav>

        <div className="homeUser">
          <span className="homeAvatar" aria-hidden="true" />
          <span>
            <strong>小美</strong>
            <small>{user ? user.phone : "管理员"}</small>
          </span>
          {user ? (
            <button className="homeUserAction" onClick={logout} type="button" aria-label="退出登录">
              <Icon name="chevron" />
            </button>
          ) : (
            <a className="homeUserAction" href="/login" aria-label="前往登录">
              <Icon name="chevron" />
            </a>
          )}
        </div>
      </aside>

      <section className="homeHero" aria-label="首页产品入口">
        <div className="homeHeroImage" aria-hidden="true" />
        <div className="homeHeroVeil" aria-hidden="true" />
        <div className="homeStatus">
          <span />
          陪伴服务运行中
        </div>

        <div className="homeHeroContent">
          <h1>
            让爱跨越距离，
            <br />
            AI 陪伴温暖每一天
          </h1>
          <p>为家人创建专属陪伴体验，守护长辈的幸福晚年</p>
          <div className="homeCtas">
            <a className="homePrimaryCta" href="/elder">
              开始陪伴之旅
            </a>
            <a className="homeSecondaryCta" href="/family">
              了解更多
            </a>
          </div>
        </div>

        <section className="homeStats" aria-label="陪伴概览">
          {stats.map((item) => (
            <article className="homeStat" key={item.label}>
              <span className="homeStatIcon" aria-hidden="true">
                <Icon name={item.icon} />
              </span>
              <span>
                <small>{item.label}</small>
                <strong>
                  {item.value}
                  <em>{item.suffix}</em>
                </strong>
              </span>
            </article>
          ))}
        </section>

        <section className="homeFeatureGrid" aria-label="核心能力">
          {features.map((feature) => (
            <a className="homeFeatureCard" href={feature.href} key={feature.title}>
              <span className="homeFeatureIcon" aria-hidden="true">
                <Icon name={feature.icon} />
              </span>
              <strong>{feature.title}</strong>
              <span>{feature.body}</span>
              <Icon name="arrow" />
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
