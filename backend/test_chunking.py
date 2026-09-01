# test_chunking.py
import unittest
from services.chunk_service import chunk_text_by_tokens
from services.token_service import count_tokens

class TestTokenChunking(unittest.TestCase):

    def setUp(self):
        self.paragraph_template = (
            "Section {id}: Artificial intelligence (AI) is transforming document processing. "
            "Large language models enable advanced analysis, summarization, and query processing. "
            "Using efficient chunking strategy ensures API requests remain within model context and rate limits. "
            "Paragraph {id} continues with detailed domain knowledge and structural breakdown.\n\n"
        )

    def test_1_small_text(self):
        """1. Small text should return exactly 1 chunk if within limit."""
        small_text = self.paragraph_template.format(id=1) * 3
        total_tokens = count_tokens(small_text)
        
        chunks = chunk_text_by_tokens(small_text, max_tokens_per_chunk=250, overlap_tokens=20)
        
        self.assertLessEqual(total_tokens, 250)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], small_text)
        print(f"\n[Test 1 Pass] Small text ({total_tokens} tokens) -> {len(chunks)} chunk")

    def test_2_medium_text(self):
        """2. Medium text should split into multiple chunks respecting max_tokens."""
        medium_text = "".join([self.paragraph_template.format(id=i) for i in range(1, 30)])
        total_tokens = count_tokens(medium_text)
        
        chunks = chunk_text_by_tokens(medium_text, max_tokens_per_chunk=200, overlap_tokens=40)
        
        self.assertGreater(len(chunks), 1)
        for idx, chunk in enumerate(chunks):
            chunk_tokens = count_tokens(chunk)
            self.assertLessEqual(chunk_tokens, 210)  # boundary tolerance
        print(f"[Test 2 Pass] Medium text ({total_tokens} tokens) -> {len(chunks)} chunks")

    def test_3_large_text(self):
        """3. Large text should handle high token volumes cleanly."""
        large_text = "".join([self.paragraph_template.format(id=i) for i in range(1, 300)])
        total_tokens = count_tokens(large_text)
        
        # Test with target production limits: 6500 max tokens per chunk, 400 overlap
        chunks = chunk_text_by_tokens(large_text, max_tokens_per_chunk=6500, overlap_tokens=400)
        
        self.assertTrue(len(chunks) >= 1)
        for idx, chunk in enumerate(chunks):
            self.assertLessEqual(count_tokens(chunk), 6500)
        print(f"[Test 3 Pass] Large text ({total_tokens} tokens) -> {len(chunks)} chunks (max chunk tokens: {max(count_tokens(c) for c in chunks)})")

    def test_4_overlap(self):
        """4. Overlap: consecutive chunks should share content at boundaries."""
        text = "".join([self.paragraph_template.format(id=i) for i in range(1, 40)])
        chunks = chunk_text_by_tokens(text, max_tokens_per_chunk=200, overlap_tokens=50)
        
        self.assertGreater(len(chunks), 1)
        # Check overlap between chunk 0 and chunk 1
        end_of_chunk_0 = chunks[0][-60:]
        self.assertIn(end_of_chunk_0[:30], chunks[1])
        print(f"[Test 4 Pass] Overlap verified between consecutive chunks")

    def test_5_order_preservation(self):
        """5. Order preservation: section IDs must appear in strictly ascending order across chunks."""
        text = "".join([self.paragraph_template.format(id=i) for i in range(1, 50)])
        chunks = chunk_text_by_tokens(text, max_tokens_per_chunk=300, overlap_tokens=50)
        
        found_ids = []
        for chunk in chunks:
            import re
            ids_in_chunk = [int(x) for x in re.findall(r"Section (\d+):", chunk)]
            for sec_id in ids_in_chunk:
                if not found_ids or sec_id >= found_ids[-1]:
                    found_ids.append(sec_id)
                else:
                    self.fail(f"Order violated: section {sec_id} appeared after {found_ids[-1]}")
                    
        print(f"[Test 5 Pass] Document order strictly preserved across all {len(chunks)} chunks")

if __name__ == "__main__":
    unittest.main()
