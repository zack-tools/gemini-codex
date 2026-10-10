import contextlib, io, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import check_quota as q
class Tests(unittest.TestCase):
 def test_windows(self):
  self.assertIsNone(q.normalize_window(None))
  self.assertIsNone(q.normalize_window({})['remainingPercent'])
  for used, rem in [(9,91),(92,8),(110,0),(-5,100),(0,100)]:
   self.assertEqual(q.normalize_window({'used_percent':used})['remainingPercent'],rem)
  self.assertEqual(q.normalize_window({'reset_at':0})['resetTimeLocal'],'1970-01-01 08:00:00')
 def test_auth(self):
  for auth in [{'tokens':{'access_token':'test-secret','account_id':'test-account'}},{'access_token':'test-secret','account_id':'test-account'}]:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'auth.json'; p.write_text(json.dumps(auth))
    with patch.object(q.urllib.request,'build_opener') as factory:
     factory.return_value.open.return_value.__enter__.return_value=io.StringIO(json.dumps({'rate_limit':{'primary_window':{'used_percent':9}},'additional_rate_limits':[{'limit_name':'extra','rate_limit':{'secondary_window':{'used_percent':20}}}]}))
     r=q.collect_openai_quota(p)
     req=factory.return_value.open.call_args.args[0]
     self.assertEqual(req.full_url,'https://chatgpt.com/backend-api/wham/usage')
     self.assertEqual(req.get_header('Authorization'),'Bearer test-secret')
     self.assertEqual(req.get_header('Chatgpt-account-id'),'test-account')
     self.assertEqual(r['rateLimits'][0]['primary']['remainingPercent'],91)
     self.assertEqual(len(r['rateLimits']),2)
     self.assertNotIn('test-secret',str(r))
 def test_errors(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'auth.json'
   self.assertIn('error',q.collect_openai_quota(p))
   for value in ['bad json','[]','{"OPENAI_API_KEY":"test-secret"}']:
    p.write_text(value); self.assertIn('error',q.collect_openai_quota(p))
   p.write_text('{"tokens":{"access_token":"test-secret"}}')
   with patch.object(q.urllib.request,'build_opener') as factory:
    factory.return_value.open.side_effect=q.urllib.error.HTTPError('https://chatgpt.com',401,'test-secret',{},None)
    r=q.collect_openai_quota(p)
    self.assertIn('401',r['error']); self.assertNotIn('test-secret',str(r))
 def test_isolation(self):
  with patch.object(q,'collect_antigravity_quota',side_effect=ValueError()),patch.object(q,'collect_openai_quota',return_value={'rateLimits':[]}),contextlib.redirect_stdout(io.StringIO()) as out:
   self.assertEqual(q.check_quota(True),1); self.assertIn('openai',json.loads(out.getvalue()))
  with patch.object(q,'collect_antigravity_quota') as other,patch.object(q,'collect_openai_quota',return_value={'rateLimits':[]}),contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(q.check_quota(True,'openai'),0); other.assert_not_called()
 def test_redirect(self):
  self.assertIsNone(q.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com'))
if __name__=='__main__': unittest.main()
