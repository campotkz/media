import unittest
from unittest.mock import patch
import json
import os
import sys

# Add parent dir to path to allow importing api.index
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set dummy environment variables to avoid errors during import
os.environ['BOT_KEY'] = 'dummy_bot_key'
os.environ['SUPABASE_KEY'] = 'dummy_supabase_key'

from api.index import app

class TestSubmitReport(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('api.index.supabase')
    @patch('api.index.bot')
    def test_submit_report_exception_handling(self, mock_bot, mock_supabase):
        # Setup mock to raise an exception when supabase is called
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = Exception("Supabase connection error")

        test_data = {
            'chat_id': 12345,
            'thread_id': 67890,
            'leads_count': 10,
            'sales_count': 5,
            'client_name': 'Test Client',
            'instagram': '@testclient'
        }

        response = self.app.post('/api/report',
                                 data=json.dumps(test_data),
                                 content_type='application/json')

        # Verify that the response status code is 500 (Internal Server Error)
        self.assertEqual(response.status_code, 500)

        # Verify that the response JSON contains the error message
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
        self.assertEqual(response_data['error'], "Supabase connection error")

if __name__ == '__main__':
    unittest.main()
