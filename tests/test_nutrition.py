import unittest
from unittest.mock import patch
import nutrition as N


class NutritionTest(unittest.IsolatedAsyncioTestCase):
    def test_only_configured_providers_are_available(self):
        with patch.dict('os.environ', {'NUTRITION_GEMINI_KEY': 'test', 'NUTRITION_GEMINI_MODEL': 'vision'}, clear=True):
            self.assertEqual(list(N.providers()), ['gemini'])

    async def test_photo_result_is_only_a_draft(self):
        class Response:
            status = 200
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def json(self):
                return {'choices': [{'message': {'content': '{"meal":"Reis", "calories":650,"details":"Portion geschätzt"}'}}]}
        class Session:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def post(self, url, **kwargs):
                self.payload = kwargs['json']
                return Response()
        with patch.object(N.aiohttp, 'ClientSession', return_value=Session()):
            result = await N.analyze(dict(kind='compatible', url='https://example.test/v1', key='secret', model='vision'), b'image', 'image/jpeg')
        self.assertEqual(result['calories'], 650)
        self.assertEqual(result['meal'], 'Reis')
