#!/usr/bin/env python3
"""Quality gate for data/edition.json (the editorial morning edition).

Fails (exit 1) on anything that must never reach the public page:
schema errors, unknown sections, A-grade stories without two independent
sources, non-https links, weekday labels that contradict the date,
placeholder/dummy wording, and stale stories.

Usage: python scripts/validate_edition.py [--require-today] [path]
"""
import json, re, sys, urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
SECTIONS = ('국내', '국제', '이스라엘·중동', 'Religion', '과학·AI')
GRADES = {'A': 2, 'B': 1, 'C': 1}          # minimum distinct source domains
SOURCE_KINDS = ('국내', '외신', '공식', '교계', '당사자', '2차')
WEEKDAYS = '월화수목금토일'                   # date.weekday() order
PLACEHOLDERS = ('예시', '샘플', '더미', '시연용', '가상의', 'lorem', 'todo', 'tbd', 'xxx')
STORY_FIELDS = ('id', 'section', 'grade', 'priority', 'published_date', 'date_label',
                'title', 'dek', 'core', 'why', 'background', 'verification', 'sources')
EVENT_FIELDS = ('id', 'section', 'start', 'time_label', 'title', 'host', 'place', 'fee',
                'status', 'apply_url')
MAX_STORY_AGE_DAYS = 30


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


def validate(ed, require_today=False, today=None):
    errs = []
    today = today or datetime.now(KST).date()
    for key in ('schema_version', 'edition_date', 'edition_label', 'published_at',
                'stories', 'events', 'watch', 'held'):
        if key not in ed:
            errs.append(f'최상위 필드 누락: {key}')
    if errs:
        return errs
    if ed['schema_version'] != 1:
        errs.append('schema_version은 1이어야 합니다')
    try:
        ed_date = iso(ed['edition_date'])
    except ValueError:
        return errs + ['edition_date 형식 오류']
    if require_today and ed_date != today:
        errs.append(f'오늘판 아님: edition_date={ed_date}, 오늘(KST)={today}')
    m = re.search(r'(\d{1,2})월\s*(\d{1,2})일\s*\(([월화수목금토일])\)', ed['edition_label'])
    if m and WEEKDAYS[date(ed_date.year, int(m[1]), int(m[2])).weekday()] != m[3]:
        errs.append('edition_label 요일이 날짜와 다릅니다')

    stories = ed['stories']
    if len(stories) < 5:
        errs.append(f'기사 수 부족: {len(stories)}건 (최소 5건)')
    ids, prios = set(), set()
    for s in stories:
        where = f"기사 {s.get('id', '?')}"
        missing = [f for f in STORY_FIELDS if not s.get(f) and s.get(f) != 0]
        if missing:
            errs.append(f'{where}: 필드 누락 {missing}')
            continue
        if s['id'] in ids:
            errs.append(f'{where}: id 중복')
        ids.add(s['id'])
        if s['priority'] in prios:
            errs.append(f'{where}: priority {s["priority"]} 중복')
        prios.add(s['priority'])
        if s['section'] not in SECTIONS:
            errs.append(f'{where}: 알 수 없는 섹션 {s["section"]}')
        if s['grade'] not in GRADES:
            errs.append(f'{where}: 등급은 A/B/C 중 하나')
            continue
        try:
            pub = iso(s['published_date'])
            if pub > ed_date:
                errs.append(f'{where}: 발행일이 판 날짜보다 미래')
            if not s.get('ongoing') and (ed_date - pub).days > MAX_STORY_AGE_DAYS:
                errs.append(f'{where}: {MAX_STORY_AGE_DAYS}일 넘은 기사 (지속 이슈면 ongoing:true)')
            errs += weekday_errors(s['date_label'], pub.year, where)
        except ValueError:
            errs.append(f'{where}: published_date 형식 오류')
        bad = [x for x in s['sources'] if not https(x.get('url', '')) or not x.get('name')]
        if bad:
            errs.append(f'{where}: https가 아니거나 이름 없는 출처 {len(bad)}건')
        kinds = [x.get('kind') for x in s['sources'] if x.get('kind') not in SOURCE_KINDS]
        if kinds:
            errs.append(f'{where}: 출처 종류 오류 {kinds}')
        domains = {domain(x['url']) for x in s['sources'] if https(x.get('url', ''))}
        if len(domains) < GRADES[s['grade']]:
            errs.append(f'{where}: {s["grade"]}급은 서로 다른 출처 도메인 {GRADES[s["grade"]]}곳 이상 필요 (현재 {len(domains)})')
        text = ' '.join(str(s[f]) for f in ('title', 'dek', 'core', 'why', 'background')).lower()
        hits = [p for p in PLACEHOLDERS if p in text]
        if hits:
            errs.append(f'{where}: 임시/더미 표현 포함 {hits}')

    for sec in SECTIONS:
        if not any(s.get('section') == sec for s in stories):
            errs.append(f'섹션 비어 있음: {sec}')

    eids = set()
    for e in ed['events']:
        where = f"일정 {e.get('id', '?')}"
        missing = [f for f in EVENT_FIELDS if not e.get(f)]
        if missing:
            errs.append(f'{where}: 필드 누락 {missing}')
            continue
        if e['id'] in eids:
            errs.append(f'{where}: id 중복')
        eids.add(e['id'])
        if e['section'] not in ('Religion', '과학·AI'):
            errs.append(f'{where}: 일정은 Religion 또는 과학·AI 아래에만 붙습니다')
        if e['status'] not in ('confirmed', 'check'):
            errs.append(f'{where}: status는 confirmed/check')
        for k in ('apply_url', 'ref_url'):
            if e.get(k) and not https(e[k]):
                errs.append(f'{where}: {k}가 https가 아님')
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
        if [p for p in PLACEHOLDERS if p in (e['title'] + e['host']).lower()]:
            errs.append(f'{where}: 임시/더미 표현 포함')

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
    print(f"PASS {ed['edition_label']} · 기사 {len(ed['stories'])}건 {grades} · "
          f"일정 {len(ed['events'])}건 · 보류 {len(ed['held'])}건")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
