import json
import os
import tempfile
import unittest
from pathlib import Path


class EventExtractorTest(unittest.TestCase):
    def test_extract_exports_json_csv_ics_without_minimax_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            os.environ["MINIMAX_API_KEY"] = ""
            os.environ["EVENTS_OUTPUT_DIR"] = str(tmp_path / "events")

            import utils.event_extractor as extractor

            extractor.EVENTS_DIR = Path(os.environ["EVENTS_OUTPUT_DIR"])

            archive_path = tmp_path / "articles.json"
            image_path = tmp_path / "poster.png"
            image_path.write_bytes(b"fake")
            archive_path.write_text(json.dumps({
                "date": "2026-05-20",
                "accounts": [{
                    "nickname": "测试公众号",
                    "fakeid": "fakeid",
                    "articles": [{
                        "title": "活动预告 | AI 创业论坛报名开启",
                        "account_name": "测试公众号",
                        "link": "https://mp.weixin.qq.com/s/test",
                        "publish_time_iso": "2026-05-19T10:00:00+08:00",
                        "plain_content": (
                            "活动时间：2026年5月20日 19:00-21:00\n"
                            "活动地点：北京大学二教 509\n"
                            "主办方：创新创业学院\n"
                            "报名链接：https://example.com/signup\n"
                        ),
                        "images": [{
                            "path": str(image_path),
                            "downloaded": True,
                            "ocr_text": "扫码报名 AI 创业论坛 2026年5月20日 19:00",
                        }],
                    }],
                }],
            }, ensure_ascii=False), encoding="utf-8")

            payload = extractor.extract_events_from_archive(
                str(archive_path),
                extractor.ExtractConfig(use_llm=True, use_vision=False),
            )

            self.assertEqual(payload["article_count"], 1)
            self.assertEqual(payload["event_count"], 1)
            outputs = payload["outputs"]
            self.assertTrue(Path(outputs["events_json"]).exists())
            self.assertTrue(Path(outputs["events_csv"]).exists())
            self.assertTrue(Path(outputs["calendar_ics"]).exists())
            self.assertIn("AI 创业论坛", payload["events"][0]["title"])
            self.assertIn("北京大学", payload["events"][0]["location"])
            ics = Path(outputs["calendar_ics"]).read_text(encoding="utf-8")
            self.assertIn("DTSTART:20260520T110000Z", ics)

            all_day_ics = extractor.build_events_ics([{
                "id": "all-day",
                "title": "全天活动",
                "start_time": "2026年5月20日",
            }])
            self.assertIn("DTSTART;VALUE=DATE:20260520", all_day_ics)
            self.assertIn("DTEND;VALUE=DATE:20260521", all_day_ics)

    def test_image_ocr_can_select_image_only_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            os.environ["MINIMAX_API_KEY"] = ""
            os.environ["EVENTS_OUTPUT_DIR"] = str(tmp_path / "events")

            import utils.event_extractor as extractor

            extractor.EVENTS_DIR = Path(os.environ["EVENTS_OUTPUT_DIR"])

            archive_path = tmp_path / "articles.json"
            image_path = tmp_path / "poster.png"
            image_path.write_bytes(b"fake")
            archive_path.write_text(json.dumps({
                "date": "2026-05-20",
                "accounts": [{
                    "nickname": "测试公众号",
                    "articles": [{
                        "title": "本周通知",
                        "link": "https://mp.weixin.qq.com/s/image-only",
                        "publish_time_iso": "2026-05-19T10:00:00+08:00",
                        "plain_content": "[纯图片文章，共 1 张图片]",
                        "images": [{
                            "path": str(image_path),
                            "downloaded": True,
                            "ocr_text": (
                                "活动报名开始：2026年5月18日\n"
                                "活动时间：2026年5月25日 14:00\n"
                                "活动地点：创新中心\n"
                            ),
                        }],
                    }],
                }],
            }, ensure_ascii=False), encoding="utf-8")

            payload = extractor.extract_events_from_archive(
                str(archive_path),
                extractor.ExtractConfig(use_llm=False, use_vision=False),
            )

            self.assertEqual(payload["selected_article_count"], 1)
            self.assertEqual(payload["event_count"], 1)
            event = payload["events"][0]
            self.assertEqual(event["calendar_time"], "2026年5月18日")
            self.assertEqual(event["calendar_time_label"], "报名开始")

    def test_anthropic_conversion_keeps_image_blocks(self):
        import utils.event_extractor as extractor

        captured = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"content": [{"type": "text", "text": "ok"}]}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, json, headers):
                captured["payload"] = json
                return FakeResponse()

        original_client = extractor.httpx.Client
        extractor.httpx.Client = FakeClient
        try:
            result = extractor._call_minimax_anthropic(
                [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "识别图片"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
                    ],
                }],
                "sk-cp-test",
                "model",
                0.1,
                100,
            )
        finally:
            extractor.httpx.Client = original_client

        self.assertEqual(result, "ok")
        content = captured["payload"]["messages"][0]["content"]
        self.assertEqual(content[1]["type"], "image")
        self.assertEqual(content[1]["source"]["media_type"], "image/png")
        self.assertEqual(content[1]["source"]["data"], "AAAA")

    def test_vision_refusal_is_not_saved_as_event(self):
        import utils.event_extractor as extractor

        raw = {
            "title": "文科生黑客松来啦",
            "start_time": "",
            "location": "请上传图片",
            "description": "很抱歉，我目前无法直接查看图片。请上传这张海报。",
        }

        self.assertFalse(extractor._is_valid_raw_event(raw))

    def test_hackathon_title_scores_image_only_article(self):
        import utils.event_extractor as extractor

        score, hits = extractor.score_activity_article({
            "title": "文科生黑客松来啦",
            "plain_content": "[纯图片文章，共 1 张图片]",
            "images": [{"path": "/tmp/poster.png", "downloaded": True}],
        })

        self.assertGreaterEqual(score, 4)
        self.assertIn("黑客松", hits)

    def test_ics_uses_earliest_key_time_before_activity_start(self):
        import utils.event_extractor as extractor

        ics = extractor.build_events_ics([{
            "id": "signup-first",
            "title": "报名优先活动",
            "start_time": "2026年5月25日 14:00",
            "signup_start_time": "2026年5月18日",
            "signup_deadline": "2026年5月22日",
        }])

        self.assertIn("DTSTART;VALUE=DATE:20260518", ics)
        self.assertIn("日历时间类型：报名开始", ics)

    def test_deadline_at_midnight_stays_on_original_deadline_date(self):
        import utils.event_extractor as extractor

        event = {
            "id": "deadline-midnight",
            "title": "截止日活动",
            "start_time": "2026-05-17",
            "signup_deadline": "2026-05-11T00:00:00+08:00",
            "evidence": "报名截止：2026年5月10日晚上24:00",
        }

        calendar_time, calendar_label = extractor.calendar_time_for_event(event)
        ics = extractor.build_events_ics([event])

        self.assertEqual(calendar_time, "2026-05-10")
        self.assertEqual(calendar_label, "报名截止")
        self.assertIn("DTSTART;VALUE=DATE:20260510", ics)
        self.assertIn("DTEND;VALUE=DATE:20260511", ics)

    def test_manual_text_extracts_dot_date_activity(self):
        import utils.event_extractor as extractor

        os.environ["MINIMAX_API_KEY"] = ""
        text = (
            "未来机域校园行·走进北大\n"
            "具身智能 & 灵巧操作专场\n"
            "时间：5.28（周四）13:30-17:00\n"
            "地点：北大英杰交流中心 阳光厅\n"
            "主题：解锁具身智能与灵巧操作新可能\n"
            "适合：机器人 / AI / 嵌入式 / 自动化方向的师生\n"
        )

        events = extractor.extract_event_candidates_from_text(
            text,
            title="未来机域校园行·走进北大",
            publish_time="2026-05-27T10:00:00+08:00",
            use_llm=False,
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertIn("未来机域", event["title"])
        self.assertIn("2026-05-28", event["calendar_time"])
        self.assertIn("13:30", event["calendar_time"])
        self.assertEqual(event["location"], "北大英杰交流中心 阳光厅")

    def test_ics_keeps_iso_time_with_timezone(self):
        import utils.event_extractor as extractor

        ics = extractor.build_events_ics([{
            "id": "iso-timezone",
            "title": "上海活动",
            "start_time": "2026-05-23T13:30:00+08:00",
            "end_time": "2026-05-23T21:00:00+08:00",
        }])

        self.assertIn("DTSTART:20260523T053000Z", ics)
        self.assertIn("DTEND:20260523T130000Z", ics)

    def test_eligibility_age_date_does_not_override_registration_deadline(self):
        import utils.event_extractor as extractor

        event = {
            "id": "english-deadline",
            "title": "UK-CICSIC 2026",
            "start_time": "March 1, 1991 24:00",
            "signup_deadline": "June 5, 2026, 24:00 (Beijing Time).",
            "description": "Participants must be aged 35 or under (born after March 1, 1991).",
        }

        calendar_time, calendar_label = extractor.calendar_time_for_event(event)

        self.assertEqual(calendar_time, "2026-06-05")
        self.assertEqual(calendar_label, "报名截止")

    def test_missing_year_date_uses_source_publish_year(self):
        import utils.event_extractor as extractor

        event = {
            "id": "missing-year",
            "title": "未名路演",
            "start_time": "5月8日下午",
            "source_publish_time": "2026-05-15T17:00:00+08:00",
        }

        calendar_time, calendar_label = extractor.calendar_time_for_event(event)

        self.assertEqual(calendar_time, "2026年5月8日下午")
        self.assertEqual(calendar_label, "活动开始")

    def test_invalid_numeric_date_does_not_crash_ics(self):
        import utils.event_extractor as extractor

        ics = extractor.build_events_ics([{
            "id": "bad-date",
            "title": "异常日期活动",
            "start_time": "27-87",
            "calendar_time": "27-87",
        }])

        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertNotIn("异常日期活动", ics)

    def test_context_supplements_missing_llm_fields(self):
        import utils.event_extractor as extractor

        compressed = {
            "title": "活动预告",
            "full_text": (
                "活动时间：2026年6月8日 14:00-16:00\n"
                "活动地点：北京 中关村创业大街路演厅\n"
                "主办方：未来产业研究院\n"
                "报名截止：2026年6月6日 24:00\n"
                "报名链接：https://example.com/register\n"
                "活动简介：面向 AI 创业团队的融资路演和导师交流活动。"
            ),
            "image_ocr": [{
                "text": "2026 AI 创业路演 北京 中关村创业大街 路演厅 扫码报名",
            }],
            "poster_vision": [],
        }

        events = extractor.supplement_events_from_context([{
            "title": "2026 AI 创业路演",
            "start_time": "",
            "location": "",
            "organizer": "",
            "signup_deadline": "",
            "signup_url": "",
            "description": "",
        }], compressed)

        event = events[0]
        self.assertIn("2026年6月8日", event["start_time"])
        self.assertIn("中关村创业大街", event["location"])
        self.assertEqual(event["city"], "北京")
        self.assertEqual(event["organizer"], "未来产业研究院")
        self.assertIn("2026年6月6日", event["signup_deadline"])
        self.assertEqual(event["signup_url"], "https://example.com/register")
        self.assertIn("融资路演", event["description"])

    def test_location_cleanup_removes_other_labeled_fields(self):
        import utils.event_extractor as extractor

        location = extractor.clean_location_value(
            "北京大学二教 509 主办方：创新创业学院 费用：免费 报名方式：扫码报名"
        )

        self.assertEqual(location, "北京大学二教 509")

    def test_location_cleanup_rejects_non_location_details(self):
        import utils.event_extractor as extractor

        location = extractor.clean_location_value("主办方：创新创业学院 费用：免费 报名方式：扫码报名")

        self.assertEqual(location, "")

    def test_fallback_location_stops_before_organizer_fee_and_signup(self):
        import utils.event_extractor as extractor

        events = extractor.fallback_extract({
            "title": "AI 创业论坛报名开启",
            "text": (
                "活动时间：2026年6月8日 14:00 "
                "活动地点：北京大学二教 509 主办方：创新创业学院 费用：免费 报名方式：扫码报名"
            ),
        })

        self.assertEqual(events[0]["location"], "北京大学二教 509")

    def test_normalize_event_sanitizes_llm_location(self):
        import utils.event_extractor as extractor

        event = extractor.normalize_event(
            {
                "title": "AI 创业论坛",
                "start_time": "2026年6月8日 14:00",
                "location": "北京大学二教 509 主办方：创新创业学院 费用：免费 报名方式：扫码报名",
            },
            {"link": "https://mp.weixin.qq.com/s/test"},
            "llm",
        )

        self.assertEqual(event["location"], "北京大学二教 509")


if __name__ == "__main__":
    unittest.main()
