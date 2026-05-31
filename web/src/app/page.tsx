"use client";

import { useEffect, useState } from "react";

import { AuthUser, clearAuthSession, getAuthUser } from "../lib/auth";

const panels = [
  {
    title: "登录",
    body: "使用手机号验证码进入家庭空间，测试期验证码固定为 000000。",
    href: "/login",
  },
  {
    title: "家庭空间",
    body: "创建家庭空间，邀请家人共同维护老人画像、家人档案和家庭记忆。",
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
  {
    title: "老人端",
    body: "提供电话式语音陪伴入口，让老人像打电话一样和家人声音聊天。",
    href: "/elder",
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
            <button className="button buttonSecondary" onClick={logout} type="button">
              退出登录
            </button>
          </>
        ) : (
          <a className="button" href="/login">去登录</a>
        )}
      </div>
      <h1>亲情陪伴系统</h1>
      <p>面向家人协作和老人陪伴的 Web 应用入口。</p>
      <section className="dashboard" aria-label="首页功能">
        {panels.map((panel) => (
          <a className="panel panelLink" href={panel.href} key={panel.title}>
            <h2>{panel.title}</h2>
            <p>{panel.body}</p>
          </a>
        ))}
      </section>
    </main>
  );
}
