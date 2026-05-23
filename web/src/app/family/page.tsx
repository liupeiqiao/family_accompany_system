import Link from "next/link";

export default function FamilyPage() {
  return (
    <main className="shell">
      <section className="sectionHeader">
        <h1>家庭空间</h1>
        <p>这里用于创建家庭空间、管理成员，并把老人画像、家人档案和家庭记忆归到同一个家庭下。</p>
      </section>
      <div className="actions">
        <button className="button" type="button">创建家庭空间</button>
        <button className="button buttonSecondary" type="button">邀请家人</button>
        <Link className="button buttonSecondary" href="/">返回首页</Link>
      </div>
      <ul className="placeholderList">
        <li>首版先接本地 API 和 SQLite 数据。</li>
        <li>后续接 Supabase Auth 后，这里会显示家庭成员和权限。</li>
      </ul>
    </main>
  );
}
