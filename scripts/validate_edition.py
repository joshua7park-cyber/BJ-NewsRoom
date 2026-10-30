#!/usr/bin/env python3
"""Quality gate for data/edition.json (the editorial morning edition, schema 3).

Fails (exit 1) on anything that must never reach the public page:
schema errors, thin or unbalanced sections, A-grade stories without two
independent sources (and, for domestic news, without a major Korean outlet),
empty "알맹이" (fewer than three concrete points), long titles, stale stories,
weekday labels that contradict the date, invented key numbers, placeholder
wording, publish times that are not real, and seminar links mislabelled as
sign-up pages.

Usage: python scripts/validate_edition.py [--require-today] [path]
"""
import json, re, sys, urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
SCHEMA_VERSION = 3
# 기본 4대 섹션 + BJ 관심 섹션: minimum stories and the checkpoints a story must name.
SECTIONS = {
    '경제': (2, ('국내외 금리', '부동산 정책', '주요 기업 실적', '환율·유가·증시')),
    '정치·사회': (2, ('국회 입법', '정부 새 제도', '주요 판결', '사회 이슈')),
    '테크·산업': (2, ('AI·반도체', '빅테크 신기술', '신재생·바이오', '규제·지원 정책')),
    '국제': (2, ('미·중·유럽 정책과 선거', '글로벌 공급망', '국제 분쟁', '주요 사건·사고', '기후')),
    '이스라엘·중동': (1, ('이스라엘 정치', '가자·레바논', '이란·호르무즈', '인도주의')),
    '종교·선교': (1, ('세계 선교', '박해·종교 자유', '목회·교단', '생명윤리')),
    '과학': (1, ('기초과학', '우주', '의학·바이오', '기후·환경')),
}
CORE = ('경제', '정치·사회', '테크·산업', '국제')
DOMESTIC = ('경제', '정치·사회')
EVENT_SECTIONS = ('종교·선교', '테크·산업', '과학')
LINK_TYPES = ('신청', '주최 측 안내', '관련 보도', '모집 공고')
GRADES = {'A': 2, 'B': 1, 'C': 1}          # minimum distinct source domains
SOURCE_KINDS = ('국내', '외신', '공식', '교계', '당사자', '2차')
# 한국의 주요 방송·신문·통신 (BJ님 요청: 국내 기사는 주요 매체를 폭넓게)
MAJOR_KR = ('yna.co.kr', 'kbs.co.kr', 'imbc.com', 'sbs.co.kr', 'jtbc.co.kr', 'ytn.co.kr', 'hani.co.kr',
            'khan.co.kr', 'chosun.com', 'joongang.co.kr', 'donga.com', 'hankookilbo.com', 'seoul.co.kr',
            'kmib.co.kr', 'mk.co.kr', 'hankyung.com', 'sedaily.com', 'fnnews.com', 'news1.kr', 'newsis.com',
            'nocutnews.co.kr', 'mt.co.kr', 'asiae.co.kr', 'edaily.co.kr', 'munhwa.com', 'segye.com')
MIN_MAJOR_KR_OUTLETS = 5
INDICATOR_TYPES = {'시세': 4, '정책금리': 120}  # max age in days
MAX_STORY_AGE_DAYS = 4
MAX_ONGOING = 2
TITLE_MAX, DEK_MAX = 40, 90
WEEKDAYS = '월화수목금토일'                   # date.weekday() order
PLACEHOLDERS = ('예시', '샘플', '더미', '시연용', '가상의', 'lorem', 'todo', 'tbd', 'xxx')
STORY_FIELDS = ('id', 'section', 'check', 'grade', 'priority', 'published_date', 'date_label',
                'title', 'dek', 'points', 'why', 'background', 'verification', 'sources')
EVENT_FIELDS = ('id', 'section', 'tag', 'start', 'time_label', 'title', 'host', 'place', 'fee',
                'status', 'links')
INDICATOR_FIELDS = ('name', 'value', 'type', 'as_of', 'source')


