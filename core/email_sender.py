# Módulo de envio de e-mail via API transacional da Brevo

import logging
import os
import traceback
from datetime import datetime

import requests
from dotenv import load_dotenv

from templates.email_template import render_email

load_dotenv()

logger = logging.getLogger(__name__)

_BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
_REQUEST_TIMEOUT_SECONDS = 15


def _mask_email(address: str) -> str:
    """Mascara o endereço mantendo informação suficiente para diagnóstico."""
    local, separator, domain = address.partition("@")
    if not separator:
        return "***"
    return f"{local[:2]}***@{domain}"


def _safe_log_text(value: object, api_key: str) -> str:
    """Converte valores para log e remove a chave da API, se ela aparecer."""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value) if value else "<vazio>"
    return text.replace(api_key, "[REDACTED]") if api_key else text


def _log_exception(message: str, api_key: str) -> None:
    """Registra o traceback completo sem permitir vazamento da chave da API."""
    logger.error("%s\n%s", message, _safe_log_text(traceback.format_exc(), api_key))


def send_jobs_email(
    jobs: list[tuple[dict, float]],
    ai_analysis: str = "",
) -> bool:
    """Envia e-mail com as vagas encontradas via API transacional da Brevo.

    Retorna True se o envio foi bem-sucedido (status 201), False caso contrário.
    """
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    from_email = os.getenv("GMAIL_USER", "").strip()
    notify_email = os.getenv("NOTIFY_EMAIL", "").strip()

    missing = [
        variable
        for variable, value in (
            ("BREVO_API_KEY", api_key),
            ("GMAIL_USER", from_email),
            ("NOTIFY_EMAIL", notify_email),
        )
        if not value
    ]
    if missing:
        logger.error(
            "Variáveis de ambiente obrigatórias não configuradas: %s",
            ", ".join(missing),
        )
        return False

    logger.info(
        "Iniciando envio via Brevo: remetente=%s destinatário=%s vagas=%d",
        _mask_email(from_email),
        _mask_email(notify_email),
        len(jobs),
    )

    try:
        subject = (
            f"🎯 {len(jobs)} nova(s) vaga(s) encontrada(s) — "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"  # noqa: DTZ005
        )
        html_body = render_email(jobs, ai_analysis)
        payload = {
            "sender": {"name": "Job Hunter Bot", "email": from_email},
            "to": [{"email": notify_email}],
            "subject": subject,
            "htmlContent": html_body,
        }
        response = requests.post(
            _BREVO_API_URL,
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        _log_exception("Erro de rede ao enviar e-mail via Brevo", api_key)
        return False
    except Exception:  # noqa: BLE001 - preserva o contrato booleano do pipeline
        _log_exception("Erro inesperado ao montar ou enviar e-mail via Brevo", api_key)
        return False

    logger.info("Brevo respondeu: status_code=%d", response.status_code)
    if response.status_code == 201:
        logger.info(
            "E-mail enviado para %s com %d vaga(s). [Brevo 201]",
            _mask_email(notify_email),
            len(jobs),
        )
        return True

    logger.error(
        "Brevo retornou erro HTTP: status_code=%d body=%s",
        response.status_code,
        _safe_log_text(response.text, api_key),
    )
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
