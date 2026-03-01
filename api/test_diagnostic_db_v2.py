import pytest
from unittest.mock import patch, MagicMock
from api.diagnostic_db_v2 import main

@pytest.fixture
def mock_supabase_client():
    with patch('api.diagnostic_db_v2.create_client') as mock_create:
        client_mock = MagicMock()
        mock_create.return_value = client_mock
        yield client_mock

def test_main_with_records(mock_supabase_client):
    # Setup mock chain: .from_(table_name).select("*").eq("chat_id", ...).execute()

    # We want to support multiple table queries.
    def side_effect_from(table_name):
        mock_builder = MagicMock()
        mock_execute = MagicMock()

        if table_name == "clients":
            mock_execute.data = [
                {"id": 1, "thread_id": 123, "name": "Test Client", "is_hidden": False, "is_active": True},
                {"id": 2, "thread_id": 456, "name": "Another Client", "is_hidden": True, "is_active": False}
            ]
        else:
            mock_execute.data = [] # Empty for other tables

        # Make the builder return itself for chainable methods
        mock_builder.select.return_value = mock_builder
        mock_builder.eq.return_value = mock_builder
        mock_builder.order.return_value = mock_builder
        mock_builder.limit.return_value = mock_builder

        # Make the terminal method return the execute mock
        mock_builder.execute.return_value = mock_execute

        return mock_builder

    mock_supabase_client.from_.side_effect = side_effect_from

    with patch('builtins.print') as mock_print:
        main()

        # Verify the mock chain was called
        # The rationale says "multiple table queries", so we verify that clients table was queried,
        # but we don't assert it was the *only* one.
        mock_supabase_client.from_.assert_any_call("clients")

        # Verify print output
        mock_print.assert_any_call("Checking projects for chat_id: -1003738942785")
        mock_print.assert_any_call("Found 2 records:")
        mock_print.assert_any_call("ID: 1 | Thread: 123 | Name: Test Client | Hidden: False | Active: True")
        mock_print.assert_any_call("ID: 2 | Thread: 456 | Name: Another Client | Hidden: True | Active: False")

def test_main_no_records(mock_supabase_client):
    # Setup mock chain for empty response across any table
    def side_effect_from(table_name):
        mock_builder = MagicMock()
        mock_execute = MagicMock()

        mock_execute.data = []

        mock_builder.select.return_value = mock_builder
        mock_builder.eq.return_value = mock_builder
        mock_builder.order.return_value = mock_builder
        mock_builder.limit.return_value = mock_builder

        mock_builder.execute.return_value = mock_execute

        return mock_builder

    mock_supabase_client.from_.side_effect = side_effect_from

    with patch('builtins.print') as mock_print:
        main()

        # Verify the mock chain was called correctly
        mock_supabase_client.from_.assert_any_call("clients")

        # Verify print output
        mock_print.assert_any_call("Checking projects for chat_id: -1003738942785")
        mock_print.assert_any_call("No records found for this chat_id.")
