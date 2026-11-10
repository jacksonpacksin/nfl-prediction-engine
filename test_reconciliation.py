import unittest
from availability_evidence import availability
from contract_reconciliation import verify
from settlement_reconciliation import settle

class ReconciliationTests(unittest.TestCase):
    def test_no_starter_inferred(self):
        f={"player_id":"P","game_id":"G","kickoff_utc":"2026-11-15T18:00:00Z","forecast_created_utc":"2026-11-15T15:00:00Z"}
        x=availability(f,[],[])
        self.assertEqual(x["starter_status"],"UNVERIFIED")
        self.assertEqual(x["injury_status"],"UNKNOWN")
    def test_injury_after_forecast_is_excluded(self):
        f={"player_id":"P","game_id":"G","kickoff_utc":"2026-11-15T18:00:00Z","forecast_created_utc":"2026-11-15T15:00:00Z"}
        injury=[{"player_id":"P","captured_utc":"2026-11-15T16:00:00Z","report_status":"Out"}]
        self.assertEqual(availability(f,injury,[])["injury_status"],"UNKNOWN")
    def test_unattested_contract_blocked(self):
        result=verify({"ticker":"X","title":"Passing yards"},
                      {"ticker":"X","rules_verified":"false"}, {})
        self.assertEqual(result["status"],"BLOCKED")
    def test_settlement_conflict_blocked(self):
        m={"ticker":"T","player_id":"P","game_id":"G","threshold":"224.5","yes_outcome":"OVER",
           "rules_verified":"true","kickoff_utc":"2026-11-15T18:00:00Z"}
        f={"forecast_created_utc":"2026-11-15T15:00:00Z","p_over":0.6}
        q={"captured_utc":"2026-11-15T16:00:00Z","yes_bid":0.4,"yes_ask":0.5}
        g={"player_id":"P","game_id":"G","pass_yards":"250"}
        self.assertEqual(settle(m,{"result":"no"},f,q,g)["status"],"BLOCKED")
    def test_settlement_agreement(self):
        m={"ticker":"T","player_id":"P","game_id":"G","threshold":"224.5","yes_outcome":"OVER",
           "rules_verified":"true","kickoff_utc":"2026-11-15T18:00:00Z"}
        f={"forecast_created_utc":"2026-11-15T15:00:00Z","p_over":0.6}
        q={"captured_utc":"2026-11-15T16:00:00Z","yes_bid":0.4,"yes_ask":0.5}
        g={"player_id":"P","game_id":"G","pass_yards":"250"}
        self.assertEqual(settle(m,{"result":"yes"},f,q,g)["status"],"VERIFIED_SETTLED")
if __name__=="__main__":unittest.main()
