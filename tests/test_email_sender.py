import os
import unittest
from unittest.mock import Mock, patch

from python_http_client.exceptions import HTTPError

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
            "SENDGRID_API_KEY": "SG.test-key",
            "GMAIL_USER": "sender@example.com",
            "NOTIFY_EMAIL": "recipient@example.com",
        }
        env.update(overrides)
        return env

    @patch("core.email_sender.SendGridAPIClient")
    def test_builds_mail_and_calls_sendgrid(self, client_class: Mock) -> None:
        client = client_class.return_value
        client.send.return_value = Mock(status_code=202, body=b"", headers={})

        with patch.dict(os.environ, self._env(SENDGRID_API_KEY="  SG.test-key  "), clear=True):
            with self.assertLogs("core.email_sender", level="INFO") as captured:
                sent = send_jobs_email(_JOBS, ai_analysis="<strong>Bom fit</strong>")

        self.assertTrue(sent)
        client_class.assert_called_once_with("SG.test-key")
        client.send.assert_called_once()
        payload = client.send.call_args.args[0].get()
        self.assertEqual(payload["from"]["email"], "sender@example.com")
        self.assertEqual(payload["personalizations"][0]["to"][0]["email"], "recipient@example.com")
        self.assertIn("1 nova(s) vaga(s)", payload["subject"])
        self.assertIn("Desenvolvedor Python Júnior", payload["content"][0]["value"])
        log_output = "\n".join(captured.output)
        self.assertIn("remetente=se***@example.com", log_output)
        self.assertIn("destinatário=re***@example.com", log_output)
        self.assertIn("vagas=1", log_output)
        self.assertIn("status_code=202", log_output)
        self.assertNotIn("SG.test-key", log_output)

    @patch("core.email_sender.SendGridAPIClient")
    def test_logs_http_error_details_and_returns_false(self, client_class: Mock) -> None:
        client_class.return_value.send.side_effect = HTTPError(
            401,
            "Unauthorized",
            b'{"errors":[{"message":"authorization required"}]}',
            {"X-Message-Id": "test-message-id"},
        )

        with patch.dict(os.environ, self._env(), clear=True):
            with self.assertLogs("core.email_sender", level="ERROR") as captured:
                sent = send_jobs_email(_JOBS)

        self.assertFalse(sent)
        log_output = "\n".join(captured.output)
        self.assertIn("status_code=401", log_output)
        self.assertIn("authorization required", log_output)
        self.assertIn("X-Message-Id", log_output)
        self.assertIn("Traceback", log_output)
        self.assertNotIn("SG.test-key", log_output)

    @patch("core.email_sender.SendGridAPIClient")
    def test_missing_required_environment_variables_skip_send(self, client_class: Mock) -> None:
        for variable in ("SENDGRID_API_KEY", "GMAIL_USER", "NOTIFY_EMAIL"):
            with self.subTest(variable=variable):
                with patch.dict(os.environ, self._env(**{variable: ""}), clear=True):
                    with self.assertLogs("core.email_sender", level="WARNING") as captured:
                        sent = send_jobs_email(_JOBS)

                self.assertFalse(sent)
                self.assertIn(variable, "\n".join(captured.output))
        client_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
