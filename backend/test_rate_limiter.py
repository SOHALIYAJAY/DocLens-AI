# test_rate_limiter.py
import unittest
import time
from services.rate_limiter_service import TokenRateLimiter

class TestTokenRateLimiter(unittest.TestCase):

    def test_token_tracking_under_limit(self):
        """1. Token usage under max_tpm should proceed immediately without blocking."""
        limiter = TokenRateLimiter(max_tpm=10000, window_seconds=2.0)
        
        start = time.time()
        limiter.wait_for_capacity(3000)
        limiter.wait_for_capacity(4000)
        elapsed = time.time() - start
        
        self.assertLess(elapsed, 0.5)
        self.assertEqual(limiter.get_current_tpm_usage(), 7000)
        print("\n[Test Pass] Token tracking under limit executed without delay")

    def test_rate_limit_blocking_and_window_refresh(self):
        """2. When token budget is exhausted, wait_for_capacity should block until window refreshes."""
        # Max capacity 10,000 tokens per 1.0 second window
        limiter = TokenRateLimiter(max_tpm=10000, window_seconds=1.0)
        
        # Consume 8,000 tokens
        limiter.wait_for_capacity(8000)
        
        start = time.time()
        # Requesting another 4,000 tokens (8000 + 4000 = 12000 > 10000) -> must wait
        limiter.wait_for_capacity(4000)
        elapsed = time.time() - start
        
        # Must have waited at least ~0.8-1.0s for the window to refresh
        self.assertGreaterEqual(elapsed, 0.7)
        print(f"[Test Pass] Rate limiter blocked as expected and resumed after {elapsed:.2f}s")

if __name__ == "__main__":
    unittest.main()
