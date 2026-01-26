import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { getMockPapersByFirstAuthor, type Paper } from "../../lib/mockPapers";

const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

export default function AuthorPapersPage() {
  const router = useRouter();

  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof window === "undefined") return "dark";
    const saved = window.localStorage.getItem("oversight_theme");
    return saved === "light" ? "light" : "dark";
  });

  useIsomorphicLayoutEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", theme);
      window.localStorage.setItem("oversight_theme", theme);
    }
  }, [theme]);

  const authorName = useMemo(() => {
    const raw = router.query.author;
    if (!raw) return "";
    const value = Array.isArray(raw) ? raw[0] : raw;
    try {
      return decodeURIComponent(value);
    } catch {
      return value;
    }
  }, [router.query.author]);

  const papers: Paper[] = useMemo(() => {
    if (!authorName) return [];
    return getMockPapersByFirstAuthor(authorName);
  }, [authorName]);

  const backTo = useMemo(() => {
    const raw = router.query.from;
    if (!raw) return "/";
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (!value) return "/";
    try {
      const decoded = decodeURIComponent(value);
      return decoded.startsWith("/") ? decoded : "/";
    } catch {
      return "/";
    }
  }, [router.query.from]);

  return (
    <div className="min-h-screen bg-base-100 font-sans text-base-content">
      <Head>
        <title>{authorName ? `${authorName} - Author` : "Author"} | Oversight</title>
        <meta name="description" content="Author papers list" />
      </Head>

      <header className="border-b border-base-300 bg-base-200/50 backdrop-blur sticky top-0 z-50">
        <div className="mx-auto flex w-full max-w-[1200px] items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-primary text-primary-content font-bold">
              O
            </div>
            <h1 className="text-xl font-bold">Oversight</h1>
          </div>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => router.push(backTo)}>
            Back to search
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1200px] px-6 py-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold">
              {authorName ? authorName : "Author"}
            </h2>
            <p className="mt-1 text-sm opacity-70">
              All papers by this author in our database
            </p>
          </div>
        </div>

        <div className="mt-8">
          {papers.length === 0 && (
            <div className="card bg-base-200/50 border border-base-300/50">
              <div className="card-body">
                <div className="text-sm opacity-70">
                  No papers found for this author.
                </div>
              </div>
            </div>
          )}

          {papers.length > 0 && (
            <div className="flex flex-col gap-4">
              <div className="text-sm opacity-70">{papers.length} papers</div>
              {papers.map((p) => (
                <div
                  key={p.paper_id}
                  className="card bg-base-200/50 border border-base-300/50 hover:bg-base-200 transition-all duration-200"
                >
                  <div className="card-body p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="text-base font-bold text-primary mb-1">
                          <a
                            href={p.link || "#"}
                            target="_blank"
                            rel="noreferrer"
                            className="hover:underline"
                          >
                            {p.title}
                          </a>
                        </h3>
                        <div className="flex flex-wrap items-center gap-3 text-xs text-base-content/70">
                          <span className="badge badge-sm badge-outline font-medium">
                            {p.source || "Unknown"}
                          </span>
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
      </main>
    </div>
  );
}
