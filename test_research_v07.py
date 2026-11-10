import unittest
from market_discovery import candidates
from pregame import project
from execution_validation import consume_book,cluster_bootstrap

class NewResearchTests(unittest.TestCase):
    def test_discovery_is_unverified(self):
        markets=[{"ticker":"T","title":"NFL QB passing yards","status":"active"},
                 {"ticker":"X","title":"NBA points","status":"active"}]
        found=candidates(markets)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["verification"],"UNVERIFIED_CANDIDATE")
    def test_workload_uses_only_supplied_history(self):
        h=[{"pass_yards":str(200+i),"pass_attempts":"30"} for i in range(8)]
        self.assertIsNotNone(project(h,[200,250],"workload_matchup_experimental"))
        self.assertIsNone(project(h[:5],[],"champion"))
    def test_depth_insufficient(self):
        book={"orderbook_fp":{"no_dollars":[["0.45","2"]]}}
        self.assertEqual(consume_book(book,"YES",5)["status"],"NO_FILL")
    def test_depth_slippage(self):
        book={"orderbook_fp":{"no_dollars":[["0.45","2"],["0.40","4"]]}}
        self.assertGreater(consume_book(book,"YES",5)["slippage_vs_best"],0)
    def test_no_false_significance(self):
        self.assertEqual(cluster_bootstrap([])["status"],"INSUFFICIENT_INDEPENDENT_PLAYER_GAMES")

if __name__=="__main__":unittest.main()
