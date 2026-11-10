"""Conservative paper-fill simulator and cluster-bootstrap comparison.

Requires prospectively timestamped, independently verified market mappings and
forecast records. Missing quotes or no depth => NO FILL, not a profitable trade.
"""
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from market_ev import fee,parse_utc,load_jsonl

def consume_book(book,side,contracts):
    """Simulate aggressive buy against opposite-side bids (fixed-point dollars)."""
    levels=book.get("orderbook_fp",{}).get("no_dollars" if side=="YES" else "yes_dollars",[])
    asks=sorted([(1-float(p),float(q)) for p,q in levels if 0<float(p)<1 and float(q)>0])
    left=contracts;cost=0.0
    for ask,qty in asks:
        fill=min(left,qty);cost+=ask*fill;left-=fill
        if left<=1e-9:break
    if left>1e-9:return {"status":"NO_FILL","missing_contracts":round(left,6)}
    avg=cost/contracts
    return {"status":"PAPER_FILLED","contracts":contracts,"average_ask":round(avg,6),
            "slippage_vs_best":round(avg-asks[0][0],6),
            "fee_estimate":fee(avg,contracts),"cost_plus_fee":round(cost+fee(avg,contracts),6)}

def cluster_bootstrap(paired,iterations=2000,seed=2026):
    """Paired differences grouped by player-game; CI on model minus market Brier."""
    clusters=defaultdict(list)
    for r in paired:
        key=(r["game_id"],r["player_id"])
        clusters[key].append((float(r["model_p"])-int(r["actual"]))**2-
                             (float(r["market_p"])-int(r["actual"]))**2)
    if len(clusters)<30:return {"status":"INSUFFICIENT_INDEPENDENT_PLAYER_GAMES","clusters":len(clusters)}
    groups=list(clusters.values());rng=random.Random(seed);n=len(groups)
    draws=[]
    for _ in range(iterations):
        sample=[groups[rng.randrange(n)] for _ in range(n)]
        draws.append(sum(map(sum,sample))/sum(map(len,sample)))
    draws.sort()
    return {"status":"EVALUATED","clusters":n,
            "mean_delta_brier":round(sum(map(sum,groups))/sum(map(len,groups)),6),
            "ci95":[round(draws[int(.025*iterations)],6),round(draws[int(.975*iterations)],6)],
            "interpretation":"Negative favors model. No edge claim unless interval excludes zero; market midpoint is not executable price."}

def run():
    root=Path("data")
    # No historical matched, settled dataset yet; do not create a fictitious result.
    path=root/"settled_point_in_time_comparisons.jsonl"
    pairs=load_jsonl(path)
    verified=[r for r in pairs if r.get("mapping_verified") is True and r.get("settlement_verified") is True
              and r.get("forecast_pre_kickoff") is True and r.get("quote_pre_kickoff") is True]
    result=cluster_bootstrap(verified)
    result["records_seen"]=len(pairs);result["verified_records"]=len(verified)
    result["warning"]="Data must be captured prospectively. Never manufacture historical quotes from present orderbooks."
    (root/"edge_validation_status.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))

if __name__=="__main__":run()
