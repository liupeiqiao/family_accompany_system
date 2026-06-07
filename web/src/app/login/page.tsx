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
      router.replace("/elder");
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
      router.replace("/elder");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败。");
    } finally {
      setIsVerifying(false);
    }
  }

  return (
    <main className="loginShell">
      <div className="loginTableGlow" aria-hidden="true" />
      <section className="loginMemoryWall" aria-hidden="true">
        <article className="loginPolaroid spring">
          <span />
          <strong>2022 春节</strong>
        </article>
        <article className="loginPolaroid seaside">
          <span />
          <strong>和妈妈一起去青岛</strong>
        </article>
        <article className="loginPolaroid birthday">
          <span />
          <strong>奶奶 80 岁生日</strong>
        </article>
        <article className="loginPolaroid together">
          <span />
          <strong>我们在一起的时光</strong>
        </article>
        <article className="loginPolaroid craft">
          <span />
          <strong>爸爸的手艺</strong>
        </article>
        <article className="loginPolaroid warm">
          <span />
          <strong>最暖的时光</strong>
        </article>
      </section>

      <section className="loginCard" aria-label="手机号登录">
        <div className="loginPanelBrand" aria-hidden="true">
          <Icon name="brand" />
          <span>简体中文⌄</span>
        </div>

        <section className="loginPanel">
          <div className="sectionHeader">
            <h1>手机号登录</h1>
            <p>请输入内测账号和验证码登录。</p>
          </div>
          <form onSubmit={handleSubmit}>
            <label>
              <span>内测账号</span>
              <div className="loginPhoneField">
                <b>+86</b>
                <input
                  autoComplete="tel"
                  inputMode="tel"
                  onChange={(event) => setPhone(event.target.value)}
                  placeholder="请输入内测账号"
                  value={phone}
                />
              </div>
            </label>
            <label>
              <span>验证码</span>
              <div className="loginCodeField">
                <input
                  autoComplete="off"
                  inputMode="numeric"
                  onChange={(event) => setCode(event.target.value)}
                  placeholder="请输入测试版验证码"
                  type="text"
                  value={code}
                />
                <button className="buttonSecondary" disabled={isSending || !phone.trim()} onClick={handleSendCode} type="button">
                  {isSending ? "检查中" : "检查账号"}
                </button>
              </div>
            </label>
            <div className="actions">
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

  return null;
}
