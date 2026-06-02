"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getAuthToken, sendLoginCode, verifyLoginCode } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  useEffect(() => {
    if (getAuthToken()) {
      router.replace("/family");
    }
  }, [router]);

  async function handleSendCode() {
    setError("");
    setMessage("");
    setIsSending(true);
    try {
      const result = await sendLoginCode(phone);
      setMessage(result.test_mode ? "账号可用，请输入内测验证码登录。" : "验证码已发送。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "账号检查失败。");
    } finally {
      setIsSending(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsVerifying(true);
    try {
      await verifyLoginCode(phone, code);
      router.replace("/family");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败。");
    } finally {
      setIsVerifying(false);
    }
  }

  return (
    <main className="loginShell">
      <section className="loginCard" aria-label="手机号登录">
        <div className="loginStoryPanel">
          <div className="loginStepBadge" aria-hidden="true">
            2
          </div>
          <div className="loginStoryCopy">
            <p>手机号登录</p>
            <h2>
              科技连接亲情
              <br />
              陪伴从心开始
            </h2>
          </div>
          <div className="loginMemoryScene" aria-hidden="true">
            <div className="loginVase" />
            <div className="loginPhotoFrame">
              <div className="loginPhotoImage" />
            </div>
            <div className="loginSnapshot loginSnapshotOne" />
            <div className="loginSnapshot loginSnapshotTwo" />
          </div>
        </div>

        <section className="loginPanel">
          <div className="sectionHeader">
            <h1>手机号登录</h1>
            <p>请输入内测账号和验证码登录。</p>
          </div>
          <form onSubmit={handleSubmit}>
            <label>
              <span>内测账号</span>
              <input
                autoComplete="tel"
                inputMode="tel"
                onChange={(event) => setPhone(event.target.value)}
                placeholder="请输入内测账号"
                value={phone}
              />
            </label>
            <label>
              <span>验证码</span>
              <input
                autoComplete="off"
                inputMode="numeric"
                onChange={(event) => setCode(event.target.value)}
                placeholder="请输入测试版验证码"
                type="text"
                value={code}
              />
            </label>
            <div className="actions">
              <button className="buttonSecondary" disabled={isSending || !phone.trim()} onClick={handleSendCode} type="button">
                {isSending ? "检查中" : "检查账号"}
              </button>
              <button disabled={isVerifying || !phone.trim() || !code.trim()} type="submit">
                {isVerifying ? "登录中" : "登录"}
              </button>
            </div>
            {message ? <p className="successText">{message}</p> : null}
            {error ? <p className="errorText">{error}</p> : null}
          </form>
        </section>
      </section>
    </main>
  );
}
