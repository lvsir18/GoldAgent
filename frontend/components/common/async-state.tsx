"use client";

import { useLanguage } from "@/i18n/language";

export function LoadingState({ label }: { label?: string }) {
  const { text } = useLanguage();
  return <div className="card animate-pulse p-6 text-sm text-muted">{label ?? text("正在加载", "Loading")}…</div>;
}
export function EmptyState({ title, detail }: { title: string; detail?: string }) { return <div className="card p-8 text-center"><div className="font-medium">{title}</div>{detail && <p className="mt-2 text-sm text-muted">{detail}</p>}</div>; }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  const { text } = useLanguage();
  return <div className="card border-negative/40 p-6"><div className="font-medium text-negative">{text("请求失败", "Request failed")}</div><p className="text-sm text-muted">{message}</p>{retry && <button onClick={retry} className="focus-ring rounded bg-gold px-3 py-2 text-sm text-black">{text("重试", "Retry")}</button>}</div>;
}
