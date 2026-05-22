import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


class DailyArchiveTest(unittest.TestCase):
    def test_archive_writes_json_and_image_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            os.environ["RSS_DB_PATH"] = str(tmp_path / "rss.db")
            os.environ["DAILY_ARCHIVE_DIR"] = str(tmp_path / "archives")
            os.environ["DAILY_ARCHIVE_TIMEZONE"] = "Asia/Shanghai"

            from utils import rss_store
            import utils.daily_archive as daily_archive

            rss_store.DB_PATH = Path(os.environ["RSS_DB_PATH"])
            daily_archive.ARCHIVE_DIR = Path(os.environ["DAILY_ARCHIVE_DIR"])
            rss_store.init_db()

            rss_store.add_subscription(
                "fakeid_1",
                nickname="测试公众号",
                alias="test_alias",
                head_img="https://wx.qlogo.cn/mmhead/test",
            )

            publish_time = int(datetime(2026, 5, 20, 12, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp())
            proxied = (
                "http://localhost:5001/api/image?url="
                "https%3A%2F%2Fmmbiz.qpic.cn%2Fmmbiz_png%2Fabc%2F0%3Fwx_fmt%3Dpng"
            )
            rss_store.save_articles("fakeid_1", [{
                "aid": "aid_1",
                "title": "测试文章",
                "link": "https://mp.weixin.qq.com/s/test",
                "digest": "摘要",
                "cover": "https://mmbiz.qpic.cn/mmbiz_jpg/cover/0?wx_fmt=jpeg",
                "author": "作者",
                "content": f'<p>正文</p><img src="{proxied}">',
                "plain_content": "正文",
                "publish_time": publish_time,
            }])

            with patch("utils.daily_archive._download_url", return_value=(b"image-bytes", "image/png")):
                payload = daily_archive.archive_daily_articles("2026-05-20")

            archive_file = daily_archive.get_archive_file("2026-05-20")
            self.assertTrue(archive_file.exists())
            saved = json.loads(archive_file.read_text(encoding="utf-8"))

            self.assertEqual(payload["article_count"], 1)
            self.assertEqual(saved["account_count"], 1)
            article = saved["accounts"][0]["articles"][0]
            self.assertEqual(article["title"], "测试文章")
            self.assertEqual(len(article["images"]), 2)

            for image in article["images"]:
                self.assertTrue(image["downloaded"])
                self.assertTrue(image["path"])
                self.assertTrue(Path(image["path"]).exists())
                self.assertIn("relative_path", image)

            self.assertEqual(article["images"][1]["url"], "https://mmbiz.qpic.cn/mmbiz_png/abc/0?wx_fmt=png")

            payload_without_download = daily_archive.archive_daily_articles(
                "2026-05-20",
                download_images=False,
            )
            article_without_download = payload_without_download["accounts"][0]["articles"][0]

            self.assertEqual(payload_without_download["downloaded_image_count"], 2)
            for image in article_without_download["images"]:
                self.assertTrue(image["downloaded"])
                self.assertTrue(image["path"])

    def test_subscription_auto_fetch_toggle_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RSS_DB_PATH"] = str(Path(tmp) / "rss.db")

            from utils import rss_store

            rss_store.DB_PATH = Path(os.environ["RSS_DB_PATH"])
            rss_store.init_db()
            rss_store.add_subscription("fakeid_auto", nickname="自动号")
            rss_store.add_subscription("fakeid_manual", nickname="手动号")

            self.assertTrue(rss_store.update_subscription_auto_fetch("fakeid_manual", False))

            all_fakeids = set(rss_store.get_all_fakeids())
            auto_fakeids = set(rss_store.get_all_fakeids(auto_fetch_only=True))

            self.assertEqual(all_fakeids, {"fakeid_auto", "fakeid_manual"})
            self.assertEqual(auto_fakeids, {"fakeid_auto"})


if __name__ == "__main__":
    unittest.main()
