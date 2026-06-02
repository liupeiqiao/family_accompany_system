"use client";

import { useEffect, useState } from "react";

import { AuthUser, clearAuthSession, getAuthUser } from "../lib/auth";

const elderPanel = {
  title: "老人端语音陪伴",
  body: "登录后优先进入电话式语音陪伴，让老人直接和家人声音聊天。",
  href: "/elder",
  hero: true,
};

const familyPanels = [
  {
    title: "家属管理",
    body: "创建家庭空间，作为档案、音色、记忆和对话历史的数据归属后台。",
    href: "/family",
  },
  {
    title: "档案与记忆",
    body: "集中管理老人信息、AI 扮演角色、家人档案和可用于对话的温暖记忆。",
    href: "/records",
  },
  {
    title: "对话历史",
    body: "查看老人端和家人声音 AI 的最近对话，按角色、老人和时间筛选，并重播已保存的 AI 回复。",
    href: "/history",
  },
  {
    title: "声音克隆",
    body: "导入或创建授权音色，并绑定到 AI 角色，用于老人端语音陪伴。",
    href: "/voices",
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
    <main className="shell">
      <div className="authBar">
        {user ? (
          <>
            <span>已登录：{user.phone}</span>
            <a className="button" href="/elder">开始语音陪伴</a>
            <button className="button buttonSecondary" onClick={logout} type="button">
              退出登录
            </button>
          </>
        ) : (
          <a className="button" href="/login">去登录</a>
        )}
      </div>
      <h1>亲情陪伴系统</h1>
      <p>登录后默认进入老人端语音陪伴；家属管理入口用于维护档案、音色、记忆和历史。</p>
      <div className="primaryCta">
        <a className="button" href="/elder">开始语音陪伴</a>
        <a className="button buttonSecondary" href="/family">进入家属管理</a>
      </div>
      <section className="dashboard" aria-label="首页功能">
        <a className="panel panelLink hero" href={elderPanel.href}>
          <h2>{elderPanel.title}</h2>
          <p>{elderPanel.body}</p>
        </a>
        <p className="dashboardLabel">家属管理</p>
        {familyPanels.map((panel) => (
          <a className="panel panelLink" href={panel.href} key={panel.title}>
            <h2>{panel.title}</h2>
            <p>{panel.body}</p>
          </a>
        ))}
      </section>
    </main>
  );
}
