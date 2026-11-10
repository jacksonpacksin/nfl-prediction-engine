import unittest
from market_capture import orderbook_prices
from market_ev import fee,evaluate,audit

class MarketTests(unittest.TestCase):
    def test_complementary_asks(self):
        p=orderbook_prices({"orderbook_fp":{"yes_dollars":[["0.40","10"]],"no_dollars":[["0.55","8"]]}})
        self.assertEqual(p["yes_ask"],0.45)
        self.assertEqual(p["no_ask"],0.60)
        self.assertEqual(p["yes_ask_size"],8)
    def test_no_ask_when_empty(self):
        p=orderbook_prices({"orderbook_fp":{"yes_dollars":[],"no_dollars":[]}})
        self.assertIsNone(p["yes_ask"])
    def test_fees(self):
        self.assertEqual(fee(0.5,100),1.75)
        self.assertEqual(fee(0.5,1),0.02)
    def test_ev(self):
        e=evaluate(0.6,0.5,0.5,100)
        self.assertAlmostEqual(e["YES"]["expected_profit_dollars"],8.25)
    def test_rules_gate(self):
        x=audit([{"ticker":"T","rules_verified":"false"}],[],[])
        self.assertEqual(x[0]["status"],"BLOCKED_RULES_UNVERIFIED")
    def test_hindsight_block(self):
        m=[dict(ticker="T",rules_verified="true",player_id="P",game_id="G",
                threshold="224.5",kickoff_utc="2026-11-10T20:00:00+00:00",
                fee_multiplier="1",contracts="1",yes_outcome="OVER")]
        f=[dict(player_id="P",game_id="G",threshold="224.5",p_yes="0.6",
                forecast_created_utc="2026-11-10T20:01:00+00:00")]
        q=[dict(ticker="T",captured_utc="2026-11-10T19:00:00+00:00",status="active",yes_ask=0.5,no_ask=0.5)]
        self.assertEqual(audit(m,f,q)[0]["status"],"BLOCKED")

if __name__=="__main__":unittest.main()
