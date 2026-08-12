import logging
import os
import sys
from collections import Counter
from pathlib import Path

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
from core.company_watchlist import match_target_company
from core.description_fetcher import fetch_descriptions
from core.email_sender import send_jobs_email
from core.filter_engine import filter_jobs
from core.resume_analyzer import analyze_jobs
from core.state_manager import filter_new_jobs, save_seen_ids
from scrapers.gupy_scraper import fetch_jobs as gupy_fetch
from scrapers.linkedin_scraper import fetch_jobs as linkedin_fetch
from scrapers.programathor_scraper import fetch_jobs as programathor_fetch

_SEP = "─" * 60


def _log_watchlist_presence(jobs: list[dict]) -> None:
    """Registra presença por fonte para orientar monitoramento direto na Fase C2."""
    presence: Counter[tuple[str, str]] = Counter()
    for job in jobs:
        match = match_target_company(job.get("company", ""))
        if match:
            presence[(job.get("source", "?"), match.canonical_name)] += 1

    for (source, company), count in sorted(presence.items()):
        logger.info(
            "WATCHLIST PRESENCE | fonte=%s | empresa=%s | vagas=%d",
            source,
            company,
            count,
        )


def _log_watchlist_summary(
    collected_jobs: list[dict],
    top_jobs: list[tuple[dict, float]] | None = None,
) -> None:
    matches = [
        match_target_company(job.get("company", "")) for job in collected_jobs
    ]
    found = [match for match in matches if match]
    unique_companies = {match.canonical_name for match in found}
    top_matches = sum(
        1
        for job, _ in (top_jobs or [])
        if job.get("target_company")
        or match_target_company(job.get("company", ""))
    )

    logger.info("Watchlist:")
    logger.info("  matches encontrados: %d", len(found))
    logger.info("  empresas únicas: %d", len(unique_companies))
    logger.info("  vagas da watchlist no top 20: %d", top_matches)


def _safe_fetch(name: str, fetch_fn) -> list[dict]:
    """Executa um scraper isolando falhas para não parar o pipeline."""
    try:
        jobs = fetch_fn()
        if not jobs:
            logger.warning("%-14s  ⚠  zero vagas retornadas", name)
        else:
            logger.info("%-14s  ✔  %d vaga(s) coletada(s)", name, len(jobs))
        return jobs
    except Exception as exc:  # noqa: BLE001 - isola falhas dos scrapers
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
    _log_watchlist_presence(all_jobs)

    if not all_jobs:
        logger.warning("Nenhuma vaga coletada em nenhuma fonte. Encerrando ciclo.")
        _log_watchlist_summary(all_jobs)
        return

    # ── 2. Filtro de relevância ───────────────────────────────────────────────
    logger.info("[ 2/7 ] Aplicando filtro inicial (min_score=10.0)...")
    scored_jobs = filter_jobs(all_jobs, min_score=10.0, final=False)
    logger.info(
        "        %d/%d vaga(s) passaram no filtro",
        len(scored_jobs), len(all_jobs),
    )

    if not scored_jobs:
        logger.warning("Nenhuma vaga atingiu o score mínimo. Encerrando ciclo.")
        _log_watchlist_summary(all_jobs)
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
        _log_watchlist_summary(all_jobs)
        logger.info(_SEP)
        return

    # ── 4b. Seleciona candidatas para enriquecimento ──────────────────────────
    _ENRICHMENT_LIMIT = 40
    new_jobs.sort(key=lambda t: t[1], reverse=True)
    if len(new_jobs) > _ENRICHMENT_LIMIT:
        postponed = len(new_jobs) - _ENRICHMENT_LIMIT
        new_jobs = new_jobs[:_ENRICHMENT_LIMIT]
        logger.info(
            "        %d vaga(s) fora do lote de enriquecimento (limite=%d)",
            postponed,
            _ENRICHMENT_LIMIT,
        )

    # ── 3b. Busca descrições + re-filtro ──────────────────────────────────────
    logger.info("[ 3b  ] Buscando descrições das %d vaga(s) top...", len(new_jobs))
    new_jobs = fetch_descriptions(new_jobs)

    before_refilter = len(new_jobs)
    new_jobs = filter_jobs(
        [job for job, _ in new_jobs],
        min_score=10.0,
        final=True,
    )
    dropped_by_desc = before_refilter - len(new_jobs)
    if dropped_by_desc:
        logger.info(
            "        %d vaga(s) descartada(s) pelo re-filtro com descrição",
            dropped_by_desc,
        )

    if not new_jobs:
        logger.info("Nenhuma vaga aprovada após re-filtro com descrição. Encerrando ciclo.")
        _log_watchlist_summary(all_jobs)
        logger.info(_SEP)
        return

    _EMAIL_LIMIT = 20
    if len(new_jobs) > _EMAIL_LIMIT:
        discarded = len(new_jobs) - _EMAIL_LIMIT
        new_jobs = new_jobs[:_EMAIL_LIMIT]
        logger.info(
            "        %d vaga(s) descartada(s) após ranking final (top %d)",
            discarded,
            _EMAIL_LIMIT,
        )

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
    _log_watchlist_summary(all_jobs, new_jobs)
    logger.info(_SEP)
    logger.info(
        "CICLO CONCLUÍDO  |  coletadas: %d  |  filtradas: %d  |  novas: %d  |  email: %s",
        len(all_jobs),
        len(scored_jobs),
        len(new_jobs),
        "✔ enviado" if sent else "✘ falhou",
    )
    logger.info(_SEP)


