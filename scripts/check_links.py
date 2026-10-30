#!/usr/bin/env python3
"""Open every source, seminar and indicator link in data/edition.json and record the result.

Runs inside GitHub Actions (full internet access) before each deploy.
Writes site/link-report.json, which the page reads to mark each link.

  ok       2xx/3xx
  blocked  401/403/405/429/451 or an unfollowable redirect: the site exists but refuses automated checks
  broken   404/410, 5xx after retries, DNS or connection failure

Exit 1 (deploy stops) when an A-grade story keeps fewer than two working
sources, every sign-up/organizer link of a confirmed seminar is broken,
or over 25% of links are broken. Pass --report-only to always exit 0.
"""
import json, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36 BJNewsroomLinkCheck/1.0')
# 3xx here means a redirect urllib would not follow (loop or scheme change): the site exists.
BLOCKED = {301, 302, 303, 307, 308, 401, 403, 405, 429, 451}
OFFICIAL = ('신청', '주최 측 안내')


def probe(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
            with urllib.request.urlopen(req, timeout=20) as r:
                r.read(2048)
                return {'url': url, 'status': 'ok', 'code': r.status, 'final_url': r.geturl()}
        except urllib.error.HTTPError as ex:
            if ex.code in BLOCKED:
                return {'url': url, 'status': 'blocked', 'code': ex.code}
            last = {'url': url, 'status': 'broken', 'code': ex.code}
            if ex.code in (404, 410):
                return last
        except Exception as ex:  # DNS, TLS, timeout
            last = {'url': url, 'status': 'broken', 'code': None, 'error': str(ex)[:160]}
        time.sleep(2 * (attempt + 1))
    return last


def collect(ed):
    urls = {}
    for s in ed['stories']:
        for src in s['sources']:
            urls.setdefault(src['url'], []).append(('story', s['id']))
    for e in ed['events']:
        for ln in e.get('links', []):
            urls.setdefault(ln['url'], []).append(('event', e['id']))
    for x in ed.get('indicators', []):
        urls.setdefault(x['source']['url'], []).append(('indicator', x['name']))
    return urls


def judge(ed, results):
    status = {r['url']: r['status'] for r in results}
    problems = []
    for s in ed['stories']:
        if s['grade'] == 'A':
            alive = [x for x in s['sources'] if status.get(x['url']) != 'broken']
            if len(alive) < 2:
                problems.append(f"A급 기사 {s['id']}: 열리는 출처가 {len(alive)}곳뿐")
    for e in ed['events']:
        official = [ln for ln in e.get('links', []) if ln.get('type') in OFFICIAL]
        if e.get('status') == 'confirmed' and official and all(status.get(ln['url']) == 'broken' for ln in official):
            problems.append(f"일정 {e['id']}: 신청·주최 측 링크가 모두 열리지 않음")
    broken = sum(r['status'] == 'broken' for r in results)
    if results and broken / len(results) > 0.25:
        problems.append(f'오류 링크 비율 {broken}/{len(results)}')
    return problems


def main(argv):
    ed = json.loads((ROOT / 'data' / 'edition.json').read_text(encoding='utf-8'))
    urls = collect(ed)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, urls))
    for r in results:
        r['used_by'] = [f'{kind}:{ident}' for kind, ident in urls[r['url']]]
    problems = judge(ed, results)
    counts = {k: sum(r['status'] == k for r in results) for k in ('ok', 'blocked', 'broken')}
    report = {'checked_at': datetime.now(KST).isoformat(timespec='minutes'),
              'edition_date': ed['edition_date'], 'total': len(results), **counts,
              'problems': problems, 'results': sorted(results, key=lambda r: r['status'])}
    out = ROOT / 'site' / 'link-report.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"links: {counts} of {len(results)} → {out.relative_to(ROOT)}")
    for r in results:
        if r['status'] != 'ok':
            print(f"  {r['status']:7} {r.get('code')} {r['url']}")
            if r['status'] == 'broken':  # visible in the Actions summary without opening logs
                print(f"::warning title=링크 오류 {r.get('code') or r.get('error', '')[:60]}::{r['url']} ({', '.join(r['used_by'])})")
    for p in problems:
        print('  PROBLEM', p)
        print(f'::error title=배포 중단::{p}')
    return 0 if '--report-only' in argv or not problems else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
