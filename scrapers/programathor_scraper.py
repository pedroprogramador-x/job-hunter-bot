import hashlib
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE_URL = "https://programathor.com.br"
_JOBS_URL = f"{_BASE_URL}/jobs-python"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _make_id(url: str) -> str:
    return "programathor_" + hashlib.md5(url.encode()).hexdigest()[:12]


def _infer_workplace_type(location: str, title: str) -> str:
    combined = (location + " " + title).lower()
    return "remote" if "remoto" in combined else "onsite"


def _extract_icon_text(card, icon_class: str) -> str:
    """Extrai texto do <span> que contém um <i> com a classe dada."""
    icon = card.select_one(f"i.{icon_class}")
    if icon and icon.parent:
        return icon.parent.get_text(separator=" ", strip=True)
    return ""


def fetch_jobs() -> list[dict]:
    try:
        response = requests.get(_JOBS_URL, headers=_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Programathor: erro de rede — %s", exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # Cada vaga é um <a href="/jobs/..."> que não aponta para a própria listagem
    job_anchors = [
        a for a in soup.find_all("a", href=True)
        if a["href"].startswith("/jobs/") and "jobs-python" not in a["href"]
    ]

    seen_ids: set[str] = set()
    jobs: list[dict] = []

    for anchor in job_anchors:
        path = anchor["href"]
        full_url = _BASE_URL + path
        job_id = _make_id(full_url)

        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        # Título — <h3> dentro do card
        title_el = anchor.select_one("h3")
        title = title_el.get_text(strip=True) if title_el else path

        # Empresa — span que contém <i class="fa fa-briefcase">
        company = _extract_icon_text(anchor, "fa-briefcase")

        # Localização — span que contém <i class="fas fa-map-marker-alt">
        location = _extract_icon_text(anchor, "fa-map-marker-alt")

        jobs.append({
            "id": job_id,
            "source": "Programathor",
            "title": title,
            "company": company,
            "location": location,
            "workplace_type": _infer_workplace_type(location, title),
            "job_type": "unknown",
            "url": full_url,
            "published_at": "",
            "applications_open": True,
        })

    logger.info("Programathor: %d vagas encontradas.", len(jobs))
    return jobs


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    results = fetch_jobs()
    print(f"\nTotal de vagas encontradas: {len(results)}\n")
    for job in results:
        print(f"  [{job['workplace_type']}] {job['title']} - {job['company']} ({job['location']})")