_LEGACY_RESUME_FALLBACK = """\
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


_RESUME_FALLBACK = """\
PEDRO HENRIQUE BEZERRA DE LIMA
Maceió, AL — Brasil
Estudante de Engenharia de Software | Backend Python em formação

OBJETIVO
Estágio ou vaga júnior em desenvolvimento de software, com prioridade para backend Python, APIs REST, automação e integrações. Aberto também a oportunidades de entrada em backend ou full-stack com JavaScript ou Java.

RESUMO PROFISSIONAL
Estudante de Engenharia de Software com foco em desenvolvimento backend, automação e APIs. Possui experiência prática em projetos pessoais com Python, FastAPI, PostgreSQL, scraping, integrações externas, IA generativa, testes e notificações automatizadas. Não possui experiência profissional como desenvolvedor.

CONHECIMENTOS
Python, FastAPI, APIs REST, SQLAlchemy, PostgreSQL, JWT, Pydantic, Requests, BeautifulSoup, APScheduler, pytest, Git, GitHub, Railway e Linux básico.
Integração com APIs externas, scraping, automação e IA generativa.
JavaScript e Java em desenvolvimento.

PROJETOS PESSOAIS

SPORTS ANALYSIS BOT
API REST com Python, FastAPI, PostgreSQL e SQLAlchemy para análise esportiva, seleção de value bets e histórico de picks.
- Autenticação JWT com cadastro, login, hash de senha e tokens Bearer.
- Integração com API externa de dados esportivos e Telegram Bot API.
- Rotinas automáticas com APScheduler.
- Testes automatizados para regras de negócio, resultados, timezone e estatísticas.
- Deploy no Railway.

JOB HUNTER BOT
Worker Python em produção no Railway para monitoramento automatizado de vagas.
- Coleta vagas de Gupy, LinkedIn e Programathor usando APIs e scraping.
- Motor de scoring, busca de descrição completa e deduplicação.
- Persistência com escrita atômica.
- Gemini API para análise de compatibilidade entre vagas e currículo.
- Brevo Transactional API para notificações por e-mail.
- Testes automatizados, logs, diagnóstico de credenciais e tratamento de falhas.

EXPERIÊNCIA PROFISSIONAL

Carrefour — Atendimento e pós-venda por call center, home office — atual.
Experiência não técnica com atendimento, comunicação e resolução de problemas.

Operador de Caixa — Farmácia Permanente — fev/2025 a abr/2026 — Maceió/AL.
- Operação do sistema Procfit, estoque, entrada de produtos e relatórios.
- Abertura e fechamento de caixa, pagamentos e conciliação.
- Treinamento de novos colaboradores.
- Atendimento em ambiente de alto fluxo.

FORMAÇÃO
Bacharelado em Engenharia de Software — Estácio — mar/2025 a dez/2028, cursando — Maceió/AL.

CURSOS
Python do Zero ao Avançado — Módulos 1 e 2 — Curso em Vídeo.

IDIOMAS
Português nativo.
Inglês básico, com leitura técnica de documentação e código.
"""


def _write_resume_atomic(resume_path: Path, content: str) -> None:
    """Substitui o currículo por escrita atômica no mesmo diretório."""
    tmp_path = resume_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, resume_path)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _ensure_resume(data_dir: Path | None = None) -> None:
    """Cria ou migra o currículo conhecido sem sobrescrever personalizações."""
    data_dir = data_dir or Path(os.getenv("DATA_DIR", "./data"))
    resume_path = data_dir / "resume.txt"

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        if not resume_path.exists():
            _write_resume_atomic(resume_path, _RESUME_FALLBACK)
            logger.info("Currículo criado em '%s' com o perfil atual.", resume_path)
            return

        persisted_resume = resume_path.read_text(encoding="utf-8")
        if persisted_resume == _RESUME_FALLBACK:
            logger.debug("Currículo persistido já está atualizado em '%s'.", resume_path)
            return

        if persisted_resume == _LEGACY_RESUME_FALLBACK:
            _write_resume_atomic(resume_path, _RESUME_FALLBACK)
            logger.info("Currículo legado migrado com segurança em '%s'.", resume_path)
            return

        logger.warning(
            "Currículo persistido em '%s' difere da versão legada conhecida; "
            "não foi atualizado automaticamente para preservar personalizações.",
            resume_path,
        )
    except OSError as exc:
        logger.warning("Não foi possível criar ou migrar o currículo em '%s': %s", resume_path, exc)


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