def domain(url):
    host = (urllib.parse.urlsplit(url).hostname or '').lower()
    parts = host.removeprefix('www.').split('.')
    # keep the registrable part: co.kr / or.kr style suffixes need three labels
    keep = 3 if len(parts) > 2 and parts[-2] in ('co', 'or', 'go', 'ac', 'ne', 'com') else 2
    return '.'.join(parts[-keep:])


def https(url):
    try:
        u = urllib.parse.urlsplit(url)
        return u.scheme == 'https' and bool(u.hostname)
    except ValueError:
        return False


def iso(value):
    return date.fromisoformat(value)


def placeholder_hits(text):
    text = text.lower()
    return [p for p in PLACEHOLDERS if p in text]


def weekday_errors(label, ref_year, where):
    """Every 'MM.DD(요일)' in a label must match the real weekday."""
    errs = []
    for m, d, w in re.findall(r'(\d{1,2})\.(\d{1,2})\s*\(([월화수목금토일])\)', label):
        try:
            real = WEEKDAYS[date(ref_year, int(m), int(d)).weekday()]
        except ValueError:
            errs.append(f'{where}: 존재하지 않는 날짜 {m}.{d}')
            continue
        if real != w:
            errs.append(f'{where}: {m}.{d}은 {real}요일인데 ({w})로 표기됨')
    return errs


def story_text(s):
    return ' '.join(str(x) for x in [s.get('title', ''), s.get('dek', ''), *s.get('points', []),
                                     s.get('why', ''), s.get('background', ''), s.get('next', ''),
                                     s.get('verification', '')])


def check_figures(s, where):
    """Key numbers shown on cards must be numbers the story itself states."""
    figs = s.get('figures')
    if figs is None:
        return []
    if not isinstance(figs, list) or not 1 <= len(figs) <= 4:
        return [f'{where}: figures는 1~4개']
    text = story_text(s).replace(',', '')
    errs = []
    for f in figs:
        if not isinstance(f, dict) or not f.get('label') or not f.get('value'):
            errs.append(f'{where}: figures 항목에는 label과 value가 필요')
            continue
        if f.get('dir') and f['dir'] not in ('up', 'down', 'flat'):
            errs.append(f'{where}: figures dir은 up/down/flat')
        for num in re.findall(r'\d+(?:[.,]\d+)*', f['value']):
            if num.replace(',', '') not in text:
                errs.append(f'{where}: 핵심 숫자 {num}이 기사 본문에 없습니다')
    return errs


