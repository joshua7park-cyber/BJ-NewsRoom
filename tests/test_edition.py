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
        for path in ('./data/edition.json', './site/link-report.json', './site/newsroom.json'):
            self.assertIn(path, self.html)

    def test_sections_and_controls(self):
        for name in ('국내', '국제', '이스라엘·중동', 'Religion', '과학·AI', '포털 보기', '데스크 보기',
                     '모두 펼치기', '글자 크게', '검증 보류', '교육·세미나 달력', '실시간 제목 색인'):
            self.assertIn(name, self.html)

    def test_calm_five_only_default(self):
        self.assertIn('function viewCalm()', self.html)
        self.assertIn("filter(s=>(TAB==='전체'||s.section===TAB)&&hit(s))).slice(0,5)", self.html)
        self.assertIn("$('#view').replaceChildren(viewCalm())", self.html)
        self.assertIn('class:\'bj-events\'', self.html)
        self.assertIn('.mode,.legend,#kpis,#status', self.html)

    def test_accessibility_controls_still_exist(self):
        for ident in ('id="q"', 'id="font"', 'id="zm"', 'id="zp"', 'id="ex"'):
            self.assertIn(ident, self.html)
        self.assertIn('function story(', self.html)

    def test_no_inline_articles_in_page(self):
        # Articles live in data/edition.json only, never hard-coded in the page.
        for s in ED['stories']:
            self.assertNotIn(s['title'], self.html)
        self.assertIsNone(re.search(r'(예시|샘플|더미|시연용)\s*(기사|뉴스)', self.html))


if __name__ == '__main__':
    unittest.main()
