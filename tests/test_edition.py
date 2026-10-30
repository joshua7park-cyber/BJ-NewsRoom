import copy, json, re, sys, unittest
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_edition import validate, domain, SECTIONS, EVENT_SECTIONS, KST
from check_links import judge

ED = json.loads((ROOT / 'data' / 'edition.json').read_text(encoding='utf-8'))
DAY = date.fromisoformat(ED['edition_date'])


def first(section=None, grade=None):
    return next((s for s in ED['stories'] if (section is None or s['section'] == section)
                 and (grade is None or s['grade'] == grade)), None)


class EditionGate(unittest.TestCase):
    def errs(self, ed, **kw):
        return validate(ed, today=DAY, **kw)

    def changed(self, story_id, **fields):
        ed = copy.deepcopy(ED)
        s = next(x for x in ed['stories'] if x['id'] == story_id)
        s.update(fields)
        return ed

    def test_current_edition_passes(self):
        self.assertEqual(self.errs(ED, require_today=True), [])

    def test_wrong_weekday_is_caught(self):
        s = first()
        ed = self.changed(s['id'], date_label='10.29(화)')
        self.assertTrue(any('요일' in e for e in self.errs(ed)))

    def test_handwritten_event_weekday_is_rejected(self):
        ed = copy.deepcopy(ED)
        if not ed['events']:
            self.skipTest('이번 판에 일정 없음')
        ed['events'][0]['time_label'] = '11.11(화) 18:00'
        self.assertTrue(any('요일' in e for e in self.errs(ed)))

    def test_a_grade_needs_two_domains(self):
        s = first()
        ed = self.changed(s['id'], grade='A', sources=[s['sources'][0], dict(s['sources'][0], name='같은 매체')])
        self.assertTrue(any('A급' in e for e in self.errs(ed)))

    def test_domestic_a_grade_needs_major_outlet(self):
        s = first()
        minor = [{'name': '지역지 하나', 'url': 'https://www.example-local.kr/a', 'kind': '국내'},
                 {'name': '지역지 둘', 'url': 'https://news.another-local.kr/b', 'kind': '국내'}]
        ed = self.changed(s['id'], section='경제', check='국내외 금리', grade='A', sources=minor)
        self.assertTrue(any('주요 방송·신문·통신' in e for e in self.errs(ed)))

    def test_source_names_have_no_memo(self):
        s = first()
        ed = self.changed(s['id'], sources=[dict(x, name=x['name'] + ' (메모)') for x in s['sources']])
        self.assertTrue(any('괄호' in e for e in self.errs(ed)))

    def test_points_are_required_substance(self):
        s = first()
        ed = self.changed(s['id'], points=['짧음'])
        self.assertTrue(any('핵심 정리' in e for e in self.errs(ed)))

    def test_long_title_is_rejected(self):
        s = first()
        ed = self.changed(s['id'], title='가' * 41)
        self.assertTrue(any('제목' in e for e in self.errs(ed)))

    def test_checkpoint_must_belong_to_section(self):
        s = first()
        ed = self.changed(s['id'], check='어느 섹션에도 없는 항목')
        self.assertTrue(any('체크 포인트' in e for e in self.errs(ed)))

    def test_old_story_is_rejected(self):
        s = first()
        old = (DAY - timedelta(days=10)).isoformat()
        ed = self.changed(s['id'], published_date=old, date_label='지난 기사')
        self.assertTrue(any('일 넘은 기사' in e for e in self.errs(ed)))

    def test_placeholder_text_is_rejected(self):
        s = first()
        ed = self.changed(s['id'], dek=s['dek'][:60] + ' 예시 기사')
        self.assertTrue(any('더미' in e for e in self.errs(ed)))

    def test_figures_must_come_from_story(self):
        s = first()
        ed = self.changed(s['id'], figures=[{'label': '지어낸 숫자', 'value': '987,654'}])
        self.assertTrue(any('핵심 숫자' in e for e in self.errs(ed)))

    def test_stale_edition_fails_only_when_today_required(self):
        later = DAY + timedelta(days=1)
        self.assertEqual(validate(ED, today=later), [])
        self.assertTrue(validate(ED, today=later, require_today=True))

    def test_publish_time_cannot_be_in_the_future(self):
        pub = datetime.fromisoformat(ED['published_at'])
        self.assertTrue(any('아직 오지 않은' in e for e in validate(ED, today=DAY, now=pub - timedelta(hours=1))))
        self.assertEqual(validate(ED, today=DAY, now=pub + timedelta(minutes=1)), [])

    def test_every_section_has_news(self):
        ed = copy.deepcopy(ED)
        ed['stories'] = [s for s in ed['stories'] if s['section'] != '종교·선교']
        self.assertTrue(any('종교·선교' in e for e in self.errs(ed)))

    def test_core_sections_need_two_checkpoints(self):
        ed = copy.deepcopy(ED)
        sec = [s for s in ed['stories'] if s['section'] == '경제']
        for s in sec:
            s['check'] = sec[0]['check']
        self.assertTrue(any('체크 포인트가 한 가지' in e for e in self.errs(ed)))

    def test_priorities_are_one_to_n(self):
        ed = copy.deepcopy(ED)
        ed['stories'][-1]['priority'] = 99
        self.assertTrue(any('priority' in e for e in self.errs(ed)))

    def test_brief_is_three_lines(self):
        ed = copy.deepcopy(ED)
        ed['brief'] = ed['brief'][:2]
        self.assertTrue(any('brief' in e for e in self.errs(ed)))

    def test_stale_market_number_is_rejected(self):
        ed = copy.deepcopy(ED)
        ed['indicators'] = [{'name': '코스피', 'value': '1', 'type': '시세', 'note': '마감',
                             'as_of': (DAY - timedelta(days=10)).isoformat(),
                             'source': {'name': '연합뉴스', 'url': 'https://www.yna.co.kr/'}}]
        self.assertTrue(any('기준일' in e for e in self.errs(ed)))

    def test_events_only_under_event_sections(self):
        ed = copy.deepcopy(ED)
        if not ed['events']:
            self.skipTest('이번 판에 일정 없음')
        ed['events'][0]['section'] = '경제'
        self.assertTrue(any('일정은' in e for e in self.errs(ed)))

    def test_confirmed_event_needs_official_link(self):
        ed = copy.deepcopy(ED)
        if not ed['events']:
            self.skipTest('이번 판에 일정 없음')
        e = ed['events'][0]
        e['status'] = 'confirmed'
        e['links'] = [{'type': '관련 보도', 'url': 'https://news.example.com/a'}]
        self.assertTrue(any('일정 확인됨' in x for x in self.errs(ed)))

    def test_original_seminars_are_listed(self):
        # BJ님 처음 시안의 종교·과학 교육 일정은 끝나기 전까지 빠짐없이 싣습니다 (확인 전이면 '확인 필요'로).
        # 취소되거나 실제로 없는 것으로 밝혀지면 '검증 보류'에 이유를 적고 뺄 수 있습니다.
        required = {'kwma-forum': ('2026-11-04', '한국선교지도자포럼'), 'perspectives': ('2026-11-02', '퍼스펙티브스'),
                    'quantum-taiwan': ('2026-11-11', 'Quantum Taiwan'), 'kaia-fall': ('2026-11-20', '인공지능학회'),
                    'epic-quantum': ('2026-11-23', 'Photonics for Quantum')}
        ids = {e['id'] for e in ED['events']}
        held = ' '.join(h['title'] for h in ED['held'])
        for needed, (end, name) in required.items():
            if DAY <= date.fromisoformat(end):
                self.assertTrue(needed in ids or name in held, f'{name} 일정이 빠졌습니다 (취소면 검증 보류에 사유)')

    def test_domain_grouping(self):
        self.assertEqual(domain('https://www.ytn.co.kr/a'), 'ytn.co.kr')
        self.assertEqual(domain('https://weekly.khan.co.kr/a'), 'khan.co.kr')
        self.assertEqual(domain('https://www.aljazeera.com/x'), 'aljazeera.com')


