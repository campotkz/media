import unittest
from unittest.mock import patch, MagicMock

# Set required environment variables before importing api.index
import os
os.environ["BOT_KEY"] = "mock_bot_key"
os.environ["SUPABASE_URL"] = "http://mock-url"
os.environ["SUPABASE_KEY"] = "mock_supabase_key"

# Mock the supabase client globally before importing index
with patch('supabase.create_client') as mock_create_client:
    mock_supabase = MagicMock()
    mock_create_client.return_value = mock_supabase

    # We also need to mock telebot to prevent it from doing network requests on load if any
    with patch('telebot.TeleBot') as mock_telebot:
        import api.index as index_module

class TestFetchCastingApplications(unittest.TestCase):

    def _create_mock_chain(self):
        """Helper to create the mock chain for supabase queries"""
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_eq2 = MagicMock()
        mock_order = MagicMock()
        mock_range = MagicMock()

        return mock_table, mock_select, mock_eq, mock_eq2, mock_order, mock_range

    @patch('api.index.supabase')
    def test_happy_path_single_page(self, mock_supabase):
        mock_table, mock_select, mock_eq, _, mock_order, mock_range = self._create_mock_chain()
        mock_res = MagicMock()

        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.order.return_value = mock_order
        mock_order.range.return_value = mock_range
        mock_range.execute.return_value = mock_res

        expected_rows = [{"id": 1, "chat_id": 123}, {"id": 2, "chat_id": 123}]
        mock_res.data = expected_rows

        from api.index import fetch_casting_applications
        result = fetch_casting_applications(123)

        self.assertEqual(result, expected_rows)
        mock_supabase.table.assert_called_once_with("casting_applications")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("chat_id", 123)
        mock_eq.order.assert_called_once_with("created_at", desc=False)
        mock_order.range.assert_called_once_with(0, 499)
        mock_range.execute.assert_called_once()

    @patch('api.index.supabase')
    def test_pagination(self, mock_supabase):
        mock_table, mock_select, mock_eq, _, mock_order, mock_range = self._create_mock_chain()

        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.order.return_value = mock_order
        mock_order.range.return_value = mock_range

        page_size = 5
        page_1_data = [{"id": i, "chat_id": 123} for i in range(page_size)]
        page_2_data = [{"id": 5, "chat_id": 123}, {"id": 6, "chat_id": 123}]

        mock_res1 = MagicMock()
        mock_res1.data = page_1_data

        mock_res2 = MagicMock()
        mock_res2.data = page_2_data

        mock_range.execute.side_effect = [mock_res1, mock_res2]

        from api.index import fetch_casting_applications
        result = fetch_casting_applications(123, page_size=page_size)

        self.assertEqual(result, page_1_data + page_2_data)

        self.assertEqual(mock_order.range.call_count, 2)
        mock_order.range.assert_any_call(0, 4)
        mock_order.range.assert_any_call(5, 9)

    @patch('api.index.supabase')
    def test_with_thread_id(self, mock_supabase):
        mock_table, mock_select, mock_eq1, mock_eq2, mock_order, mock_range = self._create_mock_chain()

        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq1
        mock_eq1.eq.return_value = mock_eq2
        mock_eq2.order.return_value = mock_order
        mock_order.range.return_value = mock_range

        expected_rows = [{"id": 1, "chat_id": 123, "thread_id": 456}]

        mock_res = MagicMock()
        mock_res.data = expected_rows
        mock_range.execute.return_value = mock_res

        from api.index import fetch_casting_applications
        result = fetch_casting_applications(123, thread_id=456)

        self.assertEqual(result, expected_rows)
        mock_supabase.table.assert_called_once_with("casting_applications")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("chat_id", 123)
        mock_eq1.eq.assert_called_once_with("thread_id", 456)
        mock_eq2.order.assert_called_once_with("created_at", desc=False)
        mock_order.range.assert_called_once_with(0, 499)
        mock_range.execute.assert_called_once()

    @patch('api.index.supabase')
    def test_empty_results(self, mock_supabase):
        mock_table, mock_select, mock_eq, _, mock_order, mock_range = self._create_mock_chain()

        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.order.return_value = mock_order
        mock_order.range.return_value = mock_range

        mock_res = MagicMock()
        mock_res.data = []
        mock_range.execute.return_value = mock_res

        from api.index import fetch_casting_applications
        result = fetch_casting_applications(123)

        self.assertEqual(result, [])
        mock_supabase.table.assert_called_once_with("casting_applications")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("chat_id", 123)
        mock_eq.order.assert_called_once_with("created_at", desc=False)
        mock_order.range.assert_called_once_with(0, 499)
        mock_range.execute.assert_called_once()

    @patch('api.index.supabase')
    def test_none_data(self, mock_supabase):
        mock_table, mock_select, mock_eq, _, mock_order, mock_range = self._create_mock_chain()

        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.order.return_value = mock_order
        mock_order.range.return_value = mock_range

        mock_res = MagicMock()
        mock_res.data = None
        mock_range.execute.return_value = mock_res

        from api.index import fetch_casting_applications
        result = fetch_casting_applications(123)

        self.assertEqual(result, [])
        mock_supabase.table.assert_called_once_with("casting_applications")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("chat_id", 123)
        mock_eq.order.assert_called_once_with("created_at", desc=False)
        mock_order.range.assert_called_once_with(0, 499)
        mock_range.execute.assert_called_once()

if __name__ == '__main__':
    unittest.main()
