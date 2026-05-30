"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { sendLoginCode, verifyLoginCode } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("000000");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  async function handleSendCode() {
    setError("");
    setMessage("");
    setIsSending(true);
    try {
      const result = await sendLoginCode(phone);
      setMessage(result.test_mode ? "测试模式验证码为 000000。" : "验证码已发送。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送验证码失败。");
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
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败。");
    } finally {
      setIsVerifying(false);
    }
  }

  return (
    <main className="shell">
      <section className="loginPanel">
        <div className="sectionHeader">
          <h1>手机号登录</h1>
          <p>测试期任意手机号可使用验证码 000000 登录。</p>
        </div>
        <form onSubmit={handleSubmit}>
          <label>
            <span>手机号</span>
            <input
              autoComplete="tel"
              inputMode="tel"
              onChange={(event) => setPhone(event.target.value)}
              placeholder="请输入手机号"
              value={phone}
            />
          </label>
          <label>
            <span>验证码</span>
            <input
              autoComplete="one-time-code"
              inputMode="numeric"
              onChange={(event) => setCode(event.target.value)}
              value={code}
            />
          </label>
          <div className="actions">
            <button disabled={isSending || !phone.trim()} onClick={handleSendCode} type="button">
              {isSending ? "发送中" : "发送验证码"}
            </button>
            <button disabled={isVerifying || !phone.trim() || !code.trim()} type="submit">
              {isVerifying ? "登录中" : "登录"}
            </button>
          </div>
          {message ? <p className="successText">{message}</p> : null}
          {error ? <p className="errorText">{error}</p> : null}
        </form>
      </section>
    </main>
  );
}
