import unittest
import sys
import os

# Set dummy environment variables to avoid Supabase error during import
os.environ['SUPABASE_URL'] = 'https://dummy.supabase.co'
os.environ['SUPABASE_KEY'] = 'dummy_key'
os.environ['BOT_KEY'] = 'dummy_bot_key'

# Add the parent directory to sys.path so we can import api.index
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.index import optimize_url

class TestOptimizeUrl(unittest.TestCase):
    def test_optimize_url_valid_supabase_url(self):
        url = "https://example.supabase.co/storage/v1/object/public/images/test.jpg"
        expected = "https://example.supabase.co/storage/v1/object/public/images/test.jpg?width=1280&quality=80&format=origin"
        self.assertEqual(optimize_url(url), expected)

    def test_optimize_url_valid_supabase_url_with_existing_query(self):
        url = "https://example.supabase.co/storage/v1/object/public/images/test.jpg?foo=bar"
        # Current behavior: returns original url since extension check fails
        # ('jpg?foo=bar' is not in the extension list)
        expected = url
        self.assertEqual(optimize_url(url), expected)

    def test_optimize_url_non_supabase_url(self):
        url = "https://example.com/images/test.jpg"
        self.assertEqual(optimize_url(url), url)

    def test_optimize_url_non_image_extension(self):
        url = "https://example.supabase.co/storage/v1/object/public/documents/test.pdf"
        self.assertEqual(optimize_url(url), url)

    def test_optimize_url_invalid_type(self):
        # Passing invalid types to trigger Exception handling block
        # The bare except should gracefully return the invalid input as-is
        self.assertEqual(optimize_url(123), 123)
        self.assertEqual(optimize_url(None), None)
        self.assertEqual(optimize_url(3.14), 3.14)
        self.assertEqual(optimize_url({"url": "test"}), {"url": "test"})
        self.assertEqual(optimize_url(["http://example.com"]), ["http://example.com"])

if __name__ == '__main__':
    unittest.main()
