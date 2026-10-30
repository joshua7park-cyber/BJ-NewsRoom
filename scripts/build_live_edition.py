#!/usr/bin/env python3
"""Publish a small, honest near-real-time headline briefing from publishers' RSS feeds.
No model API key needed. RSS excerpts are NOT described as independently verified.
Never insert fabricated article details. Keeps five-story UX compact.
"""
import json, os, re, html, hashlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT=Path(__file__).resolve().parents[1]
KST=timezone(timedelta(hours=9))
OUT=ROOT/'site'/'live-edition.json'
UA='Mozilla/5.0 (compatible; BJNewsroom/1.0; editorial digest)'
# Publisher-operated, publicly documented RSS URLs. The remaining category
# queries are explicitly marked "Google News RSS 경유", never publisher-direct.
FEEDS=[
 ('뉴시스','경제·금융','https://www.newsis.com/RSS/economy.xml'),
 ('뉴시스','정치·사회','https://www.newsis.com/RSS/politics.xml'),
 ('뉴시스','국제','https://www.newsis.com/RSS/international.xml'),
 ('뉴시스','테크·산업','https://www.newsis.com/RSS/industry.xml'),
 ('뉴시스','과학','https://www.newsis.com/RSS/health.xml'),
 ('SBS 뉴스','정치·사회','https://news.sbs.co.kr/news/newsflashRssFeed.do?plink=RSSREADER'),
 ('SBS 뉴스','경제·금융','https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02&plink=RSSREADER'),
 ('MBN','경제·금융','https://www.mbn.co.kr/rss/economy/'),
 ('MBN','국제','https://www.mbn.co.kr/rss/international/'),
 ('MBN','정치·사회','https://www.mbn.co.kr/rss/politics/'),
]
GOOGLE=[
 ('Religion','기독교 선교 목회 교회 종교'),
 ('이스라엘','이스라엘 중동 외교 안보 인도주의'),
 ('AI 교육','인공지능 AI 교육 세미나 강의'),
 ('과학','과학 우주 양자 반도체 연구'),
]
BLOCK_TERMS=('연예','스타','가수','배우','배구','야구','축구','스포츠','경마','핫딜','광고','협찬')
TOPIC_BONUS={'경제·금융':18,'정치·사회':18,'국제':18,'테크·산업':16,'이스라엘':16,'Religion':14,'과학':15,'AI 교육':12}
CONTEXT={
 '경제·금융':'금리·환율·기업 실적과 국내 생활경제에 미칠 영향은 후속 공식 통계와 함께 살펴볼 필요가 있습니다.',
 '정치·사회':'제도·정책 변화의 실제 내용과 시민 생활에 미치는 영향을 우선 확인할 필요가 있습니다.',
 '테크·산업':'산업 정책·기업 투자·기술 경쟁에 관한 추세와 공식 발표를 함께 확인해야 합니다.',
 '국제':'외교·무역·안보 변화가 한국에 미칠 영향을 후속 발표와 함께 관찰할 필요가 있습니다.',
 '이스라엘':'당사국 발표와 독립 국제 보도 및 인도주의 자료를 구분해 비교할 필요가 있습니다.',
 'Religion':'교계·선교적 의미와 지역사회에 미칠 영향은 추가 자료를 통해 확인해야 합니다.',
 '과학':'연구 결과와 실제 적용 가능성은 원 논문·학회 발표를 확인한 후 판단해야 합니다.',
 'AI 교육':'주최 기관의 공식 안내에서 일정·비용·신청 가능 여부를 별도로 확인해야 합니다.'
}
def normalize(s):
 s=re.sub(r'<[^>]*>',' ',html.unescape(str(s or '')))
 return re.sub(r'\s+',' ',s).strip()
