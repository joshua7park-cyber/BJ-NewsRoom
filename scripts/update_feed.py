#!/usr/bin/env python3
"""Build a transparent, sourced news digest from public RSS searches.
RSS indexing != independent fact-checking. Never label indexed articles verified.
"""
import json, os, re, sys, html, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'site'
KST=timezone(timedelta(hours=9))
SECTIONS=[('kbs','📺','KBS 뉴스9'),('domestic','🇰🇷','국내 종합'),('global','🌍','국제 정세·경제'),('israel','🛡️','이스라엘·중동'),('religion','✝️','Religion / 세계 종교'),('mission','🌐','글로벌 선교·생명 윤리'),('science','🔬','과학·첨단기술'),('ai','🎓','AI 교육·행사')]
QUERIES={
 'domestic':['site:yna.co.kr 한국 주요 뉴스','site:news.kbs.co.kr 한국 주요 뉴스','site:imnews.imbc.com 한국 주요 뉴스','site:news.sbs.co.kr 한국 주요 뉴스','site:news.jtbc.co.kr 한국 주요 뉴스','site:ytn.co.kr 한국 주요 뉴스','site:hankookilbo.com 한국 주요 뉴스','site:hani.co.kr 한국 주요 뉴스','site:khan.co.kr 한국 주요 뉴스','site:joongang.co.kr 한국 주요 뉴스','site:donga.com 한국 주요 뉴스','site:chosun.com 한국 주요 뉴스','site:seoul.co.kr 한국 주요 뉴스','site:mk.co.kr 한국 경제','site:hankyung.com 한국 경제','site:sedaily.com 한국 경제','site:etnews.com 한국 산업','site:news1.kr 한국 주요 뉴스','site:newsis.com 한국 주요 뉴스'],
 'global':['international relations global economy','US China Japan Europe world economy'],
 'israel':['Israel Gaza Middle East diplomacy humanitarian','이스라엘 중동 외교 인도주의'],
 'religion':['religion catholic protestant buddhism islam ethics','세계 종교 가톨릭 불교 이슬람 윤리'],
 'mission':['기독교 세계 선교 신학 목회 KWMA','global Christian mission church ethics'],
 'science':['AI semiconductor space quantum science','인공지능 반도체 우주 양자 기술'],
 'ai':['생성형 AI 교육 세미나 ChatGPT Gemini Claude','AI training workshop seminar Korea'],
}

MAX_PER_SECTION=16
TRUSTED_KOREAN_DOMAINS=('yna.co.kr','kbs.co.kr','imbc.com','sbs.co.kr','jtbc.co.kr','ytn.co.kr','hankookilbo.com','hani.co.kr','khan.co.kr','joongang.co.kr','donga.com','chosun.com','seoul.co.kr','mk.co.kr','hankyung.com','sedaily.com','etnews.com','news1.kr','newsis.com')
DOMESTIC_PUBLISHERS=('연합뉴스','KBS','MBC','SBS','JTBC','YTN','한국일보','한겨레','경향신문','중앙일보','동아일보','조선일보','서울신문','매일경제','한국경제','서울경제','전자신문','뉴스1','뉴시스')
def balanced_select(items,limit=MAX_PER_SECTION):
 pool={}
 for n in unique(items):
  pool.setdefault(n['source'].strip(),[]).append(n)
 result=[]
 for i in range(2):
  for name in sorted(pool):
   if len(result)>=limit:break
   if len(pool[name])>i:result.append(pool[name][i])
 return result


def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'BJNewsroomRSS/1.0 (news research dashboard)'})
 with urllib.request.urlopen(req,timeout=22) as response:
  return response.read(2_000_000)

def txt(element,name):
 found=element.find(name)
 return ''.join(found.itertext()).strip() if found is not None else ''

def trusted_original(url):
 """Return independently validated Korean publisher URL; never claim an aggregator is original."""
 try:
  u=urllib.parse.urlsplit(url)
  if u.scheme!='https':return None
  host=(u.hostname or '').lower()
  if any(host==d or host.endswith('.'+d) for d in TRUSTED_KOREAN_DOMAINS):
   return url
 except ValueError:pass
 return None

def resolve_original(url, opener=None):
 """Best-effort redirect check; fail closed if Google does not redirect to publisher."""
 if trusted_original(url):return url
 if not url.startswith('https://news.google.com/'):return None
 opener=opener or urllib.request.urlopen
 try:
  request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; BJNewsroom/1.0)'})
  with opener(request,timeout=6) as res:
   final=res.geturl()
  return trusted_original(final)
 except (OSError, ValueError):return None

