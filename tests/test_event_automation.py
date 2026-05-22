import os
import unittest

from utils.event_automation import _format_upcoming_events, should_notify_automation


class EventAutomationTest(unittest.TestCase):
    def setUp(self):
        self.original = {
            "EVENT_AUTOMATION_WEBHOOK_ENABLED": os.environ.get("EVENT_AUTOMATION_WEBHOOK_ENABLED"),
            "EVENT_AUTOMATION_NOTIFY_MANUAL": os.environ.get("EVENT_AUTOMATION_NOTIFY_MANUAL"),
        }

    def tearDown(self):
        for key, value in self.original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_should_notify_scheduled_by_default(self):
        os.environ.pop("EVENT_AUTOMATION_WEBHOOK_ENABLED", None)
        os.environ.pop("EVENT_AUTOMATION_NOTIFY_MANUAL", None)

        self.assertTrue(should_notify_automation("scheduled"))
        self.assertFalse(should_notify_automation("manual"))

    def test_should_notify_manual_when_enabled(self):
        os.environ["EVENT_AUTOMATION_NOTIFY_MANUAL"] = "true"

        self.assertTrue(should_notify_automation("manual"))

    def test_should_not_notify_when_disabled(self):
        os.environ["EVENT_AUTOMATION_WEBHOOK_ENABLED"] = "false"
        os.environ["EVENT_AUTOMATION_NOTIFY_MANUAL"] = "true"

        self.assertFalse(should_notify_automation("scheduled"))
        self.assertFalse(should_notify_automation("manual"))

    def test_format_upcoming_events_limits_output(self):
        events = [
            {
                "title": "AI 创业论坛",
                "start_time": "2026年5月22日",
                "location": "二教",
                "account": "北大创新创业",
            },
            {
                "title": "路演",
                "start_time": "2026年5月23日",
                "location": "",
                "account": "测试号",
            },
        ]

        text = _format_upcoming_events(events, max_items=1)

        self.assertIn("AI 创业论坛", text)
        self.assertIn("还有 1 个活动", text)

    def test_automation_config_reads_lookback_days(self):
        from utils.event_automation import EventAutomation

        automation = EventAutomation()
        automation.configure({
            "daily_fetch_enabled": True,
            "daily_fetch_time": "08:15",
            "daily_fetch_lookback_days": 5,
        })

        self.assertTrue(automation.enabled)
        self.assertEqual(automation.schedule_time, "08:15")
        self.assertEqual(automation.status()["lookback_days"], 5)

    def test_progress_state_is_reported_in_status(self):
        from utils.event_automation import EventAutomation

        automation = EventAutomation()
        automation._set_progress("running", "poll", "正在轮询", 25)
        status = automation.status()

        self.assertTrue(status["progress"]["active"])
        self.assertEqual(status["progress"]["stage"], "poll")
        self.assertEqual(status["progress"]["percent"], 25)
        self.assertEqual(status["progress"]["logs"][-1]["message"], "正在轮询")


if __name__ == "__main__":
    unittest.main()
