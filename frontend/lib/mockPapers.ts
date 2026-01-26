export type Paper = {
  paper_id: string;
  title: string;
  abstract: string;
  keywords?: string[];
  source?: string | null;
  link?: string | null;
  paper_date?: string | null;
  citation_count?: number;
  authors?: string;
  first_author?: string;
};

const KATHERINE_LIU_PAPERS: Paper[] = Array.from({ length: 24 }, (_, idx) => {
  const i = idx + 1;
  const year = 2025 - Math.floor(idx / 6);
  const month = ((idx % 12) + 1).toString().padStart(2, "0");
  const day = ((idx % 27) + 1).toString().padStart(2, "0");
  return {
    paper_id: `kliu-${i}`,
    title: `LLM Serving Efficiency: Practical Optimizations in the KV Cache Stack [${i}]`,
    abstract:
      "We study practical optimizations for LLM serving efficiency across the KV cache pipeline, including memory layout, prefill/decoding scheduling, and reuse strategies. We report consistent throughput and tail-latency improvements across a range of model sizes and prompt distributions.",
    keywords: ["llm efficiency", "serving", "kv cache", "throughput", "tail latency"],
    source: idx % 3 === 0 ? "OSDI" : idx % 3 === 1 ? "NSDI" : "MLSys",
    paper_date: `${year}-${month}-${day}`,
    link: "#",
    citation_count: 20 + idx * 3,
    first_author: "Katherine Liu",
    authors: "Katherine Liu, Stanford University; Maria Santos, Stanford University",
  };
});

