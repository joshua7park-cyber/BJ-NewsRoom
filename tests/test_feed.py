import unittest,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_feed import parse_feed,build,unique
SAMPLE=b'''<rss><channel><item><title>Example &amp; report</title><link>https://news.google.com/x</link><pubDate>Thu, 29 Oct 2026 00:00:00 GMT</pubDate><source>Agency</source></item></channel></rss>'''
class FeedsTest(unittest.TestCase):
 def test_parses_and_labels_unverified(self):
  items=parse_feed(SAMPLE,'global',datetime(2026,10,29,1,tzinfo=timezone.utc))
  self.assertEqual(len(items),1)
  self.assertEqual(items[0]['verification_level'],'indexed')
  self.assertEqual(items[0]['title'],'Example & report')
 def test_duplicate(self):
  obj={'title':'Same headline'}
  self.assertEqual(len(unique([obj,obj])),1)
 def test_build_does_not_fake_kbs_or_verification(self):
  out=build(fetcher=lambda _: SAMPLE,now=datetime(2026,10,29,1,tzinfo=timezone.utc))
  self.assertEqual(out['counts']['kbs'],0)
  self.assertFalse(out['status']['kbs_broadcast_verified'])
  self.assertFalse(out['status']['minimum_5_verified_per_section'])
if __name__=='__main__':unittest.main()