def check_story(s, ed_date):
    where = f"기사 {s.get('id', '?')}"
    missing = [f for f in STORY_FIELDS if not s.get(f) and s.get(f) != 0]
    if missing:
        return [f'{where}: 필드 누락 {missing}']
    errs = []
    if s['section'] not in SECTIONS:
        return [f'{where}: 알 수 없는 섹션 {s["section"]}']
    if s['check'] not in SECTIONS[s['section']][1]:
        errs.append(f'{where}: 체크 포인트 "{s["check"]}"는 {s["section"]} 섹션의 항목이 아닙니다')
    if s['grade'] not in GRADES:
        return errs + [f'{where}: 등급은 A/B/C 중 하나']
    if len(s['title']) > TITLE_MAX:
        errs.append(f'{where}: 제목이 {len(s["title"])}자입니다 ({TITLE_MAX}자 이하로 간결하게)')
    if len(s['dek']) > DEK_MAX:
        errs.append(f'{where}: 요약(dek)이 {len(s["dek"])}자입니다 ({DEK_MAX}자 이하)')
    pts = s['points']
    if not isinstance(pts, list) or not 3 <= len(pts) <= 5 or not all(isinstance(p, str) and len(p) >= 20 for p in pts):
        errs.append(f'{where}: 핵심 정리(points)는 20자 이상 문장 3~5개여야 합니다')
    elif not any(re.search(r'\d', p) for p in pts):
        errs.append(f'{where}: 핵심 정리에 숫자·날짜 같은 구체적 사실이 하나도 없습니다')
    try:
        pub = iso(s['published_date'])
        if pub > ed_date:
            errs.append(f'{where}: 발행일이 판 날짜보다 미래')
        if not s.get('ongoing') and (ed_date - pub).days > MAX_STORY_AGE_DAYS:
            errs.append(f'{where}: {MAX_STORY_AGE_DAYS}일 넘은 기사 (꼭 필요한 지속 이슈면 ongoing:true)')
        errs += weekday_errors(s['date_label'], pub.year, where)
    except ValueError:
        errs.append(f'{where}: published_date 형식 오류')
    srcs = s['sources']
    bad = [x for x in srcs if not https(x.get('url', '')) or not x.get('name')]
    if bad:
        errs.append(f'{where}: https가 아니거나 이름 없는 출처 {len(bad)}건')
    if any(re.search(r'[()]', x.get('name', '')) for x in srcs):
        errs.append(f'{where}: 출처 이름에 괄호 메모를 넣지 않습니다 (매체 이름만)')
    kinds = [x.get('kind') for x in srcs if x.get('kind') not in SOURCE_KINDS]
    if kinds:
        errs.append(f'{where}: 출처 종류 오류 {kinds}')
    domains = {domain(x['url']) for x in srcs if https(x.get('url', ''))}
    if len(domains) < GRADES[s['grade']]:
        errs.append(f'{where}: {s["grade"]}급은 서로 다른 출처 도메인 {GRADES[s["grade"]]}곳 이상 필요 (현재 {len(domains)})')
    if s['grade'] == 'A' and s['section'] in DOMESTIC and not domains & set(MAJOR_KR):
        errs.append(f'{where}: 국내 A급 기사는 주요 방송·신문·통신 출처가 1곳 이상 필요')
    hits = placeholder_hits(story_text(s))
    if hits:
        errs.append(f'{where}: 임시/더미 표현 포함 {hits}')
    return errs + check_figures(s, where)


def check_stories(stories, ed_date):
    errs, ids, prios = [], set(), []
    for s in stories:
        errs += check_story(s, ed_date)
        if s.get('id') in ids:
            errs.append(f"기사 {s.get('id')}: id 중복")
        ids.add(s.get('id'))
        prios.append(s.get('priority'))
    if sorted(p for p in prios if isinstance(p, int)) != list(range(1, len(prios) + 1)):
        errs.append('priority는 1부터 빠짐없이 이어지는 편집 순서여야 합니다')
    if sum(bool(s.get('ongoing')) for s in stories) > MAX_ONGOING:
        errs.append(f'지속 이슈(ongoing)는 {MAX_ONGOING}건까지만 둡니다')
    for sec, (minimum, _) in SECTIONS.items():
        mine = [s for s in stories if s.get('section') == sec]
        if len(mine) < minimum:
            errs.append(f'섹션 {sec}: 기사 {len(mine)}건 (최소 {minimum}건)')
        if sec in CORE and len({s.get('check') for s in mine}) < 2:
            errs.append(f'섹션 {sec}: 체크 포인트가 한 가지뿐입니다 (서로 다른 2가지 이상)')
    majors = {domain(x['url']) for s in stories for x in s.get('sources', []) if https(x.get('url', ''))} & set(MAJOR_KR)
    if len(majors) < MIN_MAJOR_KR_OUTLETS:
        errs.append(f'국내 주요 매체 출처가 {len(majors)}곳뿐입니다 (최소 {MIN_MAJOR_KR_OUTLETS}곳, 한 매체 쏠림 방지)')
    return errs


