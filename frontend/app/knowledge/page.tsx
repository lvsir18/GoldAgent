"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Trash2 } from "lucide-react";
import { knowledgeApi } from "@/services/api/domain";
import { PageHeading } from "@/components/common/page-heading";
import { useLanguage } from "@/i18n/language";
import { userError } from "@/lib/presentation";

type KnowledgeDocument = {
  id: string;
  filename: string;
  status: string;
  metadata?: { chunk_count?: number; embedding_provider?: string };
};

export default function KnowledgePage() {
  const { text } = useLanguage();
  const queryClient = useQueryClient();
  const documents = useQuery({ queryKey: ["documents"], queryFn: knowledgeApi.list });
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState("美联储加息如何影响黄金");
  const [results, setResults] = useState<any[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  useEffect(() => { const chunk = new URLSearchParams(window.location.search).get("chunk"); if (chunk) knowledgeApi.chunk(chunk).then(item => { setResults([item]); setSearched(true); }).catch(e => setSearchError(e.message)); }, []);

  const upload = useMutation({
    mutationFn: () => knowledgeApi.upload(file!),
    onSuccess: () => {
      setFile(null);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => knowledgeApi.remove(id),
    onMutate: id => setDeletingId(id),
    onSuccess: (_data, id) => {
      setResults(old => old.filter(item => item.document_id !== id));
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onSettled: () => setDeletingId(null),
  });

  const deleteDocument = (document: KnowledgeDocument) => {
    if (!window.confirm(text(`确定删除“${document.filename}”及其可检索内容吗？`, `Delete “${document.filename}” and its searchable content?`))) return;
    remove.mutate(document.id);
  };

  const search = async (event: FormEvent) => {
    event.preventDefault();
    setSearching(true); setSearchError(""); setSearched(true);
    try { setResults(await knowledgeApi.search(query)); }
    catch(e) { setSearchError((e as Error).message); }
    finally { setSearching(false); }
  };

  return (
    <div>
      <PageHeading
        eyebrow="LONG-TERM KNOWLEDGE"
        title={text("金融知识库", "Financial Knowledge Base")}
        description={text(
          "上传 PDF、Markdown 或 TXT 后，可在对话中查阅并引用；删除后将不再检索这份资料。",
          "Upload PDF, Markdown or TXT files to reference in conversations. Deleted documents will no longer appear in searches.",
        )}
      />

      <section className="card p-5">
        <div className="flex flex-wrap items-center gap-3">
          <input type="file" accept=".pdf,.md,.txt" onChange={event => setFile(event.target.files?.[0] ?? null)} className="text-sm" />
          <button disabled={!file || upload.isPending} onClick={() => upload.mutate()} className="focus-ring rounded bg-gold px-4 py-2 text-sm text-black disabled:opacity-40">
            {upload.isPending ? text("正在处理…", "Processing…") : text("上传文档", "Upload document")}
          </button>
          {upload.isError && <span className="text-sm text-negative">{userError(upload.error, text)}</span>}
        </div>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <h2 className="font-medium">{text("已上传文档", "Documents")}</h2>
          <div className="mt-3 space-y-2">
            {documents.isLoading && <p className="text-sm text-muted">{text("正在加载…", "Loading…")}</p>}
            {documents.isError && <p className="text-sm text-negative">{userError(documents.error, text)}</p>}
            {documents.data?.length === 0 && <p className="rounded border border-dashed border-line p-4 text-sm text-muted">{text("尚未上传文档", "No documents uploaded yet")}</p>}
            {documents.data?.map((document: KnowledgeDocument) => (
              <div key={document.id} className="flex items-center gap-3 rounded border border-line p-3">
                <FileText className="shrink-0 text-gold" size={18} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium" title={document.filename}>{document.filename}</div>
                  <div className="text-xs text-muted">
                    {document.status === "ready" ? text("可在对话中引用", "Ready to reference in chat") : document.status === "failed" ? text("处理未完成，请重新上传", "Processing failed; upload again") : text("正在整理文档", "Preparing document")}
                  </div>
                </div>
                <button
                  onClick={() => deleteDocument(document)}
                  disabled={remove.isPending}
                  className="focus-ring rounded-lg p-2 text-muted hover:bg-negative/10 hover:text-negative disabled:opacity-40"
                  aria-label={text(`删除文档：${document.filename}`, `Delete document: ${document.filename}`)}
                  title={text("删除文档", "Delete document")}
                >
                  {deletingId === document.id ? <Loader2 className="animate-spin" size={17} /> : <Trash2 size={17} />}
                </button>
              </div>
            ))}
            {remove.isError && <p className="text-sm text-negative">{userError(remove.error, text)}</p>}
          </div>
        </div>

        <div className="card p-5">
          <h2 className="font-medium">{text("查找文档内容", "Find document content")}</h2>
          <form onSubmit={search} className="mt-3 flex gap-2">
            <input value={query} onChange={event => setQuery(event.target.value)} aria-label={text("知识库查询", "Knowledge query")} className="focus-ring flex-1 rounded border border-line bg-canvas p-2" />
            <button disabled={searching || query.trim().length < 2} className="focus-ring rounded bg-gold px-4 text-black disabled:opacity-50">{searching ? text("检索中…", "Searching…") : text("检索", "Search")}</button>
          </form>
          <div className="mt-4 space-y-2">
            {searchError && <p role="alert" className="text-sm text-negative">{userError(searchError, text)}</p>}
            {searched && !searching && !searchError && results.length === 0 && <p className="text-sm text-muted">{text("资料不足：未找到相关内容，不会用无关文档凑答案。", "Insufficient evidence: no relevant content was found.")}</p>}
            {results.map(result => (
              <article key={result.chunk_id} className="rounded border border-line p-3">
                <div className="text-xs text-gold">{result.metadata?.filename} · {text("第", "Page")} {result.metadata?.page ?? "—"} {text("页", "")}</div>
                <p className="mt-2 text-sm text-muted">{result.content}</p>
                <Link className="mt-3 inline-block text-xs text-gold" href={`/chat?q=${encodeURIComponent(`请基于知识库中的《${result.metadata?.filename ?? "这份资料"}》回答：${query}。请引用相关原文并标明页码。`)}`}>{text("基于这份资料研究 →", "Research with this document →")}</Link>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
