# Analisador de fit entre o currículo do usuário e a descrição da vaga via Gemini API

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_MODEL = "gemini-flash-lite-latest"
_DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
_RESUME_FILE = _DATA_DIR / "resume.txt"


def _load_resume() -> str:
    """Lê DATA_DIR/resume.txt e retorna o conteúdo. Retorna string vazia se não existir."""
    if not _RESUME_FILE.exists():
        logger.warning(
            "Currículo não encontrado em '%s' — análise sem currículo.", _RESUME_FILE
        )
        return ""
    try:
        content = _RESUME_FILE.read_text(encoding="utf-8").strip()
        logger.debug("Currículo carregado (%d chars) de '%s'.", len(content), _RESUME_FILE)
        return content
    except OSError as exc:
        logger.warning("Erro ao ler currículo '%s': %s", _RESUME_FILE, exc)
        return ""


def _build_prompt(jobs: list[tuple[dict, float]]) -> str:
    lines = []
    for job, score in jobs:
        lines.append(
            f"- {job.get('title', '?')} | {job.get('company', '?')} "
            f"| {job.get('source', '?')} | Score: {score:.1f}"
        )
    jobs_block = "\n".join(lines) if lines else "(nenhuma vaga)"

    resume = _load_resume()

    if resume:
        return f"""Você é um assistente de carreira especializado em tecnologia.

Analise as vagas abaixo e compare com o currículo do candidato.
Identifique: quais vagas têm melhor fit, o que destacar ou ajustar no currículo para cada vaga, e uma dica prática de candidatura.

CURRÍCULO DO CANDIDATO:
{resume}

VAGAS ENCONTRADAS:
{jobs_block}

Responda em HTML simples (sem markdown, sem ```html). Máximo 250 palavras. Seja direto e específico."""

    # Fallback: sem currículo
    return f"""Você é um assistente de carreira especializado em tecnologia.

Analise as seguintes vagas e forneça sugestões práticas e diretas para um candidato a estágio ou vaga júnior remota em back-end ou full-stack com Python.

VAGAS ENCONTRADAS:
{jobs_block}

Responda em HTML simples (sem markdown, sem ```html), com:
1. Quais vagas têm melhor fit com o perfil
2. O que destacar no currículo para essas vagas
3. Uma dica prática de candidatura

Seja direto e objetivo. Máximo 200 palavras."""


def analyze_jobs(jobs: list[tuple[dict, float]]) -> str:
    """Analisa as vagas com Gemini e retorna HTML com sugestões de carreira.

    Retorna string vazia se a chave não estiver configurada ou se a API falhar.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY não configurada — análise de IA desativada."
        )
        return ""

    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=api_key)
        prompt = _build_prompt(jobs)
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                http_options=genai_types.HttpOptions(timeout=30_000),
            ),
        )
        result = response.text.strip()
        logger.info("Análise Gemini concluída (%d chars).", len(result))
        return result
    except ImportError:
        logger.error(
            "Pacote google-genai não instalado. "
            "Execute: pip install google-genai"
        )
    except Exception as exc:  # noqa: BLE001 — degradação graciosa intencional
        logger.error("Falha na API Gemini: %s", exc)

    return ""


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    mock_jobs: list[tuple[dict, float]] = [
        (
            {
                "id": "gupy_1",
                "source": "Gupy",
                "title": "Pessoa Desenvolvedora Python Júnior",
                "company": "Empresa Exemplo S.A.",
                "location": "Remoto",
                "workplace_type": "remote",
                "job_type": "full-time",
                "url": "https://exemplo.gupy.io/job/1",
                "published_at": "2026-05-27T10:00:00Z",
                "applications_open": True,
            },
            9.0,
        ),
        (
            {
                "id": "linkedin_2",
                "source": "LinkedIn",
                "title": "Junior Python Developer — Remote Work",
                "company": "Tech Corp Brasil",
                "location": "Brasil",
                "workplace_type": "remote",
                "job_type": "unknown",
                "url": "https://br.linkedin.com/jobs/view/2",
                "published_at": "2026-05-27",
                "applications_open": True,
            },
            7.0,
        ),
        (
            {
                "id": "programathor_3",
                "source": "Programathor",
                "title": "Desenvolvedor Python Automação RPA",
                "company": "BotCorp",
                "location": "Remoto",
                "workplace_type": "remote",
                "job_type": "unknown",
                "url": "https://programathor.com.br/jobs/3",
                "published_at": "",
                "applications_open": True,
            },
            10.0,
        ),
    ]

    print("Enviando vagas para análise do Gemini...\n")
    result = analyze_jobs(mock_jobs)

    if result:
        print("─" * 60)
        print(result)
        print("─" * 60)
        print(f"\n✔  Análise retornada ({len(result)} chars)")
    else:
        print("✘  Análise vazia — verifique GEMINI_API_KEY e logs acima.")
