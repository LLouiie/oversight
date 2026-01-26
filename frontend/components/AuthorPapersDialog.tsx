import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Paper = {
  paper_id: string;
  title: string;
  abstract: string;
  source?: string | null;
  link?: string | null;
  paper_date?: string | null;
};

export function AuthorPapersDialog({
  open,
  authorName,
  onClose,
}: {
  open: boolean;
  authorName: string;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);

  const authorHref = useMemo(() => {
    if (!authorName) return "";
    return `/author/${encodeURIComponent(authorName)}`;
  }, [authorName]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open || !authorName) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setPapers([]);

    fetch(`/api/author/papers?name=${encodeURIComponent(authorName)}`, { signal: controller.signal })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const msg = typeof data?.error === "string" ? data.error : "请求失败";
          throw new Error(msg);
        }
        return data;
      })
      .then((data) => {
        setPapers(Array.isArray(data?.results) ? data.results : []);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : "请求失败");
      })
      .finally(() => {
        if (controller.signal.aborted) return;
        setLoading(false);
      });

    return () => controller.abort();
  }, [open, authorName]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <button type="button" className="absolute inset-0 bg-black/40" onClick={onClose} aria-label="关闭弹窗背景" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={authorName ? `${authorName} 论文列表` : "作者论文列表"}
        className="relative w-full max-w-4xl overflow-hidden rounded-2xl border border-base-300 bg-base-100 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-base-300 bg-base-200/40 px-6 py-4">
          <div className="min-w-0">
            <div className="text-xs opacity-70">作者</div>
            <div className="truncate text-lg font-bold">{authorName || "—"}</div>
            <div className="mt-1 text-sm opacity-70">该作者在我们数据库中的全部论文</div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {authorName && (
              <Link href={authorHref} target="_blank" rel="noreferrer" className="btn btn-sm btn-outline">
                在新标签页打开
              </Link>
            )}
            <button type="button" className="btn btn-sm btn-ghost" onClick={onClose}>
              关闭
            </button>
          </div>
        </div>

        <div className="max-h-[70vh] overflow-y-auto px-6 py-5">
          {loading && (
            <div className="card bg-base-200/50 border border-base-300/50">
              <div className="card-body">
                <div className="flex items-center gap-3">
                  <span className="loading loading-spinner loading-sm" />
                  <span className="text-sm opacity-70">加载中…</span>
                </div>
              </div>
            </div>
          )}

          {!loading && error && (
            <div className="alert alert-error">
              <span className="text-sm">{error}</span>
            </div>
          )}

          {!loading && !error && papers.length === 0 && (
            <div className="card bg-base-200/50 border border-base-300/50">
              <div className="card-body">
                <div className="text-sm opacity-70">没有找到该作者的论文。</div>
              </div>
            </div>
          )}

          {!loading && !error && papers.length > 0 && (
            <div className="flex flex-col gap-4">
              <div className="text-sm opacity-70">共 {papers.length} 篇</div>
              {papers.map((p) => (
                <div
                  key={p.paper_id}
                  className="card bg-base-200/50 border border-base-300/50 hover:bg-base-200 transition-all duration-200"
                >
                  <div className="card-body p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h3 className="mb-1 text-base font-bold text-primary">
                          <a href={p.link || "#"} target="_blank" rel="noreferrer" className="hover:underline">
                            {p.title}
                          </a>
                        </h3>
                        <div className="flex flex-wrap items-center gap-3 text-xs text-base-content/70">
                          <span className="badge badge-sm badge-outline font-medium">{p.source || "Unknown"}</span>
                          {p.paper_date && <span>{new Date(p.paper_date).toLocaleDateString()}</span>}
                        </div>
                      </div>
                    </div>
                    <p className="mt-3 text-sm leading-relaxed opacity-80">{p.abstract}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
