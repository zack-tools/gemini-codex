import unittest
from unittest.mock import patch, mock_open
import check_quota as q
class GeminiRegression(unittest.TestCase):
 def collect(self,models):
  with patch.object(q,'get_auth_file',return_value=__file__),patch('builtins.open',mock_open(read_data='{"access_token":"fake"}')),patch.object(q,'fetch_models',return_value={'models':models}):
   return q.collect_antigravity_quota()
 def test_internal_flash_does_not_override_missing_gemini(self):
  r=self.collect({'tab_flash_lite_preview':{'quotaInfo':{'remainingFraction':1}},'gemini-3.1-pro-high':{'quotaInfo':{'resetTime':'2026-09-30T10:52:21Z'}}})
  self.assertIsNone(r['gemini']['percent'])
  self.assertEqual(r['gemini']['resetTimeLocal'],'2026-09-30 18:52:21')
  self.assertEqual(len(r['geminiModels']),1)
 def test_lowest_and_missing(self):
  models={'gemini-a':{'quotaInfo':{'remainingFraction':.7}},'gemini-b':{'quotaInfo':{'remainingFraction':.2}}}
  self.assertEqual(self.collect(models)['gemini']['percent'],20)
  models['gemini-c']={'quotaInfo':{'resetTime':'2026-09-30T10:52:21Z'}}
  self.assertIsNone(self.collect(models)['gemini']['percent'])
 def test_only_internal(self):
  self.assertIsNone(self.collect({'tab_flash_lite_preview':{'quotaInfo':{'remainingFraction':1}}})['gemini'])
