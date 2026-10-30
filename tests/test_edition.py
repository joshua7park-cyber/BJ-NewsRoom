import copy, json, re, sys, unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_edition import validate, domain
from check_links import judge

ED = json.loads((ROOT / 'data' / 'edition.json').read_text(encoding='utf-8'))
DAY = date.fromisoformat(ED['edition_date'])


class EditionGate(unittest.TestCase):
    def errs(self, ed, **kw):
        return validate(ed, today=DAY, **kw)

    def test_current_edition_passes(self):
        self.assertEqual(self.errs(ED, require_today=True), [])

    def test_wrong_weekday_is_caught(self):
        ed = copy.deepcopy(ED)
        ed['stories'][0]['date_label'] = '10.29(화)'
        self.assertTrue(any('요일' in e for e in self.errs(ed)))

    def test_handwritten_event_weekday_is_rejected(self):
        ed = copy.deepcopy(ED)
        ed['events'][0]['time_label'] = '11.11(화) 18:00'
        self.assertTrue(any('요일' in e for e in self.errs(ed)))

    def test_a_grade_needs_two_domains(self):
        ed = copy.deepcopy(ED)
        a = next(s for s in ed['stories'] if s['grade'] == 'A')
        a['sources'] = [a['sources'][0], dict(a['sources'][0], name='same site')]
        self.assertTrue(any('A급' in e for e in self.errs(ed)))

    def test_placeholder_text_is_rejected(self):
        ed = copy.deepcopy(ED)
        ed['stories'][0]['dek'] += ' (예시 기사)'
        self.assertTrue(any('더미' in e for e in self.errs(ed)))

    def test_stale_edition_fails_only_when_today_required(self):
        later = DAY + timedelta(days=1)
        self.assertEqual(validate(ED, today=later), [])
        self.assertTrue(validate(ED, today=later, require_today=True))

    def test_every_section_has_news(self):
        ed = copy.deepcopy(ED)
        ed['stories'] = [s for s in ed['stories'] if s['section'] != 'Religion']
        self.assertTrue(any('Religion' in e for e in self.errs(ed)))

    def test_domain_grouping(self):
        self.assertEqual(domain('https://www.ytn.co.kr/a'), 'ytn.co.kr')
        self.assertEqual(domain('https://weekly.khan.co.kr/a'), 'khan.co.kr')
        self.assertEqual(domain('https://www.aljazeera.com/x'), 'aljazeera.com')


class LinkGate(unittest.TestCase):
    def test_a_grade_with_one_live_source_blocks_deploy(self):
        a = next(s for s in ED['stories'] if s['grade'] == 'A')
        results = [{'url': x['url'], 'status': 'broken'} for x in a['sources'][1:]]
        self.assertTrue(any(a['id'] in p for p in judge(ED, results)))

    def test_blocked_sites_do_not_block_deploy(self):
        results = [{'url': x['url'], 'status': 'blocked'} for s in ED['stories'] for x in s['sources']]
        self.assertEqual(judge(ED, results), [])


class PageContract(unittest.TestCase):
    html = (ROOT / 'index.html').read_text(encoding='utf-8')

    def test_single_operational_page(self):
        stray = [p.name for p in ROOT.glob('*.html') if p.name != 'index.html']
        self.assertEqual(stray, [], 'index.html 하나만 운영본입니다')

    def test_reads_live_data(self):
        for path in ('./data/edition.json',):
            self.assertIn(path, self.html)

    def test_essential_first_contract(self):
        for value in ('오늘의 하이라이트', '국내', '국제', '이스라엘', 'Religion', '과학', 'AI 교육'):
            self.assertIn(value,self.html)
        self.assertIn('.slice(0,5)',self.html)
        self.assertNotIn('site/newsroom.json',self.html)
        self.assertNotIn('51건',self.html)

    def test_controls_and_accessibility(self):
        for ident in ('id="search"','id="font"','id="minus"','id="plus"','id="events"'):
            self.assertIn(ident,self.html)
        self.assertIn('확인 범위',self.html)
        self.assertIn("make('details'",self.html)

    def test_no_inline_articles_in_page(self):
        # Articles live in data/edition.json only, never hard-coded in the page.
        for s in ED['stories']:
            self.assertNotIn(s['title'], self.html)
        self.assertIsNone(re.search(r'(예시|샘플|더미|시연용)\s*(기사|뉴스)', self.html))


if __name__ == '__main__':
    unittest.main()
