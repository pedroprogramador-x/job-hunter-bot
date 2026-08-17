# Job Hunter Bot — Contexto do Projeto

Sistema Python em produção no Railway que monitora vagas de TI de hora em hora e envia email com análise de IA personalizada.

## Stack
Python 3.11 · APScheduler · Requests · BeautifulSoup4 · Brevo · Gemini API (gemini-flash-lite-latest) · Railway (worker + volume /data)

## Estrutura
- `main.py` — orquestrador + APScheduler + _ensure_resume()
- `scrapers/gupy_scraper.py` — API employability-portal.gupy.io, buscas globais + coletor genérico de boards estratégicos
- `core/strategic_boards.py` — configuração central dos boards Gupy por company_id
- `core/job_deduplication.py` — deduplicação do ciclo por ID, URL canônica e fallback conservador
- `scrapers/linkedin_scraper.py` — Guest API pública, buscas remotas + Maceió
- `scrapers/programathor_scraper.py` — HTML scraping (bloqueado no Railway por Cloudflare)
- `scrapers/indeed_scraper.py` — RSS (bloqueado por Cloudflare)
- `core/filter_engine.py` — normalização, hard blocks e scoring para estágio/júnior, min_score=10.0
- `core/state_manager.py` — seen_jobs.json em /data, write atômico via os.replace()
- `core/resume_analyzer.py` — Gemini API, lê /data/resume.txt, degrada graciosamente, timeout 30s
- `core/email_sender.py` — API transacional da Brevo via HTTP, timeout 15s, remetente e destinatário mascarados nos logs
- `templates/email_template.py` — HTML com cards por vaga, html.escape() em todos os campos externos

## Pipeline por ciclo
1. Gupy global + boards estratégicos, LinkedIn e Programathor; falhas isoladas por fonte/board
2. Deduplicação global do ciclo antes do filtro de relevância
3. Hard blocks + scoring inicial min_score=10.0
4. State manager remove vagas já notificadas
5. Se zero novas → encerra sem email
6. Top 40 recebem descrição completa; hard blocks finais + ranking top 20
7. Gemini analisa vagas comparando com currículo do Pedro (/data/resume.txt)
8. Brevo envia email; estado salvo APENAS se o envio tiver sucesso

## Regras obrigatórias
- Sempre degradar graciosamente — falha em um componente não para o pipeline
- Write atômico no state manager via os.replace()
- html.escape() em todos os campos externos no template
- Nunca commitar .env ou arquivos em data/
- Rodar python main.py localmente antes de qualquer commit
- Commit em português, mensagens descritivas

## Variáveis de ambiente
GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAIL, GEMINI_API_KEY, BREVO_API_KEY, DATA_DIR=/data, SCHEDULE_INTERVAL_HOURS=1

## Deploy
Railway · projeto: sweet-emotion · serviço: worker · volume: worker-volume montado em /data
Redeploy automático via push no GitHub (pedroprogramador-x/job-hunter-bot)

## Candidato
Pedro Henrique · Engenharia de Software (Estácio, cursando) · Maceió, AL
Objetivo: estágio ou júnior em desenvolvimento, priorizando backend Python, APIs, automação e integrações; remoto Brasil ou Maceió/AL
