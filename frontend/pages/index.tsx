import { useEffect, useMemo, useRef, useState } from "react";
import Head from "next/head";
import { DateRangePicker } from "../components/DateRangePicker";
import { type Paper } from "../lib/mockPapers";

function tokenizeQuery(text: string): string[] {
  const rawTokens = text
    .toLowerCase()
    .replace(/[^\w\s-]/g, " ")
    .split(/[\s,]+/g)
    .map((t) => t.trim())
    .filter(Boolean);

  const unique = new Set<string>();
  for (const t of rawTokens) unique.add(t);
  return Array.from(unique);
}

type QueryGroupResult = {
  branch_id: string;
  status?: string;
  search_query?: string | null;
  error?: string | null;
  results?: Paper[];
};

type AgentMeta = {
  enabled: boolean;
  round1_status?: string;
  partial_success?: boolean;
  model?: string;
  base_url?: string;
  error?: string;
  debug?: {
    round1_output?: Record<string, unknown>;
  };
};

function branchLabel(branchId: string): string {
  const m = /^branch_(\d+)$/.exec(branchId);
  if (m) return `Direction ${Number(m[1]) + 1}`;
  if (branchId === "branch_a") return "Branch A";
  if (branchId === "branch_b") return "Branch B";
  if (branchId === "branch_c") return "Branch C";
  return branchId;
}

