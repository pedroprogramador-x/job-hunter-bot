# Analisador de fit entre o currículo do usuário e a descrição da vaga via Gemini API

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_MODEL = "gemini-flash-lite-latest"

_CANDIDATE_PROFILE = """PERFIL DO CANDIDATO:
- Nome: Pedro
- Formação: Engenharia de Software — Estácio (cursando, dez/2028)
- Stack: Python (intermediário), FastAPI, PostgreSQL, SQLAlchemy, JWT, APScheduler, SQL, JavaScript (iniciando), Git
- Projetos: Sports Analysis Bot (API REST em produção no Railway), Task Manager, Finance Manager, Job Hunter Bot (sistema de monitoramento de vagas com scraping e IA)
- Experiência formal em TI: nenhuma
- Objetivo: estágio ou júnior remoto em back-end ou full-stack"""


def _build_prompt(jobs: list[tuple[dict, float]]) -> str:
    lines = []
    for job, score in jobs:
        lines.append(
            f"- {job.get('title', '?')} | {job.get('company', '?')} "
            f"| {job.get('source', '?')} | Score: {score:.1f}"
        )
    jobs_block = "\n".join(lines) if lines else "(nenhuma vaga)"

    return f"""Você é um assistente de carreira especializado em tecnologia.

Analise as seguintes vagas encontradas para o candidato abaixo e forneça sugestões práticas e diretas.

{_CANDIDATE_PROFILE}

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
