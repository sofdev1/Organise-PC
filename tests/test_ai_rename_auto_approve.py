import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from config import settings
from core import pipeline
from utils import ai_namer


class AutoApproveAiRenameTest(unittest.TestCase):
    def test_auto_approve_skips_prompt(self):
        settings.AI_RENAME_AUTO_APPROVE = True

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file_path = Path(tmp.name)

        try:
            with patch.object(pipeline, "sorter") as mock_sorter, \
                 patch.object(pipeline.ai_namer, "suggest_name", return_value="quarterly_sales"), \
                 patch.object(pipeline.renamer, "rename_file", return_value=file_path) as mock_rename, \
                 patch.object(pipeline.approval_ui, "confirm_rename") as mock_confirm:
                mock_sorter.sort_file.return_value = file_path
                mock_sorter._is_excluded.return_value = False

                pipeline.process_downloads_file(file_path)

                mock_confirm.assert_not_called()
                mock_rename.assert_called_once_with(file_path, override_stem="quarterly_sales")
        finally:
            file_path.unlink(missing_ok=True)

    def test_quota_pause_resumes_after_retry_window(self):
        ai_namer._AI_PAUSED_UNTIL = time.time() + 60
        self.assertTrue(ai_namer._is_ai_paused())

        ai_namer._AI_PAUSED_UNTIL = time.time() - 1
        self.assertFalse(ai_namer._is_ai_paused())

        ai_namer._record_quota_pause("429 RESOURCE_EXHAUSTED ... retryDelay '37s'")
        self.assertTrue(ai_namer._AI_PAUSED_UNTIL > time.time())

        future_time = time.time() + 10
        ai_namer._AI_PAUSED_UNTIL = future_time
        self.assertTrue(ai_namer._is_ai_paused())

    def test_media_files_are_renamed(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            file_path = Path(tmp.name)

        try:
            with patch.object(pipeline, "screenshots") as mock_screenshots, \
                 patch.object(pipeline, "converter") as mock_converter, \
                 patch.object(pipeline, "duplicates") as mock_duplicates, \
                 patch.object(pipeline.renamer, "rename_file", return_value=file_path) as mock_rename:
                mock_screenshots.is_screenshot.return_value = False
                mock_duplicates.check_and_flag_duplicate.return_value = False

                pipeline.process_media_file(file_path)

                mock_rename.assert_called_once_with(file_path)
        finally:
            file_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