function PaperCard({
  p,
  navigateToAbstract,
  openAuthorPage,
}: {
  p: Paper;
  navigateToAbstract: (paper: Paper) => void;
  openAuthorPage: (authorName: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const abstractRef = useRef<HTMLParagraphElement | null>(null);
  const [canToggle, setCanToggle] = useState(false);

  const firstAuthorName = useMemo(() => {
    if (p.first_author && p.first_author.trim()) return p.first_author.trim();
    if (!p.authors) return null;
    const firstGroup = p.authors.split(";")[0]?.trim() ?? "";
    if (!firstGroup) return null;
    const withoutParens = firstGroup.replace(/\([^)]*\)/g, "").trim();
    const beforeAffiliation = withoutParens.split(",")[0]?.trim() ?? "";
    return beforeAffiliation || null;
  }, [p.authors, p.first_author]);

  // Extract affiliation from authors string
  // Supports formats: "Name (Affiliation)" or "Name, Affiliation"
  const affiliation = useMemo(() => {
    if (!p.authors) return null;
    
    // Try extracting from parentheses first
    const parenMatch = p.authors.match(/\(([^)]+)\)/);
    if (parenMatch) return parenMatch[1];

    // Fallback: assume "Name, Affiliation" format
    // Take first author group (separated by ;)
    const firstAuthorGroup = p.authors.split(';')[0];
    const parts = firstAuthorGroup.split(',');
    if (parts.length > 1) {
      return parts[parts.length - 1].trim();
    }
    
    return null;
  }, [p.authors]);

  useEffect(() => {
    if (expanded) return;

    const el = abstractRef.current;
    if (!el) return;

    const checkOverflow = () => {
      setCanToggle(el.scrollHeight > el.clientHeight + 1);
    };

    checkOverflow();
    window.addEventListener("resize", checkOverflow);
    return () => window.removeEventListener("resize", checkOverflow);
  }, [p.abstract, expanded]);

  return (
    <div className="card bg-base-200/50 border border-base-300/50 hover:bg-base-200 transition-all duration-200">
      <div className="card-body p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="card-title text-lg font-bold text-primary mb-1">
               <a href={p.link || '#'} target="_blank" rel="noreferrer" className="hover:underline">{p.title}</a>
            </h2>
            <div className="flex flex-wrap items-center gap-3 text-xs text-base-content/70 mb-3">
               <span className="badge badge-sm badge-outline font-medium">{p.source || 'Unknown'}</span>
               {p.paper_date && <span>{new Date(p.paper_date).toLocaleDateString()}</span>}
              {firstAuthorName && (
                <>
                  <span className="badge badge-sm badge-outline font-medium">First Author</span>
                  <button
                    type="button"
                    className="badge badge-sm badge-outline font-medium text-base-content/70 border-base-content/20 cursor-pointer hover:text-primary hover:border-primary/40 transition-colors"
                    title={`Open a new tab for ${firstAuthorName}'s papers`}
                    onClick={() => openAuthorPage(firstAuthorName)}
                  >
                    {firstAuthorName}
                  </button>
                </>
              )}
               {affiliation && (
                 <span className="flex items-center gap-1 max-w-[200px] truncate" title={affiliation}>
                   <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
                     <path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 00.281-.14c.186-.096.446-.24.757-.433.62-.384 1.445-.966 2.274-1.765C15.302 14.988 17 12.493 17 9A7 7 0 103 9c0 3.492 1.698 5.988 3.355 7.584a13.731 13.731 0 002.273 1.765 11.842 11.842 0 00.976.544l.062.029.006.003.002.001.001.001zm-1.602-5.74l-.457-.142a1 1 0 01-.65-1.157l.18-1.256-.474-.438a1 1 0 01.378-1.658l1.096-.34 1.493-2.618a1 1 0 011.758 0l1.493 2.618 1.096.34a1 1 0 01.378 1.658l-.475.438.181 1.256a1 1 0 01-.65 1.157l-.458.142a2.5 2.5 0 00-1.638 1.638l-.142.457a1 1 0 01-1.916 0l-.142-.457a2.5 2.5 0 00-1.638-1.638z" clipRule="evenodd" />
                   </svg>
                   {affiliation}
                 </span>
               )}
               {p.citation_count !== undefined && (
                 <span className="citation-tooltip-wrapper">
                   <span className="flex items-center gap-1">
                     <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
                       <path d="M3.288 4.819A1.5 1.5 0 001 6.095v5.855c0 .518.315.963.769 1.216l7.462 3.865a1 1 0 00.94 0l7.462-3.865a1.375 1.375 0 00.769-1.216V6.095a1.5 1.5 0 00-2.288-1.276l-6.416 3.325-6.416-3.325z" />
                       <path d="M3.288 1.5A1.5 1.5 0 001 2.776v1.168l8.308 4.306 8.308-4.306V2.776a1.5 1.5 0 00-2.288-1.276l-6.416 3.325L3.288 1.5z" />
                     </svg>
                     {p.citation_count}
                   </span>
                   <span className="citation-tooltip-bubble">
                     citation
                   </span>
                 </span>
               )}
               {p.semantic_score !== undefined && (
                 <span className="badge badge-sm badge-secondary font-mono bg-secondary/10 text-secondary border-secondary/20">
                   Score: {p.semantic_score.toFixed(3)}
                 </span>
               )}
            </div>
          </div>
          {p.link && (
            <a href={p.link} target="_blank" rel="noreferrer" className="btn btn-square btn-sm btn-ghost opacity-50 hover:opacity-100">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
            </a>
          )}
        </div>

        <div className="relative">
          <p
            ref={abstractRef}
            className={`text-sm leading-relaxed opacity-80 ${expanded ? "" : "abstract-clamp-4 pr-28"}`}
          >
            {p.abstract}
          </p>
          {!expanded && canToggle && (
            <button type="button" onClick={() => setExpanded(true)} className="abstract-toggle-btn">
              Show more
            </button>
          )}
        </div>

        {expanded && canToggle && (
          <div className="flex justify-end">
            <button type="button" onClick={() => setExpanded(false)} className="abstract-toggle-btn-expanded">
              Show less
            </button>
          </div>
        )}

        <div className="card-actions mt-4 justify-end">
          <button 
            className="btn btn-xs btn-outline"
            onClick={() => navigateToAbstract(p)}
          >
            Find Similar
          </button>
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  const [text, setText] = useState("");
  
  // Lookback Window State
  const [lookbackOption, setLookbackOption] = useState<'any' | 'pastYear' | 'pastMonth' | 'pastWeek' | 'custom'>('any');
  
  // Default to last year -> today
  const [customStartDate, setCustomStartDate] = useState<string>(() => {
      const d = new Date();
      d.setFullYear(d.getFullYear() - 1);
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
  });
  const [customEndDate, setCustomEndDate] = useState<string>(() => {
      const d = new Date();
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
  });

  const [showCustomRange, setShowCustomRange] = useState(false);
  const [rerankEnabled, setRerankEnabled] = useState(false);
  const [rerankMaxInput, setRerankMaxInput] = useState(60);
  const [viewMode, setViewMode] = useState<"subquery" | "rerank">("subquery");

  const [limit, setLimit] = useState<number | 'all' | ''>('all');
  const [sources, setSources] = useState({
    arxiv: true,
    // AI conferences
    ICML: true,
    NeurIPS: true,
    ICLR: true,
    // Systems conferences
    OSDI: true,
    SOSP: true,
    ASPLOS: true,
    ATC: true,
    NSDI: true,
    MLSys: true,
    EuroSys: true,
    VLDB: true
  });
  const [loading, setLoading] = useState(false);
  const lastRequestIdRef = useRef<number>(0);
  const activeRequestControllerRef = useRef<AbortController | null>(null);
  const hasSearchedRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Paper[]>([]);
  const [queryGroups, setQueryGroups] = useState<QueryGroupResult[] | null>(null);
  const [agentMeta, setAgentMeta] = useState<AgentMeta | null>(null);
  
  const [sortBy, setSortBy] = useState<"relevance" | "date">("relevance");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  
  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  function openAuthorPage(authorName: string) {
    const url = `/author/${encodeURIComponent(authorName)}`;
    window.open(url, "_blank", "noopener,noreferrer");
  }

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", theme);
      window.localStorage.setItem("oversight_theme", theme);
    }
  }, [theme]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem("oversight_theme");
    const next = saved === "light" ? "light" : "dark";
    setTheme(next);
  }, []);

  // Reset pagination when search changes
  useEffect(() => {
      setCurrentPage(1);
  }, [text, lookbackOption, limit, sortBy, sortDirection]);

  // Trigger search when time range or sources changes
  useEffect(() => {
    if (hasSearchedRef.current && text.trim()) {
      onSubmit({ preventDefault: () => {} } as React.FormEvent);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lookbackOption, customStartDate, customEndDate, sources]);

  // Conference categories
  const aiConferences = ['ICML', 'NeurIPS', 'ICLR'];
  const systemsConferences = ['OSDI', 'SOSP', 'ASPLOS', 'ATC', 'NSDI', 'MLSys', 'EuroSys', 'VLDB'];

  // Remove timeLabel useMemo as it's no longer needed

  const sortedResults = useMemo(() => {
    let res = [...results];
    
    if (sortBy === "relevance") {
        return res;
    }

    return res.sort((a, b) => {
      if (sortBy === "date") {
        const dateA = a.paper_date ? new Date(a.paper_date).getTime() : 0;
        const dateB = b.paper_date ? new Date(b.paper_date).getTime() : 0;
        return sortDirection === "desc" ? dateB - dateA : dateA - dateB;
      }
      return 0;
    });
  }, [results, sortBy, sortDirection]);

  const hasBranchResults = useMemo(
    () => Array.isArray(queryGroups) && queryGroups.some((g) => (g.results?.length ?? 0) > 0),
    [queryGroups]
  );

  const isAllAISelected = aiConferences.every(conf => sources[conf as keyof typeof sources]);
  const isAllSystemsSelected = systemsConferences.every(conf => sources[conf as keyof typeof sources]);

  function toggleSource(key: keyof typeof sources) {
    setSources((s) => ({ ...s, [key]: !s[key] }));
  }

  function toggleAllAI() {
    const newValue = !isAllAISelected;
    setSources((s) => {
      const updated = { ...s };
      aiConferences.forEach(conf => { updated[conf as keyof typeof sources] = newValue; });
      return updated;
    });
  }

  function toggleAllSystems() {
    const newValue = !isAllSystemsSelected;
    setSources((s) => {
      const updated = { ...s };
      systemsConferences.forEach(conf => { updated[conf as keyof typeof sources] = newValue; });
      return updated;
    });
  }

  async function onSubmit(e: React.FormEvent, overrideText?: string) {
    e.preventDefault();
    const queryText = (overrideText ?? text).trim();
    if (!queryText) return;
    
    setError(null);
    setLoading(true);
    setResults([]);
    hasSearchedRef.current = true;

    // Keep only one in-flight search request to avoid stale-response races.
    activeRequestControllerRef.current?.abort();
    const controller = new AbortController();
    activeRequestControllerRef.current = controller;

    const reqId = Date.now();
    lastRequestIdRef.current = reqId;

    const now = new Date();
    const today = now.toISOString().slice(0, 10);

    const requestBody: Record<string, unknown> = {
      text: queryText,
      sources,
      rerank: rerankEnabled,
      rerank_max_input: rerankMaxInput,
      limit: (() => {
        if (typeof limit === "number" && Number.isFinite(limit) && limit > 0) return Math.max(1, Math.min(100, limit));
        if (limit === "") return 10;
        return 100;
      })(),
    };

    if (lookbackOption === "custom") {
      requestBody.start_date = customStartDate;
      requestBody.end_date = customEndDate;

      const start = new Date(`${customStartDate}T00:00:00`);
      const end = new Date(`${customEndDate}T23:59:59.999`);
      const diffDays = Math.ceil((end.getTime() - start.getTime()) / (24 * 60 * 60 * 1000));
      if (Number.isFinite(diffDays) && diffDays > 0) requestBody.time_window_days = diffDays;
    } else if (lookbackOption !== "any") {
      const days = lookbackOption === "pastYear" ? 365 : lookbackOption === "pastMonth" ? 30 : 7;
      requestBody.time_window_days = days;
      const start = new Date(now);
      start.setDate(start.getDate() - days);
      requestBody.start_date = start.toISOString().slice(0, 10);
      requestBody.end_date = today;
    }

    try {
      const resp = await fetch(`/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
        cache: "no-store",
        signal: controller.signal,
        body: JSON.stringify(requestBody),
      });

      const contentType = resp.headers.get("content-type") || "";
      const payload: any = contentType.includes("application/json") ? await resp.json() : await resp.text();
      let data: Record<string, any> = {};
      if (typeof payload === "string") {
        try {
          data = JSON.parse(payload);
        } catch {
          data = {};
        }
      } else if (payload && typeof payload === "object") {
        data = payload;
      }
      const root = (data && typeof data.data === "object") ? data.data : data;
      const groups: QueryGroupResult[] | null = Array.isArray(root?.query_groups)
        ? root.query_groups
        : (Array.isArray(root?.queryGroups) ? root.queryGroups : null);
      const agent: AgentMeta | null = root?.agent || root?.agent_meta || null;

      if (!resp.ok) {
        if (lastRequestIdRef.current !== reqId) return;
        setQueryGroups(groups);
        setAgentMeta(agent);
        const msg = typeof payload === "string" ? payload : payload?.error || `Request failed: ${resp.status}`;
        throw new Error(msg);
      }

      if (lastRequestIdRef.current !== reqId) return;

      const directResults: Paper[] = Array.isArray(data.results) ? data.results : [];

      let mergedResults: Paper[] = directResults;
      if (mergedResults.length === 0 && groups) {
        const seen = new Set<string>();
        const collected: Paper[] = [];
        for (const g of groups) {
          for (const p of g?.results || []) {
            if (!p?.paper_id) continue;
            if (seen.has(p.paper_id)) continue;
            seen.add(p.paper_id);
            collected.push(p);
          }
        }
        mergedResults = collected;
      }

      if (lookbackOption === "custom") {
        const start = new Date(`${customStartDate}T00:00:00`);
        const end = new Date(`${customEndDate}T23:59:59.999`);
        mergedResults = mergedResults.filter((p) => {
          if (!p.paper_date) return true;
          const d = new Date(p.paper_date);
          if (Number.isNaN(d.getTime())) return true;
          return d >= start && d <= end;
        });
      }

      setResults(mergedResults);
      setQueryGroups(groups);
      setAgentMeta(agent);
    } catch (err: any) {
      if (err?.name === "AbortError") return;
      if (lastRequestIdRef.current !== reqId) return;
      setError(err?.message || String(err));
    } finally {
      if (activeRequestControllerRef.current === controller) {
        activeRequestControllerRef.current = null;
      }
      if (lastRequestIdRef.current === reqId) setLoading(false);
    }
  }

  function navigateToAbstract(paper: Paper) {
    const nextText = (paper.abstract || "").trim() || paper.title;
    setText(nextText);
    setSortBy("relevance");
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setTimeout(() => {
      onSubmit({ preventDefault: () => {} } as React.FormEvent, nextText);
    }, 100);
  }

  return (
    <div data-theme={theme} className="min-h-screen bg-base-100 font-sans text-base-content">
      <Head>
        <title>Oversight - Academic Search</title>
        <meta name="description" content="Embeddings-backed academic paper search" />
      </Head>

      <div className="flex flex-col min-h-screen">
        {/* Header */}
        <header className="border-b border-base-300 bg-base-200/50 backdrop-blur sticky top-0 z-50">
          <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between px-6 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded bg-primary text-primary-content font-bold">
                O
              </div>
              <h1 className="text-xl font-bold">Oversight</h1>
            </div>
            
            <button 
              className="btn btn-sm btn-ghost btn-circle"
              onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
              title={theme === 'dark' ? "Switch to the Light mode" : "Switch to the Dark mode"}
            >
              {theme === 'dark' ? (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
                </svg>
              )}
            </button>
          </div>
        </header>

        {/* Main Layout */}
        <div className="mx-auto grid w-full max-w-[1600px] grid-cols-1 gap-6 px-6 pt-6 md:grid-cols-[300px,1fr]">
          
          {/* Sidebar */}
          <aside className="flex flex-col gap-6 pr-2">
            
            {/* Filters */}
            <div className="rounded-xl bg-base-200 p-4 shadow-sm">
              <h3 className="mb-3 text-sm font-bold uppercase tracking-wider opacity-70">Time Range</h3>
              
              <div className="mt-2">
                <div className="flex flex-wrap gap-2">
                  {[
                      { id: 'any', label: 'Any time' },
                      { id: 'pastYear', label: 'Past year' },
                      { id: 'pastMonth', label: 'Past month' },
                      { id: 'pastWeek', label: 'Past 7 days' },
                  ].map((opt) => (
                      <button
                          key={opt.id}
                          className={`btn btn-sm rounded-full normal-case font-medium ${lookbackOption === opt.id ? 'btn-primary' : 'btn-ghost bg-base-200/50 hover:bg-base-300'}`}
                          onClick={() => { setLookbackOption(opt.id as any); setShowCustomRange(false); }}
                      >
                          {opt.label}
                      </button>
                  ))}

                  <div 
                    className="relative inline-block"
                    onMouseEnter={() => {
                        setLookbackOption('custom'); 
                        setShowCustomRange(true); 
                    }}
                    onMouseLeave={() => {
                        setShowCustomRange(false);
                    }}
                  >
                    <button
                        className={`btn btn-sm rounded-full normal-case font-medium ${lookbackOption === 'custom' ? 'btn-primary' : 'btn-ghost bg-base-200/50 hover:bg-base-300'}`}
                        // Remove onClick toggle since hover handles it, but keep for click support
                        onClick={() => { setLookbackOption('custom'); setShowCustomRange(true); }}
                    >
                        Custom range
                    </button>
                    
                    {showCustomRange && (
                        <div className="absolute top-full left-0 pt-2 z-50">
                            <DateRangePicker 
                                startDate={customStartDate} 
                                endDate={customEndDate} 
                                onChange={(start, end) => {
                                    setCustomStartDate(start);
                                    setCustomEndDate(end);
                                }} 
                            />
                        </div>
                    )}
                  </div>
                </div>
              </div>


            </div>

            <div className="rounded-xl bg-base-200 p-4 shadow-sm">
              <h3 className="mb-4 text-sm font-bold uppercase tracking-wider opacity-70">Settings</h3>
              <div className="form-control">
                <label className="flex cursor-pointer items-center justify-between py-1 hover:bg-base-300/50 p-1 rounded">
                  <span className="text-sm font-medium">Semantic Rerank</span>
                  <input 
                    type="checkbox" 
                    className="toggle toggle-primary toggle-sm" 
                    checked={rerankEnabled} 
                    onChange={() => setRerankEnabled(!rerankEnabled)} 
                  />
                </label>
                {rerankEnabled && (
                  <div className="mt-2 px-1">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-[10px] font-bold opacity-70">Rerank Depth</span>
                      <span className="badge badge-primary badge-sm font-mono text-[10px]">{rerankMaxInput} papers</span>
                    </div>
                    <input 
                      type="range" 
                      min="10" 
                      max="200" 
                      step="10" 
                      value={rerankMaxInput} 
                      onChange={(e) => setRerankMaxInput(parseInt(e.target.value))}
                      className="range range-primary range-xs" 
                    />
                    <div className="flex justify-between text-[8px] opacity-40 px-1">
                      <span>10</span>
                      <span>100</span>
                      <span>200</span>
                    </div>
                  </div>
                )}
                <p className="text-[10px] opacity-50 mt-1 leading-tight">
                  Uses BGE-v2-m3 Cross-Encoder for deep semantic re-ranking (High VRAM usage).
                </p>
              </div>
            </div>

            <div className="rounded-xl bg-base-200 p-4 shadow-sm">
              <h3 className="mb-4 text-sm font-bold uppercase tracking-wider opacity-70">Sources</h3>
              
              <div className="space-y-3">
                <label className="flex cursor-pointer items-center gap-3 rounded hover:bg-base-300/50 p-1">
                  <input type="checkbox" className="checkbox checkbox-sm checkbox-primary" checked={sources.arxiv} onChange={() => toggleSource("arxiv")} />
                  <span className="text-sm">arXiv</span>
                </label>

                <div className="divider my-1"></div>
                
                <div className="space-y-1">
                  <label className="flex cursor-pointer items-center gap-3 py-1 hover:bg-base-300/50 p-1 rounded">
                    <input 
                      type="checkbox" 
                      className="checkbox checkbox-xs checkbox-primary" 
                      checked={isAllAISelected}
                      onChange={toggleAllAI}
                    />
                    <span className="text-sm">AI conferences</span>
                  </label>
                  <div className="pl-6 space-y-1">
                    {aiConferences.map(conf => (
                      <label key={conf} className="flex cursor-pointer items-center gap-3 hover:bg-base-300/50 p-1 rounded">
                        <input
                          type="checkbox"
                          className="checkbox checkbox-xs checkbox-primary"
                          checked={sources[conf as keyof typeof sources]}
                          onChange={() => toggleSource(conf as keyof typeof sources)}
                        />
                        <span className="text-sm opacity-80">{conf}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="divider my-1"></div>

                <div className="space-y-1">
                  <label className="flex cursor-pointer items-center gap-3 py-1 hover:bg-base-300/50 p-1 rounded">
                    <input 
                      type="checkbox" 
                      className="checkbox checkbox-xs checkbox-primary" 
                      checked={isAllSystemsSelected}
                      onChange={toggleAllSystems}
                    />
                    <span className="text-sm">Systems conferences</span>
                  </label>
                  <div className="pl-6 space-y-1">
                    {systemsConferences.map(conf => (
                      <label key={conf} className="flex cursor-pointer items-center gap-3 hover:bg-base-300/50 p-1 rounded">
                        <input
                          type="checkbox"
                          className="checkbox checkbox-xs checkbox-primary"
                          checked={sources[conf as keyof typeof sources]}
                          onChange={() => toggleSource(conf as keyof typeof sources)}
                        />
                        <span className="text-sm opacity-80">{conf}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex flex-col gap-4 overflow-hidden h-full">
            
            {/* Search Box Area */}
            <div className="flex-none">
              <div className="relative group">
                <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/50 to-secondary/50 rounded-2xl opacity-20 group-hover:opacity-40 transition duration-500 blur-sm"></div>
                <div className="relative bg-base-100 rounded-2xl overflow-hidden shadow-sm border border-base-200">
                  <form onSubmit={onSubmit}>
                    <textarea
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          onSubmit(e);
                        }
                      }}
                      placeholder="e.g. 'Efficient attention mechanisms for long sequences' or paste a paper abstract..."
                      className="w-full bg-transparent text-base placeholder:opacity-40 focus:outline-none min-h-[120px] resize-none py-4 px-5"
                    />
                  </form>
                  
                  {/* Footer with Search Button and Info */}
                  <div className="flex items-center justify-between px-4 py-3 bg-base-200/50 border-t border-base-200/50 backdrop-blur-sm">
                    <div className="flex items-center gap-2 text-sm text-base-content/60 max-w-[70%]">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 flex-none">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
                      </svg>
                      <span className="truncate">Describe your research interest or paste an abstract to find similar papers</span>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => onSubmit(e as any)}
                      className="btn btn-primary btn-sm rounded-lg px-6 shadow-md shadow-primary/20 h-9 font-bold tracking-wide"
                      disabled={loading}
                    >
                      {loading ? (
                          <>
                              <span className="loading loading-spinner loading-xs mr-2"></span>
                              Searching...
                          </>
                      ) : (
                          <>
                              SEARCH
                          </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {error && (
              <div className="alert alert-error flex-none">
                <span className="text-sm">{error}</span>
              </div>
            )}

            {(agentMeta !== null || queryGroups !== null) && (
              <div className="bg-base-200 border border-base-300 rounded-box flex-none p-4">
                <div className="text-sm font-medium mb-3">Agent details</div>
                <div className="text-sm">
                  {Array.isArray(queryGroups) && queryGroups.length > 0 && (
                    <div className="mb-3 space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wide opacity-70">Branch queries</div>
                      {queryGroups.map((g) => (
                        <div key={`agent-query-${g.branch_id}`} className="rounded bg-base-100 border border-base-300/50 p-2">
                          <div className="text-xs font-medium opacity-80">{branchLabel(g.branch_id)}</div>
                          <div className="text-xs opacity-70 break-words">{g.search_query || "(no query generated)"}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  <pre className="mt-1 max-h-72 overflow-auto rounded bg-base-100 p-3 text-xs border border-base-300/50">
                    {JSON.stringify(agentMeta ?? { message: "No agent metadata returned for this request." }, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Toolbar */}
            {results.length > 0 && (
              <div className="flex flex-none items-center justify-between px-1">
                <div className="flex items-center gap-4">
                  <div className="tabs tabs-boxed bg-base-100 border border-base-300 h-8 p-0.5">
                    <a 
                      className={`tab tab-sm h-full rounded-md transition-all ${viewMode === 'subquery' ? 'tab-active !bg-primary !text-primary-content' : 'hover:bg-base-200'}`}
                      onClick={() => setViewMode('subquery')}
                    >
                      Subqueries
                    </a>
                    <a 
                      className={`tab tab-sm h-full rounded-md transition-all ${viewMode === 'rerank' ? 'tab-active !bg-primary !text-primary-content' : 'hover:bg-base-200'}`}
                      onClick={() => {
                        setViewMode('rerank');
                        if (!rerankEnabled) setRerankEnabled(true);
                      }}
                    >
                      Reranked All
                    </a>
                  </div>
                  <span className="text-sm opacity-60">
                    {(limit === 'all' || limit === '') ? results.length : Math.min(results.length, limit as number)} results found
                  </span>
                </div>
                
                <div className="flex items-center gap-2">
                  {/* Max Results Input */}
                  <div className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-base-300 bg-base-100 hover:border-base-content/20 transition-colors h-8">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 opacity-70">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
                      </svg>
                      <span className="text-sm font-medium">Max Result:</span>
            <input
                type="text"
                value={limit === 'all' ? 'All' : limit}
                onChange={(e) => {
                   let val = e.target.value;
                   
                   // Handle case where user types number while "All" is selected (e.g. "All1")
                   if (limit === 'all' && val.toLowerCase().startsWith('all') && val.length > 3) {
                       val = val.substring(3);
                   }
                   
                   if (val === '') {
                      setLimit('');
                   } else if (val.toLowerCase() === 'all') {
                      setLimit('all');
                   } else {
                      const num = parseInt(val);
                      if (!isNaN(num) && num >= 0) {
                          setLimit(num);
                      } else if (limit === 'all') {
                          // If user modifies "All" to something invalid (e.g. "Al"), clear it to allow typing
                          setLimit('');
                      }
                   }
                }}
                className="w-10 bg-transparent text-sm font-medium focus:outline-none text-center [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            />
                  </div>

                  {/* Custom Sort Pill Button */}
                  <div className="dropdown dropdown-end">
                    <label tabIndex={0} className="btn btn-sm btn-outline gap-2 rounded-full border-base-300 bg-base-100 hover:bg-base-200 hover:border-base-content/20 normal-case font-medium">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="21" x2="3" y1="6" y2="6"></line>
                      <line x1="15" x2="3" y1="12" y2="12"></line>
                      <line x1="9" x2="3" y1="18" y2="18"></line>
                    </svg>
                    Sort: {sortBy.charAt(0).toUpperCase() + sortBy.slice(1)}
                  </label>
                    <ul tabIndex={0} className="dropdown-content menu menu-sm p-2 shadow bg-base-200 rounded-box w-40 z-10 mt-1">
                    <li><a className={sortBy === 'relevance' ? 'active' : ''} onClick={() => { setSortBy('relevance'); (document.activeElement as HTMLElement)?.blur(); }}>Relevance</a></li>
                    <li><a className={sortBy === 'date' ? 'active' : ''} onClick={() => { setSortBy('date'); setSortDirection('desc'); (document.activeElement as HTMLElement)?.blur(); }}>Date</a></li>
                  </ul>
                </div>
                </div>
              </div>
            )}

            {/* Results List */}
            <div className="flex-1 space-y-4 pr-2 pb-10">
              {viewMode === "subquery" && hasBranchResults && Array.isArray(queryGroups) ? (
                <div className="space-y-6">
                  {queryGroups.map((g) => {
                    const papers = g.results || [];
                    const topPapers = papers.slice(0, 10);
                    return (
                      <section key={g.branch_id} className="space-y-3">
                        <div className="flex items-center gap-2">
                          <span className="badge badge-primary">{branchLabel(g.branch_id)}</span>
                          {g.status && (
                            <span className={`badge ${g.status === "success" ? "badge-success" : g.status === "timeout" ? "badge-warning" : "badge-error"}`}>
                              {g.status}
                            </span>
                          )}
                          <span className="text-xs opacity-70">Top {topPapers.length} results</span>
                        </div>
                        {topPapers.length > 0 ? (
                          <div className="space-y-4">
                            {topPapers.map((p) => (
                              <PaperCard
                                key={`${g.branch_id}-${p.paper_id}`}
                                p={p}
                                navigateToAbstract={navigateToAbstract}
                                openAuthorPage={openAuthorPage}
                              />
                            ))}
                          </div>
                        ) : (
                          <div className="text-xs opacity-60">No papers for this branch.</div>
                        )}
                      </section>
                    );
                  })}
                </div>
              ) : (() => {
                  const limitedResults = limit === 'all' || limit === '' ? sortedResults : sortedResults.slice(0, limit as number);
                  const totalPages = Math.ceil(limitedResults.length / itemsPerPage);
                  const currentResults = limitedResults.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);
                  
                  return (
                    <>
                        {currentResults.map((p) => (
                            <PaperCard
                              key={p.paper_id}
                              p={p}
                              navigateToAbstract={navigateToAbstract}
                              openAuthorPage={openAuthorPage}
                            />
                        ))}
                        
                        {/* Pagination Controls */}
                        {limitedResults.length > itemsPerPage && (
                            <div className="flex justify-center items-center gap-2 mt-8 select-none">
                                <button 
                                    className="btn btn-sm btn-ghost gap-1"
                                    onClick={() => {
                                        setCurrentPage(p => Math.max(1, p - 1));
                                        window.scrollTo({ top: 0, behavior: 'smooth' });
                                    }}
                                    disabled={currentPage === 1}
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                                    </svg>
                                    Previous
                                </button>
                                
                                <div className="flex items-center">
                                    {Array.from({ length: totalPages }).map((_, i) => {
                                        const page = i + 1;
                                        // Simple logic to show limited pages if too many, similar to Google's style logic
                                        // For now, let's just show all since we won't have 100 pages in mock
                                        return (
                                            <button
                                                key={page}
                                                className={`btn btn-sm btn-ghost w-8 h-8 p-0 rounded-full font-medium ${currentPage === page ? 'text-primary bg-primary/10' : 'text-base-content/70'}`}
                                                onClick={() => {
                                                    setCurrentPage(page);
                                                    window.scrollTo({ top: 0, behavior: 'smooth' });
                                                }}
                                            >
                                                {page}
                                            </button>
                                        );
                                    })}
                                </div>

                                <button 
                                    className="btn btn-sm btn-ghost gap-1"
                                    onClick={() => {
                                        setCurrentPage(p => Math.min(totalPages, p + 1));
                                        window.scrollTo({ top: 0, behavior: 'smooth' });
                                    }}
                                    disabled={currentPage === totalPages}
                                >
                                    Next
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                                    </svg>
                                </button>
                            </div>
                        )}
                    </>
                  );
              })()}

              {results.length === 0 && !loading && (
                <div className="flex h-full flex-col items-center justify-center text-center opacity-30 mt-20">
                   <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-16 h-16 mb-4">
                     <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                   </svg>
                   <p className="text-lg font-medium">No papers selected</p>
                </div>
              )}

              {loading && (
                <div className="flex h-full flex-col items-center justify-center text-center mt-20">
                   <div className="loader"></div>
                </div>
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
