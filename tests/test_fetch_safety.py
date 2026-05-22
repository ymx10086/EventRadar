import os
import logging
import unittest
from unittest.mock import patch

from utils.fetch_safety import FetchSafetyConfig, FetchSafetyController, load_fetch_safety_config


class FetchSafetyTest(unittest.TestCase):
    def setUp(self):
        self.original = {
            "WECHAT_FETCH_CONCURRENCY": os.environ.get("WECHAT_FETCH_CONCURRENCY"),
            "WECHAT_FETCH_DELAY_MIN": os.environ.get("WECHAT_FETCH_DELAY_MIN"),
            "WECHAT_FETCH_DELAY_MAX": os.environ.get("WECHAT_FETCH_DELAY_MAX"),
            "WECHAT_ACCOUNT_DELAY": os.environ.get("WECHAT_ACCOUNT_DELAY"),
            "WECHAT_MAX_ARTICLES_PER_ACCOUNT": os.environ.get("WECHAT_MAX_ARTICLES_PER_ACCOUNT"),
            "WECHAT_VERIFICATION_PAUSE_MINUTES": os.environ.get("WECHAT_VERIFICATION_PAUSE_MINUTES"),
            "WECHAT_VERIFICATION_STOP_THRESHOLD": os.environ.get("WECHAT_VERIFICATION_STOP_THRESHOLD"),
            "WECHAT_PROXY_REQUIRED": os.environ.get("WECHAT_PROXY_REQUIRED"),
        }

    def tearDown(self):
        for key, value in self.original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_loads_env_defaults_and_normalizes_delay(self):
        os.environ["WECHAT_FETCH_CONCURRENCY"] = "3"
        os.environ["WECHAT_FETCH_DELAY_MIN"] = "12"
        os.environ["WECHAT_FETCH_DELAY_MAX"] = "4"
        os.environ["WECHAT_ACCOUNT_DELAY"] = "15"
        os.environ["WECHAT_PROXY_REQUIRED"] = "true"

        config = load_fetch_safety_config({})

        self.assertEqual(config.article_concurrency, 3)
        self.assertEqual(config.article_delay_min, 12)
        self.assertEqual(config.article_delay_max, 12)
        self.assertEqual(config.account_delay, 15)
        self.assertTrue(config.proxy_required)

    def test_settings_override_env_and_are_clamped(self):
        os.environ["WECHAT_FETCH_CONCURRENCY"] = "1"

        config = load_fetch_safety_config({
            "wechat_fetch_concurrency": 99,
            "wechat_max_articles_per_account": 999,
            "wechat_verification_stop_threshold": 0,
        })

        self.assertEqual(config.article_concurrency, 5)
        self.assertEqual(config.max_articles_per_account, 100)
        self.assertEqual(config.verification_stop_threshold, 1)

    def test_verification_threshold_pauses_fetching(self):
        controller = FetchSafetyController()
        config = FetchSafetyConfig(verification_stop_threshold=2, verification_pause_minutes=30)

        logging.getLogger("utils.fetch_safety").disabled = True
        try:
            with patch("utils.fetch_safety.load_fetch_safety_config", return_value=config):
                controller.record_verification("test")
            self.assertFalse(controller.is_paused())
            with patch("utils.fetch_safety.load_fetch_safety_config", return_value=config):
                controller.record_verification("test")
        finally:
            logging.getLogger("utils.fetch_safety").disabled = False

        self.assertTrue(controller.is_paused())
        self.assertGreater(controller.cooldown_remaining_seconds(), 0)
        controller.clear_pause()
        self.assertFalse(controller.is_paused())

    def test_default_threshold_pauses_on_first_verification(self):
        controller = FetchSafetyController()

        logging.getLogger("utils.fetch_safety").disabled = True
        try:
            controller.record_verification("test")
        finally:
            logging.getLogger("utils.fetch_safety").disabled = False

        self.assertTrue(controller.is_paused())

    def test_empty_settings_use_env_values(self):
        os.environ["WECHAT_FETCH_CONCURRENCY"] = "2"
        os.environ["WECHAT_MAX_ARTICLES_PER_ACCOUNT"] = "12"

        config = load_fetch_safety_config({})

        self.assertEqual(config.article_concurrency, 2)
        self.assertEqual(config.max_articles_per_account, 12)


if __name__ == "__main__":
    unittest.main()
