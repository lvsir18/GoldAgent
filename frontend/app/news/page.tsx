"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { newsApi } from "@/services/api/domain";
import { PageHeading } from "@/components/common/page-heading";
import { ErrorState, LoadingState } from "@/components/common/async-state";
import { useLanguage } from "@/i18n/language";

export default function NewsPage() {
  const { locale, text } = useLanguage();
  const [query, setQuery] = useState("黄金 美联储 美元");
  const q = useQuery({ queryKey: ["news", query], queryFn: () => newsApi.list(query) });
  const dateLocale = locale === "zh" ? "zh-CN" : "en-US";

  return <div>
    <PageHeading
      eyebrow="REAL-TIME SEARCH"
      title={text("黄金新闻", "Gold News")}
      description={text(
        "优先展示最近 72 小时的新闻，数量不足时补充最近 14 天内容。",
        "Prioritizes the last 72 hours and expands to 14 days when needed.",
      )}
    />
    <input
      value={query}
      onChange={event => setQuery(event.target.value)}
      aria-label={text("新闻搜索词", "News search query")}
      className="mb-4 w-full max-w-xl rounded border border-line bg-surface p-3"
    />
    {q.isLoading
      ? <LoadingState label={text("搜索最新新闻", "Searching latest news")} />
      : q.isError
        ? <ErrorState message={(q.error as Error).message} />
        : <div className="grid gap-3 lg:grid-cols-2">
          {q.data?.articles.map((article: any, index: number) => <article key={index} className="card p-5">
            <div className="flex flex-wrap gap-x-2 text-xs text-gold">
              <span>{article.source}</span>
              <span aria-hidden="true">·</span>
              <time dateTime={article.published_at}>
                {new Date(article.published_at).toLocaleString(dateLocale)}
              </time>
            </div>
            <h2 className="mt-2 font-medium">{article.title}</h2>
            <p className="mt-2 line-clamp-4 text-sm leading-6 text-muted">{article.summary}</p>
            {article.url && <a href={article.url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-sm text-gold">
              {text("查看来源", "View source")}
            </a>}
          </article>)}
        </div>}
  </div>;
}
