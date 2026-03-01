import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Set environment variables for import
os.environ['BOT_KEY'] = 'mock_bot_key'
os.environ['SUPABASE_KEY'] = 'mock_supabase_key'

# Add parent dir to sys.path to import api module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from api.index
from api.index import handle_calendar, bot, APP_URL, types

class TestHandleCalendar(unittest.TestCase):
    def setUp(self):
        # Create a mock message object
        self.mock_message = MagicMock()
        self.mock_message.chat.id = 12345

    @patch('api.index.bot.send_message')
    def test_handle_calendar_with_thread_id(self, mock_send_message):
        self.mock_message.message_thread_id = 67890

        handle_calendar(self.mock_message)

        # Verify the markup URL
        expected_url = f"{APP_URL}index.html?cid=12345&tid=67890"

        # Verify bot.send_message was called correctly
        mock_send_message.assert_called_once()
        args, kwargs = mock_send_message.call_args

        self.assertEqual(args[0], 12345)
        self.assertIn("GULYWOOD CALENDAR", args[1])
        self.assertEqual(kwargs.get('message_thread_id'), 67890)
        self.assertEqual(kwargs.get('parse_mode'), "Markdown")

        # Check that markup has the correct URL
        markup = kwargs.get('reply_markup')
        self.assertIsInstance(markup, types.InlineKeyboardMarkup)
        keyboard = markup.keyboard
        self.assertTrue(any(
            button.url == expected_url
            for row in keyboard
            for button in row
            if hasattr(button, 'url')
        ))

    @patch('api.index.bot.send_message')
    def test_handle_calendar_without_thread_id(self, mock_send_message):
        self.mock_message.message_thread_id = None

        handle_calendar(self.mock_message)

        # Verify the markup URL
        expected_url = f"{APP_URL}index.html?cid=12345&tid="

        # Verify bot.send_message was called correctly
        mock_send_message.assert_called_once()
        args, kwargs = mock_send_message.call_args

        self.assertEqual(args[0], 12345)
        self.assertIn("GULYWOOD CALENDAR", args[1])
        self.assertEqual(kwargs.get('message_thread_id'), None)
        self.assertEqual(kwargs.get('parse_mode'), "Markdown")

        # Check that markup has the correct URL
        markup = kwargs.get('reply_markup')
        self.assertIsInstance(markup, types.InlineKeyboardMarkup)
        keyboard = markup.keyboard
        self.assertTrue(any(
            button.url == expected_url
            for row in keyboard
            for button in row
            if hasattr(button, 'url')
        ))

    @patch('api.index.bot.reply_to')
    @patch('api.index.bot.send_message')
    def test_handle_calendar_exception(self, mock_send_message, mock_reply_to):
        self.mock_message.message_thread_id = 67890

        # Force send_message to raise an exception
        mock_send_message.side_effect = Exception("Test Error")

        handle_calendar(self.mock_message)

        # Verify that the exception was caught and reply_to was called
        mock_reply_to.assert_called_once()
        args, kwargs = mock_reply_to.call_args

        self.assertEqual(args[0], self.mock_message)
        self.assertIn("❌ Ошибка: Test Error", args[1])

if __name__ == '__main__':
    unittest.main()
