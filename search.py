import os

from dotenv import load_dotenv
from ConferenceSearchEngine import ConferenceSearchEngine
from reranker import BGEReranker

def pretty_print_doc(doc, score=None):
	title = doc.metadata.get("title", "Untitled")
	
	conference = doc.metadata.get("conference", [])
	if isinstance(conference, list):
		conference_str = ",".join(conference)
	else:
		conference_str = str(conference)
	
	year = doc.metadata.get("year", "")
	session = doc.metadata.get("session", "")
	
	metadata_parts = [p for p in [conference_str, year, session] if p]
	metadata_str = f" ({', '.join(metadata_parts)})" if metadata_parts else ""

	if score is not None:
		print(f"--- [Semantic Score: {score:.4f}] ---")
	print(f"{title}{metadata_str}")
	print(doc.metadata.get("authors", ""))
	print()
	print(doc.page_content)
	print()
	print(doc.metadata.get("link", ""))
	print()
	print()

def main():
	load_dotenv()

	embedded_docs_path = "data/docs/gemini_embedded_docs.json"
	if not os.path.exists(embedded_docs_path):
		print(f"Error: Embedded documents file not found at {embedded_docs_path}")
		print("Please ensure you have generated the embeddings or check the path.")
		return

	search_engine = ConferenceSearchEngine(
		embedded_docs_path=embedded_docs_path,
		embedding_model="models/embedding-001",
		filter=lambda _: True,
		google_api_key=os.environ.get("GOOGLE_API_KEY")
	)

	query = "Large language model (LLM) applications are evolving beyond simple chatbots into dynamic, general-purpose agentic programs, which scale LLM calls and output tokens to help AI agents reason, explore, and solve complex tasks. However, existing LLM serving systems ignore dependencies between programs and calls, missing significant opportunities for optimization. Our analysis reveals that programs submitted to LLM serving engines experience long cumulative wait times, primarily due to head-of-line blocking at both the individual LLM request and the program.  To address this, we introduce Autellix, an LLM serving system that treats programs as first-class citizens to minimize their end-to-end latencies."

	# 1. Similarity Search (Retrieval)
	docs = search_engine.vs.similarity_search(query, k=20)

	# 2. Re-ranking
	enabled = os.getenv("OVERSIGHT_RERANK_ENABLED", "true").lower() == "true"
	if enabled:
		reranker = BGEReranker()
		papers = []
		for doc in docs:
			papers.append({
				"title": doc.metadata["title"],
				"abstract": doc.page_content,
				"metadata": doc.metadata
			})
		
		reranked = reranker.rerank(query=query, papers=papers, top_k=10)
		for doc_info in reranked:
			# Mocking back a doc object for pretty_print
			class MockDoc:
				def __init__(self, title, content, metadata):
					self.metadata = metadata
					self.page_content = content
			
			pretty_print_doc(
				MockDoc(doc_info["title"], doc_info["abstract"], doc_info["metadata"]), 
				score=doc_info.get("semantic_score")
			)
	else:
		for doc in docs[:10]:
			pretty_print_doc(doc)

if __name__ == "__main__":
	main()

	

	