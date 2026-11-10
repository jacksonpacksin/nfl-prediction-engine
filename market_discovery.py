"""Discover NFL player-stat market CANDIDATES; do not infer settlement mappings."""
import json
import re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from market_capture import http_json,orderbook_prices,append_jsonl,now_utc

# Conservative screening: must mention NFL plus a QB passing-yards phrase.
NFL=re.compile(r"\b(NFL|football|passing yards|pass yards|quarterback)\b",re.I)
PASS=re.compile(r"\b(pass(?:ing)? yards?|yards? pass(?:ing)?)\b",re.I)
def candidates(markets):
    result=[]
    for m in markets:
        combined=" ".join(str(m.get(k) or "") for k in ("title","subtitle","rules_primary","rules_secondary","event_ticker","series_ticker"))
        if m.get("status") not in ("active","open") or not NFL.search(combined) or not PASS.search(combined):
            continue
        result.append({"ticker":m.get("ticker"),"title":m.get("title"),"subtitle":m.get("subtitle"),
            "event_ticker":m.get("event_ticker"),"series_ticker":m.get("series_ticker"),
            "rules_primary":m.get("rules_primary"),"rules_secondary":m.get("rules_secondary"),
            "status":m.get("status"),"close_time":m.get("close_time"),
            "verification":"UNVERIFIED_CANDIDATE"})
    return [m for m in result if m["ticker"]]

def discover(max_pages=30):
    cursor=None;all_markets=[]
    for _ in range(max_pages):
        params={"limit":100,"status":"open"}
        if cursor:params["cursor"]=cursor
        response=http_json("/markets?"+urlencode(params))
        all_markets.extend(response.get("markets",[]))
        next_cursor=response.get("cursor")
        if not next_cursor or next_cursor==cursor:break
        cursor=next_cursor
    return candidates(all_markets),len(all_markets),bool(cursor)

def run():
    stamp=now_utc();out=Path("data");out.mkdir(exist_ok=True)
    try:
        found,scanned,possibly_truncated=discover()
        (out/"discovery_status.json").write_text(json.dumps({
            "captured_utc":stamp,"markets_scanned":scanned,"candidates":len(found),
            "possibly_truncated":possibly_truncated,
            "status":"CANDIDATES_ONLY","note":"No automatic contract-to-player matching or verified settlement rules. Screen may miss markets outside page cap."},indent=2)+"\n")
        if found:append_jsonl(out/"kalshi_discovered_candidates.jsonl",[{**m,"captured_utc":stamp} for m in found])
        # Preserve raw rule text and book for future audit; never label as verified.
        quotes=[]
        for m in found[:40]:
            try:
                book=http_json("/markets/"+m["ticker"]+"/orderbook")
                quotes.append({**m,"captured_utc":now_utc(),**orderbook_prices(book),"source":"Kalshi public REST"})
            except Exception as e:
                quotes.append({"ticker":m["ticker"],"captured_utc":now_utc(),"error":str(e)})
        if quotes:append_jsonl(out/"kalshi_orderbook_snapshots.jsonl",quotes)
        print("Market candidates",len(found),"scanned",scanned,"quotes",len(quotes))
    except Exception as e:
        (out/"discovery_status.json").write_text(json.dumps({"captured_utc":stamp,"status":"ERROR","error":str(e)})+"\n")
        print("Discovery unavailable:",e)

if __name__=="__main__":run()
