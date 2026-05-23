import Link from "next/link";

export default function VoicesPage() {
  return (
    <main className="shell">
      <section className="sectionHeader">
        <h1>声音克隆</h1>
        <p>这里用于上传授权声音样本、查看克隆状态，并把语音回复接到老人端聊天。</p>
      </section>
      <div className="actions">
        <button className="button" type="button">上传声音样本</button>
        <button className="button buttonSecondary" type="button">查看声音档案</button>
        <Link className="button buttonSecondary" href="/">返回首页</Link>
      </div>
      <ul className="placeholderList">
        <li>首版声音 provider 已有 mock 边界。</li>
        <li>接真实第三方声音服务前，需要保留授权确认和审计字段。</li>
      </ul>
    </main>
  );
}
