import unittest
import sys
import os
from unittest.mock import MagicMock

# Add parent dir to path to import api.index
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
os.environ['SUPABASE_KEY'] = 'test-key'
os.environ['SUPABASE_PAT'] = 'test-pat'
os.environ['BOT_KEY'] = 'test-bot-key'

from api.index import _check_blacklist, _prepare_telegram_media

class TestCastingHelpers(unittest.TestCase):
    def test_check_blacklist_blocked_phone(self):
        mock_supabase = MagicMock()
        mock_query = mock_supabase.table.return_value.select.return_value.eq.return_value
        mock_query.execute.return_value.data = [{"id": 1}]

        is_blocked, response = _check_blacklist("123456789", None, mock_supabase)

        self.assertTrue(is_blocked)
        self.assertEqual(response['status'], 'blocked')

    def test_check_blacklist_not_blocked(self):
        mock_supabase = MagicMock()
        mock_query = mock_supabase.table.return_value.select.return_value.eq.return_value
        mock_query.execute.return_value.data = []

        is_blocked, response = _check_blacklist("123456789", None, mock_supabase)

        self.assertFalse(is_blocked)
        self.assertIsNone(response)

    def test_prepare_telegram_media_only_photos(self):
        mock_types = MagicMock()

        data = {'photo_urls': ['http://url1', 'http://url2']}
        media = _prepare_telegram_media(data, "caption", mock_types)

        self.assertEqual(len(media), 2)
        mock_types.InputMediaPhoto.assert_any_call('http://url1', caption="caption", parse_mode="HTML")
        mock_types.InputMediaPhoto.assert_any_call('http://url2')

    def test_prepare_telegram_media_video_only(self):
        mock_types = MagicMock()

        data = {'video_audition_url': 'http://video1'}
        media = _prepare_telegram_media(data, "caption", mock_types)

        self.assertEqual(len(media), 1)
        mock_types.InputMediaVideo.assert_called_once_with('http://video1', caption="caption", parse_mode="HTML")

if __name__ == '__main__':
    unittest.main()
