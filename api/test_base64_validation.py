import unittest
from unittest.mock import patch, MagicMock
import base64
import os
import sys

# Mock environment variables before importing index.py
os.environ['BOT_KEY'] = 'test_bot_key'
os.environ['SUPABASE_KEY'] = 'test_supabase_key'

# Add api directory to path so index.py can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, MAX_BASE64_LENGTH

class TestBase64Validation(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    @patch('index.supabase')
    @patch('index.bot')
    def test_valid_base64_payload(self, mock_bot, mock_supabase):
        # Mock supabase response
        mock_response = MagicMock()
        mock_response.data = [{'chat_id': 12345, 'thread_id': 67890}]
        mock_supabase.from_.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        valid_base64 = base64.b64encode(b'Hello World!').decode('utf-8')
        response = self.client.post('/api/send_excel', json={
            'project_name': 'Test Project',
            'base64_data': valid_base64
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'ok')
        mock_bot.send_document.assert_called_once()

    def test_oversized_base64_payload(self):
        # Create a payload just over the limit
        oversized_base64 = 'A' * (MAX_BASE64_LENGTH + 1)
        response = self.client.post('/api/send_excel', json={
            'project_name': 'Test Project',
            'base64_data': oversized_base64
        })

        self.assertEqual(response.status_code, 413)
        self.assertIn('error', response.json)
        self.assertEqual(response.json['error'], 'Payload too large')

    @patch('index.supabase')
    def test_invalid_base64_payload(self, mock_supabase):
        # Mock supabase response
        mock_response = MagicMock()
        mock_response.data = [{'chat_id': 12345, 'thread_id': 67890}]
        mock_supabase.from_.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        invalid_base64 = 'This is not valid base64 data!!! ###'
        response = self.client.post('/api/send_excel', json={
            'project_name': 'Test Project',
            'base64_data': invalid_base64
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)
        self.assertEqual(response.json['error'], 'Invalid base64 data')

if __name__ == '__main__':
    unittest.main()
