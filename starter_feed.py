"""Independent starter feed adapter. No provider configured => no verified starters.

Provider must return HTTPS JSON:
{"updated_utc":"2026-11-15T16:00:00Z","starters":[
 {"game_id":"2026_11_KC_BUF","player_id":"00-0033873",
  "team":"KC","status":"confirmed","source_url":"https://...","confirmed_utc":"..."}]}
A depth chart, projection, or probable listing is NOT a confirmed starter.
"""
import json,os,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
from market_ev import parse_utc

def verify_payload(payload,now):
    updated=parse_utc(payload["updated_utc"])
    if not now-timedelta(hours=6)<=updated<=now+timedelta(minutes=5):
        raise ValueError("Provider feed stale or future-dated")
    valid=[];rejected=[]
    for row in payload.get("starters",[]):
        try:
            if row.get("status")!="confirmed":raise ValueError("Not confirmed")
            if not all(row.get(k) for k in ("game_id","player_id","team","source_url","confirmed_utc")):
                raise ValueError("Missing independent evidence")
            if not row["source_url"].startswith("https://"):raise ValueError("Source must use HTTPS")
            confirmed=parse_utc(row["confirmed_utc"])
            if not now-timedelta(hours=24)<=confirmed<=now+timedelta(minutes=5):
                raise ValueError("Confirmation stale or future-dated")
            valid.append({**{k:row[k] for k in ("game_id","player_id","team","source_url","confirmed_utc")},"captured_utc":now.isoformat(),"provider_status":"CONFIRMED_CLAIM_NOT_INDEPENDENTLY_AUDITED"})
        except (ValueError,KeyError,TypeError) as e:
            rejected.append({"game_id":row.get("game_id"),"reason":str(e)})
    return valid,rejected

def run():
    root=Path("data");root.mkdir(exist_ok=True)
    url=os.environ.get("NFL_STARTER_FEED_URL","").strip()
    status={"captured_utc":datetime.now(timezone.utc).isoformat(),
            "status":"NOT_CONFIGURED","verified":0}
    if url:
        try:
            if not url.startswith("https://"):raise ValueError("Feed must be HTTPS")
            req=urllib.request.Request(url,headers={"Accept":"application/json",
                "Authorization":"Bearer "+os.environ["NFL_STARTER_FEED_TOKEN"]})
            with urllib.request.urlopen(req,timeout=20) as r:payload=json.load(r)
            valid,rejected=verify_payload(payload,datetime.now(timezone.utc))
            # Replace current state, never forge earlier confirmations.
            (root/"independent_starter_feed.json").write_text(json.dumps(valid,indent=2)+"\n")
            status.update(status="VERIFIED_FEED_ROWS" if valid else "NO_CONFIRMED_ROWS",
                          verified=len(valid),rejected=rejected[:30])
        except Exception as e:status.update(status="ERROR",error=str(e))
    (root/"starter_feed_status.json").write_text(json.dumps(status,indent=2)+"\n")
    print(json.dumps(status))
if __name__=="__main__":run()
