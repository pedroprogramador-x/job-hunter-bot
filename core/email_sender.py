# Módulo de envio de e-mail via SendGrid API

import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from templates.email_template import render_email

load_dotenv()

logger = logging.getLogger(__name__)


def send_jobs_email(
    jobs: list[tuple[dict, float]],
    ai_analysis: str = "",
) -> bool:
    """Envia e-mail com as vagas encontradas via SendGrid API.

    Retorna True se o envio foi bem-sucedido (status 202), False caso contrário.
    """
    api_key      = os.getenv("SENDGRID_API_KEY", "")
    from_email   = os.getenv("GMAIL_USER", "")
    notify_email = os.getenv("NOTIFY_EMAIL", "")

    if not api_key:
        logger.warning(
            "SENDGRID_API_KEY não configurada — envio de e-mail desativado."
        )
        return False

    missing = [v for v, val in [
        ("GMAIL_USER", from_email),
        ("NOTIFY_EMAIL", notify_email),
    ] if not val]

    if missing:
        logger.error(
            "Variáveis de ambiente obrigatórias não configuradas: %s",
            ", ".join(missing),
        )
        return False

    subject   = (
        f"🎯 {len(jobs)} nova(s) vaga(s) encontrada(s) — "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    html_body = render_email(jobs, ai_analysis)

    message = Mail(
        from_email=from_email,
        to_emails=notify_email,
        subject=subject,
        html_content=html_body,
    )

    try:
        client   = SendGridAPIClient(api_key)
        client.client.timeout = 15
        response = client.send(message)
        if response.status_code == 202:
            masked = notify_email[:3] + "***"
            logger.info(
                "E-mail enviado para %s com %d vaga(s). [SendGrid 202]",
                masked, len(jobs),
            )
            return True
        logger.error(
            "SendGrid retornou status inesperado %d.",
            response.status_code,
        )
    except Exception as exc:
        logger.error("Erro ao enviar e-mail via SendGrid: %s", exc)

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