def check_events(events):
    errs, eids = [], set()
    for e in events:
        where = f"일정 {e.get('id', '?')}"
        missing = [f for f in EVENT_FIELDS if not e.get(f)]
        if missing:
            errs.append(f'{where}: 필드 누락 {missing}')
            continue
        if e['id'] in eids:
            errs.append(f'{where}: id 중복')
        eids.add(e['id'])
        if e['section'] not in EVENT_SECTIONS:
            errs.append(f'{where}: 일정은 {"/".join(EVENT_SECTIONS)} 아래에만 붙습니다')
        if e['status'] not in ('confirmed', 'check'):
            errs.append(f'{where}: status는 confirmed/check')
        links = e['links']
        if not isinstance(links, list) or not links:
            errs.append(f'{where}: 링크가 1개 이상 필요')
            continue
        for ln in links:
            if ln.get('type') not in LINK_TYPES or not https(ln.get('url', '')):
                errs.append(f'{where}: 링크 종류는 {"/".join(LINK_TYPES)} 중 하나, 주소는 https')
        if e['status'] == 'confirmed' and not any(ln.get('type') in ('신청', '주최 측 안내') for ln in links):
            errs.append(f'{where}: "일정 확인됨"은 신청 페이지나 주최 측 안내가 있어야 합니다 (보도만 있으면 check)')
        try:
            start = iso(e['start'])
            end = iso(e['end']) if e.get('end') else start
            extra = [iso(x) for x in e.get('extra_dates', [])]
            if end < start or any(x < start for x in extra):
                errs.append(f'{where}: 날짜 순서 오류')
        except ValueError:
            errs.append(f'{where}: 날짜 형식 오류 (YYYY-MM-DD)')
            continue
        # Weekdays are rendered from the dates; a hand-written weekday is a bug magnet.
        if re.search(r'\([월화수목금토일]\)', e['title'] + e['time_label']):
            errs.append(f'{where}: 요일은 직접 쓰지 말고 날짜에서 계산합니다')
        if placeholder_hits(e['title'] + e['host']):
            errs.append(f'{where}: 임시/더미 표현 포함')
    return errs


def check_indicators(indicators, ed_date):
    errs = []
    if len(indicators) > 8:
        errs.append('지표는 8개 이하로 둡니다')
    for x in indicators:
        where = f"지표 {x.get('name', '?')}"
        missing = [f for f in INDICATOR_FIELDS if not x.get(f)]
        if missing:
            errs.append(f'{where}: 필드 누락 {missing}')
            continue
        if x['type'] not in INDICATOR_TYPES:
            errs.append(f'{where}: type은 {"/".join(INDICATOR_TYPES)}')
            continue
        if x.get('dir') and x['dir'] not in ('up', 'down', 'flat'):
            errs.append(f'{where}: dir은 up/down/flat')
        src = x['source']
        if not isinstance(src, dict) or not src.get('name') or not https(src.get('url', '')):
            errs.append(f'{where}: 출처 이름과 https 링크 필요')
        try:
            age = (ed_date - iso(x['as_of'])).days
            if age < 0 or age > INDICATOR_TYPES[x['type']]:
                errs.append(f'{where}: 기준일 {x["as_of"]}이 판 날짜와 맞지 않음 ({x["type"]}는 {INDICATOR_TYPES[x["type"]]}일 이내)')
        except ValueError:
            errs.append(f'{where}: as_of 형식 오류')
    return errs


def check_times(ed, ed_date, now):
    """Publish and cutoff times must be real: on the edition date and not in the future."""
    errs = []
    try:
        pub = datetime.fromisoformat(ed['published_at'])
        cut = datetime.fromisoformat(ed['cutoff'])
    except (KeyError, TypeError, ValueError):
        return ['published_at과 cutoff는 "2026-10-31T07:40:00+09:00" 형식의 실제 시각이어야 합니다']
    if pub.tzinfo is None or cut.tzinfo is None:
        return ['published_at과 cutoff에는 시간대(+09:00)가 필요합니다']
    if pub.astimezone(KST).date() != ed_date:
        errs.append('published_at 날짜가 판 날짜와 다릅니다')
    if cut > pub:
        errs.append('수집 기준 시각(cutoff)이 발행 시각보다 늦습니다')
    if now is not None and pub > now + timedelta(minutes=5):
        errs.append('published_at이 아직 오지 않은 시각입니다 (실제 발행 시각만 씁니다)')
    return errs


