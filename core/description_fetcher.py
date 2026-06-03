# Busca a descrição textual de cada vaga a partir da URL da página.
# Seletores confirmados via inspeção real do HTML (2026-06-03):
#   Gupy    → div[data-testid="text-section"]  (múltiplos, classe sc-* dinâmica)
#   LinkedIn → div.show-more-less-html__markup

import logging
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

_MAX_CHARS = 2000
_RATE_LIMIT_SECS = 1.0


def _fetch_gupy(url: str) -> str:
    r = requests.get(url, headers=_HEADERS, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    # data-testid="text-section" cobre: descrição, responsabilidades,
    # requisitos e informações adicionais (onde aparece presencial/híbrido)
    sections = soup.select('div[data-testid="text-section"]')
    if sections:
        return " ".join(s.get_text(" ", strip=True) for s in sections)
    return ""


def _fetch_linkedin(url: str) -> str:
    r = requests.get(url, headers=_HEADERS, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    el = soup.select_one("div.show-more-less-html__markup")
    if el:
        return el.get_text(" ", strip=True)
    return ""


def _fetch_description(job: dict) -> str:
    """Faz GET na URL da vaga e extrai o texto da descrição. Retorna '' em caso de falha."""
    url = job.get("url", "")
    if not url:
        return ""

    source = job.get("source", "").lower()
    try:
        if source == "gupy" or "gupy.io" in url:
            return _fetch_gupy(url)
        elif source == "linkedin" or "linkedin.com" in url:
            return _fetch_linkedin(url)
        else:
            # Fallback genérico: tenta os dois seletores conhecidos
            r = requests.get(url, headers=_HEADERS, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for sel in [
                'div[data-testid="text-section"]',
                "div.show-more-less-html__markup",
                "div.job-description",
            ]:
                els = soup.select(sel)
                if els:
                    return " ".join(e.get_text(" ", strip=True) for e in els)
            return ""

    except requests.exceptions.Timeout:
        logger.warning("Timeout ao buscar descrição: %s", url)
    except requests.exceptions.HTTPError as exc:
        logger.warning(
            "HTTP %s ao buscar descrição: %s",
            exc.response.status_code if exc.response is not None else "?",
            url,
        )
    except requests.RequestException as exc:
        logger.warning("Erro de rede ao buscar descrição de '%s': %s", url, exc)
    except Exception as exc:  # noqa: BLE001 — degradação graciosa intencional
        logger.warning("Erro inesperado ao buscar descrição de '%s': %s", url, exc)

    return ""


def fetch_descriptions(
    jobs: list[tuple[dict, float]],
) -> list[tuple[dict, float]]:
    """Enriquece cada vaga com o campo 'description' (máx 2000 chars).

    Nunca trava o pipeline — falhas resultam em description=''.
    Aguarda 1 segundo entre requisições para evitar bloqueio.
    """
    enriched: list[tuple[dict, float]] = []
    for i, (job, score) in enumerate(jobs):
        if i > 0:
            time.sleep(_RATE_LIMIT_SECS)

        desc = _fetch_description(job)
        enriched_job = dict(job)  # não muta o dict original
        enriched_job["description"] = desc[:_MAX_CHARS] if desc else ""

        if enriched_job["description"]:
            logger.debug(
                "Descrição obtida: '%s' (%d chars)",
                job.get("title", "?"),
                len(enriched_job["description"]),
            )
        else:
            logger.debug("Sem descrição para: '%s'", job.get("title", "?"))

        enriched.append((enriched_job, score))

    logger.info(
        "description_fetcher: %d/%d vaga(s) com descrição",
        sum(1 for job, _ in enriched if job["description"]),
        len(enriched),
    )
    return enriched


if __name__ == "__main__":
    import sys
    import logging as _logging
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")

    # URLs reais para testar (uma por fonte)
    test_jobs: list[tuple[dict, float]] = [
        (
            {
                "id": "gupy_test",
                "source": "Gupy",
                "title": "Desenvolvedor Full-stack | Python | JR/PL",
                "company": "Lumini IT Solutions",
                "url": "https://luminiitsolutions.gupy.io/job/eyJqb2JJZCI6MTE0MjY1NzYsInNvdXJjZSI6Imd1cHlfcG9ydGFsIn0=?jobBoardSource=gupy_portal",
                "workplace_type": "remote",
            },
            8.0,
        ),
        (
            {
                "id": "linkedin_test",
                "source": "LinkedIn",
                "title": "Analista de Dados Júnior",
                "company": "enjoei",
                "url": "https://br.linkedin.com/jobs/view/analista-de-dados-j%C3%BAnior-at-enjoei-4423299033",
                "workplace_type": "remote",
            },
            6.0,
        ),
    ]

    print(f"Buscando descrições de {len(test_jobs)} vagas...\n")
    results = fetch_descriptions(test_jobs)

    for job, score in results:
        desc = job.get("description", "")
        status = f"OK ({len(desc)} chars)" if desc else "VAZIO"
        print(f"[{status}] {job['title']} ({job['source']})")
        if desc:
            print(f"  Preview: {desc[:200]!r}")
        print()
