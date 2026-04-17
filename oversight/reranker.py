import time
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class BGEReranker:
    """
    Provides semantic re-ranking using the BAAI/bge-reranker-v2-m3 Cross-Encoder.
    This implementation is optimized for high-performance GPUs (e.g., NVIDIA L40S)
    using FP16 precision and batch processing.
    """

    def __init__(self, model_name: str = 'BAAI/bge-reranker-base', use_fp16: bool = True):
        """
        Initialize the Cross-Encoder model.

        Args:
            model_name: The HuggingFace model identifier.
            use_fp16: Enable half-precision to reduce VRAM usage and increase throughput.
        """
        logger.info("Initializing Reranker: %s (FP16=%s)", model_name, use_fp16)
        try:
            import torch
            
            # Determine best available device
            device = "cpu"
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            
            # CRITICAL: MPS often hangs or errors with FP16 for certain models (like v2-m3).
            # Force FP32 on MPS for stability.
            if device == "mps":
                logger.info("MPS detected. Forcing FP32 for stability with heavy models.")
                use_fp16 = False
            
            if "bge-reranker" in model_name.lower():
                from FlagEmbedding import FlagReranker
                if use_fp16 and device == "cpu":
                    logger.warning("FP16 requested but running on CPU. Falling back to FP32.")
                    use_fp16 = False
                self.reranker = FlagReranker(model_name, use_fp16=use_fp16, device=device)
                
                # Warmup: Run a dummy inference to compile kernels/shaders
                # This prevents the first real request from timing out.
                logger.info("Warming up reranker model...")
                self.reranker.compute_score([["warmup", "warmup text"]], normalize=True)
                logger.info("Warmup complete.")
            else:
                # Fallback to SentenceTransformers for other cross-encoders
                from sentence_transformers import CrossEncoder
                self.reranker = CrossEncoder(model_name, device=device)
                
            logger.info("Reranker model loaded successfully on %s", device.upper())
        except ImportError:
            logger.error("Required libraries (FlagEmbedding, torch, sentence-transformers) not found.")
            self.reranker = None
        except Exception as e:
            logger.error("Failed to load reranker model: %s", str(e))
            self.reranker = None

    def rerank(self, query: str, papers: List[Dict[str, Any]], top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Scores a list of papers against a query and returns the top-K results sorted by relevance.

        Args:
            query: The original user query or a decomposed subquery.
            papers: A list of dictionaries, each containing 'title' and 'abstract'.
            top_k: The number of results to return after re-ranking.

        Returns:
            A list of papers sorted by semantic_score in descending order.
        """
        if not self.reranker or not papers:
            return papers[:top_k]

        # Construct input pairs: [query, title + abstract (truncated)]
        sentence_pairs = []
        for paper in papers:
            title = paper.get('title', '')
            # Truncate abstract to 600 chars. This covers the most important semantic 
            # information while drastically reducing the number of tokens to process.
            # Transformer complexity is roughly O(N^2), so shorter is MUCH faster.
            abstract = paper.get('abstract', '')
            if abstract and len(abstract) > 600:
                abstract = abstract[:600] + "..."
            
            context = f"{title}. {abstract}"
            sentence_pairs.append([query, context])

        import torch
        start_time = time.time()
        # Use inference_mode for maximum performance on MPS
        with torch.inference_mode():
            try:
                # Check if it's FlagReranker which supports batch_size in compute_score
                if hasattr(self.reranker, "compute_score"):
                    # Slightly increased batch_size to 12 for better throughput
                    scores = self.reranker.compute_score(sentence_pairs, normalize=True, batch_size=12)
                else:
                    scores = self.reranker.predict(sentence_pairs, batch_size=12)
            except Exception as e:
                logger.error("Error during reranking inference: %s", str(e))
                return papers[:top_k]
            
        duration = time.time() - start_time

        logger.info("Reranked %d papers in %.4f seconds", len(papers), duration)

        # Assign scores and sort
        if isinstance(scores, (float, int)):
            scores = [scores]
            
        for i, paper in enumerate(papers):
            # Handle potential numpy or torch scalar types
            score = scores[i]
            if hasattr(score, "item"):
                score = score.item()
            paper['semantic_score'] = float(score)

        sorted_papers = sorted(papers, key=lambda x: x.get('semantic_score', 0.0), reverse=True)
        return sorted_papers[:top_k]