def validate(ed, require_today=False, today=None, now=None):
    errs = []
    now = now or (datetime.now(KST) if today is None else None)
    today = today or datetime.now(KST).date()
    for key in ('schema_version', 'edition_date', 'edition_label', 'published_at', 'cutoff',
                'brief', 'stories', 'events', 'watch', 'held'):
        if key not in ed:
            errs.append(f'최상위 필드 누락: {key}')
    if errs:
        return errs
    if ed['schema_version'] != SCHEMA_VERSION:
        errs.append(f'schema_version은 {SCHEMA_VERSION}이어야 합니다')
    try:
        ed_date = iso(ed['edition_date'])
    except ValueError:
        return errs + ['edition_date 형식 오류']
    if require_today and ed_date != today:
        errs.append(f'오늘판 아님: edition_date={ed_date}, 오늘(KST)={today}')
    m = re.search(r'(\d{1,2})월\s*(\d{1,2})일\s*\(([월화수목금토일])\)', ed['edition_label'])
    if not m:
        errs.append('edition_label은 "YYYY년 M월 D일(요일) 아침판" 형식')
    elif WEEKDAYS[date(ed_date.year, int(m[1]), int(m[2])).weekday()] != m[3] or (int(m[1]), int(m[2])) != (ed_date.month, ed_date.day):
        errs.append('edition_label의 날짜·요일이 edition_date와 다릅니다')
    errs += check_times(ed, ed_date, now)

    brief = ed['brief']
    if not isinstance(brief, list) or len(brief) != 3 or not all(isinstance(b, str) and 15 <= len(b) <= 180 for b in brief):
        errs.append('brief는 15~180자 문장 3개(오늘의 3줄)여야 합니다')
    elif placeholder_hits(' '.join(brief)):
        errs.append('brief에 임시/더미 표현 포함')

    errs += check_stories(ed['stories'], ed_date)
    errs += check_events(ed['events'])
    errs += check_indicators(ed.get('indicators', []), ed_date)

    for g in ed.get('event_gaps', []):
        if g.get('section') not in EVENT_SECTIONS or not g.get('text'):
            errs.append(f'event_gaps 항목 오류: {g}')
    fronts = ed.get('frontpages', [])
    if fronts and not (3 <= len(fronts) <= 12 and all(f.get('paper') and f.get('headline') for f in fronts)):
        errs.append('frontpages는 신문 이름과 1면 제목이 있는 3~12개 항목이어야 합니다')
    for w in ed['watch']:
        try:
            iso(w['date'])
        except (KeyError, ValueError):
            errs.append(f'관전 포인트 날짜 오류: {w}')
        if not w.get('text'):
            errs.append('관전 포인트 내용 누락')
    for h in ed['held']:
        if not h.get('title') or not h.get('reason'):
            errs.append(f'검증 보류 항목에는 제목과 사유가 모두 필요: {h}')
    return errs


def main(argv):
    require_today = '--require-today' in argv
    paths = [a for a in argv if not a.startswith('--')]
    path = Path(paths[0]) if paths else ROOT / 'data' / 'edition.json'
    try:
        ed = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as ex:
        print(f'FAIL {path}: 읽을 수 없음 ({ex})')
        return 1
    errs = validate(ed, require_today=require_today)
    if errs:
        print(f'FAIL {path} — {len(errs)}건')
        for e in errs:
            print('  -', e)
        return 1
    grades = {g: sum(s['grade'] == g for s in ed['stories']) for g in GRADES}
    per = ' '.join(f"{k}{sum(s['section'] == k for s in ed['stories'])}" for k in SECTIONS)
    print(f"PASS {ed['edition_label']} · 기사 {len(ed['stories'])}건 {grades} · {per} · "
          f"지표 {len(ed.get('indicators', []))} · 일정 {len(ed['events'])}건 · 보류 {len(ed['held'])}건")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
