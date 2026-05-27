import logging
import os
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Silencia logs verbosos de bibliotecas externas
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ── Importações dos módulos do bot ────────────────────────────────────────────
from scrapers.gupy_scraper        import fetch_jobs as gupy_fetch
from scrapers.linkedin_scraper    import fetch_jobs as linkedin_fetch
from scrapers.programathor_scraper import fetch_jobs as programathor_fetch
from core.filter_engine           import filter_jobs
from core.state_manager           import filter_new_jobs, save_seen_ids
from core.resume_analyzer         import analyze_jobs
from core.email_sender            import send_jobs_email

_SEP = "─" * 60


def _safe_fetch(name: str, fetch_fn) -> list[dict]:
    """Executa um scraper isolando falhas para não parar o pipeline."""
    try:
        jobs = fetch_fn()
        if not jobs:
            logger.warning("%-14s  ⚠  zero vagas retornadas", name)
        else:
            logger.info("%-14s  ✔  %d vaga(s) coletada(s)", name, len(jobs))
        return jobs
    except Exception as exc:
        logger.error("%-14s  ✘  erro inesperado: %s", name, exc)
        return []


def run_pipeline() -> None:
    logger.info(_SEP)
    logger.info("INÍCIO DO CICLO")
    logger.info(_SEP)

    # ── 1. Coleta ─────────────────────────────────────────────────────────────
    logger.info("[ 1/7 ] Coletando vagas dos scrapers...")
    all_jobs: list[dict] = []
    for name, fn in [
        ("Gupy",         gupy_fetch),
        ("LinkedIn",     linkedin_fetch),
        ("Programathor", programathor_fetch),
    ]:
        all_jobs.extend(_safe_fetch(name, fn))

    logger.info("        Total coletado: %d vaga(s)", len(all_jobs))

    if not all_jobs:
        logger.warning("Nenhuma vaga coletada em nenhuma fonte. Encerrando ciclo.")
        return

    # ── 2. Filtro de relevância ───────────────────────────────────────────────
    logger.info("[ 2/7 ] Aplicando filtro de relevância (min_score=3.0)...")
    scored_jobs = filter_jobs(all_jobs, min_score=3.0)
    logger.info(
        "        %d/%d vaga(s) passaram no filtro",
        len(scored_jobs), len(all_jobs),
    )

    if not scored_jobs:
        logger.warning("Nenhuma vaga atingiu o score mínimo. Encerrando ciclo.")
        return

    # ── 3. Filtra novas ───────────────────────────────────────────────────────
    logger.info("[ 3/7 ] Verificando vagas já notificadas...")
    jobs_only = [job for job, _ in scored_jobs]
    new_jobs_raw, updated_ids = filter_new_jobs(jobs_only)

    # Reconstrói tuplas (job, score) apenas para as vagas novas
    score_map = {job["id"]: score for job, score in scored_jobs}
    new_jobs: list[tuple[dict, float]] = [
        (job, score_map[job["id"]]) for job in new_jobs_raw
    ]

    logger.info(
        "        %d nova(s) / %d já notificada(s)",
        len(new_jobs),
        len(scored_jobs) - len(new_jobs),
    )

    # ── 4. Sem novidades → encerra ────────────────────────────────────────────
    if not new_jobs:
        logger.info("Nenhuma vaga nova neste ciclo. Aguardando próxima execução.")
        logger.info(_SEP)
        return

    for job, score in new_jobs:
        logger.info(
            "  [%.1f] %-50s  %s",
            score, job["title"][:50], job["source"],
        )

    # ── 5. Análise com Gemini ─────────────────────────────────────────────────
    logger.info("[ 5/7 ] Analisando vagas com Gemini...")
    ai_analysis = analyze_jobs(new_jobs)
    if ai_analysis:
        logger.info("        Análise gerada (%d chars)", len(ai_analysis))
    else:
        logger.info("        Análise de IA indisponível — continuando sem ela")

    # ── 6. Envio do e-mail ────────────────────────────────────────────────────
    logger.info("[ 6/7 ] Enviando e-mail...")
    sent = send_jobs_email(new_jobs, ai_analysis=ai_analysis)

    # ── 7. Persiste estado apenas se o e-mail foi enviado ─────────────────────
    if sent:
        logger.info("[ 7/7 ] Salvando estado...")
        save_seen_ids(updated_ids)
        logger.info(
            "        ✔  %d vaga(s) marcada(s) como notificadas", len(new_jobs)
        )
    else:
        logger.warning(
            "[ 7/7 ] E-mail não enviado — estado NÃO salvo para retentar no próximo ciclo"
        )

    # ── 8. Resumo do ciclo ────────────────────────────────────────────────────
    logger.info(_SEP)
    logger.info(
        "CICLO CONCLUÍDO  |  coletadas: %d  |  filtradas: %d  |  novas: %d  |  email: %s",
        len(all_jobs),
        len(scored_jobs),
        len(new_jobs),
        "✔ enviado" if sent else "✘ falhou",
    )
    logger.info(_SEP)


