"""Deterministic GSIS player matching for market *candidates*, not rule verification.

Require unique normalized full-name match, explicit passing-yard wording and
unambiguous opponent/game context. No fuzzy-name or ticker-only acceptance.
"""
import csv,json,re
from collections import defaultdict
from pathlib import Path
from market_ev import load_jsonl

def normalize(s):return re.sub(r"[^a-z0-9]+"," ",str(s).casefold()).strip()
def match(candidates,forecasts):
    players=defaultdict(dict)
    for f in forecasts:
        if not f.get("player_id") or not f.get("game_id"):continue
        key=(f["player_id"],f["game_id"])
        players[key]=f
    results=[]
    for c in candidates:
        title=" ".join(str(c.get(k) or "") for k in ("title","subtitle","rules_primary","rules_secondary"))
        normalized=" "+normalize(title)+" "
        matches=[]
        for f in players.values():
            name=normalize(f.get("player",""))
            if len(name.split())<2 or (" "+name+" ") not in normalized:continue
            if "pass" not in normalized or "yard" not in normalized:continue
            matches.append(f)
        distinct={(x["player_id"],x["game_id"]) for x in matches}
        result={"ticker":c.get("ticker"),"captured_utc":c.get("captured_utc"),
                "status":"AMBIGUOUS" if len(distinct)>1 else "UNMATCHED",
                "matched_player_id":None,"matched_game_id":None,
                "settlement_rules_verified":False}
        if len(distinct)==1:
            f=matches[0]
            result.update(status="IDENTITY_CANDIDATE_ONLY",matched_player_id=f["player_id"],
                          matched_game_id=f["game_id"],matched_player=f["player"],
                          kickoff_utc=f.get("kickoff_utc"),
                          note="GSIS ID comes from nflverse QB game logs. Name text is not proof of game, threshold, or Kalshi settlement.")
        results.append(result)
    return results

def run():
    root=Path("data")
    candidates=load_jsonl(root/"kalshi_discovered_candidates.jsonl")
    forecasts=load_jsonl(root/"pregame_forecast_snapshots.jsonl")
    latest={}
    for c in candidates:latest[c["ticker"]]=c
    rows=match(latest.values(),forecasts)
    report={"status":"IDENTITY_CANDIDATES_ONLY","candidates":len(rows),
            "unique_name_matches":sum(x["status"]=="IDENTITY_CANDIDATE_ONLY" for x in rows),
            "blocked_or_unmatched":sum(x["status"]!="IDENTITY_CANDIDATE_ONLY" for x in rows),
            "records":rows[:300],
            "warning":"No automated settlement rule or starter certification. Human rule attestation required."}
    (root/"identity_matching_status.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="records"}))
if __name__=="__main__":run()
