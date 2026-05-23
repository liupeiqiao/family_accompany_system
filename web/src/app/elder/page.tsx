export default function ElderChatPage() {
  return (
    <main className="shell">
      <section className="chat" aria-label="老人端聊天">
        <h1>老人端</h1>
        <div className="message">
          <strong>家人回复</strong>
          <p>妈，我在呢。您慢慢说，我陪您聊一会儿。</p>
          <audio controls src="/sample-reply.mp3">
            当前浏览器不支持音频播放。
          </audio>
        </div>
        <form>
          <label htmlFor="elder-message">想和家人说的话</label>
          <textarea id="elder-message" name="message" rows={4} />
          <button type="submit">发送</button>
        </form>
      </section>
    </main>
  );
}
