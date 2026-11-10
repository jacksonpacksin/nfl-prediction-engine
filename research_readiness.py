"""Operational readiness report for prospective NFL player-prop research.

A positive EV or name match never makes a contract trade-ready. This report
summarizes coverage and missing prerequisites without placing any orders.
"""
import json
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
from market_ev import load_jsonl,parse_utc

def readiness(forecasts,candidates,quotes,identities,availability,settlements,now):
    latest={}
    for f in forecasts:
        key=(f.get("game_id"),f.get("player_id"),f.get("model_id"),str(f.get("threshold")))
        if all(key[:2]) and f.get("forecast_created_utc"):
            if key not in latest or f["forecast_created_utc"]>latest[key]["forecast_created_utc"]:
                latest[key]=f
    upcoming={}
    for f in latest.values():
        try:
            kickoff=parse_utc(f["kickoff_utc"])
            if now<kickoff<=now+timedelta(days=8):
                upcoming[f["game_id"]]=kickoff
        except (ValueError,TypeError,KeyError):pass
    unique_candidates={c["ticker"]:c for c in candidates if c.get("ticker")}
    recent_quotes={}
    for q in quotes:
        try:
            ts=parse_utc(q["captured_utc"])
            if q.get("ticker") and now-timedelta(hours=24)<=ts<=now and (
                q.get("yes_ask") is not None or q.get("no_ask") is not None
            ):
                if q["ticker"] not in recent_quotes or ts>parse_utc(recent_quotes[q["ticker"]]["captured_utc"]):
                    recent_quotes[q["ticker"]]=q
        except (ValueError,KeyError,TypeError):pass
    matched={r.get("ticker") for r in identities if r.get("status")=="IDENTITY_CANDIDATE_ONLY"}
    confirmed={(r.get("game_id"),r.get("player_id")) for r in availability
               if r.get("starter_status")=="CONFIRMED_AS_OF_FORECAST"}
    return {
        "generated_utc":now.isoformat(),"status":"RESEARCH_ONLY",
        "upcoming_games":len(upcoming),
        "unique_pregame_forecasts":len(latest),
        "unique_discovered_candidates":len(unique_candidates),
        "candidates_with_identity_match":len(matched),
        "candidates_with_recent_executable_side":len(set(recent_quotes)&set(unique_candidates)),
        "player_games_with_attested_starter":len(confirmed),
        "verified_settlements":sum(x.get("status")=="VERIFIED_SETTLED" for x in settlements),
        "market_edge_status":"NOT_ESTABLISHED",
        "blocking_reasons":[
            "Name-to-GSIS candidate match does not establish exact game, threshold or settlement rules",
            "No independently connected starter verification provider",
            "Injury status is evidence-only, not probability-adjusted",
            "No verified contemporaneous matched market forecast/settlement archive",
            "Order-book snapshots are indicative and do not establish fills"
        ]
    }

def run():
    root=Path("data")
    def records(name):return load_jsonl(root/name)
    def status_records(name):
        try:return json.loads((root/name).read_text()).get("records",[])
        except (OSError,ValueError):return []
    report=readiness(records("pregame_forecast_snapshots.jsonl"),
                     records("kalshi_discovered_candidates.jsonl"),
                     records("kalshi_orderbook_snapshots.jsonl"),
                     status_records("identity_matching_status.json"),
                     status_records("availability_status.json"),
                     status_records("settlement_status.json"),
                     datetime.now(timezone.utc))
    (root/"research_readiness.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":run()
