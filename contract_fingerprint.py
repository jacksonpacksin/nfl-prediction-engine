"""Audit current Kalshi contract rules against reviewed mappings, fail closed.

This checks cryptographic identity of the reviewed rule text. It does not
magically determine whether the human reviewer interpreted the contract right.
"""
import csv,hashlib,json
from pathlib import Path
from market_capture import http_json
from market_ev import parse_utc

def canonical_rules(m):
    return "\n".join(str(m.get(k) or "") for k in
        ("ticker","event_ticker","title","rules_primary","rules_secondary","strike_type","floor_strike","cap_strike"))

def fingerprint(m):return hashlib.sha256(canonical_rules(m).encode()).hexdigest()

def audit(review,market):
    reasons=[]
    if review.get("rules_verified")!="true":reasons.append("NOT_REVIEWED")
    if review.get("ticker")!=market.get("ticker"):reasons.append("TICKER_MISMATCH")
    if not review.get("rules_sha256") or review["rules_sha256"].lower()!=fingerprint(market):
        reasons.append("RULES_CHANGED_OR_HASH_MISMATCH")
    if not review.get("event_ticker") or review["event_ticker"]!=market.get("event_ticker"):
        reasons.append("EVENT_TICKER_MISMATCH")
    if not review.get("strike_type") or review["strike_type"]!=str(market.get("strike_type") or ""):
        reasons.append("STRIKE_TYPE_MISMATCH")
    for k in ("floor_strike","cap_strike"):
        if str(review.get(k) or "")!=str(market.get(k) or ""):reasons.append(k.upper()+"_MISMATCH")
    if not review.get("source_game_reference"):reasons.append("GAME_REFERENCE_UNATTESTED")
    return {"ticker":review.get("ticker"),"status":"RULE_FINGERPRINT_MATCH" if not reasons else "BLOCKED",
            "reasons":reasons,"current_rules_sha256":fingerprint(market)}

def run():
    root=Path("data");cfg=Path("config/reviewed_contracts.csv")
    results=[]
    if cfg.exists():
        with cfg.open(newline="") as f:reviews=list(csv.DictReader(f))
        for r in reviews:
            try:
                m=http_json("/markets/"+r["ticker"]).get("market",{})
                results.append(audit(r,m))
            except Exception as e:results.append({"ticker":r.get("ticker"),"status":"BLOCKED","reasons":[str(e)]})
    report={"status":"RESEARCH_ONLY","reviewed_contracts":len(results),
            "rule_fingerprint_matches":sum(r["status"]=="RULE_FINGERPRINT_MATCH" for r in results),
            "records":results,"note":"Reviewer must inspect full terms, void rules and player/game identity."}
    (root/"contract_fingerprint_status.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="records"}))
if __name__=="__main__":run()
