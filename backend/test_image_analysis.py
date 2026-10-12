import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.image_analysis import ImageAnalysisService


class ImageAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / 'image.jpg'
        self.image.write_bytes(b'first-image')
        self.service = ImageAnalysisService(self.root / 'cache')
        self.analysis = {'raw_text': 'Alex -> 3 kg Beans -> Friday',
                         'normalized_text': 'Alex -> 3 kg Beans -> Friday',
                         'document': {'type': 'CUSTOMER_ORDER'},
                         'fields': {'amount': {'value': None, 'status': 'NOT_PRESENT'}}}

    def tearDown(self):
        self.temp.cleanup()

    def response(self):
        response = Mock(status_code=200)
        response.json.return_value = {'candidates': [{'content': {'parts': [{'text': json.dumps(self.analysis)}]}}]}
        return response

    @patch('app.services.image_analysis.httpx.post')
    def test_identical_bytes_reuse_provider_only_result(self, request):
        request.return_value = self.response()
        first, cached = self.service.analyze(self.image)
        self.assertFalse(cached)
        second, cached = self.service.analyze(self.image)
        self.assertTrue(cached)
        self.assertEqual(first, second)
        self.assertIsNone(second['fields']['amount']['value'])
        request.assert_called_once()

    @patch('app.services.image_analysis.httpx.post')
    def test_changed_bytes_never_reuse_other_image_result(self, request):
        request.return_value = self.response()
        self.service.analyze(self.image)
        self.image.write_bytes(b'different-image')
        _, cached = self.service.analyze(self.image)
        self.assertFalse(cached)
        self.assertEqual(request.call_count, 2)

    @patch('app.services.image_analysis.httpx.post')
    def test_hash_mismatch_stops_before_network_or_cache(self, request):
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.service.analyze(self.image, hashlib.sha256(b'wrong-image').hexdigest())
        request.assert_not_called()

    @patch('app.services.image_analysis.httpx.post')
    def test_quota_failure_is_not_cached_or_returned_as_text(self, request):
        request.return_value = Mock(status_code=429)
        with self.assertRaisesRegex(RuntimeError, 'quota'):
            self.service.analyze(self.image)
        self.assertFalse((self.root / 'cache').exists())


if __name__ == '__main__':
    unittest.main()
