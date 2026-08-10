import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class ResumeMigrationTests(unittest.TestCase):
    def test_creates_missing_resume_with_current_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)

            main._ensure_resume(data_dir)

            resume_path = data_dir / "resume.txt"
            self.assertEqual(
                resume_path.read_text(encoding="utf-8"),
                main._RESUME_FALLBACK,
            )
            self.assertFalse(resume_path.with_suffix(".tmp").exists())

    def test_migrates_exact_legacy_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            resume_path = data_dir / "resume.txt"
            resume_path.write_text(main._LEGACY_RESUME_FALLBACK, encoding="utf-8")

            main._ensure_resume(data_dir)

            self.assertEqual(
                resume_path.read_text(encoding="utf-8"),
                main._RESUME_FALLBACK,
            )

    def test_keeps_already_updated_resume_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            resume_path = data_dir / "resume.txt"
            resume_path.write_text(main._RESUME_FALLBACK, encoding="utf-8")

            with patch("main._write_resume_atomic") as atomic_write:
                main._ensure_resume(data_dir)

            atomic_write.assert_not_called()
            self.assertEqual(
                resume_path.read_text(encoding="utf-8"),
                main._RESUME_FALLBACK,
            )

    def test_preserves_customized_resume_and_logs_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            resume_path = data_dir / "resume.txt"
            custom_resume = "Perfil personalizado pelo usuário.\n"
            resume_path.write_text(custom_resume, encoding="utf-8")

            with self.assertLogs("main", level="WARNING") as captured:
                main._ensure_resume(data_dir)

            self.assertEqual(resume_path.read_text(encoding="utf-8"), custom_resume)
            self.assertIn("preservar personalizações", "\n".join(captured.output))

    def test_write_failure_preserves_legacy_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            resume_path = data_dir / "resume.txt"
            resume_path.write_text(main._LEGACY_RESUME_FALLBACK, encoding="utf-8")

            with patch(
                "main.os.replace", side_effect=OSError("disk error")
            ), self.assertLogs("main", level="WARNING") as captured:
                main._ensure_resume(data_dir)

            self.assertEqual(
                resume_path.read_text(encoding="utf-8"),
                main._LEGACY_RESUME_FALLBACK,
            )
            self.assertFalse(resume_path.with_suffix(".tmp").exists())
            self.assertIn("disk error", "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
