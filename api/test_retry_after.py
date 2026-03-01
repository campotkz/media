import unittest
from index import _get_retry_after_seconds
from telebot.apihelper import ApiTelegramException

def create_telegram_exception(error_code=429, retry_after=None, description="Too Many Requests"):
    """Helper function to create a mocked ApiTelegramException."""
    result_json = {"error_code": error_code, "description": description}
    if retry_after is not None:
        result_json["parameters"] = {"retry_after": retry_after}

    class MockResult:
        def __init__(self, json_data):
            self.json = lambda: json_data

    # ApiTelegramException expects (function_name, result, result_json)
    exc = ApiTelegramException("function_name", MockResult(result_json), result_json)
    return exc

class TestGetRetryAfterSeconds(unittest.TestCase):

    def test_with_api_telegram_exception_and_parameters(self):
        """Test with valid 429 error and integer retry_after in parameters."""
        exc = create_telegram_exception(retry_after=10)
        result = _get_retry_after_seconds(exc)
        self.assertEqual(result, 10)

    def test_with_api_telegram_exception_and_string_retry_after(self):
        """Test with valid 429 error and string retry_after in parameters."""
        exc = create_telegram_exception(retry_after="15")
        result = _get_retry_after_seconds(exc)
        self.assertEqual(result, 15)

    def test_with_api_telegram_exception_and_no_parameters(self):
        """Test with 429 error but no parameters containing retry_after."""
        exc = create_telegram_exception()
        result = _get_retry_after_seconds(exc)
        self.assertIsNone(result)

    def test_with_api_telegram_exception_and_not_429(self):
        """Test with an error that is not 429, even if retry_after is present."""
        exc = create_telegram_exception(error_code=400, retry_after=10, description="Bad Request")
        result = _get_retry_after_seconds(exc)
        self.assertIsNone(result)

    def test_with_regex_match(self):
        """Test fallback regex matching when exception message contains 'retry after X'."""
        exc = Exception("Telegram API returned an error: retry after 20 seconds")
        result = _get_retry_after_seconds(exc)
        self.assertEqual(result, 20)

    def test_with_regex_match_different_case(self):
        """Test fallback regex matching with different case."""
        exc = Exception("Retry After 25")
        result = _get_retry_after_seconds(exc)
        self.assertEqual(result, 25)

    def test_with_no_match(self):
        """Test with exception that has no matching criteria."""
        exc = Exception("Some other error")
        result = _get_retry_after_seconds(exc)
        self.assertIsNone(result)

    def test_with_none(self):
        """Test passing None safely returns None."""
        result = _get_retry_after_seconds(None)
        self.assertIsNone(result)

    def test_api_telegram_exception_malformed_retry_after(self):
        """Test with a malformed retry_after value that cannot be cast to int."""
        exc = create_telegram_exception(retry_after="not_an_int")
        result = _get_retry_after_seconds(exc)
        self.assertIsNone(result)

    def test_api_telegram_exception_missing_result_json(self):
        """Test with ApiTelegramException lacking result_json entirely."""
        exc = create_telegram_exception()
        exc.result_json = None
        result = _get_retry_after_seconds(exc)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
