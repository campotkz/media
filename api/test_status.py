import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Set required environment variables before importing
os.environ['BOT_KEY'] = '123456:dummy'
os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
os.environ['SUPABASE_KEY'] = 'test_supabase_key'

# Add parent directory to path to allow import api.index
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.index import handle_status, VERSION

class TestHandleStatus(unittest.TestCase):
    def setUp(self):
        # Create a mock message and user
        self.mock_message = MagicMock()
        self.mock_user = MagicMock()
        self.mock_user.id = 123456789
        self.mock_user.first_name = "TestUser"
        self.mock_message.from_user = self.mock_user

    @patch('api.index.supabase')
    @patch('api.index.bot.reply_to')
    def test_handle_status_with_position(self, mock_reply_to, mock_supabase):
        # Mock supabase response
        mock_execute = MagicMock()
        mock_execute.execute.return_value.data = [{'position': 'Director'}]
        mock_eq = MagicMock()
        mock_eq.eq.return_value = mock_execute
        mock_select = MagicMock()
        mock_select.select.return_value = mock_eq
        mock_supabase.from_.return_value = mock_select

        handle_status(self.mock_message)

        expected_text = f"🤖 **Bot Status**\nVersion: `{VERSION}`\nUser: `TestUser`\nID: `123456789`\nPosition: `Director`"
        mock_reply_to.assert_called_with(self.mock_message, expected_text, parse_mode="Markdown")

    @patch('api.index.supabase')
    @patch('api.index.bot.reply_to')
    def test_handle_status_unregistered(self, mock_reply_to, mock_supabase):
        # Mock supabase response
        mock_execute = MagicMock()
        mock_execute.execute.return_value.data = []
        mock_eq = MagicMock()
        mock_eq.eq.return_value = mock_execute
        mock_select = MagicMock()
        mock_select.select.return_value = mock_eq
        mock_supabase.from_.return_value = mock_select

        handle_status(self.mock_message)

        expected_text = f"🤖 **Bot Status**\nVersion: `{VERSION}`\nUser: `TestUser`\nID: `123456789`\nPosition: `не зарегистрирован`"
        mock_reply_to.assert_called_with(self.mock_message, expected_text, parse_mode="Markdown")

    @patch('api.index.supabase')
    @patch('api.index.bot.reply_to')
    def test_handle_status_no_position(self, mock_reply_to, mock_supabase):
        # Mock supabase response
        mock_execute = MagicMock()
        mock_execute.execute.return_value.data = [{}]  # Empty dict, missing 'position'
        mock_eq = MagicMock()
        mock_eq.eq.return_value = mock_execute
        mock_select = MagicMock()
        mock_select.select.return_value = mock_eq
        mock_supabase.from_.return_value = mock_select

        handle_status(self.mock_message)

        expected_text = f"🤖 **Bot Status**\nVersion: `{VERSION}`\nUser: `TestUser`\nID: `123456789`\nPosition: `None`"
        mock_reply_to.assert_called_with(self.mock_message, expected_text, parse_mode="Markdown")

    @patch('api.index.supabase')
    @patch('api.index.bot.reply_to')
    def test_handle_status_exception(self, mock_reply_to, mock_supabase):
        # Mock supabase response to raise Exception
        mock_supabase.from_.side_effect = Exception("Database connection error")

        handle_status(self.mock_message)

        mock_reply_to.assert_called_with(self.mock_message, "Status Error: Database connection error")

if __name__ == '__main__':
    unittest.main()
