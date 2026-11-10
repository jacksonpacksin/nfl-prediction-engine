import unittest
from datetime import datetime,timezone
from kalshi_research_bot import analyze

NOW=datetime(2026,11,10,18,tzinfo=timezone.utc)
class ResearchBotTests(unittest.TestCase):
    def ask(self,question,quotes=None,reconciled=None):
        return analyze(question,[],quotes or [],[],{"records":[]},
                       {"market_edge_status":"NOT_ESTABLISHED"},reconciled or [],NOW)
    def test_no_verified_pick(self):
        self.assertIn("NO VERIFIED PICK",self.ask("What should I pick on Kalshi?"))
    def test_unreviewed_quote_not_recommended(self):
        q=[{"ticker":"X","captured_utc":"2026-11-10T17:59:00Z","yes_ask":0.4}]
        self.assertIn("NO VERIFIED PICK",self.ask("best pick",q))
    def test_reviewed_quote_not_called_pick(self):
        q=[{"ticker":"X","captured_utc":"2026-11-10T17:59:00Z","yes_ask":0.4}]
        a=[{"ticker":"X","status":"VERIFIED_REVIEWED"}]
        self.assertIn("not picks",self.ask("best pick",q,a).lower())
    def test_stale_quote_blocked(self):
        q=[{"ticker":"X","captured_utc":"2026-11-10T17:00:00Z","yes_ask":0.4}]
        a=[{"ticker":"X","status":"VERIFIED_REVIEWED"}]
        self.assertIn("NO VERIFIED PICK",self.ask("best pick",q,a))
if __name__=="__main__":unittest.main()
