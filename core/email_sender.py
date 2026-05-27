# Módulo de envio de e-mail via Gmail SMTP com suporte a app password

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from templates.email_template import render_email

load_dotenv()

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def send_jobs_email(
    jobs: list[tuple[dict, float]],
    ai_analysis: str = "",
) -> bool:
    """Envia e-mail com as vagas encontradas via Gmail SMTP.

    Retorna True se o envio foi bem-sucedido, False caso contrário.
    """
    gmail_user     = os.getenv("GMAIL_USER", "")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "")
    notify_email   = os.getenv("NOTIFY_EMAIL", "")

    missing = [v for v, val in [
        ("GMAIL_USER", gmail_user),
        ("GMAIL_APP_PASSWORD", gmail_password),
        ("NOTIFY_EMAIL", notify_email),
    ] if not val]

    if missing:
        logger.error(
            "Variáveis de ambiente obrigatórias não configuradas: %s",
            ", ".join(missing),
        )
        return False

    subject = (
        f"🎯 {len(jobs)} nova(s) vaga(s) encontrada(s) — "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    html_body = render_email(jobs, ai_analysis)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = notify_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, notify_email, msg.as_string())
        logger.info("E-mail enviado para %s com %d vaga(s).", notify_email, len(jobs))
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Falha de autenticação no Gmail. "
            "Verifique GMAIL_USER e GMAIL_APP_PASSWORD (use App Password, não a senha normal)."
        )
    except smtplib.SMTPException as exc:
        logger.error("Erro SMTP ao enviar e-mail: %s", exc)
    except OSError as exc:
        logger.error("Erro de rede ao conectar ao Gmail SMTP: %s", exc)
    return False


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    mock_jobs: list[tuple[dict, float]] = [
        (
            {
                "id": "gupy_abc123",
                "source": "Gupy",
                "title": "Pessoa Desenvolvedora Python Júnior",
                "company": "Empresa Exemplo S.A.",
                "location": "Remoto",
                "workplace_type": "remote",
                "job_type": "full-time",
                "url": "https://exemplo.gupy.io/job/123",
                "published_at": "2026-05-27T10:00:00Z",
                "applications_open": True,
            },
            9.0,
        ),
        (
            {
                "id": "linkedin_def456",
                "source": "LinkedIn",
                "title": "Junior Python Developer — Remote Work",
                "company": "Tech Corp Brasil",
                "location": "Brasil",
                "workplace_type": "remote",
                "job_type": "unknown",
                "url": "https://br.linkedin.com/jobs/view/123456",
                "published_at": "2026-05-27",
                "applications_open": True,
            },
            7.0,
        ),
        (
            {
                "id": "programathor_ghi789",
                "source": "Programathor",
                "title": "Desenvolvedor Python Automação RPA",
                "company": "BotCorp",
                "location": "Remoto",
                "workplace_type": "remote",
                "job_type": "unknown",
                "url": "https://programathor.com.br/jobs/99999-dev-python-rpa",
                "published_at": "",
                "applications_open": True,
            },
            10.0,
        ),
    ]

    mock_ai = (
        "As vagas desta rodada têm forte foco em Python para automação e back-end.\n"
        "Destaque para a vaga da BotCorp (score 10.0) que combina Python + RPA,\n"
        "alinhada ao seu perfil de automação. Recomendo candidatar-se às 3 vagas."
    )

    print("Enviando e-mail de teste com 3 vagas mockadas...")
    ok = send_jobs_email(mock_jobs, ai_analysis=mock_ai)
    if ok:
        print("✔  E-mail enviado com sucesso!")
    else:
        print("✘  Falha ao enviar. Verifique os logs acima.")
