import unittest
from datetime import datetime,timezone,timedelta
from identity_matching import match
from near_kickoff_capture import target_tickers

class IdentityAndCaptureTests(unittest.TestCase):
    def test_unique_name_is_only_candidate(self):
        c=[{"ticker":"X","title":"Patrick Mahomes passing yards"}]
        f=[{"player":"Patrick Mahomes","player_id":"gsis1","game_id":"G","kickoff_utc":"2026-11-15T18:00:00Z"}]
        x=match(c,f)[0]
        self.assertEqual(x["status"],"IDENTITY_CANDIDATE_ONLY")
        self.assertFalse(x["settlement_rules_verified"])
    def test_ambiguous_games_are_blocked(self):
        c=[{"ticker":"X","title":"Patrick Mahomes passing yards"}]
        f=[{"player":"Patrick Mahomes","player_id":"gsis1","game_id":g} for g in ("G1","G2")]
        self.assertEqual(match(c,f)[0]["status"],"AMBIGUOUS")
    def test_no_upcoming_game_no_capture(self):
        self.assertEqual(target_tickers([], [{"ticker":"T"}],datetime.now(timezone.utc)),[])
    def test_upcoming_game_capture_candidates(self):
        now=datetime(2026,11,15,12,tzinfo=timezone.utc)
        f=[{"game_id":"G","kickoff_utc":"2026-11-15T18:00:00Z"}]
        self.assertEqual(target_tickers(f,[{"ticker":"T","captured_utc":"2026-11-15T11:00:00Z"}],now),["T"])
    def test_stale_candidate_excluded(self):
        now=datetime(2026,11,15,12,tzinfo=timezone.utc)
        f=[{"game_id":"G","kickoff_utc":"2026-11-15T18:00:00Z"}]
        self.assertEqual(target_tickers(f,[{"ticker":"T","captured_utc":"2026-11-12T11:00:00Z"}],now),[])
    def test_past_kickoff_not_targeted(self):
        now=datetime(2026,11,15,19,tzinfo=timezone.utc)
        f=[{"game_id":"G","kickoff_utc":"2026-11-15T18:00:00Z"}]
        self.assertEqual(target_tickers(f,[{"ticker":"T"}],now),[])
if __name__=="__main__":unittest.main()
