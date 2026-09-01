# test_groq_429_retry.py
import unittest
from unittest.mock import MagicMock, patch
import os
import groq
from services.llm_service import (
    execute_groq_completion_with_retry,
    extract_retry_wait_time,
    is_rate_limit_error
)

class TestGroq429RetryHandling(unittest.TestCase):

    def test_1_is_rate_limit_error_detection(self):
        """1. Detects Groq 429 errors accurately across different exception formats."""
        # 1a. groq.RateLimitError instance
        err_response = MagicMock()
        err_response.status_code = 429
        rate_err = groq.RateLimitError(
            message="Rate limit reached. Please try again in 2.5s",
            response=err_response,
            body={"error": {"message": "Rate limit reached"}}
        )
        self.assertTrue(is_rate_limit_error(rate_err))

        # 1b. Generic Exception with 429 message
        generic_err = Exception("Groq API error 429: rate_limit_exceeded")
        self.assertTrue(is_rate_limit_error(generic_err))

        # 1c. Non-429 error (500 internal server error)
        server_err = Exception("Internal server error 500")
        self.assertFalse(is_rate_limit_error(server_err))

        print("\n[Test Pass] 429 Rate limit error detection verified")

    def test_2_extract_retry_wait_time(self):
        """2. Extracts wait duration from HTTP header and error message text."""
        # 2a. Header extraction
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "4.5"}
        err_with_header = groq.RateLimitError(
            message="Rate limit reached",
            response=mock_resp,
            body=None
        )
        self.assertEqual(extract_retry_wait_time(err_with_header), 4.5)

        # 2b. Regex extraction from message string (seconds)
        err_msg_sec = Exception("Rate limit reached. Please try again in 3.2s.")
        self.assertEqual(extract_retry_wait_time(err_msg_sec), 3.2)

        # 2c. Regex extraction from message string (minutes and seconds)
        err_msg_min = Exception("Rate limit reached. Please try again in 1m15s.")
        self.assertEqual(extract_retry_wait_time(err_msg_min), 75.0)

        print("[Test Pass] Server-provided retry/wait extraction verified")

    @patch("time.sleep")
    def test_3_successful_retry_after_429(self, mock_sleep):
        """3. Retries after 429 and succeeds on second attempt."""
        mock_client = MagicMock()
        mock_success = MagicMock()
        mock_success.choices[0].message.content = "Successful summary after retry"

        err_429 = Exception("Groq Rate limit reached. Please try again in 1.0s")
        # 1st call fails with 429, 2nd call succeeds
        mock_client.chat.completions.create.side_effect = [err_429, mock_success]

        response = execute_groq_completion_with_retry(mock_client, model="groq/compound")

        self.assertEqual(response.choices[0].message.content, "Successful summary after retry")
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)
        mock_sleep.assert_called_once()
        print("[Test Pass] 429 Retry -> Wait -> Success flow executed correctly")

    @patch("time.sleep")
    def test_4_max_retries_exceeded_error(self, mock_sleep):
        """4. Stops after max retries and raises descriptive error without infinite loop."""
        mock_client = MagicMock()
        err_429 = Exception("Persistent Rate limit 429 error")
        mock_client.chat.completions.create.side_effect = err_429

        os.environ["GROQ_MAX_RETRIES"] = "3"

        with self.assertRaises(Exception) as cm:
            execute_groq_completion_with_retry(mock_client, model="groq/compound")

        self.assertIn("exceeded after 3 retries", str(cm.exception))
        # Total calls should equal MAX_RETRIES (3)
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)
        print("[Test Pass] Max retry enforcement and descriptive error verified")

if __name__ == "__main__":
    unittest.main()
