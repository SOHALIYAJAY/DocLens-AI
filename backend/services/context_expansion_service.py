# services/context_expansion_service.py
import os
import json
from typing import List, Dict, Any
from core.config import settings
from services.token_service import count_tokens

CONTEXT_STORE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".context_chunks.json")

class ContextExpansionService:
    """
    Service managing document-level sequential chunk order and context expansion
    with parent section scope and contiguous neighbor block merging.
    """
    def __init__(self):
        self.doc_chunks: List[Dict[str, Any]] = []
        self.chunk_id_to_index: Dict[str, int] = {}
        self._load_from_disk()

    def _save_to_disk(self):
        try:
            with open(CONTEXT_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.doc_chunks, f, ensure_ascii=False)
        except Exception as e:
            print(f"[CONTEXT EXPANSION] Save error: {e}")

    def _load_from_disk(self):
        if os.path.exists(CONTEXT_STORE_PATH):
            try:
                with open(CONTEXT_STORE_PATH, "r", encoding="utf-8") as f:
                    chunks = json.load(f)
                    if chunks:
                        self.set_document_chunks(chunks, persist=False)
                        print(f"[CONTEXT EXPANSION] Loaded {len(chunks)} sequential document chunks from disk.")
            except Exception as e:
                print(f"[CONTEXT EXPANSION] Load error: {e}")

    def set_document_chunks(self, chunks: List[Dict[str, Any]], persist: bool = True):
        """
        Stores the ordered sequential list of all document chunks.
        """
        self.doc_chunks = chunks
        self.chunk_id_to_index = {}
        for idx, c in enumerate(chunks):
            cid = c.get("chunk_id", f"chunk_{idx}")
            self.chunk_id_to_index[cid] = idx

        if persist:
            self._save_to_disk()

    def clear_chunks(self):
        self.doc_chunks = []
        self.chunk_id_to_index = {}
        if os.path.exists(CONTEXT_STORE_PATH):
            try:
                os.remove(CONTEXT_STORE_PATH)
            except Exception:
                pass

    def expand_chunks(
        self,
        query: str,
        reranked_chunks: List[Dict[str, Any]],
        max_neighbors: int = None,
        max_tokens: int = None
    ) -> List[Dict[str, Any]]:
        """
        Expands top reranked chunks with parent section scope and neighboring sequential chunks,
        merging adjacent blocks and deduplicating text.
        """
        if not reranked_chunks or not settings.ENABLE_CONTEXT_EXPANSION or not self.doc_chunks:
            return reranked_chunks

        k_neighbors = max_neighbors if max_neighbors is not None else settings.MAX_NEIGHBOR_CHUNKS
        budget_tokens = max_tokens or settings.MAX_CONTEXT_TOKENS

        indices_to_include = set()
        neighbor_log = []

        # 1. Identify chunk indices for target chunks + neighbors
        for item in reranked_chunks:
            cid = item.get("chunk_id")
            if cid in self.chunk_id_to_index:
                idx = self.chunk_id_to_index[cid]
                indices_to_include.add(idx)

                added_neighbors = []
                target_sec = item.get("section", "")
                target_chap = item.get("chapter", "")

                for offset in range(1, k_neighbors + 1):
                    # Check prev neighbor
                    prev_idx = idx - offset
                    if prev_idx >= 0:
                        prev_c = self.doc_chunks[prev_idx]
                        same_doc = prev_c.get("document_id") == item.get("document_id")
                        same_scope = (not target_sec) or (prev_c.get("section") == target_sec) or (target_chap and prev_c.get("chapter") == target_chap)
                        if same_doc and same_scope:
                            indices_to_include.add(prev_idx)
                            added_neighbors.append(prev_c.get("chunk_id"))

                    # Check next neighbor
                    next_idx = idx + offset
                    if next_idx < len(self.doc_chunks):
                        next_c = self.doc_chunks[next_idx]
                        same_doc = next_c.get("document_id") == item.get("document_id")
                        same_scope = (not target_sec) or (next_c.get("section") == target_sec) or (target_chap and next_c.get("chapter") == target_chap)
                        if same_doc and same_scope:
                            indices_to_include.add(next_idx)
                            added_neighbors.append(next_c.get("chunk_id"))

                if added_neighbors:
                    neighbor_log.append(f"{cid} -> {added_neighbors}")

        if not indices_to_include:
            return reranked_chunks

        sorted_indices = sorted(list(indices_to_include))

        # 2. Group contiguous indices into contiguous blocks
        contiguous_blocks = []
        current_block = [sorted_indices[0]]

        for idx in sorted_indices[1:]:
            if idx == current_block[-1] + 1:
                current_block.append(idx)
            else:
                contiguous_blocks.append(current_block)
                current_block = [idx]
        contiguous_blocks.append(current_block)

        # 3. Create expanded chunk objects for each block
        expanded_chunks = []
        total_used_tokens = 0

        # Build map of reranked target chunk IDs for priority metadata assignment
        target_chunk_ids = {c.get("chunk_id") for c in reranked_chunks if c.get("chunk_id")}

        for block in contiguous_blocks:
            block_chunks = [self.doc_chunks[i] for i in block]
            
            # Select target chunk in block if present, else first chunk
            primary_c = block_chunks[0]
            for c in block_chunks:
                if c.get("chunk_id") in target_chunk_ids:
                    primary_c = c
                    break

            page_start = min(c.get("page_start", c.get("page", 1)) for c in block_chunks)
            page_end = max(c.get("page_end", c.get("page", 1)) for c in block_chunks)

            # Combine texts without duplicating contiguous sentences
            text_snippets = []
            for c in block_chunks:
                t = c.get("text", "").strip()
                if t and t not in text_snippets:
                    text_snippets.append(t)

            combined_text = "\n".join(text_snippets)
            block_tokens = count_tokens(combined_text)

            if total_used_tokens + block_tokens > budget_tokens and expanded_chunks:
                break

            total_used_tokens += block_tokens

            expanded_item = {
                "chunk_id": primary_c.get("chunk_id"),
                "document_id": primary_c.get("document_id"),
                "document_name": primary_c.get("document_name"),
                "page_number": primary_c.get("page_number", primary_c.get("page", 1)),
                "page_start": page_start,
                "page_end": page_end,
                "section": primary_c.get("section", "General"),
                "heading": primary_c.get("heading", ""),
                "chapter": primary_c.get("chapter", ""),
                "content_type": primary_c.get("content_type", "text"),
                "text": combined_text,
                "expanded_block_size": len(block_chunks),
                "metadata": primary_c.get("metadata", {})
            }
            expanded_chunks.append(expanded_item)


        print(f"\n[CONTEXT EXPANSION]")
        print(f"Input reranked chunks: {len(reranked_chunks)}")
        print(f"Expanded context blocks: {len(expanded_chunks)}")
        print(f"Total tokens: {total_used_tokens}")
        if neighbor_log:
            print(f"Included neighbors for chunk_ids: {neighbor_log[:3]}\n")

        return expanded_chunks

# Global singleton instance
context_expansion_service = ContextExpansionService()