class LinkGate(unittest.TestCase):
    def test_a_grade_with_one_live_source_blocks_deploy(self):
        a = first(grade='A')
        if a is None:
            self.skipTest('이번 판에 A급 없음')
        results = [{'url': x['url'], 'status': 'broken'} for x in a['sources'][1:]]
        self.assertTrue(any(a['id'] in p for p in judge(ED, results)))

    def test_blocked_sites_do_not_block_deploy(self):
        results = [{'url': x['url'], 'status': 'blocked'} for s in ED['stories'] for x in s['sources']]
        self.assertEqual(judge(ED, results), [])

    def event_case(self, status):
        ed = copy.deepcopy(ED)
        ed['events'] = [{'id': 'case', 'status': status, 'links': [{'type': '신청', 'url': 'https://example.org/apply'}]}]
        return ed, [{'url': 'https://example.org/apply', 'status': 'broken'}]

    def test_confirmed_event_with_all_official_links_broken_blocks(self):
        ed, results = self.event_case('confirmed')
        self.assertTrue(any('case' in p for p in judge(ed, results)))

    def test_unconfirmed_event_link_does_not_block(self):
        ed, results = self.event_case('check')
        self.assertFalse(any('case' in p for p in judge(ed, results)))


class PageContract(unittest.TestCase):
    html = (ROOT / 'index.html').read_text(encoding='utf-8')

    def test_single_operational_page(self):
        stray = [p.name for p in ROOT.glob('*.html') if p.name != 'index.html']
        self.assertEqual(stray, [], 'index.html 하나만 운영본입니다')

    def test_reads_live_data(self):
        for path in ('./data/edition.json', './site/link-report.json', './site/newsroom.json'):
            self.assertIn(path, self.html)
        self.assertIn('d.schema_version!==3', self.html)

    def test_sections_and_controls(self):
        for name in ('포털 보기', '데스크 보기', '모두 펼치기', '글자 크게', '검증 보류', '교육·세미나 달력',
                     '실시간 제목 색인', '기본 4대 섹션', 'BJ 관심 섹션', '오늘 아침 5분', '오늘의 3줄',
                     '오늘의 지표', '5분 헤드라인', '오늘의 대문', 'Featured', '검증된 뉴스만 싣습니다',
                     '오늘의 검증 뉴스', '오늘의 관전 포인트', '다가오는 교육·세미나', '핵심 정리',
                     '앞으로 볼 것', '매일 08:00'):
            self.assertIn(name, self.html)

    def test_page_sections_match_gate(self):
        page = re.findall(r"\{name:'([^']+)',group:'(core|bj)',key:'[a-z]+',why:'[^']*',checks:\[([^\]]*)\]", self.html)
        self.assertEqual([n for n, _, _ in page], list(SECTIONS))
        self.assertEqual([n for n, g, _ in page if g == 'core'], ['경제', '정치·사회', '테크·산업', '국제'])
        for name, _, checks in page:
            self.assertEqual(tuple(re.findall(r"'([^']+)'", checks)), SECTIONS[name][1], name)
        for sec in EVENT_SECTIONS:
            self.assertRegex(self.html, r"\{name:'" + re.escape(sec) + r"'[^}]*events:'")

    def test_approved_layout_is_a_plus_c(self):
        # BJ님이 고른 운영 화면(2026-10-30): 포털(A)과 데스크(C) 전환, 상태 줄, 숫자 칸이 보여야 합니다.
        self.assertIn('function viewPortal()', self.html)
        self.assertIn('function viewDesk()', self.html)
        self.assertIn("MODE==='desk'?viewDesk():viewPortal()", self.html)
        css = ' '.join(re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.S))
        hidden = re.search(r'(\.mode|#kpis|#status|\.kpis|\.status)\b[^{}]*\{[^}]*display\s*:\s*none', css)
        self.assertIsNone(hidden, f'승인된 화면 요소를 숨기는 CSS: {hidden and hidden.group(0)[:120]}')

    def test_search_home_and_expand_are_wired(self):
        for code in ("['input','compositionend','search'].forEach", 'function renderDrop()', 'id="sr"',
                     "$('#ex').onclick=toggleAll", "class:'btn ex-btn'", 'function goHome()', 'id="fab"',
                     "$('#fab-home').onclick=goHome", 'homeBtn()', "addEventListener('toggle',syncEx,true)"):
            self.assertIn(code, self.html)

    def test_no_fake_popularity(self):
        # 조회수 데이터가 없으므로 "많이 본" 순위나 조회수 숫자를 만들지 않습니다.
        for word in ('많이 본', 'Most Viewed', '조회수 순', 'views'):
            self.assertNotIn(word, self.html)

    def test_no_hardcoded_publish_time(self):
        self.assertNotIn('07:30 발행', self.html)
        self.assertIn('hm(ED.published_at)', self.html)

    def test_no_inline_articles_in_page(self):
        # Articles live in data/edition.json only, never hard-coded in the page.
        for s in ED['stories']:
            self.assertNotIn(s['title'], self.html)
        self.assertIsNone(re.search(r'(예시|샘플|더미|시연용)\s*(기사|뉴스)', self.html))


if __name__ == '__main__':
    unittest.main()