def read(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/rss+xml,application/xml,text/xml,*/*'})
 with urllib.request.urlopen(req,timeout=16) as r:return r.read(2_000_000)
def parse(raw,category,source,now):
 root=ET.fromstring(raw);items=[]
 for item in root.findall('.//item')[:35]:
  title=normalize(''.join(item.find('title').itertext()) if item.find('title') is not None else '')
  link=normalize(''.join(item.find('link').itertext()) if item.find('link') is not None else '')
  desc=normalize(''.join(item.find('description').itertext()) if item.find('description') is not None else '')
  date=normalize(''.join(item.find('pubDate').itertext()) if item.find('pubDate') is not None else '')
  src=normalize(''.join(item.find('source').itertext()) if item.find('source') is not None else source)
  if len(title)<13 or not link.startswith('https://'):continue
  if any(x in title for x in BLOCK_TERMS):continue
  try:dt=parsedate_to_datetime(date).astimezone(timezone.utc)
  except (TypeError,ValueError):continue
  age=(now-dt).total_seconds()/3600
  if age < -1 or age>42:continue
  if 'news.google.com' in urllib.parse.urlsplit(link).hostname.lower():
   source_label=src+' · Google News RSS 경유'
   direct=False
  else:
   source_label=source
   direct=True
  # Never quote entire articles; use short RSS excerpt only, if substantive.
  excerpt=desc[:220] if len(desc)>55 and desc!=title and title not in desc[:70] else ''
  items.append({'title':title[:165], 'excerpt':excerpt,
   'section':category,'source':source_label,'publisher':src if not direct else source,
   'url':link,'published_at':dt.isoformat(),'publisher_direct':direct,
   'age_hours':round(max(0,age),1)})
 return items
def collect(now=None,fetcher=read,feeds=FEEDS,google=GOOGLE):
 now=now or datetime.now(timezone.utc)
 targets=list(feeds)
 for category,query in google:
  url='https://news.google.com/rss/search?'+urllib.parse.urlencode(
   {'q':query+' when:1d','hl':'ko','gl':'KR','ceid':'KR:ko'})
  targets.append(('Google News',category,url))
 results=[];errors=[]
 with ThreadPoolExecutor(max_workers=8) as pool:
  jobs={pool.submit(fetcher,u):(source,category,u) for source,category,u in targets}
  for fut in as_completed(jobs):
   source,cat,url=jobs[fut]
   try:results.extend(parse(fut.result(),cat,source,now))
   except Exception as ex:errors.append({'category':cat,'feed':source,'error':str(ex)[:110]})
 seen=set();items=[]
 for n in sorted(results,key=lambda x:x['published_at'],reverse=True):
  key=re.sub(r'\W','',n['title'].lower())[:72]
  if key in seen:continue
  seen.add(key)
  score=TOPIC_BONUS.get(n['section'],10)+(max(0,42-n['age_hours'])*.44)+(7 if n['publisher_direct'] else -5)
  score+=5 if len(n['excerpt'])>100 else 0
  n['score']=round(score,2);items.append(n)
 items.sort(key=lambda x:-x['score'])
 if not items:return {'error':'no_recent_feed','errors':errors,'stories':[]}
 selected=[];used=set()
 # At most one first-pass item per category, avoid source domination.
 for section in ('경제·금융','정치·사회','국제','테크·산업','이스라엘','Religion','과학','AI 교육'):
  for n in items:
   if n['section']==section and n['title'] not in used:
    selected.append(n);used.add(n['title']);break
 for n in items:
  if len(selected)>=12:break
  if n['title'] not in used:selected.append(n);used.add(n['title'])
 selected=selected[:12]
 out=[]
 for i,n in enumerate(selected):
  ts=datetime.fromisoformat(n['published_at']).astimezone(KST)
  section=n['section']
  excerpt=n['excerpt']
  has_excerpt=bool(excerpt)
  core=(excerpt if has_excerpt else n['title']+' — 공개 RSS 제목을 확인했습니다. 본문 세부 내용은 독립 확인 전입니다.')
  url_type='발행처 RSS' if n['publisher_direct'] else 'Google News RSS 색인'
  out.append({'id':'live-'+hashlib.sha1(n['url'].encode()).hexdigest()[:12],
   'section':section,'topics':[section], 'grade':'C','priority':i+1,
   'published_date':ts.date().isoformat(),'date_label':ts.strftime('%m.%d %H:%M'),
   'title':n['title'], 'dek':(excerpt[:108]+'…' if len(excerpt)>110 else excerpt) if has_excerpt else '공개 RSS 제목 색인 · 원문 상세 확인 전',
   'core':core,'why':CONTEXT[section],
   'background': ('발행처가 제공한 공개 RSS 설명을 축약했습니다. 기사 전체 내용에 대한 심층 분석은 아닙니다.'
                  if has_excerpt else '공개 RSS 제목 이외의 기사 본문은 읽지 못했습니다. 구체적인 주장·수치를 덧붙이지 않습니다.'),
   'verification':url_type+'에서 발행 제목·시각 확인. 본문 독립 검증 및 복수 매체 교차확인 전.',
   'sources':[{'name':n['source'],'url':n['url'],'kind':'국내' if n['publisher_direct'] else '2차'}],
   'source_level':'rss_excerpt' if has_excerpt else 'rss_headline',
   'published_at':n['published_at']})
 d=now.astimezone(KST)
 return {'schema_version':1,'kind':'rss_sourced_auto_digest',
  'edition_date':d.date().isoformat(),
  'edition_label':d.strftime('%Y년 %m월 %d일 자동 수집판'),
  'published_at':d.isoformat(), 'built_at':now.isoformat(),
  'collected_range':'최근 42시간', 'stories':out,'events':[],
  'feed_count':len(results),'unique_count':len(items),
  'successful_feeds':len(targets)-len(errors),'total_feeds':len(targets),
  'errors':errors,'verification_note':'발행처 RSS의 짧은 설명·제목을 선별한 자동판입니다. 독립 취재·전문 분석·교차검증 완료라고 주장하지 않습니다.'}
if __name__=='__main__':
 data=collect()
 if not data.get('stories') or len(data['stories'])<5:
  raise SystemExit('Insufficient fresh RSS (<5); retain previous digest, fail without fabrication')
 OUT.parent.mkdir(exist_ok=True,parents=True)
 OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('LIVE EDITION',data['edition_date'],'articles',len(data['stories']),'feeds',data['successful_feeds'],'/',data['total_feeds'])
