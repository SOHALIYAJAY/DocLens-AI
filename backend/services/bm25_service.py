# services/bm25_service.py
import math
import re
from typing import List, Dict, Any
from collections import Counter

def tokenize(text: str) -> List[str]:
    """
    Tokenizes text for BM25 lexical search.
    Preserves exact terms, numbers, percentages, dates, acronyms, and model codes.
    """
    if not text:
        return []
    # Extract words, numbers with decimals/percents, currencies, and technical terms
    tokens = re.findall(r"\b[\w\.\%\$-]+(?:\.[\w\.\%\$-]+)*\b", text.lower())
    return [t for t in tokens if len(t) > 0]

class BM25Okapi:
    """
    Self-contained Okapi BM25 ranking algorithm.
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avgdl = 0.0
        self.doc_lengths = []
        self.doc_term_freqs = []
        self.doc_freqs = Counter()
        self.idf = {}
        self.chunks = []

    def index_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Indexes a list of metadata-enriched text chunks.
        """
        self.chunks = chunks
        self.doc_count = len(chunks)
        if self.doc_count == 0:
            return

        total_length = 0
        self.doc_lengths = []
        self.doc_term_freqs = []
        self.doc_freqs = Counter()

        for chunk in chunks:
            text = chunk.get("text", "")
            tokens = tokenize(text)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_length += doc_len

            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)

            for token in tf.keys():
                self.doc_freqs[token] += 1

        self.avgdl = total_length / self.doc_count if self.doc_count > 0 else 0.0

        # Calculate IDF values
        self.idf = {}
        for token, df in self.doc_freqs.items():
            idf_val = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
            self.idf[token] = max(idf_val, 0.0001)

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Searches the BM25 index for the query and returns top_k candidate chunks with BM25 score.
        """
        if self.doc_count == 0 or not query:
            return []

        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        scores = [0.0] * self.doc_count

        for q_token in q_tokens:
            if q_token not in self.idf:
                continue

            idf_val = self.idf[q_token]

            for doc_idx, tf_map in enumerate(self.doc_term_freqs):
                tf = tf_map.get(q_token, 0)
                if tf == 0:
                    continue

                doc_len = self.doc_lengths[doc_idx]
                num = tf * (self.k1 + 1.0)
                den = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl if self.avgdl > 0 else 1.0))
                scores[doc_idx] += idf_val * (num / den)

        # Sort candidate indices by BM25 score descending
        scored_indices = [(score, idx) for idx, score in enumerate(scores) if score > 0]
        scored_indices.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, idx in scored_indices[:top_k]:
            chunk_copy = dict(self.chunks[idx])
            chunk_copy["bm25_score"] = score
            results.append(chunk_copy)

        return results

import os
import json

BM25_PERSIST_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".bm25_index.json")

class BM25Service:
    """
    Global service managing the active PDF's persistent BM25 lexical index.
    """
    def __init__(self):
        self.index = BM25Okapi()
        self._load_from_disk()

    def _save_to_disk(self):
        """Saves current chunks to persistent storage."""
        try:
            with open(BM25_PERSIST_PATH, "w", encoding="utf-8") as f:
                json.dump(self.index.chunks, f, ensure_ascii=False)
        except Exception as e:
            print(f"[BM25] Save error: {e}")

    def _load_from_disk(self):
        """Loads index from persistent disk storage if present."""
        if os.path.exists(BM25_PERSIST_PATH):
            try:
                with open(BM25_PERSIST_PATH, "r", encoding="utf-8") as f:
                    chunks = json.load(f)
                    if chunks:
                        self.index.index_chunks(chunks)
                        print(f"[BM25] Loaded persistent index with {len(chunks)} chunks from disk.")
            except Exception as e:
                print(f"[BM25] Load error: {e}")

    def clear_index(self):
        """Clears current BM25 index and removes disk store."""
        self.index = BM25Okapi()
        if os.path.exists(BM25_PERSIST_PATH):
            try:
                os.remove(BM25_PERSIST_PATH)
            except Exception:
                pass

    def add_documents(self, chunks: List[Dict[str, Any]]):
        """Indexes chunks in BM25 and persists to disk."""
        self.index.index_chunks(chunks)
        self._save_to_disk()
        print(f"[BM25] Indexed {len(chunks)} chunks into BM25 lexical index (saved to disk).")

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Searches BM25 index and prints query statistics."""
        results = self.index.search(query, top_k=top_k)
        chunk_ids = [r.get("chunk_id", "") for r in results]
        page_nums = [r.get("page_number", r.get("page", 1)) for r in results]
        
        print(f"[BM25 SEARCH]")
        print(f"  Query: '{query}'")
        print(f"  Candidates Found: {len(results)}")
        print(f"  Selected Chunk IDs: {chunk_ids}")
        print(f"  Selected Page Numbers: {page_nums}")
        
        return results

# Global singleton instance
bm25_service = BM25Service()

