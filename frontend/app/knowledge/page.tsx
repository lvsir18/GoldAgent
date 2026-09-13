"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Trash2 } from "lucide-react";
import { knowledgeApi } from "@/services/api/domain";
import { PageHeading } from "@/components/common/page-heading";
import { useLanguage } from "@/i18n/language";

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
    if (!window.confirm(text(`确定删除“${document.filename}”及其全部分块吗？`, `Delete “${document.filename}” and all of its chunks?`))) return;
    remove.mutate(document.id);
  };

  const search = async (event: FormEvent) => {
    event.preventDefault();
    setResults(await knowledgeApi.search(query));
  };

  return (
    <div>
      <PageHeading
        eyebrow="LONG-TERM KNOWLEDGE"
        title={text("金融知识库", "Financial Knowledge Base")}
        description={text(
          "上传 PDF、Markdown 或 TXT；文档会分块并持久化 Embedding。删除文档时会同步删除其全部分块。",
          "Upload PDF, Markdown, or TXT files. Documents are chunked and embedded persistently; deleting a document also removes all chunks.",
        )}
      />

      <section className="card p-5">
        <div className="flex flex-wrap items-center gap-3">
          <input type="file" accept=".pdf,.md,.txt" onChange={event => setFile(event.target.files?.[0] ?? null)} className="text-sm" />
          <button disabled={!file || upload.isPending} onClick={() => upload.mutate()} className="focus-ring rounded bg-gold px-4 py-2 text-sm text-black disabled:opacity-40">
            {upload.isPending ? text("正在索引…", "Indexing…") : text("上传并索引", "Upload and index")}
          </button>
          {upload.isError && <span className="text-sm text-negative">{upload.error.message}</span>}
        </div>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <h2 className="font-medium">{text("已上传文档", "Documents")}</h2>
          <div className="mt-3 space-y-2">
            {documents.isLoading && <p className="text-sm text-muted">{text("正在加载…", "Loading…")}</p>}
            {documents.isError && <p className="text-sm text-negative">{documents.error.message}</p>}
            {documents.data?.length === 0 && <p className="rounded border border-dashed border-line p-4 text-sm text-muted">{text("尚未上传文档", "No documents uploaded yet")}</p>}
            {documents.data?.map((document: KnowledgeDocument) => (
              <div key={document.id} className="flex items-center gap-3 rounded border border-line p-3">
                <FileText className="shrink-0 text-gold" size={18} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium" title={document.filename}>{document.filename}</div>
                  <div className="text-xs text-muted">
                    {document.status} · {document.metadata?.chunk_count ?? 0} {text("个分块", "chunks")} · {document.metadata?.embedding_provider ?? "—"}
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
            {remove.isError && <p className="text-sm text-negative">{remove.error.message}</p>}
          </div>
        </div>

        <div className="card p-5">
          <h2 className="font-medium">{text("检索测试", "Retrieval test")}</h2>
          <form onSubmit={search} className="mt-3 flex gap-2">
            <input value={query} onChange={event => setQuery(event.target.value)} aria-label={text("知识库查询", "Knowledge query")} className="focus-ring flex-1 rounded border border-line bg-canvas p-2" />
            <button className="focus-ring rounded bg-gold px-4 text-black">{text("检索", "Search")}</button>
          </form>
          <div className="mt-4 space-y-2">
            {results.map(result => (
              <article key={result.chunk_id} className="rounded border border-line p-3">
                <div className="text-xs text-gold">Knowledge Base · score {result.score.toFixed(3)}</div>
                <p className="mt-2 text-sm text-muted">{result.content}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
