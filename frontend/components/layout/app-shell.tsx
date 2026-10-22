"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { BarChart3, Bot, Brain, FileText, FlaskConical, Gauge, Landmark, Newspaper, Settings, TrendingUp, ListChecks, Menu, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";
import { useLanguage } from "@/i18n/language";
import { authApi } from "@/services/api/auth";
import { useAuthStore } from "@/stores/auth";
import { useChatStore } from "@/stores/chat";

const navigation = [
  ["/dashboard", "仪表盘", "Dashboard", Gauge],
  ["/analysis", "市场分析", "Analysis", BarChart3],
  ["/chat", "Agent 对话", "Agent Chat", Bot],
  ["/forecast", "价格预测", "Forecast", TrendingUp],
  ["/backtest", "策略回测", "Backtest", FlaskConical],
  ["/portfolio", "投资组合", "Portfolio", Landmark],
  ["/news", "市场新闻", "News", Newspaper],
  ["/reports", "分析报告", "Reports", FileText],
  ["/knowledge", "知识库", "Knowledge", Brain],
  ["/tasks", "研究任务", "Research tasks", ListChecks],
  ["/settings", "设置", "Settings", Settings],
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [more, setMore] = useState(false);
  const queryClient = useQueryClient();
  const isChat = pathname.startsWith("/chat");
  const { locale, setLocale, text } = useLanguage();
  const { tokens, hydrated, hydrate, setTokens } = useAuthStore();
  const chatRunning = useChatStore(state => state.busy);
  const running = <Loader2 role="img" aria-label={text("Agent 正在运行", "Agent running")} size={14} className="shrink-0 animate-spin text-gold"/>;

  useEffect(() => hydrate(), [hydrate]);

  const logout = async () => {
    useChatStore.getState().reset();
    if (tokens?.refresh_token) await authApi.logout(tokens.refresh_token).catch(() => undefined);
    setTokens(null);
    queryClient.clear();
    window.location.assign("/dashboard");
  };

  return (
    <div className="min-h-dvh md:grid md:h-dvh md:grid-cols-[230px_minmax(0,1fr)] md:overflow-hidden">
      <aside className="hidden h-dvh overflow-y-auto border-r border-line bg-surface p-4 md:block">
        <div className="mb-8 px-3">
          <div className="text-xl font-semibold tracking-tight text-gold">GoldAgent</div>
          <div className="text-xs text-muted">AI MARKET INTELLIGENCE</div>
        </div>
        <nav className="space-y-1">
          {navigation.map(([href, zh, en, Icon]) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted hover:bg-canvas hover:text-ink",
                pathname.startsWith(href) && "bg-canvas text-gold",
              )}
            >
              <Icon size={17}/>{text(zh, en)}
              {href === "/chat" && chatRunning && running}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 md:flex md:h-dvh md:flex-col md:overflow-hidden">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between border-b border-line bg-canvas/95 px-4 backdrop-blur md:static md:px-7">
          <span className="font-medium">GoldAgent</span>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-line bg-surface p-0.5" aria-label={text("语言选择", "Language selector")}>
              <button
                onClick={() => setLocale("zh")}
                className={cn("rounded-md px-2.5 py-1 text-xs", locale === "zh" ? "bg-gold text-black" : "text-muted")}
              >
                中文
              </button>
              <button
                onClick={() => setLocale("en")}
                className={cn("rounded-md px-2.5 py-1 text-xs", locale === "en" ? "bg-gold text-black" : "text-muted")}
              >
                EN
              </button>
            </div>
            <span className="hidden rounded-full border border-line px-3 py-1 text-xs text-muted sm:inline">
              {text("仅供参考", "Advisory only")}
            </span>
            {hydrated && (tokens ? (
              <button onClick={logout} className="rounded border border-line px-3 py-1 text-xs text-muted">
                {text("退出", "Log out")}
              </button>
            ) : (
              <Link href="/login" className="rounded border border-line px-3 py-1 text-xs text-gold">
                {text("登录", "Log in")}
              </Link>
            ))}
          </div>
        </header>
        <main className={cn(
          "min-w-0 p-4 pb-24 md:p-7",
          isChat && "h-[calc(100dvh-8rem)] overflow-hidden pb-4 md:h-auto md:flex-1 md:p-4",
          !isChat && "md:flex-1 md:overflow-y-auto",
        )}>
          {children}
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 flex overflow-x-auto border-t border-line bg-surface p-2 md:hidden">
        {[navigation[0], navigation[2], navigation[5], navigation[6]].map(([href, zh, en, Icon]) => (
          <Link
            key={href}
            href={href}
            className={cn("min-w-0 flex-1 rounded-lg p-2 text-center text-[11px] text-muted", pathname.startsWith(href) && "text-gold")}
          >
            <Icon className="mx-auto mb-1" size={17}/>{text(zh, en)}
            {href === "/chat" && chatRunning && <span className="flex justify-center">{running}</span>}
          </Link>
        ))}
        <button aria-expanded={more} onClick={() => setMore(v => !v)} className="flex-1 rounded-lg p-2 text-center text-[11px] text-muted"><Menu className="mx-auto mb-1" size={17}/>{text("更多", "More")}</button>
      </nav>
      {more && <div role="dialog" aria-modal="true" aria-label={text("全部功能", "All features")} className="fixed inset-0 z-40 flex items-end bg-black/70 md:hidden" onClick={() => setMore(false)}><div className="w-full rounded-t-2xl border border-line bg-surface p-5 pb-8" onClick={e => e.stopPropagation()}><div className="mb-4 flex justify-between"><h2>{text("全部功能", "All features")}</h2><button onClick={() => setMore(false)} aria-label={text("关闭", "Close")}><X size={20}/></button></div><div className="grid grid-cols-3 gap-3">{navigation.map(([href,zh,en,Icon]) => <Link key={href} href={href} onClick={() => setMore(false)} className="rounded-lg border border-line p-3 text-center text-xs"><Icon className="mx-auto mb-2 text-gold" size={20}/>{text(zh,en)}</Link>)}</div></div></div>}
    </div>
  );
}
