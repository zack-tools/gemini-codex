import contextlib,io,json,unittest,urllib.error
from unittest.mock import patch,MagicMock
import check_quota as q

def response(value):
 m=MagicMock(); m.__enter__.return_value=io.BytesIO(json.dumps(value).encode()); return m
class QuotaBucketTests(unittest.TestCase):
 def test_explicit_zero_and_positive(self):
  model={'models':{'gemini-pro':{'quotaInfo':{'resetTime':'today'}},'claude-sonnet':{'quotaInfo':{'remainingFraction':1}}}}
  quota={'buckets':[{'modelId':'gemini-pro','remainingFraction':0,'resetTime':'later'},{'modelId':'claude-sonnet','remainingFraction':.42}]}
  with patch.object(q.urllib.request,'urlopen',side_effect=[response(model),response(quota)]) as call:
   r=q.fetch_models('fake')
   self.assertEqual(r['models']['gemini-pro']['quotaInfo']['remainingFraction'],0)
   self.assertEqual(r['models']['claude-sonnet']['quotaInfo']['remainingFraction'],.42)
   self.assertEqual(call.call_args.args[0].full_url,'https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota')
 def test_failure_preserves_fallback(self):
  model={'models':{'gemini-pro':{'quotaInfo':{'resetTime':'today'}}}}
  with patch.object(q.urllib.request,'urlopen',side_effect=[response(model),urllib.error.URLError('offline')]):
   self.assertEqual(q.fetch_models('fake'),model)
 def test_missing_bucket_fraction_not_zero(self):
  model={'models':{'gemini-pro':{'quotaInfo':{'remainingFraction':.5}}}}
  with patch.object(q.urllib.request,'urlopen',side_effect=[response(model),response({'buckets':[{'modelId':'gemini-pro'}]})]):
   self.assertEqual(q.fetch_models('fake'),model)
 def test_different_resets_not_collapsed(self):
  rows=q.antigravity_rows([{'modelId':'gemini-a','percent':0,'resetTimeLocal':'a'},{'modelId':'gemini-b','percent':0,'resetTimeLocal':'b'}])
  self.assertEqual(len(rows),2)
