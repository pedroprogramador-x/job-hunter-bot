import os
import unittest
from unittest.mock import Mock, patch

import requests

from core.email_sender import send_jobs_email

_JOBS = [
    (
        {
            "id": "gupy_123",
            "source": "Gupy",
            "title": "Desenvolvedor Python Júnior",
            "company": "Empresa & Filhos",
            "location": "Remoto",
            "url": "https://example.com/jobs/123?a=1&b=2",
        },
        8.0,
    )
]


class SendJobsEmailTests(unittest.TestCase):
    def _env(self, **overrides: str) -> dict[str, str]:
        env = {
            "BREVO_API_KEY": "brevo-test-key",
            "GMAIL_USER": "sender@example.com",
            "NOTIFY_EMAIL": "recipient@example.com",
        }
        env.update(overrides)
        return env

    @patch("core.email_sender.requests.post")
    def test_builds_brevo_payload_and_handles_success(self, post: Mock) -> None:
        post.return_value = Mock(status_code=201, text='{"messageId":"test-id"}')

        with patch.dict(
            os.environ,
            self._env(
                BREVO_API_KEY="  brevo-test-key  ",
                GMAIL_USER="  sender@example.com  ",
                NOTIFY_EMAIL="  recipient@example.com  ",
            ),
            clear=True,
        ), self.assertLogs("core.email_sender", level="INFO") as captured:
            sent = send_jobs_email(_JOBS, ai_analysis="<strong>Bom fit</strong>")

        self.assertTrue(sent)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(kwargs["headers"]["api-key"], "brevo-test-key")
        self.assertEqual(kwargs["timeout"], 15)
        payload = kwargs["json"]
        self.assertEqual(
            payload["sender"],
            {"name": "Job Hunter Bot", "email": "sender@example.com"},
        )
        self.assertEqual(payload["to"], [{"email": "recipient@example.com"}])
        self.assertIn("1 nova(s) vaga(s)", payload["subject"])
        self.assertIn("Desenvolvedor Python Júnior", payload["htmlContent"])
        self.assertIn("Empresa &amp; Filhos", payload["htmlContent"])
        self.assertIn("<strong>Bom fit</strong>", payload["htmlContent"])

        log_output = "\n".join(captured.output)
        self.assertIn("Iniciando envio via Brevo", log_output)
        self.assertIn("remetente=se***@example.com", log_output)
        self.assertIn("destinatário=re***@example.com", log_output)
        self.assertIn("vagas=1", log_output)
        self.assertIn("status_code=201", log_output)
        self.assertIn("E-mail enviado", log_output)
        self.assertNotIn("brevo-test-key", log_output)

    @patch("core.email_sender.requests.post")
    def test_authentication_failure_logs_status_and_body(self, post: Mock) -> None:
        post.return_value = Mock(
            status_code=401,
            text='{"code":"unauthorized","message":"Key not found"}',
        )

        with patch.dict(
            os.environ, self._env(), clear=True
        ), self.assertLogs("core.email_sender", level="INFO") as captured:
            sent = send_jobs_email(_JOBS)

        self.assertFalse(sent)
        log_output = "\n".join(captured.output)
        self.assertIn("status_code=401", log_output)
        self.assertIn("Key not found", log_output)

    @patch("core.email_sender.requests.post")
    def test_http_error_logs_status_and_body(self, post: Mock) -> None:
        post.return_value = Mock(
            status_code=500,
            text='{"code":"internal_error","message":"temporary failure"}',
        )

        with patch.dict(
            os.environ, self._env(), clear=True
        ), self.assertLogs("core.email_sender", level="INFO") as captured:
            sent = send_jobs_email(_JOBS)

        self.assertFalse(sent)
        log_output = "\n".join(captured.output)
        self.assertIn("status_code=500", log_output)
        self.assertIn("temporary failure", log_output)

    @patch("core.email_sender.requests.post")
    def test_network_error_logs_redacted_traceback(self, post: Mock) -> None:
        post.side_effect = requests.ConnectionError(
            "connection failed while using brevo-test-key"
        )

        with patch.dict(
            os.environ, self._env(), clear=True
        ), self.assertLogs("core.email_sender", level="ERROR") as captured:
            sent = send_jobs_email(_JOBS)

        self.assertFalse(sent)
        log_output = "\n".join(captured.output)
        self.assertIn("Erro de rede", log_output)
        self.assertIn("Traceback", log_output)
        self.assertIn("[REDACTED]", log_output)
        self.assertNotIn("brevo-test-key", log_output)

    @patch("core.email_sender.requests.post")
    def test_missing_brevo_api_key(self, post: Mock) -> None:
        with patch.dict(
            os.environ,
            self._env(BREVO_API_KEY="   ", SENDGRID_API_KEY="legacy-key"),
            clear=True,
        ), self.assertLogs("core.email_sender", level="ERROR") as captured:
            sent = send_jobs_email(_JOBS)

        self.assertFalse(sent)
        self.assertIn("BREVO_API_KEY", "\n".join(captured.output))
        post.assert_not_called()

    @patch("core.email_sender.requests.post")
    def test_missing_gmail_user(self, post: Mock) -> None:
        with patch.dict(
            os.environ, self._env(GMAIL_USER=""), clear=True
        ), self.assertLogs("core.email_sender", level="ERROR") as captured:
            sent = send_jobs_email(_JOBS)

        self.assertFalse(sent)
        self.assertIn("GMAIL_USER", "\n".join(captured.output))
        post.assert_not_called()

    @patch("core.email_sender.requests.post")
    def test_missing_notify_email(self, post: Mock) -> None:
        with patch.dict(
            os.environ, self._env(NOTIFY_EMAIL=""), clear=True
        ), self.assertLogs("core.email_sender", level="ERROR") as captured:
            sent = send_jobs_email(_JOBS)

        self.assertFalse(sent)
        self.assertIn("NOTIFY_EMAIL", "\n".join(captured.output))
        post.assert_not_called()

    @patch("core.email_sender.requests.post")
    def test_api_key_is_redacted_from_http_error_body(self, post: Mock) -> None:
        post.return_value = Mock(
            status_code=400,
            text='{"message":"invalid brevo-test-key"}',
        )

        with patch.dict(
            os.environ, self._env(), clear=True
        ), self.assertLogs("core.email_sender", level="INFO") as captured:
            sent = send_jobs_email(_JOBS)

        self.assertFalse(sent)
        log_output = "\n".join(captured.output)
        self.assertIn("[REDACTED]", log_output)
        self.assertNotIn("brevo-test-key", log_output)


if __name__ == "__main__":
    unittest.main()
