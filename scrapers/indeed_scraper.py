import hashlib
import logging
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

_RSS_URL = "https://br.indeed.com/rss?q=python+junior+remoto&l=&sort=date"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://br.indeed.com/",
}


def _infer_workplace_type(title: str) -> str:
    return "remote" if "remoto" in title.lower() else "unknown"


def _infer_job_type(title: str) -> str:
    t = title.lower()
    if "estágio" in t or "estagio" in t:
        return "intern"
    if "junior" in t or "júnior" in t:
        return "full-time"
    return "unknown"


def _make_id(link: str) -> str:
    return "indeed_" + hashlib.md5(link.encode()).hexdigest()[:12]


def fetch_jobs() -> list[dict]:
    try:
        response = requests.get(_RSS_URL, headers=_HEADERS, timeout=15)
        if response.status_code == 403:
            logger.warning(
                "Indeed bloqueou o acesso (403 Forbidden). "
                "O feed RSS requer sessão autenticada no browser. "
                "Retornando lista vazia."
            )
            return []
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Indeed: erro de rede ao acessar RSS — %s", exc)
        return []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        logger.error("Indeed: erro ao parsear XML — %s", exc)
        return []

    ns = ""
    channel = root.find("channel")
    if channel is None:
        logger.warning("Indeed: RSS sem elemento <channel>.")
        return []

    items = channel.findall("item")
    seen_ids: set[str] = set()
    jobs: list[dict] = []

    for item in items:
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        source_el = item.find("source")
        company = (source_el.text if source_el is not None else "").strip()
        published_at = (item.findtext("pubDate") or "").strip()

        if not link:
            continue

        job_id = _make_id(link)
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        jobs.append({
            "id": job_id,
            "source": "Indeed",
            "title": title,
            "company": company,
            "location": "",
            "workplace_type": _infer_workplace_type(title),
            "job_type": _infer_job_type(title),
            "url": link,
            "published_at": published_at,
            "applications_open": True,
        })

    logger.info("Indeed: %d vagas encontradas.", len(jobs))
    return jobs


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    results = fetch_jobs()
    print(f"\nTotal de vagas encontradas: {len(results)}\n")
    for job in results:
        print(f"  {job['title']} - {job['company']} [{job['workplace_type']}]")
