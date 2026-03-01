import unittest
from unittest.mock import patch, MagicMock, call
import os

# Set dummy environment variables to prevent initialization errors
os.environ['BOT_KEY'] = '123456:dummy_bot_key'
os.environ['SUPABASE_KEY'] = 'dummy_supabase_key'
os.environ['SUPABASE_PAT'] = 'dummy_supabase_pat'

# Now we can import the api.index module safely
import api.index as api_index

class TestHandleStart(unittest.TestCase):
    @patch('api.index.bot.send_message')
    @patch('api.index.supabase')
    def test_handle_start_with_thread(self, mock_supabase, mock_send_message):
        # Create a mock message
        mock_message = MagicMock()
        mock_message.chat.id = 123
        mock_message.message_thread_id = 456

        # Setup mock supabase behavior
        mock_supabase_chain = MagicMock()
        mock_supabase.from_.return_value = mock_supabase_chain

        # For update operation
        mock_supabase_update = MagicMock()
        mock_supabase_chain.update.return_value = mock_supabase_update
        mock_supabase_update.eq.return_value = mock_supabase_update

        # For select operation
        mock_supabase_select = MagicMock()
        mock_supabase_chain.select.return_value = mock_supabase_select
        mock_supabase_select.eq.return_value = mock_supabase_select

        # Setup mock response for the select query
        mock_select_response = MagicMock()
        mock_select_response.data = [{'name': 'Test Project'}]
        mock_supabase_select.execute.return_value = mock_select_response

        # Call the function
        api_index.handle_start(mock_message)

        # 1. Verify update query
        mock_supabase.from_.assert_any_call('clients')
        mock_supabase_chain.update.assert_called_with({'is_active': True})

        # 2. Verify select query
        mock_supabase_chain.select.assert_called_with('name')

        # 3. Verify bot.send_message
        mock_send_message.assert_called_once()
        args, kwargs = mock_send_message.call_args

        # Check basic arguments
        self.assertEqual(args[0], 123)
        self.assertEqual(args[1], "🦾 **GULYWOOD ERP**")
        self.assertEqual(kwargs['message_thread_id'], 456)
        self.assertEqual(kwargs['parse_mode'], "Markdown")

        # Check markup
        markup = kwargs['reply_markup']
        self.assertIsNotNone(markup)

        # Extract buttons
        # Telebot InlineKeyboardMarkup stores buttons in keyboard
        buttons = []
        for row in markup.keyboard:
            for btn in row:
                buttons.append(btn)

        self.assertEqual(len(buttons), 4)

        # Check button properties
        self.assertEqual(buttons[0].text, "📅 КАЛЕНДАРЬ")
        self.assertTrue("cid=123&tid=456" in buttons[0].url)

        self.assertEqual(buttons[1].text, "📊 ФИДБЕК")
        self.assertTrue("cid=123&tid=456" in buttons[1].url)

        self.assertEqual(buttons[2].text, "🎭 КАСТИНГ")
        self.assertEqual(buttons[2].url, f"{api_index.APP_URL}casting.html")

        self.assertEqual(buttons[3].text, "🎯 ТОЛЬКО ЭТОТ КАСТИНГ")
        self.assertTrue("proj=Test%20Project" in buttons[3].url)
        self.assertTrue("cid=123&tid=456" in buttons[3].url)

    @patch('api.index.bot.send_message')
    @patch('api.index.supabase')
    def test_handle_start_without_thread(self, mock_supabase, mock_send_message):
        # Create a mock message
        mock_message = MagicMock()
        mock_message.chat.id = 123
        mock_message.message_thread_id = None

        # Call the function
        api_index.handle_start(mock_message)

        # 1. Verify supabase was NOT called
        mock_supabase.from_.assert_not_called()

        # 2. Verify bot.send_message
        mock_send_message.assert_called_once()
        args, kwargs = mock_send_message.call_args

        # Check basic arguments
        self.assertEqual(args[0], 123)
        self.assertEqual(args[1], "🦾 **GULYWOOD ERP**")
        self.assertIsNone(kwargs['message_thread_id'])
        self.assertEqual(kwargs['parse_mode'], "Markdown")

        # Check markup
        markup = kwargs['reply_markup']
        self.assertIsNotNone(markup)

        # Extract buttons
        buttons = []
        for row in markup.keyboard:
            for btn in row:
                buttons.append(btn)

        self.assertEqual(len(buttons), 3) # Should only have 3 buttons

        # Check button properties
        self.assertEqual(buttons[0].text, "📅 КАЛЕНДАРЬ")
        self.assertTrue("cid=123&tid=" in buttons[0].url)

        self.assertEqual(buttons[1].text, "📊 ФИДБЕК")
        self.assertTrue("cid=123&tid=" in buttons[1].url)

        self.assertEqual(buttons[2].text, "🎭 КАСТИНГ")
        self.assertEqual(buttons[2].url, f"{api_index.APP_URL}casting.html")

if __name__ == '__main__':
    unittest.main()
