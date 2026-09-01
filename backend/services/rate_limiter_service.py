# services/rate_limiter_service.py
import time
import os
import threading
from typing import List, Tuple

class TokenRateLimiter:
    """
    Sliding-window token-aware rate limiter for LLM API calls.
    Prevents Groq HTTP 429 (Rate Limit Exceeded) errors by tracking token usage per minute.
    """
    def __init__(self, max_tpm: int = None, window_seconds: float = None):
        # Configurable via environment variables GROQ_MAX_TPM (default 25,000) and GROQ_RATE_WINDOW_SECONDS (default 60.0)
        if max_tpm is None:
            max_tpm = int(os.getenv("GROQ_MAX_TPM", "25000"))
        if window_seconds is None:
            window_seconds = float(os.getenv("GROQ_RATE_WINDOW_SECONDS", "60.0"))
        self.max_tpm = max_tpm
        self.window_seconds = window_seconds
        self.history: List[Tuple[float, int]] = []  # Stores (timestamp, token_count)
        self.lock = threading.Lock()

    def _purge_expired(self, now: float):
        """Removes requests older than the sliding window."""
        cutoff = now - self.window_seconds
        self.history = [entry for entry in self.history if entry[0] > cutoff]

    def get_current_tpm_usage(self) -> int:
        """Returns total tokens consumed within the active sliding window."""
        now = time.time()
        with self.lock:
            self._purge_expired(now)
            return sum(tokens for _, tokens in self.history)

    def wait_for_capacity(self, estimated_tokens: int):
        """
        Blocks and waits if adding estimated_tokens would exceed max_tpm in the active window.
        Records the token allocation once capacity is guaranteed.
        """
        estimated_tokens = min(estimated_tokens, self.max_tpm)
        with self.lock:
            while True:
                now = time.time()
                self._purge_expired(now)
                current_usage = sum(tokens for _, tokens in self.history)

                if current_usage + estimated_tokens <= self.max_tpm:
                    self.history.append((now, estimated_tokens))
                    return

                # Calculate exact wait duration until the oldest request expires
                if self.history:
                    oldest_time = self.history[0][0]
                    wait_time = max(0.1, (oldest_time + self.window_seconds) - now + 0.1)
                else:
                    wait_time = 1.0

                print(
                    f"[RateLimiter] Token budget reached ({current_usage}/{self.max_tpm} TPM). "
                    f"Waiting {wait_time:.1f}s for rate limit window to refresh..."
                )
                
                # Release lock while waiting so other operations aren't blocked
                self.lock.release()
                time.sleep(wait_time)
                self.lock.acquire()

# Shared singleton rate limiter instance for Groq requests
groq_rate_limiter = TokenRateLimiter()
