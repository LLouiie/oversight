import type { Paper } from "./mockPapers";

export type AuthorExpertise = {
  author: string;
  institution: string;
  domain: string;
  publicationsInDomain: number;
};

export type DemoPaper = Paper & {
  semantic_score?: number;
  author_expertise?: AuthorExpertise;
  expertise_match_badge?: string;
};

export const LLM_EFFICIENCY_DOMAIN = "LLM Optimization";

export const AUTHOR_EXPERTISE: Record<string, AuthorExpertise> = {
  "Evan Park": {
    author: "Evan Park",
    institution: "Newbridge University",
    domain: LLM_EFFICIENCY_DOMAIN,
    publicationsInDomain: 1,
  },
  "Mina Al-Khatib": {
    author: "Mina Al-Khatib",
    institution: "Rising Stars Lab",
    domain: LLM_EFFICIENCY_DOMAIN,
    publicationsInDomain: 1,
  },
  "Katherine Liu": {
    author: "Katherine Liu",
    institution: "Stanford University",
    domain: LLM_EFFICIENCY_DOMAIN,
    publicationsInDomain: 24,
  },
  "Noah Stein": {
    author: "Noah Stein",
    institution: "University of Washington",
    domain: LLM_EFFICIENCY_DOMAIN,
    publicationsInDomain: 6,
  },
  "Aisha Rahman": {
    author: "Aisha Rahman",
    institution: "Carnegie Mellon University",
    domain: LLM_EFFICIENCY_DOMAIN,
    publicationsInDomain: 9,
  },
};

export const DEMO_LLM_EFFICIENCY_RESULTS: DemoPaper[] = [
  {
    paper_id: "llmeff-A",
    title: "Token-Level KV Cache Pruning for Faster LLM Serving",
    abstract:
      "We propose token-level KV cache pruning to reduce memory traffic during autoregressive decoding. By learning a lightweight retention policy conditioned on attention patterns, we reduce KV cache footprint with minimal quality loss. Experiments on long-context benchmarks show 1.8× throughput gains and improved tail latency under constrained GPU memory.",
    source: "NeurIPS",
    paper_date: "2025-12-01",
    link: "#",
    citation_count: 3,
    first_author: "Evan Park",
    authors: "Evan Park, Newbridge University; Li Wei, Newbridge University",
    semantic_score: 0.97,
    author_expertise: AUTHOR_EXPERTISE["Evan Park"],
  },
  {
    paper_id: "llmeff-B",
    title: "Efficient Prefill Scheduling for Multi-Request LLM Inference",
    abstract:
      "We study prefill-stage scheduling for LLM inference under bursty traffic. Our approach groups prompts by length and dynamically adjusts micro-batch boundaries to reduce head-of-line blocking. On production-like traces, we observe up to 1.6× throughput improvement while maintaining stable latency percentiles.",
    source: "ICML",
    paper_date: "2025-07-01",
    link: "#",
    citation_count: 5,
    first_author: "Mina Al-Khatib",
    authors: "Mina Al-Khatib, Rising Stars Lab; Arjun Menon, Rising Stars Lab",
    semantic_score: 0.95,
    author_expertise: AUTHOR_EXPERTISE["Mina Al-Khatib"],
  },
  {
    paper_id: "llmeff-C",
    title: "Systems-Level Optimization for End-to-End LLM Efficiency",
    abstract:
      "We present a systems-level study of end-to-end efficiency for large language model inference, focusing on memory movement, batching policy, and KV cache reuse. While individual optimizations offer modest gains, we show that coordinated design across the serving stack yields consistent improvements in throughput and tail latency across models and workloads.",
    source: "OSDI",
    paper_date: "2024-10-15",
    link: "#",
    citation_count: 312,
    first_author: "Katherine Liu",
    authors: "Katherine Liu, Stanford University; Maria Santos, Stanford University",
    semantic_score: 0.71,
    author_expertise: AUTHOR_EXPERTISE["Katherine Liu"],
    expertise_match_badge: "Expertise Match : Author has 20+ publications in LLM Optimization.",
  },
  {
    paper_id: "llmeff-D",
    title: "Quantization-Aware Kernels for Efficient Transformer Inference",
    abstract:
      "We introduce quantization-aware GPU kernels for transformer inference with reduced precision activations. The method combines calibration-free quantization with fused operators to minimize memory bandwidth overhead. Results show improved latency and energy efficiency on modern accelerators.",
    source: "MLSys",
    paper_date: "2024-06-15",
    link: "#",
    citation_count: 44,
    first_author: "Aisha Rahman",
    authors: "Aisha Rahman, Carnegie Mellon University; Daniel Deutch, Tel Aviv University",
    semantic_score: 0.83,
    author_expertise: AUTHOR_EXPERTISE["Aisha Rahman"],
  },
  {
    paper_id: "llmeff-E",
    title: "Adaptive Batching for Tail-Latency-Critical LLM Serving",
    abstract:
      "We propose an adaptive batching controller for tail-latency-critical LLM serving. The controller adjusts batch size in response to queueing dynamics and model phase behavior, improving p95 latency without sacrificing average throughput across mixed prompt distributions.",
    source: "NSDI",
    paper_date: "2024-04-20",
    link: "#",
    citation_count: 61,
    first_author: "Noah Stein",
    authors: "Noah Stein, University of Washington; Priya Nair, University of Toronto",
    semantic_score: 0.79,
    author_expertise: AUTHOR_EXPERTISE["Noah Stein"],
  },
];

export const EXPERTISE_REFINE_CORE_PROMPT =
  "Given a ranked list of semantically similar papers, re-rank results using auxiliary metadata signals. If an author's publication history indicates strong expertise in LLM Optimization (20+ publications) and the institution is top-tier, substantially boost that result and provide a concise explanation badge.";

