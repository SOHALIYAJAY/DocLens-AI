# core/config.py
# This file holds the main configuration for the FastAPI application.

class Settings:
    PROJECT_NAME: str = "AI PDF Assistant API"
    PROJECT_VERSION: str = "1.0.0"
    API_PREFIX: str = ""

    # Hybrid RAG Retrieval Parameters
    VECTOR_TOP_K: int = 10
    BM25_TOP_K: int = 10
    HYBRID_TOP_K: int = 15
    RERANK_TOP_K: int = 5
    RRF_K: int = 60
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Context Expansion Parameters
    MAX_NEIGHBOR_CHUNKS: int = 1
    ENABLE_CONTEXT_EXPANSION: bool = True
    MAX_CONTEXT_TOKENS: int = 3500

# Instantiate the settings so it can be imported across the project
settings = Settings()





