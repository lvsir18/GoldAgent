"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { authApi } from "@/services/api/auth";
import { useAuthStore } from "@/stores/auth";
import { useLanguage } from "@/i18n/language";

export default function LoginPage() {
  const router = useRouter();
  const { text } = useLanguage();
  const setTokens = useAuthStore(state => state.setTokens);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [register, setRegister] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const tokens = await (register ? authApi.register({ email, password }) : authApi.login({ email, password }));
      setTokens(tokens); router.push("/dashboard");
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  };

  return <div className="mx-auto mt-16 max-w-md">
    <div className="card p-7">
      <p className="text-xs tracking-widest text-gold">SECURE ACCESS</p>
      <h1 className="mt-2 text-2xl font-semibold">{register ? text("创建 GoldAgent 账户", "Create a GoldAgent account") : text("登录 GoldAgent", "Log in to GoldAgent")}</h1>
      <p className="mt-2 text-sm text-muted">{text("Demo 模式可直接使用；生产模式通过 JWT 隔离用户数据。", "Demo mode works immediately; production mode isolates user data with JWT authentication.")}</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block text-sm">{text("邮箱", "Email")}<input aria-label={text("邮箱", "Email")} type="email" required value={email} onChange={event => setEmail(event.target.value)} className="mt-2 w-full rounded border border-line bg-canvas p-3" /></label>
        <label className="block text-sm">{text("密码", "Password")}<input aria-label={text("密码", "Password")} type="password" minLength={8} required value={password} onChange={event => setPassword(event.target.value)} className="mt-2 w-full rounded border border-line bg-canvas p-3" /></label>
        <button disabled={busy} className="w-full rounded bg-gold p-3 font-medium text-black disabled:opacity-50">{busy ? text("处理中…", "Processing…") : register ? text("注册", "Register") : text("登录", "Log in")}</button>
      </form>
      {error && <p className="mt-3 text-sm text-negative">{error}</p>}
      <button onClick={() => setRegister(value => !value)} className="mt-4 text-sm text-gold">{register ? text("已有账户？登录", "Already have an account? Log in") : text("没有账户？注册", "Need an account? Register")}</button>
    </div>
  </div>;
}
