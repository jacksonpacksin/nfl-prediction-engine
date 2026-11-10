"""Research-only market EV evaluation using explicit, audited mappings and captured quotes.

Do not equate game-log hindsight with pregame forecasts. A forecast must have its own
captured_at timestamp and precede the quote and game kickoff.
"""
import csv
import json
import math
from datetime import datetime,timezone
from pathlib import Path

def fee(price,contracts=1,multiplier=1.0):
    """General Kalshi taker fee; conservatively round up to nearest cent per order.
    Series-specific rates must be verified manually; default is NOT universal."""
    if not 0<price<1 or contracts<1 or multiplier<0:raise ValueError("Bad fee inputs")
    return math.ceil((0.07*multiplier*contracts*price*(1-price))*100-1e-12)/100

def evaluate(p_yes,yes_ask,no_ask,contracts=1,multiplier=1.0):
    if not 0<=p_yes<=1:raise ValueError("Invalid probability")
    result={}
    for side,ask,prob in (("YES",yes_ask,p_yes),("NO",no_ask,1-p_yes)):
        if ask is None:continue
        ask=float(ask)
        if not 0<ask<1:continue
        costs=fee(ask,contracts,multiplier)
        ev=contracts*(prob-ask)-costs
        result[side]={"ask":ask,"model_probability":prob,"contracts":contracts,
            "taker_fee_total":costs,"expected_profit_dollars":round(ev,6),
            "expected_profit_per_contract":round(ev/contracts,6),
            "break_even_probability":round(ask+costs/contracts,6),
            "edge_probability_points_after_fee":round(100*(prob-ask-costs/contracts),3)}
    return result

def parse_utc(s):
    dt=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("Timestamp missing timezone")
    return dt.astimezone(timezone.utc)

def load_jsonl(path):
    if not Path(path).exists():return []
    with open(path,encoding="utf-8") as f:return [json.loads(line) for line in f if line.strip()]

def audit(mappings,forecasts,quotes,max_age_minutes=15):
    """Only report verified one-to-one event mappings with as-of forecasts.
    Inputs are *external* timestamped forecasts; v0.5 holdout outcomes cannot be used.
    """
    f_by_key={(f["player_id"],f["game_id"],str(f["threshold"])):f for f in forecasts}
    output=[]
    for mapping in mappings:
        ticker=mapping["ticker"]
        if mapping.get("rules_verified","").lower()!="true":
            output.append({"ticker":ticker,"status":"BLOCKED_RULES_UNVERIFIED"});continue
        key=(mapping["player_id"],mapping["game_id"],str(mapping["threshold"]))
        forecast=f_by_key.get(key)
        if not forecast:
            output.append({"ticker":ticker,"status":"BLOCKED_NO_TIMESTAMPED_FORECAST"});continue
        matching=[q for q in quotes if q.get("ticker")==ticker and "error" not in q]
        if not matching:
            output.append({"ticker":ticker,"status":"BLOCKED_NO_ORDERBOOK"});continue
        quote=max(matching,key=lambda q:q["captured_utc"])
        try:
            forecast_time=parse_utc(forecast["forecast_created_utc"])
            quote_time=parse_utc(quote["captured_utc"])
            kickoff=parse_utc(mapping["kickoff_utc"])
            if not(forecast_time<=quote_time<kickoff):
                raise ValueError("Forecast/quote not before kickoff or forecast created after quote")
            age=(quote_time-forecast_time).total_seconds()/60
            if age>max_age_minutes:raise ValueError("Forecast stale")
            if quote.get("status") not in ("active","open"):
                raise ValueError("Market not open")
            if not quote.get("yes_ask") and not quote.get("no_ask"):
                raise ValueError("No executable asks")
            multiplier=float(mapping["fee_multiplier"])
            if multiplier<0:raise ValueError("Invalid fee multiplier")
            prob=float(forecast["p_yes"])
            # Mapping must explicitly assert whether YES means OVER or UNDER.
            if mapping["yes_outcome"] not in ("OVER","UNDER"):
                raise ValueError("Unverified YES settlement direction")
            ev=evaluate(prob,quote.get("yes_ask"),quote.get("no_ask"),int(mapping["contracts"]),multiplier)
            output.append({"ticker":ticker,"status":"RESEARCH_ONLY","quote_time":quote["captured_utc"],
                "forecast_time":forecast["forecast_created_utc"],"model_id":forecast.get("model_id"),
                "yes_outcome":mapping["yes_outcome"],"ev":ev,
                "note":"Top-of-book indicative, no guaranteed fill; verify depth and series fee schedule"})
        except (ValueError,KeyError,TypeError) as exc:
            output.append({"ticker":ticker,"status":"BLOCKED","reason":str(exc)})
    return output

def run():
    root=Path("data")
    mapping_path=Path("config/verified_market_mappings.csv")
    forecast_path=root/"pregame_forecasts.csv"
    if not mapping_path.exists() or not forecast_path.exists():
        print("No verified mappings and timestamped pregame forecasts: market comparison disabled")
        return []
    with mapping_path.open(newline="") as f:mappings=list(csv.DictReader(f))
    with forecast_path.open(newline="") as f:forecasts=list(csv.DictReader(f))
    output=audit(mappings,forecasts,load_jsonl(root/"kalshi_orderbook_snapshots.jsonl"))
    (root/"market_ev_report.json").write_text(json.dumps(output,indent=2)+"\n")
    print(json.dumps({"evaluated":sum(r["status"]=="RESEARCH_ONLY" for r in output),"blocked":sum(r["status"]!="RESEARCH_ONLY" for r in output)}))
    return output

if __name__=="__main__":run()
