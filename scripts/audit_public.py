#!/usr/bin/env python3
"""Audit the actual public GitHub Pages URL and produce an independent status JSON.
Run after deploy; never mark success without HTTP and browser checks.
"""
import json, os, sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen

base=os.environ.get("PUBLIC_URL","https://joshua7park-cyber.github.io/BJ-NewsRoom/").rstrip("/")+"/"
revision=os.environ.get("GITHUB_SHA","unknown")
run=os.environ.get("GITHUB_RUN_ID","unknown")
p=Path("site/deployment-status.json")
obj={"schema_version":1,"observed_at_utc":datetime.now(timezone.utc).isoformat(),"run_id":run,
     "revision":revision,"deploy":"completed","public_http":"failed","public_browser":os.environ.get("BROWSER_CHECK","not_run"),
     "latest_run_status":"failed","site_url":base}
try:
    with urlopen(base,timeout=25) as r: page=r.read().decode("utf8")
    assert "오늘의 하이라이트" in page and "site/newsroom.json" not in page
    with urlopen(base+"data/edition.json",timeout=25) as r: news=json.load(r)
    assert len(news["stories"])>=5
    obj["public_http"]="passed"
    obj["edition_date"]=news["edition_date"]
    if obj["public_browser"]=="passed":obj["latest_run_status"]="success"
except Exception as exc:
    obj["error"]=str(exc)[:350]
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(json.dumps(obj,ensure_ascii=False))
if obj["latest_run_status"]!="success":sys.exit(1)
