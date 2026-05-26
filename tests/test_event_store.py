import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from utils import event_store


class EventStoreTest(unittest.TestCase):
    def test_save_events_preserves_existing_image_paths_when_new_payload_is_empty(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([{
                    "id": "event-1",
                    "title": "测试活动",
                    "start_time": "2026年5月20日",
                    "image_paths": ["/tmp/poster.jpg"],
                }])
                event_store.save_events([{
                    "id": "event-1",
                    "title": "测试活动更新",
                    "start_time": "2026年5月20日",
                    "image_paths": [],
                }])

                event = event_store.get_event("event-1")

                self.assertEqual(event["image_paths"], ["/tmp/poster.jpg"])
                self.assertEqual(event["title"], "测试活动更新")
            finally:
                event_store.DB_PATH = original_db

    def test_save_events_reuses_existing_event_for_repeat_import(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                source_url = "https://mp.weixin.qq.com/s/repeat"
                event_store.save_events([{
                    "id": "first-id",
                    "title": "文科生黑客松来啦",
                    "source_article_url": source_url,
                    "start_time": "2026-05-30",
                    "calendar_time": "2026-05-30",
                    "location": "北京",
                    "confidence": 0.6,
                    "extraction_method": "minimax",
                }])
                event_store.save_events([{
                    "id": "second-id",
                    "title": "文科生黑客松「词元工坊」",
                    "source_article_url": source_url,
                    "start_time": "2026-05-30T00:00:00+08:00",
                    "calendar_time": "2026-05-30T00:00:00+08:00",
                    "location": "北京",
                    "confidence": 0.9,
                    "extraction_method": "minimax",
                }])

                events = event_store.list_events(include_ignored=True, limit=10)

                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["id"], "first-id")
                self.assertEqual(events[0]["title"], "文科生黑客松「词元工坊」")
            finally:
                event_store.DB_PATH = original_db

    def test_save_events_updates_same_day_event_from_different_daily_articles(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([{
                    "id": "first-daily-post",
                    "title": "AI 创业营 Demo Day",
                    "source_article_url": "https://mp.weixin.qq.com/s/day-one",
                    "source_name": "创业公众号A",
                    "start_time": "2026-06-18 19:00",
                    "calendar_time": "2026-06-18 19:00",
                    "location": "中关村",
                    "confidence": 0.7,
                    "extraction_method": "minimax",
                }])
                event_store.save_events([{
                    "id": "second-daily-post",
                    "title": "AI创业营DemoDay",
                    "source_article_url": "https://mp.weixin.qq.com/s/day-two",
                    "source_name": "创业公众号B",
                    "start_time": "2026-06-18 19:00",
                    "calendar_time": "2026-06-18 19:00",
                    "location": "中关村路演厅",
                    "confidence": 0.95,
                    "description": "更新后的更完整活动说明",
                    "extraction_method": "minimax",
                }])

                events = event_store.list_events(start="2026-06-18", end="2026-06-18", include_ignored=True, limit=10)

                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["id"], "first-daily-post")
                self.assertEqual(events[0]["title"], "AI创业营DemoDay")
                self.assertEqual(events[0]["description"], "更新后的更完整活动说明")
            finally:
                event_store.DB_PATH = original_db

    def test_list_events_dedupes_existing_duplicate_rows(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                source_url = "https://mp.weixin.qq.com/s/repeat-list"
                event_store.save_events([
                    {
                        "id": "older",
                        "title": "头号Builder全球挑战赛·北京站",
                        "source_article_url": source_url,
                        "start_time": "2026-05-23",
                        "calendar_time": "2026-05-23",
                        "location": "北京",
                        "confidence": 0.5,
                    },
                    {
                        "id": "better",
                        "title": "头号Builder全球挑战赛·北京站（stop1·北京站）",
                        "source_article_url": source_url,
                        "start_time": "2026-05-23T00:00:00+08:00",
                        "calendar_time": "2026-05-23T00:00:00+08:00",
                        "location": "北京",
                        "confidence": 0.9,
                    },
                ])
                conn = event_store._conn()
                try:
                    conn.execute(
                        "UPDATE events SET raw_json='{}' WHERE id=?",
                        ("older",),
                    )
                    conn.commit()
                finally:
                    conn.close()

                events = event_store.list_events(include_ignored=True, limit=10)

                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["title"], "头号Builder全球挑战赛·北京站（stop1·北京站）")
            finally:
                event_store.DB_PATH = original_db

    def test_list_events_filters_by_keyword_account_and_category(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([
                    {
                        "id": "event-ai",
                        "title": "AI 创业论坛",
                        "account": "北大创新创业",
                        "start_time": "2026年5月20日",
                        "location": "二教",
                        "category": "forum",
                    },
                    {
                        "id": "event-art",
                        "title": "艺术展览",
                        "account": "校园文化",
                        "start_time": "2026年5月21日",
                        "category": "exhibition",
                    },
                ])

                events = event_store.list_events(
                    start="2026-05-01",
                    end="2026-05-31",
                    account="北大创新创业",
                    category="forum",
                    q="AI",
                )
                summary = event_store.summarize_events(events)

                self.assertEqual([event["id"] for event in events], ["event-ai"])
                self.assertEqual(summary["accounts"], ["北大创新创业"])
                self.assertEqual(summary["category_counts"], {"forum": 1})
            finally:
                event_store.DB_PATH = original_db

    def test_list_events_filters_by_calendar_time(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([{
                    "id": "event-signup",
                    "title": "报名在前的活动",
                    "start_time": "2026年5月25日",
                    "signup_start_time": "2026年5月18日",
                    "calendar_time": "2026年5月18日",
                    "calendar_time_label": "报名开始",
                }])

                events = event_store.list_events(start="2026-05-18", end="2026-05-18")

                self.assertEqual([event["id"] for event in events], ["event-signup"])
                self.assertEqual(events[0]["calendar_time"], "2026年5月18日")
            finally:
                event_store.DB_PATH = original_db

    def test_list_events_filters_missing_year_calendar_time(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([{
                    "id": "event-missing-year",
                    "title": "无年份活动",
                    "start_time": "5月8日",
                    "calendar_time": "5月8日",
                }])
                conn = event_store._conn()
                try:
                    conn.execute(
                        "UPDATE events SET calendar_time=?, start_time=? WHERE id=?",
                        ("5月8日", "5月8日", "event-missing-year"),
                    )
                    conn.commit()
                finally:
                    conn.close()

                events = event_store.list_events(start="2026-05-08", end="2026-05-08")

                self.assertEqual([event["id"] for event in events], ["event-missing-year"])
            finally:
                event_store.DB_PATH = original_db

    def test_list_events_ignores_invalid_numeric_date(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([{
                    "id": "event-bad-date",
                    "title": "坏日期活动",
                    "start_time": "27-87",
                    "calendar_time": "27-87",
                }])

                events = event_store.list_events(start="2026-01-01", end="2026-12-31", include_ignored=True)

                self.assertEqual(events, [])
            finally:
                event_store.DB_PATH = original_db

    def test_list_events_applies_limit_after_date_filtering(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([
                    {
                        "id": "event-undated",
                        "title": "无日期活动",
                        "start_time": "",
                        "calendar_time": "",
                    },
                    {
                        "id": "event-match",
                        "title": "目标日期活动",
                        "start_time": "2026年5月23日",
                        "calendar_time": "2026年5月23日",
                    },
                ])

                events = event_store.list_events(
                    start="2026-05-23",
                    end="2026-05-23",
                    include_ignored=True,
                    limit=1,
                )

                self.assertEqual([event["id"] for event in events], ["event-match"])
            finally:
                event_store.DB_PATH = original_db

    def test_list_events_filters_by_favorite_flag(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([
                    {
                        "id": "fav-event",
                        "title": "收藏活动",
                        "start_time": "2026年5月20日",
                        "is_favorite": True,
                    },
                    {
                        "id": "plain-event",
                        "title": "普通活动",
                        "start_time": "2026年5月21日",
                    },
                ])

                favorite_events = event_store.list_events(favorite=True)
                unfavorite_events = event_store.list_events(favorite=False)

                self.assertEqual([event["id"] for event in favorite_events], ["fav-event"])
                self.assertEqual([event["id"] for event in unfavorite_events], ["plain-event"])
            finally:
                event_store.DB_PATH = original_db

    def test_date_range_handles_timezone_datetime_without_day_shift(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([{
                    "id": "event-timezone",
                    "title": "带时区时间活动",
                    "start_time": "2026-05-23T13:30:00+08:00",
                    "calendar_time": "2026-05-23T13:30:00+08:00",
                }])

                events_on_23 = event_store.list_events(start="2026-05-23", end="2026-05-23", include_ignored=True)
                events_on_14 = event_store.list_events(start="2026-05-14", end="2026-05-14", include_ignored=True)

                self.assertEqual([event["id"] for event in events_on_23], ["event-timezone"])
                self.assertEqual(events_on_14, [])
            finally:
                event_store.DB_PATH = original_db

    def test_refresh_calendar_times_fixes_eligibility_date(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                event_store.save_events([{
                    "id": "english-deadline",
                    "title": "UK-CICSIC 2026",
                    "start_time": "March 1, 1991 24:00",
                    "calendar_time": "March 1, 1991 24:00",
                    "calendar_time_label": "活动开始",
                    "signup_deadline": "June 5, 2026, 24:00 (Beijing Time).",
                    "description": "Participants must be aged 35 or under (born after March 1, 1991).",
                }])
                conn = event_store._conn()
                try:
                    conn.execute(
                        "UPDATE events SET calendar_time=?, calendar_time_label=? WHERE id=?",
                        ("March 1, 1991 24:00", "活动开始", "english-deadline"),
                    )
                    conn.commit()
                finally:
                    conn.close()

                result = event_store.refresh_calendar_times()
                event = event_store.get_event("english-deadline")

                self.assertEqual(result["updated_count"], 1)
                self.assertEqual(event["calendar_time"], "2026-06-05")
                self.assertEqual(event["calendar_time_label"], "报名截止")
            finally:
                event_store.DB_PATH = original_db

    def test_cleanup_deletes_only_old_unfavorited_events(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                today = datetime.now().date()
                old_date = (today - timedelta(days=30)).isoformat()
                recent_date = today.isoformat()
                event_store.save_events([
                    {
                        "id": "old-unfavorite",
                        "title": "旧未收藏",
                        "calendar_time": old_date,
                        "start_time": old_date,
                    },
                    {
                        "id": "old-favorite",
                        "title": "旧收藏",
                        "calendar_time": old_date,
                        "start_time": old_date,
                        "is_favorite": True,
                    },
                    {
                        "id": "recent-unfavorite",
                        "title": "新未收藏",
                        "calendar_time": recent_date,
                        "start_time": recent_date,
                    },
                ])

                result = event_store.delete_old_unfavorited_events(retention_days=15)
                events = event_store.list_events(
                    start=(today - timedelta(days=40)).isoformat(),
                    end=(today + timedelta(days=1)).isoformat(),
                    include_ignored=True,
                    limit=10,
                )

                self.assertEqual(result["deleted_ids"], ["old-unfavorite"])
                self.assertEqual(
                    sorted(event["id"] for event in events),
                    ["old-favorite", "recent-unfavorite"],
                )
                self.assertTrue(next(event for event in events if event["id"] == "old-favorite")["is_favorite"])
            finally:
                event_store.DB_PATH = original_db

    def test_cleanup_deletes_unreferenced_files_for_old_unfavorite(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                image_path = Path(tmp) / "old" / "poster.jpg"
                image_path.parent.mkdir(parents=True)
                image_path.write_text("poster", encoding="utf-8")
                old_date = (datetime.now().date() - timedelta(days=30)).isoformat()
                event_store.save_events([{
                    "id": "old-unfavorite-file",
                    "title": "旧未收藏带图片",
                    "calendar_time": old_date,
                    "start_time": old_date,
                    "image_paths": [str(image_path)],
                }])

                result = event_store.delete_old_unfavorited_events(retention_days=15)

                self.assertEqual(result["deleted_ids"], ["old-unfavorite-file"])
                self.assertEqual(result["deleted_file_count"], 1)
                self.assertFalse(image_path.exists())
            finally:
                event_store.DB_PATH = original_db

    def test_cleanup_keeps_files_still_referenced_by_favorite(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                shared_image = Path(tmp) / "shared" / "poster.jpg"
                shared_image.parent.mkdir(parents=True)
                shared_image.write_text("poster", encoding="utf-8")
                old_date = (datetime.now().date() - timedelta(days=30)).isoformat()
                event_store.save_events([
                    {
                        "id": "old-unfavorite-shared",
                        "title": "旧未收藏共享图片",
                        "calendar_time": old_date,
                        "start_time": old_date,
                        "image_paths": [str(shared_image)],
                    },
                    {
                        "id": "old-favorite-shared",
                        "title": "旧收藏共享图片",
                        "calendar_time": old_date,
                        "start_time": old_date,
                        "is_favorite": True,
                        "image_paths": [str(shared_image)],
                    },
                ])

                result = event_store.delete_old_unfavorited_events(retention_days=15)

                self.assertEqual(result["deleted_ids"], ["old-unfavorite-shared"])
                self.assertEqual(result["deleted_file_count"], 0)
                self.assertTrue(shared_image.exists())
            finally:
                event_store.DB_PATH = original_db

    def test_cleanup_duplicate_events_keeps_one_and_preserves_favorite(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                source_url = "https://mp.weixin.qq.com/s/duplicate"
                event_store.save_events([
                    {
                        "id": "strong",
                        "title": "UK-CICSIC 2026 国际创新创业大赛",
                        "source_article_title": "UK-CICSIC 2026 ——Now Open for Registration",
                        "source_article_url": source_url,
                        "start_time": "2026-06-24",
                        "signup_start_time": "2026-05-11",
                        "extraction_method": "minimax",
                    },
                    {
                        "id": "fallback-duplicate",
                        "title": "UK-CICSIC 2026 ——Now Open for Registration",
                        "source_article_title": "UK-CICSIC 2026 ——Now Open for Registration",
                        "source_article_url": source_url,
                        "start_time": "March 1, 1991 24:00",
                        "signup_deadline": "June 5, 2026, 24:00 (Beijing Time).",
                        "extraction_method": "fallback",
                    },
                    {
                        "id": "fallback-favorite",
                        "title": "UK-CICSIC 2026 ——Now Open for Registration",
                        "source_article_title": "UK-CICSIC 2026 ——Now Open for Registration",
                        "source_article_url": source_url,
                        "start_time": "2026-06-24",
                        "is_favorite": True,
                        "extraction_method": "fallback",
                    },
                ])

                result = event_store.cleanup_duplicate_events()
                events = event_store.list_events(include_ignored=True, limit=10)

                self.assertEqual(result["deleted_ids"], [])
                self.assertEqual(
                    [event["id"] for event in events],
                    ["strong"],
                )
                self.assertTrue(events[0]["is_favorite"])
            finally:
                event_store.DB_PATH = original_db

    def test_delete_event_removes_row_and_only_orphaned_files(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                own_image = Path(tmp) / "owned" / "poster.jpg"
                shared_image = Path(tmp) / "shared" / "poster.jpg"
                own_image.parent.mkdir(parents=True)
                shared_image.parent.mkdir(parents=True)
                own_image.write_text("own", encoding="utf-8")
                shared_image.write_text("shared", encoding="utf-8")
                event_store.save_events([
                    {
                        "id": "delete-me",
                        "title": "要删除的活动",
                        "calendar_time": "2026-05-20",
                        "start_time": "2026-05-20",
                        "image_paths": [str(own_image), str(shared_image)],
                    },
                    {
                        "id": "keep-me",
                        "title": "保留的活动",
                        "calendar_time": "2026-05-21",
                        "start_time": "2026-05-21",
                        "image_paths": [str(shared_image)],
                    },
                ])

                result = event_store.delete_event("delete-me")
                events = event_store.list_events(include_ignored=True, limit=10)

                self.assertTrue(result["deleted"])
                self.assertEqual(result["deleted_id"], "delete-me")
                self.assertEqual([event["id"] for event in events], ["keep-me"])
                self.assertFalse(own_image.exists())
                self.assertTrue(shared_image.exists())
            finally:
                event_store.DB_PATH = original_db

    def test_delete_events_removes_multiple_rows_and_orphaned_files(self):
        original_db = event_store.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            event_store.DB_PATH = Path(tmp) / "events.db"
            try:
                event_store.init_db()
                first_image = Path(tmp) / "owned" / "first.jpg"
                second_image = Path(tmp) / "owned" / "second.jpg"
                shared_image = Path(tmp) / "shared" / "poster.jpg"
                for path, text in [
                    (first_image, "first"),
                    (second_image, "second"),
                    (shared_image, "shared"),
                ]:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
                event_store.save_events([
                    {
                        "id": "delete-one",
                        "title": "删除一",
                        "calendar_time": "2026-05-20",
                        "start_time": "2026-05-20",
                        "image_paths": [str(first_image), str(shared_image)],
                    },
                    {
                        "id": "delete-two",
                        "title": "删除二",
                        "calendar_time": "2026-05-21",
                        "start_time": "2026-05-21",
                        "image_paths": [str(second_image)],
                    },
                    {
                        "id": "keep-me",
                        "title": "保留",
                        "calendar_time": "2026-05-22",
                        "start_time": "2026-05-22",
                        "image_paths": [str(shared_image)],
                    },
                ])

                result = event_store.delete_events(["delete-one", "delete-two", "missing"])
                events = event_store.list_events(include_ignored=True, limit=10)

                self.assertTrue(result["deleted"])
                self.assertEqual(set(result["deleted_ids"]), {"delete-one", "delete-two"})
                self.assertEqual(result["missing_ids"], ["missing"])
                self.assertEqual([event["id"] for event in events], ["keep-me"])
                self.assertFalse(first_image.exists())
                self.assertFalse(second_image.exists())
                self.assertTrue(shared_image.exists())
            finally:
                event_store.DB_PATH = original_db


if __name__ == "__main__":
    unittest.main()
