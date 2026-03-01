import unittest
from unittest.mock import patch, MagicMock
import os

# Set dummy environment variables to prevent initialization errors in index.py
os.environ['SUPABASE_KEY'] = 'dummy_key'
os.environ['BOT_KEY'] = 'dummy_bot_key'

# Import the function to be tested
from index import _tg_retry

class TestTgRetry(unittest.TestCase):

    @patch('index.time.sleep')
    @patch('index._get_retry_after_seconds')
    def test_success_first_try(self, mock_get_retry, mock_sleep):
        # A function that succeeds immediately
        mock_fn = MagicMock(return_value="success")

        result = _tg_retry(mock_fn, "arg1", kwarg1="val1")

        self.assertEqual(result, "success")
        mock_fn.assert_called_once_with("arg1", kwarg1="val1")
        mock_get_retry.assert_not_called()
        mock_sleep.assert_not_called()

    @patch('index.time.sleep')
    @patch('index._get_retry_after_seconds')
    def test_success_after_retries(self, mock_get_retry, mock_sleep):
        # A function that fails twice then succeeds
        mock_fn = MagicMock(side_effect=[Exception("Error 1"), Exception("Error 2"), "success"])

        # Mock _get_retry_after_seconds to return 5 seconds
        mock_get_retry.return_value = 5

        result = _tg_retry(mock_fn, "arg1")

        self.assertEqual(result, "success")
        self.assertEqual(mock_fn.call_count, 3)
        self.assertEqual(mock_get_retry.call_count, 2)

        # Sleep should be max(1, retry_after) + 1 = 5 + 1 = 6
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(6)

    @patch('index.time.sleep')
    @patch('index._get_retry_after_seconds')
    def test_max_retries_reached(self, mock_get_retry, mock_sleep):
        # A function that always fails
        mock_fn = MagicMock(side_effect=Exception("Persistent Error"))

        # Mock _get_retry_after_seconds to return 2 seconds
        mock_get_retry.return_value = 2

        with self.assertRaises(Exception) as context:
            _tg_retry(mock_fn)

        self.assertEqual(str(context.exception), "Persistent Error")

        # Attempts should be 6
        self.assertEqual(mock_fn.call_count, 6)
        # Sleep called 5 times (after attempt 1, 2, 3, 4, 5. Attempt 6 raises immediately)
        self.assertEqual(mock_sleep.call_count, 5)

    @patch('index.time.sleep')
    @patch('index._get_retry_after_seconds')
    def test_missing_retry_after(self, mock_get_retry, mock_sleep):
        # A function that fails
        mock_fn = MagicMock(side_effect=Exception("Unknown Error"))

        # Mock _get_retry_after_seconds to return None (no retry info)
        mock_get_retry.return_value = None

        with self.assertRaises(Exception) as context:
            _tg_retry(mock_fn)

        self.assertEqual(str(context.exception), "Unknown Error")

        # Should raise immediately on first attempt
        self.assertEqual(mock_fn.call_count, 1)
        mock_sleep.assert_not_called()

if __name__ == '__main__':
    unittest.main()
