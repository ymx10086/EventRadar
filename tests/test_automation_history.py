import tempfile
import unittest
from pathlib import Path

from utils import automation_history


class AutomationHistoryTest(unittest.TestCase):
    def test_append_and_list_runs_returns_newest_first(self):
        original_dir = automation_history.HISTORY_DIR
        original_file = automation_history.HISTORY_FILE
        with tempfile.TemporaryDirectory() as tmp:
            automation_history.HISTORY_DIR = Path(tmp)
            automation_history.HISTORY_FILE = Path(tmp) / "runs.jsonl"
            try:
                automation_history.append_run({"status": "success", "started_at": 1})
                automation_history.append_run({"status": "failed", "started_at": 2, "error": "boom"})

                runs = automation_history.list_runs(limit=2)

                self.assertEqual([run["started_at"] for run in runs], [2, 1])
                self.assertEqual(runs[0]["error"], "boom")
            finally:
                automation_history.HISTORY_DIR = original_dir
                automation_history.HISTORY_FILE = original_file


if __name__ == "__main__":
    unittest.main()
