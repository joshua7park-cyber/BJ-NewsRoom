"""Offline regression for RSS ingestion: no network, no invented claims."""
import datetime
import sys
import unittest
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_live_edition import collect

class LiveEditionTests(unittest.TestCase):
    def test_fake_feed_cannot_be_presented_as_verified_article(self):
        now=datetime.datetime(2026,10,31,5,0,tzinfo=datetime.timezone.utc)
        def fetch(url):
            query=parse_qs(urlparse(url).query).get('q',[''])[0]
            sig=(query or url).split('/')[-1][:25]
            title='뉴스 핵심 정책과 세계 변화 '+sig
            desc='정식 기사 본문이 아니라 RSS에서 제공되는 공개 요약입니다. 출처의 원문을 확인해야 상세 사실을 판단할 수 있습니다.'
            xml=f"<rss><channel><item><title>{escape(title)}</title><link>https://example.org/{abs(hash(url))}</link><description>{desc}</description><pubDate>{format_datetime(now)}</pubDate></item></channel></rss>"
            return xml.encode('utf-8')
        result=collect(now=now,fetcher=fetch)
        self.assertEqual(result['schema_version'],1)
        self.assertEqual(result['kind'],'rss_sourced_auto_digest')
        self.assertGreaterEqual(len(result['stories']),5)
        self.assertLessEqual(len(result['stories']),12)
        for item in result['stories']:
            self.assertEqual(item['grade'],'C')
            self.assertIn('교차확인 전',item['verification'])
            self.assertTrue(item['sources'][0]['url'].startswith('https://'))
            self.assertNotIn('독립 검증 완료',item['verification'])
    def test_error_on_unreachable_feeds(self):
        def fail(url):
            raise OSError('Simulated offline')
        result=collect(fetcher=fail)
        self.assertEqual(result['stories'],[])
        self.assertEqual(result['error'],'no_recent_feed')

if __name__=='__main__':
    unittest.main()