export const MOCK_PAPERS: Paper[] = [
  {
    paper_id: "mh1",
    title: "Multi-hop Retrieval for Complex Research Questions",
    first_author: "Gengrui Zhang",
    authors: "Gengrui Zhang, University of Toronto; Hans-Arno Jacobsen, University of Toronto",
    abstract:
      "We study multi-hop retrieval for complex research questions that require chaining evidence across multiple papers. Our method decomposes a query into intermediate sub-queries, retrieves supporting documents at each hop, and aggregates evidence with a lightweight reasoning module. Experiments show improved accuracy on multi-step benchmarks while keeping latency low.",
    keywords: ["multi-hop", "query decomposition", "iterative retrieval", "evidence chaining", "reasoning"],
    source: "NeurIPS",
    paper_date: "2024-12-01",
    link: "#",
    citation_count: 8,
  },
  {
    paper_id: "mh2",
    title: "Evidence Chaining with Lightweight Verifiers",
    first_author: "Gengrui Zhang",
    authors: "Gengrui Zhang, University of Toronto; Priya Nair, University of Toronto",
    abstract:
      "We introduce a lightweight verifier to improve evidence chaining for retrieval-augmented generation. The verifier scores candidate evidence sets and guides iterative retrieval, improving factual consistency under strict latency budgets.",
    keywords: ["retrieval-augmented generation", "verification", "evidence", "latency"],
    source: "ICLR",
    paper_date: "2024-05-10",
    link: "#",
    citation_count: 14,
  },
  {
    paper_id: "mh3",
    title: "Decomposed Queries for Scientific Literature Search",
    first_author: "Gengrui Zhang",
    authors: "Gengrui Zhang, University of Toronto; Hans-Arno Jacobsen, University of Toronto",
    abstract:
      "We propose a query decomposition pipeline for scientific search that generates intermediate sub-queries aligned to domain-specific concepts. Results show higher recall on multi-step literature tasks compared with single-shot retrieval.",
    keywords: ["scientific search", "multi-step", "retrieval", "query decomposition"],
    source: "NeurIPS",
    paper_date: "2023-12-01",
    link: "#",
    citation_count: 33,
  },
  {
    paper_id: "sd1",
    title: "Optimizing LLM Inference with Speculative Decoding",
    first_author: "Lei Chen",
    authors: "Lei Chen, The Hong Kong University of Science and Technology; Zengyang Gong, The Hong Kong University of Science and Technology",
    abstract:
      "This paper presents a novel approach to speed up LLM inference by leveraging a smaller draft model to generate candidate tokens, which are then verified by the larger target model in parallel. We show that this method can achieve 2-3x speedups on standard benchmarks without compromising generation quality.",
    keywords: ["speculative decoding", "llm inference", "draft model", "latency", "throughput"],
    source: "ICML",
    paper_date: "2023-07-01",
    link: "https://arxiv.org/abs/2301.00001",
    citation_count: 145,
  },
  {
    paper_id: "sd2",
    title: "Draft-Verify Decoding for Low-Latency Generation",
    first_author: "Lei Chen",
    authors: "Lei Chen, The Hong Kong University of Science and Technology; Mingyu Li, Shanghai Jiao Tong University",
    abstract:
      "We analyze draft-verify decoding under practical deployment constraints, including batching, KV cache reuse, and variable-length outputs. The proposed scheduler improves tail latency while preserving output quality.",
    keywords: ["decoding", "scheduling", "kv cache", "serving", "latency"],
    source: "MLSys",
    paper_date: "2024-06-15",
    link: "#",
    citation_count: 21,
  },
  {
    paper_id: "sd3",
    title: "Adaptive Speculation: When to Draft and When to Verify",
    first_author: "Lei Chen",
    authors: "Lei Chen, The Hong Kong University of Science and Technology; Zengyang Gong, The Hong Kong University of Science and Technology",
    abstract:
      "We introduce an adaptive policy that selects speculation depth based on token-level uncertainty. This reduces wasted draft compute and yields consistent speedups across heterogeneous prompts.",
    keywords: ["speculation", "uncertainty", "policy", "inference"],
    source: "NeurIPS",
    paper_date: "2024-12-01",
    link: "#",
    citation_count: 9,
  },
  {
    paper_id: "fa1",
    title: "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
    first_author: "Omer Abramovich",
    authors: "Omer Abramovich, Tel Aviv University; Daniel Deutch, Tel Aviv University",
    abstract:
      "We introduce FlashAttention, an IO-aware exact attention algorithm that uses tiling to reduce the number of memory accesses between GPU HBM and on-chip SRAM. FlashAttention trains Transformers faster than existing baselines: 15% end-to-end wall-clock speedup on BERT-large (seqlen 512), 3x speedup on GPT-2 (seqlen 1K), and 2.4x speedup on long-range arena (seqlen 1K-4K).",
    keywords: ["flashattention", "io-aware", "attention", "memory efficiency", "transformers"],
    source: "NeurIPS",
    paper_date: "2022-12-01",
    link: "https://arxiv.org/abs/2205.14135",
    citation_count: 890,
  },
  {
    paper_id: "fa2",
    title: "Kernel-Aware Tiling Strategies for Efficient Attention",
    first_author: "Omer Abramovich",
    authors: "Omer Abramovich, Tel Aviv University; Daniel Deutch, Tel Aviv University",
    abstract:
      "We benchmark attention kernels under different tiling strategies and propose a kernel-aware selection rule. The method improves throughput across varying sequence lengths and GPU architectures.",
    keywords: ["attention", "kernels", "tiling", "benchmark"],
    source: "ICML",
    paper_date: "2023-07-01",
    link: "#",
    citation_count: 57,
  },
  {
    paper_id: "fa3",
    title: "IO-Aware Exact Attention for Long Context",
    first_author: "Omer Abramovich",
    authors: "Omer Abramovich, Tel Aviv University; Daniel Deutch, Tel Aviv University",
    abstract:
      "We extend IO-aware exact attention to long-context settings with dynamic tiling. Experiments show improved memory efficiency and stable runtime on long sequences.",
    keywords: ["long context", "io-aware", "attention", "memory"],
    source: "ICLR",
    paper_date: "2024-01-15",
    link: "#",
    citation_count: 18,
  },
  {
    paper_id: "sort1",
    title: "Older Paper Example for Sorting Test",
    first_author: "Junhao Hu",
    authors: "Junhao Hu, Peking University; Jiang Xu, Huawei Cloud",
    abstract:
      "An older paper to test if date sorting works correctly. This paper discusses fundamental concepts in distributed systems consensus algorithms.",
    keywords: ["distributed systems", "consensus", "sorting test", "latency", "reliability"],
    source: "OSDI",
    paper_date: "2020-10-15",
    link: "#",
    citation_count: 3200,
  },
  {
    paper_id: "sort2",
    title: "Practical Consensus in Cloud-Scale Systems",
    first_author: "Junhao Hu",
    authors: "Junhao Hu, Peking University; Jiang Xu, Huawei Cloud",
    abstract:
      "We present practical lessons for implementing consensus in cloud-scale systems, focusing on failure detection, configuration changes, and operator-friendly observability.",
    keywords: ["consensus", "cloud", "observability", "reliability"],
    source: "SOSP",
    paper_date: "2021-10-01",
    link: "#",
    citation_count: 410,
  },
  {
    paper_id: "sort3",
    title: "Latency-Aware Replication for Geo-Distributed Services",
    first_author: "Junhao Hu",
    authors: "Junhao Hu, Peking University; Mei Lin, Tsinghua University",
    abstract:
      "We propose a latency-aware replication strategy for geo-distributed services. The system dynamically selects replica placement and quorum sizes to reduce tail latency while maintaining correctness.",
    keywords: ["replication", "geo-distributed", "tail latency", "quorum"],
    source: "NSDI",
    paper_date: "2022-04-20",
    link: "#",
    citation_count: 96,
  },
  {
    paper_id: "gnn1",
    title: "Recent Advances in Graph Neural Networks",
    first_author: "Zihao Chang",
    authors: "Zihao Chang, Institute of Computing Technology, CAS; Jiaqi Zhu, University of Chinese Academy of Sciences",
    abstract:
      "A comprehensive survey of Graph Neural Networks (GNNs) covering various architectures including Graph Convolutional Networks (GCNs), Graph Attention Networks (GATs), and their applications in social network analysis, drug discovery, and recommendation systems.",
    keywords: ["graph neural networks", "gcn", "gat", "survey", "graph learning"],
    source: "ICLR",
    paper_date: "2024-01-10",
    link: "#",
    citation_count: 12,
  },
  {
    paper_id: "gnn2",
    title: "Graph Transformers for Recommendation Systems",
    first_author: "Zihao Chang",
    authors: "Zihao Chang, Institute of Computing Technology, CAS; Jiaqi Zhu, University of Chinese Academy of Sciences",
    abstract:
      "We study graph transformers for large-scale recommendation systems and propose a sampling strategy that improves training stability. The approach achieves stronger ranking metrics under tight memory budgets.",
    keywords: ["recommendation", "graph transformers", "sampling", "ranking"],
    source: "NeurIPS",
    paper_date: "2023-12-01",
    link: "#",
    citation_count: 27,
  },
  {
    paper_id: "gnn3",
    title: "Scalable Message Passing with Adaptive Neighborhoods",
    first_author: "Zihao Chang",
    authors: "Zihao Chang, Institute of Computing Technology, CAS; Ke Wang, Peking University",
    abstract:
      "We propose an adaptive neighborhood scheme for scalable message passing on massive graphs. The method improves convergence and reduces unnecessary computation in sparse regions of the graph.",
    keywords: ["message passing", "scalability", "graphs", "adaptive neighborhoods"],
    source: "ICML",
    paper_date: "2024-07-01",
    link: "#",
    citation_count: 5,
  },
  {
    paper_id: "med1",
    title: "Large Language Models in Healthcare: A Comprehensive Review",
    first_author: "Sushant Kumar Gupta",
    authors: "Sushant Kumar Gupta, Google LLC; Anil Raghunath Iyer, Google LLC",
    abstract:
      "The integration of Large Language Models (LLMs) into healthcare systems presents both transformative opportunities and significant challenges. This review explores the current state of LLM applications in medical diagnosis, patient record analysis, and drug discovery. We analyze the performance of various models including GPT-4, Med-PaLM, and others across a range of medical benchmarks. Furthermore, we discuss critical ethical considerations such as data privacy, bias in model outputs, and the necessity for human-in-the-loop verification systems. The paper also proposes a new framework for evaluating the clinical safety of LLMs before deployment. Our findings suggest that while LLMs demonstrate remarkable potential in assisting healthcare professionals, substantial work remains in ensuring their reliability and explainability in critical medical contexts. We conclude with a roadmap for future research directions in medical AI.",
    keywords: ["healthcare", "llm", "clinical safety", "medical ai", "human-in-the-loop"],
    source: "Nature Medicine",
    paper_date: "2024-02-15",
    link: "#",
    citation_count: 45,
  },
  {
    paper_id: "med2",
    title: "Evaluating Clinical Safety of Medical LLMs",
    first_author: "Sushant Kumar Gupta",
    authors: "Sushant Kumar Gupta, Google LLC; Anil Raghunath Iyer, Google LLC",
    abstract:
      "We propose a clinical safety evaluation protocol for medical LLMs focused on uncertainty calibration, harmful suggestion detection, and evidence attribution. The evaluation reveals common failure modes and mitigation strategies.",
    keywords: ["clinical safety", "evaluation", "uncertainty", "evidence attribution"],
    source: "Nature Medicine",
    paper_date: "2025-01-20",
    link: "#",
    citation_count: 4,
  },
  {
    paper_id: "med3",
    title: "Human-in-the-Loop Verification for High-Stakes Generation",
    first_author: "Sushant Kumar Gupta",
    authors: "Sushant Kumar Gupta, Google LLC; Maria Santos, Stanford University",
    abstract:
      "We study human-in-the-loop verification workflows for high-stakes generation tasks. A structured checklist and evidence display reduces critical errors and improves reviewer agreement.",
    keywords: ["human-in-the-loop", "verification", "safety", "workflow"],
    source: "ICLR",
    paper_date: "2024-05-10",
    link: "#",
    citation_count: 11,
  },
  ...KATHERINE_LIU_PAPERS,
];

export function getMockPapersByFirstAuthor(authorName: string): Paper[] {
  const normalized = authorName.trim().toLowerCase();
  if (!normalized) return [];
  return MOCK_PAPERS.filter((p) => (p.first_author || "").trim().toLowerCase() === normalized);
}
