"""Reconcile settled contract outcomes with *previously captured* forecast and quote.

No settlement outcome is inferred from a market title or historical probability.
The contract's actual result is fetched from Kalshi, cross-checked with NFL game log,
and matched to a reviewed mapping. Only exact, timestamped pregame evidence qualifies.
"""
import csv
import json
from pathlib import Path
from market_capture import http_json
from market_ev import load_jsonl,parse_utc

def settle(mapping,market,forecast,quote,game):
    reasons=[]
    if mapping.get("rules_verified")!="true":reasons.append("UNVERIFIED_RULES")
    if market.get("result") not in ("yes","no"):reasons.append("MARKET_NOT_SETTLED")
    if str(game.get("player_id"))!=str(mapping.get("player_id")) or str(game.get("game_id"))!=str(mapping.get("game_id")):
        reasons.append("PLAYER_GAME_MISMATCH")
    try:
        threshold=float(mapping["threshold"]);yards=float(game["pass_yards"])
        # This equality is valid ONLY for reviewed OVER/UNDER thresholds and no special void rules.
        over=yards>threshold
        expected_yes=over if mapping["yes_outcome"]=="OVER" else not over
        actual_yes=market.get("result")=="yes"
        if expected_yes!=actual_yes:reasons.append("NFL_KALSHI_SETTLEMENT_CONFLICT")
        ft=parse_utc(forecast["forecast_created_utc"]);qt=parse_utc(quote["captured_utc"])
        kickoff=parse_utc(mapping["kickoff_utc"])
        if not ft<=qt<kickoff:reasons.append("NOT_POINT_IN_TIME")
    except (ValueError,KeyError,TypeError):reasons.append("INVALID_REQUIRED_FIELDS")
    if reasons:return {"ticker":mapping.get("ticker"),"status":"BLOCKED","reasons":reasons}
    return {"ticker":mapping["ticker"],"status":"VERIFIED_SETTLED","game_id":mapping["game_id"],
            "player_id":mapping["player_id"],"threshold":mapping["threshold"],
            "actual":int(market["result"]=="yes"),
            "model_p":float(forecast["p_over"]) if mapping["yes_outcome"]=="OVER" else 1-float(forecast["p_over"]),
            "market_p":float(quote["yes_bid"]+quote["yes_ask"])/2,
            "forecast_pre_kickoff":True,"quote_pre_kickoff":True,
            "mapping_verified":True,"settlement_verified":True,
            "quote_time":quote["captured_utc"],"forecast_time":forecast["forecast_created_utc"],
            "caveat":"Market midpoint is not executable; no fill or profitability implied."}

def run():
    root=Path("data");config=Path("config/reviewed_contracts.csv")
    output=[];checked=0
    if config.exists():
        with config.open(newline="") as f:reviews=list(csv.DictReader(f))
        forecasts=load_jsonl(root/"pregame_forecast_snapshots.jsonl")
        quotes=load_jsonl(root/"kalshi_orderbook_snapshots.jsonl")
        with (root/"qb_game_logs.csv").open(newline="") as f:games=list(csv.DictReader(f))
        for mapping in reviews:
            if mapping.get("rules_verified")!="true" or not all(mapping.get(k) for k in ("reviewer","reviewed_utc","rules_url","rules_sha256","threshold_rule_quote","settlement_source")):continue
            ticker=mapping["ticker"]
            try:
                market=http_json("/markets/"+ticker).get("market",{})
                if market.get("result") not in ("yes","no"):continue
                match_f=[x for x in forecasts if x.get("player_id")==mapping["player_id"] and
                         x.get("game_id")==mapping["game_id"] and
                         str(x.get("threshold"))==str(mapping["threshold"]) and x.get("model_id")=="champion"]
                match_q=[x for x in quotes if x.get("ticker")==ticker and
                         x.get("yes_bid") is not None and x.get("yes_ask") is not None]
                match_g=[x for x in games if x.get("player_id")==mapping["player_id"] and x.get("game_id")==mapping["game_id"]]
                if not(match_f and match_q and match_g):continue
                forecast=max(match_f,key=lambda x:x["forecast_created_utc"])
                eligible=[q for q in match_q if parse_utc(forecast["forecast_created_utc"])<=parse_utc(q["captured_utc"])<
                          parse_utc(mapping["kickoff_utc"])]
                if not eligible:continue
                quote=min(eligible,key=lambda q:q["captured_utc"])
                checked+=1
                output.append(settle(mapping,market,forecast,quote,match_g[0]))
            except Exception as e:output.append({"ticker":ticker,"status":"BLOCKED","reason":str(e)})
    verified=[x for x in output if x["status"]=="VERIFIED_SETTLED"]
    # Recreate the derived file deterministically; no artificial observations.
    path=root/"settled_point_in_time_comparisons.jsonl"
    with path.open("w",encoding="utf-8") as f:
        for x in verified:f.write(json.dumps(x)+"\n")
    status={"status":"RESEARCH_ONLY","contracts_checked":checked,"verified_settled":len(verified),
            "blocked":len(output)-len(verified),
            "note":"Only reviewed mappings and actual Kalshi result + NFL game log agreement qualify. No execution proof."}
    (root/"settlement_status.json").write_text(json.dumps(status,indent=2)+"\n")
    print(json.dumps(status))
if __name__=="__main__":run()
