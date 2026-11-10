"""Near-kickoff Kalshi quote capture with strict timing and audit metadata.

Schedule every 15 minutes. Only snapshot tickers discovered previously, with
kickoff within next 6h and no more than 30 minutes after capture.
No live orders. No assumption that discovered ticker belongs to the game.
"""
import json,os
from datetime import datetime,timezone,timedelta
from pathlib import Path
from market_capture import http_json,orderbook_prices,append_jsonl,now_utc
from market_ev import load_jsonl,parse_utc

def target_tickers(forecasts,candidates,now,hours=6):
    games={}
    for f in forecasts:
        try:
            kickoff=parse_utc(f["kickoff_utc"])
            if now<kickoff<=now+timedelta(hours=hours):
                games[f["game_id"]]=kickoff
        except (KeyError,ValueError,TypeError):continue
    # Only quote recently discovered candidates; name matching remains unverified.
    if not games:return []
    unique={}
    for c in candidates:
        ticker=c.get("ticker")
        if not ticker:continue
        try:
            observed=parse_utc(c["captured_utc"])
            if not now-timedelta(hours=24)<=observed<=now:continue
            if c.get("close_time") and parse_utc(c["close_time"])<=now:continue
        except (ValueError,TypeError,KeyError):continue
        unique[ticker]=c
    return sorted(unique)[:80]

def run():
    root=Path("data");root.mkdir(exist_ok=True)
    now=datetime.now(timezone.utc)
    forecasts=load_jsonl(root/"pregame_forecast_snapshots.jsonl")
    candidates=load_jsonl(root/"kalshi_discovered_candidates.jsonl")
    # Limit to unique player/game name matches whose kickoff is approaching.
    try:
        identities=json.loads((root/"identity_matching_status.json").read_text()).get("records",[])
    except (OSError,ValueError):
        identities=[]
    upcoming_ids=set()
    for f in forecasts:
        try:
            if now<parse_utc(f["kickoff_utc"])<=now+timedelta(hours=6):
                upcoming_ids.add(f["game_id"])
        except (KeyError,ValueError,TypeError):pass
    allowed={i["ticker"] for i in identities if i.get("status")=="IDENTITY_CANDIDATE_ONLY"
             and i.get("matched_game_id") in upcoming_ids}
    tickers=[t for t in target_tickers(forecasts,candidates,now) if t in allowed]
    quotes=[];errors=[]
    for ticker in tickers:
        try:
            market=http_json("/markets/"+ticker).get("market",{})
            if market.get("status") not in ("active","open"):continue
            book=http_json("/markets/"+ticker+"/orderbook")
            quotes.append({"captured_utc":now_utc(),"ticker":ticker,
                "market_title":market.get("title"),"status":market.get("status"),
                "rules_primary":market.get("rules_primary"),
                "rules_secondary":market.get("rules_secondary"),
                "close_time":market.get("close_time"),
                "source":"Kalshi public REST near-kickoff scheduled capture",
                "capture_scope":"CANDIDATE_NOT_VERIFIED",**orderbook_prices(book),
                "orderbook_fp":book.get("orderbook_fp")})
        except Exception as e:errors.append({"ticker":ticker,"error":str(e)})
    if quotes:append_jsonl(root/"kalshi_orderbook_snapshots.jsonl",quotes)
    (root/"near_kickoff_status.json").write_text(json.dumps({
        "captured_utc":now.isoformat(),"tickers_targeted":len(tickers),"matched_upcoming_candidates":len(allowed),
        "quotes_captured":len(quotes),"errors":errors[:30],
        "status":"CAPTURE_ONLY","warning":"Scheduled 15-minute polling is not guaranteed to execute on time; no contract identity/rules inferred."},indent=2)+"\n")
    print("Near kickoff",len(quotes),"quotes",len(errors),"errors")
if __name__=="__main__":run()
