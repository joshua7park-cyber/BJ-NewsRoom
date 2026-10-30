import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class NewsroomRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text(encoding='utf-8')
        cls.data = json.loads((ROOT / 'site/newsroom.json').read_text(encoding='utf-8'))

    def test_expected_navigation(self):
        for name in ('대문 뉴스','국내','국제','이스라엘','Religion','과학','AI 교육'):
            self.assertIn(name, self.html)

    def test_live_data_connected(self):
        self.assertIn("fetch('./site/newsroom.json", self.html)
        self.assertEqual(2, self.data['schema_version'])
        self.assertTrue(self.data['news'])

    def test_no_historical_reuters_snapshots(self):
        self.assertNotIn('www.reuters.com', self.html)
        self.assertNotIn('apnews.com', self.html)
        self.assertNotIn('2026.10.30</title>', self.html)

    def test_domestic_is_not_foreign_wire_only(self):
        domestic = [n for n in self.data['news'] if n['section']=='domestic']
        self.assertTrue(domestic)
        for n in domestic:
            self.assertNotIn('reuters', n.get('source','').lower())
            self.assertNotIn('ap news', n.get('source','').lower())

    def test_status_honesty(self):
        self.assertIn('공개 RSS 색인', self.html)
        self.assertTrue(all(n.get('verification_level')=='indexed' for n in self.data['news']))

    @unittest.expectedFailure
    def test_domestic_links_resolve_directly_to_publishers(self):
        domestic = [n for n in self.data['news'] if n['section']=='domestic']
        self.assertFalse(any('news.google.com' in n['url'] for n in domestic),
                         'Known blocker: Google News redirects not verified direct originals')

    def test_editorial_reading_room(self):
        editorial=json.loads((ROOT/'site/reading-room.json').read_text(encoding='utf8'))
        self.assertEqual(editorial['schema_version'],1)
        self.assertGreater(len(editorial['articles']),0)
        self.assertIn('site/reading-room.json',self.html)
        for article in editorial['articles']:
            for field in ('summary','why','context','verification','sources'):
                self.assertTrue(article[field])
            self.assertTrue(all(x['url'].startswith('https://') for x in article['sources']))
            self.assertIsNone(article.get('popular_metric'))

    def test_morning_workflow_and_label(self):
        workflow=(ROOT/'.github/workflows/morning-edition.yml').read_text(encoding='utf8')
        pages=(ROOT/'.github/workflows/pages.yml').read_text(encoding='utf8')
        generator=(ROOT/'scripts/build_morning_index.py').read_text(encoding='utf8')
        self.assertIn("cron: '30 22 * * *'",workflow)  # 07:30 KST
        self.assertIn('BJ Morning 07:30 RSS edition',pages)
        self.assertIn('is_chatgpt_editorial',generator)
        self.assertIn('loadReadingRoom',self.html)
        self.assertIn('공식 조회수',self.html)

if __name__ == '__main__':
    unittest.main()
