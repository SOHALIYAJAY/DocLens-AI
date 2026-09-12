# services/reranker_service.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from core.config import settings

class BaseReranker(ABC):
    """
    Abstract interface for cross-encoder / relevance reranking algorithms.
    """
    @abstractmethod
    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        pass

class CrossEncoderReranker(BaseReranker):
    """
    Reranker implementation using SentenceTransformers CrossEncoder model.
    Evaluates candidate text relevance against user query.
    """
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.RERANKER_MODEL
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                print(f"[RERANKER] Loading CrossEncoder model '{self.model_name}'...")
                self._model = CrossEncoder(self.model_name)
                print(f"[RERANKER] Model '{self.model_name}' loaded successfully.")
            except Exception as e:
                print(f"[RERANKER WARNING] Failed to load CrossEncoder ({e}). Using similarity fallback...")
                self._model = "fallback"
        return self._model

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not candidates or not query:
            return []

        model = self._get_model()

        if model != "fallback":
            try:
                pairs = [[query, c.get("text", "")] for c in candidates]
                scores = model.predict(pairs)

                scored_candidates = []
                for candidate, score in zip(candidates, scores):
                    item = dict(candidate)
                    item["rerank_score"] = float(round(score, 6))
                    scored_candidates.append(item)

                scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
                return scored_candidates[:top_k]
            except Exception as err:
                print(f"[RERANKER ERROR] Prediction error: {err}. Using score fallback...")

        # Fallback ranking if model unavailable
        scored_candidates = []
        for idx, candidate in enumerate(candidates):
            item = dict(candidate)
            # Use RRF score or fallback rank
            item["rerank_score"] = float(item.get("rrf_score", item.get("score", 1.0 / (idx + 1))))
            scored_candidates.append(item)

        scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored_candidates[:top_k]

class RerankerService:
    """
    Global service managing candidate reranking stage.
    """
    def __init__(self, reranker: BaseReranker = None):
        self.reranker = reranker or CrossEncoderReranker()

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        k = top_k or settings.RERANK_TOP_K
        if not candidates:
            return []

        output_candidates = self.reranker.rerank(query, candidates, top_k=k)
        pages = sorted(list(set([c.get("page_number", c.get("page", 1)) for c in output_candidates])))

        print(f"\n[RE-RANK]")
        print(f"Input candidates: {len(candidates)}")
        print(f"Output candidates: {len(output_candidates)}")
        print(f"Pages: {pages}\n")

        return output_candidates

# Global singleton instance
reranker_service = RerankerService()
