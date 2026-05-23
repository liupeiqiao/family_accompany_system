const panels = [
  {
    title: "家庭空间",
    body: "创建家庭空间，邀请家人共同维护老人画像、家人档案和家庭记忆。",
  },
  {
    title: "档案与记忆",
    body: "集中管理老人信息、AI 扮演角色、家人档案和可用于对话的温暖记忆。",
  },
  {
    title: "声音克隆",
    body: "上传或录制授权声音样本，生成可用于语音回复的克隆声音。",
  },
  {
    title: "老人端",
    body: "提供简化聊天入口，老人输入文字后可以听到克隆语音回复。",
  },
];

export default function HomePage() {
  return (
    <main className="shell">
      <h1>亲情陪伴系统</h1>
      <p>面向家人协作和老人陪伴的正式 Web 应用入口。</p>
      <section className="dashboard" aria-label="首版功能">
        {panels.map((panel) => (
          <article className="panel" key={panel.title}>
            <h2>{panel.title}</h2>
            <p>{panel.body}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
