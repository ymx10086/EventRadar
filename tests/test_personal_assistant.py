import tempfile
import unittest
from pathlib import Path

from utils import personal_assistant


class PersonalAssistantTest(unittest.TestCase):
    def test_profile_saves_extended_preferences_and_normalizes_lists(self):
        original_dir = personal_assistant.DATA_DIR
        original_profile = personal_assistant.PROFILE_FILE
        original_settings = personal_assistant.SETTINGS_FILE
        original_sources = personal_assistant.LINK_SOURCES_FILE
        with tempfile.TemporaryDirectory() as tmp:
            personal_assistant.DATA_DIR = Path(tmp)
            personal_assistant.PROFILE_FILE = Path(tmp) / "profile.json"
            personal_assistant.SETTINGS_FILE = Path(tmp) / "settings.json"
            personal_assistant.LINK_SOURCES_FILE = Path(tmp) / "link_sources.json"
            try:
                saved = personal_assistant.save_profile({
                    "display_name": "明心",
                    "identity": "学生",
                    "organization": "北京大学",
                    "goals": "找创业比赛和 AI 讲座",
                    "preferred_cities": "北京，上海\n线上",
                    "preferred_formats": ["线下", "线上", "线下"],
                    "preferred_event_types": ["讲座", "路演"],
                    "language_preferences": ["中文", "English"],
                    "availability": ["周末下午"],
                    "recommendation_focus": ["相关度", "报名截止"],
                    "avoid_topics": "纯广告、无时间",
                    "unknown": "ignored",
                })

                self.assertEqual(saved["display_name"], "明心")
                self.assertEqual(saved["organization"], "北京大学")
                self.assertEqual(saved["preferred_cities"], ["北京", "上海", "线上"])
                self.assertEqual(saved["preferred_formats"], ["线下", "线上"])
                self.assertEqual(saved["avoid_topics"], ["纯广告", "无时间"])
                self.assertNotIn("unknown", saved)
            finally:
                personal_assistant.DATA_DIR = original_dir
                personal_assistant.PROFILE_FILE = original_profile
                personal_assistant.SETTINGS_FILE = original_settings
                personal_assistant.LINK_SOURCES_FILE = original_sources

    def test_grade_event_uses_city_format_and_event_type_preferences(self):
        profile = {
            **personal_assistant.DEFAULT_PROFILE,
            "interests": [],
            "priority_keywords": [],
            "preferred_cities": ["北京"],
            "preferred_formats": ["线下"],
            "preferred_event_types": ["路演"],
            "recommendation_focus": ["地点明确"],
            "avoid_topics": [],
        }

        grade = personal_assistant.grade_event({
            "title": "AI 创业路演",
            "description": "线下 Demo Day",
            "location": "北京 中关村路演厅",
            "city": "北京",
            "confidence": 0.7,
        }, profile)

        self.assertIn(grade["level"], {"S", "A"})
        self.assertIn("匹配偏好城市", grade["reason"])
        self.assertIn("匹配参与形式", grade["reason"])
        self.assertIn("匹配活动类型", grade["reason"])


if __name__ == "__main__":
    unittest.main()