def parse_feed(xml_bytes,section,now):
 root=ET.fromstring(xml_bytes)
 items=[]
 for item in root.findall('.//item'):
  title=html.unescape(re.sub(r'<[^>]+>','',txt(item,'title'))).strip()
  url=txt(item,'link').strip()
  pub=txt(item,'pubDate')
  source=txt(item,'source') or 'Google News RSS 색인'
  if not title or not url.startswith('https://'): continue
  if section=='domestic' and not any(p.casefold() in source.casefold() for p in DOMESTIC_PUBLISHERS):continue
  try: date=parsedate_to_datetime(pub).astimezone(timezone.utc)
  except Exception: continue
  age=(now-date).total_seconds()/3600
  if age< -3 or age>72: continue
  # Google News links are aggregator links; show explicitly.
  items.append({'section':section,'title':title[:280], 'url':url,'date':date.isoformat(),
   'source':source,'summary':'RSS에 공개된 제목을 표시합니다. 원문에서 본문과 사실관계를 확인하세요.',
   'insight':'자동 생성된 분석 없음','verification_status':'자동 수집 · 원문 사실검증 전',
   'verification_level':'indexed','kind':'news',
   'original_url':trusted_original(url),'link_type':'publisher_direct' if trusted_original(url) else 'aggregator'})
 return items

def unique(items):
 seen=set(); out=[]
 for n in items:
  key=re.sub(r'\W+','',n['title'].casefold())[:100]
  if key in seen: continue
  seen.add(key);out.append(n)
 return out

def load_events(now):
 p=ROOT/'data'/'official_events.json'
 if not p.exists():return []
 data=json.loads(p.read_text(encoding='utf8'))
 out=[]
 for e in data:
  if not e.get('official_url','').startswith('https://'):continue
  try:
   day=datetime.fromisoformat(e['date'][:10]).date()
   if not (now.astimezone(KST).date()<=day<=now.astimezone(KST).date()+timedelta(days=30)):continue
  except: continue
  e=dict(e);e['section']='ai';e['url']=e.pop('official_url');e['kind']='event'
  e['verification_status']='편집 입력된 공식 안내 · 실시간 모집상태 미보증'
  e['verification_level']='official_listing'
  out.append(e)
 return out

def build(fetcher=fetch,now=None):
 now=now or datetime.now(timezone.utc)
 counts={}; feed_errors=[]; records=[]
 for section,_,_ in SECTIONS:
  if section=='kbs':
   # Do not misrepresent search results as a specific KBS 9 broadcast.
   counts[section]=0; continue
  collected=[]
  for query in QUERIES.get(section,[]):
   rss='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query+' when:3d','hl':'ko','gl':'KR','ceid':'KR:ko'})
   try: collected.extend(parse_feed(fetcher(rss),section,now))
   except Exception as ex:feed_errors.append({'section':section,'query':query,'error':str(ex)[:160]})
  collected=balanced_select(collected) if section=='domestic' else unique(collected)[:MAX_PER_SECTION]
  if section=='domestic':
   for story in collected:
    original=resolve_original(story['url'])
    if original:
     story['url']=original;story['original_url']=original;story['link_type']='publisher_direct'
    else:story['link_type']='aggregator'
  records.extend(collected);counts[section]=len(collected)
 events=load_events(now)
 # Event category: only official curated events count toward verified event goal.
 counts['ai_events']=len(events)
 freshness={'built_at':now.isoformat(),'stale_after':(now+timedelta(hours=3)).isoformat()}
 return {'schema_version':2,'sections':[{'id':i,'icon':ico,'title':label} for i,ico,label in SECTIONS],
         'news':records,'events':events,'counts':counts,'errors':feed_errors,
         'status':{'level':'auto_indexed_not_fact_checked','kbs_broadcast_verified':False,
                   'minimum_5_verified_per_section':False,
                   'note':'자동 RSS 수집 결과는 편집 검증 뉴스가 아닙니다. KBS 뉴스9 방송 대조는 별도 검증이 필요합니다.'},
         **freshness}

if __name__=='__main__':
 SITE.mkdir(exist_ok=True,parents=True)
 result=build()
 (SITE/'newsroom.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print('Saved',SITE/'newsroom.json','news:',len(result['news']),'events:',len(result['events']),'errors:',len(result['errors']))
 if os.environ.get('REQUIRE_AT_LEAST_ONE_FEED')=='1' and not result['news']:
  sys.exit('No articles collected; not publishing empty feed')