_RESUME_FALLBACK = """\
PEDRO HENRIQUE BEZERRA DE LIMA
Desenvolvedor Backend em Formação | Python · FastAPI · PostgreSQL · REST APIs
pedrophbezerra@gmail.com | github.com/pedroprogramador-x | Maceió, AL

OBJETIVO
Estágio em Desenvolvimento de Software | Backend Python
Estudante de Engenharia de Software com projeto backend em produção real: API REST com FastAPI, PostgreSQL e autenticação JWT, rodando 24h no Railway.

PROJETOS
Sports Analysis Bot — Python · FastAPI · PostgreSQL · JWT · APScheduler · Railway [EM PRODUÇÃO]
- API REST completa com FastAPI, PostgreSQL e SQLAlchemy ORM
- Autenticação JWT completa: registro, login, tokens Bearer
- Integração com API externa paginada consumindo odds de 15+ casas de apostas
- Lógica de value betting implementada do zero
- Scheduler automático via APScheduler com notificações Telegram
- Histórico de picks com win rate e ROI via endpoint REST

Job Hunter Bot — Python · APScheduler · BeautifulSoup4 · SendGrid · Gemini API · Railway [EM PRODUÇÃO]
- Sistema automatizado de monitoramento de vagas de TI
- Scraping de Gupy, LinkedIn e Programathor com filtro de relevância por score
- Análise de vagas com IA (Gemini) e envio de email via SendGrid
- Deploy contínuo no Railway com volume persistente

Sabor Caseiro Cardápio Digital — JavaScript ES6+ · HTML5 · CSS3 · GitHub Pages
Sabor Caseiro Link de Bio — JavaScript · HTML5 · CSS3 · GitHub Pages
Gerenciador de Tarefas (CRUD) — Python
Sistema de Controle Financeiro — Python

HABILIDADES
Backend: Python · FastAPI · SQLAlchemy · PostgreSQL · JWT · APScheduler · Pydantic
Conceitos: REST APIs · CRUD · Autenticação · Automação · Consumo de APIs externas
DevOps: Git · GitHub · Railway · Linux (básico)
Frontend: JavaScript ES6+ · HTML5 · CSS3

FORMAÇÃO
Engenharia de Software — Estácio (cursando, mar/2025 – dez/2028) — Maceió, AL

EXPERIÊNCIA
Operador de Caixa — Farmácia Permanente (fev/2025 – abr/2026)
- Operação do sistema Procfit, responsabilidade financeira diária, treinamento de colaboradores

IDIOMAS
Português nativo | Inglês básico (leitura técnica)
"""


def _ensure_resume() -> None:
    """Garante que DATA_DIR/resume.txt existe, criando a partir do fallback se necessário."""
    from pathlib import Path
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    resume_path = data_dir / "resume.txt"
    if resume_path.exists():
        logger.debug("Currículo encontrado em '%s'.", resume_path)
        return
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        resume_path.write_text(_RESUME_FALLBACK, encoding="utf-8")
        logger.info("Currículo criado em '%s' a partir do fallback hardcoded.", resume_path)
    except OSError as exc:
        logger.warning("Não foi possível criar o currículo em '%s': %s", resume_path, exc)


def main() -> None:
    try:
        interval = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "1"))
    except ValueError:
        logger.warning(
            "SCHEDULE_INTERVAL_HOURS inválido — usando padrão de 1 hora."
        )
        interval = 1

    logger.info("Job Hunter Bot iniciado com sucesso.")
    logger.info("Intervalo de execução: %d hora(s)", interval)

    _ensure_resume()

    # Executa imediatamente antes de agendar
    run_pipeline()

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(run_pipeline, "interval", hours=interval)
    logger.info("Agendador iniciado. Próxima execução em %d hora(s).", interval)

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Encerramento solicitado pelo usuário. Até logo!")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
