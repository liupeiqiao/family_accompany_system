import Link from "next/link";

export default function RecordsPage() {
  return (
    <main className="shell">
      <section className="sectionHeader">
        <h1>档案与记忆</h1>
        <p>这里用于维护老人画像、AI 扮演角色、家人档案和家庭记忆。</p>
      </section>
      <div className="actions">
        <button className="button" type="button">智能解析导入</button>
        <button className="button buttonSecondary" type="button">添加记忆</button>
        <Link className="button buttonSecondary" href="/">返回首页</Link>
      </div>
      <ul className="placeholderList">
        <li>智能解析接口已在后端提供：POST /api/parse。</li>
        <li>下一步会把这里接成可编辑表单和一键导入。</li>
      </ul>
    </main>
  );
}
