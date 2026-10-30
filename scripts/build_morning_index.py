#!/usr/bin/env python3
"""Generate a clearly labeled machine-compiled morning index; not the ChatGPT scheduled editorial."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KST=timezone(timedelta(hours=9))
def build(source,now=None):
 now=now or datetime.now(timezone.utc)
 today=now.astimezone(KST).date().isoformat()
 rows=[x for x in source.get('news',[]) if x.get('title') and x.get('url','').startswith('https://')]
 primary=[x for x in rows if x['section']=='domestic'][:8]
 other=[x for x in rows if x['section']!='domestic'][:10]
 return {'schema_version':1,'date_kst':today,'built_at':now.isoformat(),
  'is_chatgpt_editorial':False,'kind':'automated_rss_index','summary':'오전 뉴스 자동색인(기사 본문 독립검증 전)',
  'items':[{'title':x['title'],'url':x['url'],'section':x['section'],
            'source':x.get('source','출처 확인 필요'),'region':'KR' if x['section']=='domestic' else 'Global',
            'verification_level':'indexed','link_type':x.get('link_type','aggregator')}
           for x in primary+other]}
if __name__=='__main__':
 src=json.loads((ROOT/'site/newsroom.json').read_text(encoding='utf8'))
 out=build(src)
 (ROOT/'morning-index.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 print('Morning RSS index',out['date_kst'],len(out['items']))
