"""Point-in-time evidence capture. Research only; never infer a past snapshot from today's data."""
import csv
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy as nfl

BASE="https://external-api.kalshi.com/trade-api/v2"
OUT=Path("data")
def now_utc():return datetime.now(timezone.utc).isoformat()
def http_json(path):
    req=urllib.request.Request(BASE+path,headers={"User-Agent":"NFLPredictionResearch/0.6","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=25) as response:
        return json.load(response)

def orderbook_prices(book):
    """Kalshi publishes bids on both sides; ask YES=1-best NO bid, vice versa."""
    fp=book.get("orderbook_fp")
    if not isinstance(fp,dict):
        raise ValueError("Missing orderbook_fp; cannot safely interpret orderbook")
    def best(key):
        levels=fp.get(key,[])
        parsed=[(float(p),float(q)) for p,q in levels if 0<float(p)<1 and float(q)>0]
        return max(parsed,key=lambda x:x[0]) if parsed else None
    yes,no=best("yes_dollars"),best("no_dollars")
    return {"yes_bid":yes[0] if yes else None,"yes_bid_size":yes[1] if yes else None,
            "no_bid":no[0] if no else None,"no_bid_size":no[1] if no else None,
            "yes_ask":round(1-no[0],6) if no else None,
            "yes_ask_size":no[1] if no else None,
            "no_ask":round(1-yes[0],6) if yes else None,
            "no_ask_size":yes[1] if yes else None}

def injury_snapshot(season,captured):
    frame=nfl.load_injuries(seasons=season)
    rows=frame.to_dicts()
    cleaned=[]
    for r in rows:
        # date_modified is the upstream source timestamp, NOT proof of when the row was first visible.
        source_modified=r.get("date_modified")
        cleaned.append({"season":r.get("season"),"week":r.get("week"),"team":r.get("team"),
            "player_id":r.get("gsis_id"),"player":r.get("full_name"),
            "report_status":r.get("report_status"),"practice_status":r.get("practice_status"),
            "injury":r.get("report_primary_injury"),"source_modified_utc":str(source_modified) if source_modified else None,
            "captured_utc":captured,"source":"nflverse injuries"})
    return cleaned

def append_jsonl(path,items):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f:
        for item in items:f.write(json.dumps(item,default=str,separators=(",",":"))+"\n")

def main():
    captured=now_utc()
    season=datetime.now(timezone.utc).year
    # Never overwrite previous snapshots: appended capture timestamps support future point-in-time evaluation.
    injuries=injury_snapshot(season,captured)
    append_jsonl(OUT/"injury_snapshots.jsonl",injuries)
    tickers=[t.strip() for t in os.environ.get("KALSHI_TICKERS","").split(",") if t.strip()]
    quotes=[]
    for ticker in tickers:
        if not all(c.isalnum() or c in "-_" for c in ticker):
            raise ValueError("Invalid ticker "+ticker)
        try:
            market=http_json("/markets/"+ticker).get("market",{})
            book=http_json("/markets/"+ticker+"/orderbook")
            prices=orderbook_prices(book)
            quotes.append({"captured_utc":now_utc(),"ticker":ticker,
                "market_title":market.get("title"),"status":market.get("status"),
                "series_ticker":market.get("series_ticker"),"rules_primary":market.get("rules_primary"),
                "rules_secondary":market.get("rules_secondary"),
                "close_time":market.get("close_time"),"expiration_time":market.get("expiration_time"),
                "source":"Kalshi public REST",**prices})
        except Exception as exc:
            quotes.append({"captured_utc":now_utc(),"ticker":ticker,"error":str(exc),"source":"Kalshi public REST"})
    if quotes:append_jsonl(OUT/"kalshi_orderbook_snapshots.jsonl",quotes)
    (OUT/"market_capture_status.json").write_text(json.dumps({
        "captured_utc":captured,"injury_records":len(injuries),
        "kalshi_tickers_requested":len(tickers),"kalshi_quotes_ok":sum("error" not in q for q in quotes),
        "kalshi_errors":[q for q in quotes if "error" in q],
        "mapping_status":"UNMAPPED: Kalshi ticker must be explicitly linked to a player, game and exact settlement threshold",
        "note":"Snapshot capture only; do not backfill historical information with later snapshots. No trades."},indent=2)+"\n")
    print("Snapshot complete: injuries",len(injuries),"quotes",len(quotes))

if __name__=="__main__":main()
