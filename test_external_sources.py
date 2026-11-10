import unittest
from datetime import datetime,timezone
from starter_feed import verify_payload
from contract_fingerprint import audit,fingerprint

class SourceFeedTests(unittest.TestCase):
    def test_projected_starter_rejected(self):
        now=datetime(2026,11,15,17,tzinfo=timezone.utc)
        payload={"updated_utc":"2026-11-15T16:00:00Z","starters":[
            {"status":"projected","game_id":"G","player_id":"P","team":"KC",
             "source_url":"https://example.org","confirmed_utc":"2026-11-15T16:00:00Z"}]}
        good,bad=verify_payload(payload,now)
        self.assertEqual(len(good),0)
        self.assertEqual(len(bad),1)
    def test_claim_capture_timestamp(self):
        now=datetime(2026,11,15,17,tzinfo=timezone.utc)
        payload={"updated_utc":"2026-11-15T16:00:00Z","starters":[
            {"status":"confirmed","game_id":"G","player_id":"P","team":"KC",
             "source_url":"https://example.org","confirmed_utc":"2026-11-15T16:00:00Z"}]}
        good,bad=verify_payload(payload,now)
        self.assertEqual(good[0]["captured_utc"],now.isoformat())
    def test_changed_rule_hash_blocked(self):
        market={"ticker":"T","event_ticker":"E","title":"QB passing yards",
                "strike_type":"greater","floor_strike":225}
        review={"ticker":"T","event_ticker":"E","rules_verified":"true",
                "rules_sha256":"0"*64,"strike_type":"greater","floor_strike":"225",
                "source_game_reference":"NFL G"}
        self.assertEqual(audit(review,market)["status"],"BLOCKED")
    def test_matching_fingerprint(self):
        market={"ticker":"T","event_ticker":"E","title":"QB passing yards",
                "strike_type":"greater","floor_strike":225}
        review={"ticker":"T","event_ticker":"E","rules_verified":"true",
                "rules_sha256":fingerprint(market),"strike_type":"greater",
                "floor_strike":"225","source_game_reference":"NFL G"}
        self.assertEqual(audit(review,market)["status"],"RULE_FINGERPRINT_MATCH")
if __name__=="__main__":unittest.main()
