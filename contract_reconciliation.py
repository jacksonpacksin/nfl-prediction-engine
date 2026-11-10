"""Fail-closed market reconciliation: candidates are NEVER self-certified.

An explicit reviewer attestation, source rule text, exact player/game and kickoff
are required. Any conflict or ambiguity produces a rejection record.
"""
import csv
import json
import re
from datetime import datetime,timezone
from pathlib import Path
from market_ev import load_jsonl,parse_utc

def norm(s):return re.sub(r"[^a-z0-9]+"," ",str(s).lower()).strip()
def verify(candidate,attestation,forecast):
    issues=[]
    required=("ticker","player_id","game_id","threshold","kickoff_utc","yes_outcome",
              "reviewer","reviewed_utc","rules_url","rules_sha256","rules_verified")
    for field in required:
        if not attestation.get(field):issues.append("MISSING_"+field.upper())
    if attestation.get("rules_verified")!="true":issues.append("RULES_NOT_ATTESTED")
    if candidate.get("ticker")!=attestation.get("ticker"):issues.append("TICKER_MISMATCH")
    if forecast.get("player_id")!=attestation.get("player_id") or forecast.get("game_id")!=attestation.get("game_id"):
        issues.append("PLAYER_GAME_MISMATCH")
    if str(forecast.get("threshold"))!=str(attestation.get("threshold")):issues.append("THRESHOLD_MISMATCH")
    if attestation.get("yes_outcome") not in ("OVER","UNDER"):issues.append("DIRECTION_UNVERIFIED")
    try:
        kickoff=parse_utc(attestation["kickoff_utc"])
        reviewed=parse_utc(attestation["reviewed_utc"])
        observed=parse_utc(candidate["captured_utc"])
        created=parse_utc(forecast["forecast_created_utc"])
        if not(observed<=reviewed<kickoff and created<kickoff):issues.append("TIMELINE_INVALID")
    except (ValueError,KeyError,TypeError):issues.append("TIMESTAMP_INVALID")
    text=" ".join(str(candidate.get(k) or "") for k in ("title","subtitle","rules_primary","rules_secondary"))
    if norm(forecast.get("player")) not in norm(text):issues.append("PLAYER_NAME_NOT_IN_RULES")
    if not re.search(r"pass(?:ing)? yards?",text,re.I):issues.append("STAT_TYPE_NOT_IN_RULES")
    # A threshold may be displayed as >= N or > N. Attestation must document this.
    if not attestation.get("threshold_rule_quote"):issues.append("THRESHOLD_TEXT_NOT_ATTESTED")
    if not attestation.get("settlement_source"):issues.append("SETTLEMENT_SOURCE_MISSING")
    return {"ticker":attestation.get("ticker"),"status":"VERIFIED_REVIEWED" if not issues else "BLOCKED",
            "issues":issues,"player_id":attestation.get("player_id"),"game_id":attestation.get("game_id"),
            "threshold":attestation.get("threshold"),"reviewer":attestation.get("reviewer"),
            "reviewed_utc":attestation.get("reviewed_utc")}

def run():
    root=Path("data");attest=Path("config/reviewed_contracts.csv")
    if not attest.exists():
        result={"status":"BLOCKED_NO_REVIEWED_CONTRACTS","verified":0,
                "note":"Automated matching cannot independently certify Kalshi settlement rules."}
    else:
        with attest.open(newline="") as f:reviews=list(csv.DictReader(f))
        candidates={c["ticker"]:c for c in load_jsonl(root/"kalshi_discovered_candidates.jsonl")}
        forecasts=load_jsonl(root/"pregame_forecast_snapshots.jsonl")
        result_rows=[]
        for a in reviews:
            c=candidates.get(a.get("ticker"),{})
            matched=[f for f in forecasts if f.get("player_id")==a.get("player_id") and
                     f.get("game_id")==a.get("game_id") and str(f.get("threshold"))==str(a.get("threshold"))]
            f=max(matched,key=lambda r:r["forecast_created_utc"]) if matched else {}
            result_rows.append(verify(c,a,f))
        result={"status":"REVIEWED","verified":sum(r["status"]=="VERIFIED_REVIEWED" for r in result_rows),
                "blocked":sum(r["status"]=="BLOCKED" for r in result_rows),"records":result_rows}
    (root/"reconciliation_status.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"verified":result.get("verified",0)}))
    return result
if __name__=="__main__":run()
