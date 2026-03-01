import unittest
from unittest.mock import patch, MagicMock

# Import the module to test
# Check db script has code executed when __main__ which is fine, but we will mock supabase client
import api.check_db as check_db

class TestCheckDB(unittest.TestCase):
    @patch('api.check_db.supabase')
    @patch('builtins.print')
    def test_check(self, mock_print, mock_supabase):
        # Create mock responses for supabase chains
        mock_team_res = MagicMock()
        mock_team_res.data = [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]

        mock_clients_res = MagicMock()
        mock_clients_res.data = [{'id': 10, 'thread_id': 't1'}, {'id': 11, 'thread_id': 't2'}]

        mock_contacts_res = MagicMock()
        mock_contacts_res.data = [{'id': 100, 'name': 'Contact A'}]

        # Setup the chains

        # 1. Team chain: supabase.from_("team").select("*").execute()
        mock_from_team = MagicMock()
        mock_select_team = MagicMock()
        mock_from_team.select.return_value = mock_select_team
        mock_select_team.execute.return_value = mock_team_res

        # 2. Clients chain: supabase.from_("clients").select("*").not_.is_("thread_id", "null").execute()
        mock_from_clients = MagicMock()
        mock_select_clients = MagicMock()
        mock_not_clients = MagicMock()
        mock_is_clients = MagicMock()

        mock_from_clients.select.return_value = mock_select_clients
        mock_select_clients.not_ = mock_not_clients
        mock_not_clients.is_.return_value = mock_is_clients
        mock_is_clients.execute.return_value = mock_clients_res

        # 3. Contacts chain: supabase.from_("contacts").select("*").execute()
        mock_from_contacts = MagicMock()
        mock_select_contacts = MagicMock()
        mock_from_contacts.select.return_value = mock_select_contacts
        mock_select_contacts.execute.return_value = mock_contacts_res

        # Map supabase.from_ calls to correct chains based on table name
        def from_side_effect(table_name):
            if table_name == "team":
                return mock_from_team
            elif table_name == "clients":
                return mock_from_clients
            elif table_name == "contacts":
                return mock_from_contacts
            else:
                return MagicMock()

        mock_supabase.from_.side_effect = from_side_effect

        # Run the check function
        check_db.check()

        # Verify supabase.from_ was called with expected arguments
        mock_supabase.from_.assert_any_call("team")
        mock_supabase.from_.assert_any_call("clients")
        mock_supabase.from_.assert_any_call("contacts")

        # Verify print was called with expected headers and data rows
        expected_prints = [
            unittest.mock.call("--- TEAM ---"),
            unittest.mock.call({'id': 1, 'name': 'Alice'}),
            unittest.mock.call({'id': 2, 'name': 'Bob'}),
            unittest.mock.call("\n--- CLIENTS (Active Topics) ---"),
            unittest.mock.call({'id': 10, 'thread_id': 't1'}),
            unittest.mock.call({'id': 11, 'thread_id': 't2'}),
            unittest.mock.call("\n--- CONTACTS ---"),
            unittest.mock.call({'id': 100, 'name': 'Contact A'}),
        ]

        mock_print.assert_has_calls(expected_prints, any_order=False)
        self.assertEqual(mock_print.call_count, len(expected_prints))

    @patch('api.check_db.supabase')
    @patch('builtins.print')
    def test_check_empty_data(self, mock_print, mock_supabase):
        # Create mock responses for supabase chains with empty data
        mock_empty_res = MagicMock()
        mock_empty_res.data = []

        # Setup the chains for empty data
        mock_from_team = MagicMock()
        mock_select_team = MagicMock()
        mock_from_team.select.return_value = mock_select_team
        mock_select_team.execute.return_value = mock_empty_res

        mock_from_clients = MagicMock()
        mock_select_clients = MagicMock()
        mock_not_clients = MagicMock()
        mock_is_clients = MagicMock()
        mock_from_clients.select.return_value = mock_select_clients
        mock_select_clients.not_ = mock_not_clients
        mock_not_clients.is_.return_value = mock_is_clients
        mock_is_clients.execute.return_value = mock_empty_res

        mock_from_contacts = MagicMock()
        mock_select_contacts = MagicMock()
        mock_from_contacts.select.return_value = mock_select_contacts
        mock_select_contacts.execute.return_value = mock_empty_res

        def from_side_effect(table_name):
            if table_name == "team":
                return mock_from_team
            elif table_name == "clients":
                return mock_from_clients
            elif table_name == "contacts":
                return mock_from_contacts
            else:
                return MagicMock()

        mock_supabase.from_.side_effect = from_side_effect

        check_db.check()

        # Only the headers should be printed, no data
        expected_prints = [
            unittest.mock.call("--- TEAM ---"),
            unittest.mock.call("\n--- CLIENTS (Active Topics) ---"),
            unittest.mock.call("\n--- CONTACTS ---"),
        ]
        mock_print.assert_has_calls(expected_prints, any_order=False)
        self.assertEqual(mock_print.call_count, len(expected_prints))

if __name__ == '__main__':
    unittest.main()
