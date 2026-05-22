import unittest
from unittest.mock import patch

from utils.account_discovery import score_candidate, subscribe_top_candidates


class AccountDiscoveryTest(unittest.TestCase):
    def test_score_prioritizes_relevant_unsubscribed_accounts(self):
        account = {
            "fakeid": "new",
            "nickname": "北大创新创业学院",
            "alias": "pku-innovation",
            "service_type": 1,
        }

        scored = score_candidate(account, "北大 创新创业", subscribed_fakeids=set())

        self.assertGreaterEqual(scored["score"], 70)
        self.assertIn("名称匹配：北大", scored["reasons"])

    def test_score_penalizes_existing_subscription(self):
        account = {
            "fakeid": "existing",
            "nickname": "北大创新创业学院",
            "alias": "pku-innovation",
        }

        new_score = score_candidate(account, "北大 创新创业", subscribed_fakeids=set())["score"]
        old_score = score_candidate(account, "北大 创新创业", subscribed_fakeids={"existing"})["score"]

        self.assertLess(old_score, new_score)

    def test_subscribe_top_candidates_skips_existing_items(self):
        payload = {
            "candidates": [
                {"fakeid": "old", "nickname": "已订阅", "subscribed": True},
                {"fakeid": "new-1", "nickname": "候选一", "subscribed": False},
                {"fakeid": "new-2", "nickname": "候选二", "subscribed": False},
            ]
        }

        with patch("utils.account_discovery.rss_store.add_subscription", return_value=True), \
             patch("utils.account_discovery.save_recommendations"):
            subscribed = subscribe_top_candidates(payload, 1)

        self.assertEqual([item["fakeid"] for item in subscribed], ["new-1"])
        self.assertTrue(payload["candidates"][1]["subscribed"])
        self.assertEqual(payload["subscribed_count"], 1)


if __name__ == "__main__":
    unittest.main()
