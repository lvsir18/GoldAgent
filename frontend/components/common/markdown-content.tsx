"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="min-w-0 break-words text-sm leading-7">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="mb-3 mt-5 text-xl font-semibold first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-2 mt-5 text-lg font-semibold first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-2 mt-4 font-semibold first:mt-0">{children}</h3>,
          p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
          blockquote: ({ children }) => <blockquote className="my-3 border-l-2 border-gold pl-3 text-muted">{children}</blockquote>,
          a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="text-gold underline underline-offset-2 hover:text-ink">{children}</a>,
          hr: () => <hr className="my-4 border-line" />,
          table: ({ children }) => <div className="my-3 overflow-x-auto"><table className="w-full border-collapse text-left text-xs">{children}</table></div>,
          th: ({ children }) => <th className="border border-line bg-surface px-3 py-2 font-medium">{children}</th>,
          td: ({ children }) => <td className="border border-line px-3 py-2 align-top">{children}</td>,
          code: ({ className, children }) => className
            ? <code className={`${className} block overflow-x-auto rounded-lg bg-black/30 p-3 text-xs leading-5`}>{children}</code>
            : <code className="rounded bg-black/30 px-1.5 py-0.5 text-xs text-gold">{children}</code>,
          pre: ({ children }) => <pre className="my-3 overflow-x-auto whitespace-pre-wrap">{children}</pre>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
