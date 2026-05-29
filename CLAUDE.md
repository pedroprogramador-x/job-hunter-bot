# Job Hunter Bot — Contexto do Projeto

Sistema Python em produção no Railway que monitora vagas de TI de hora em hora e envia email com análise de IA personalizada.

## Stack
Python 3.11 · APScheduler · Requests · BeautifulSoup4 · SendGrid · Gemini API (gemini-flash-lite-latest) · Railway (worker + volume /data)

## Estrutura
- `main.py` — orquestrador + APScheduler + _ensure_resume()
- `scrapers/gupy_scraper.py` — API employability-portal.gupy.io, 8 termos de busca, ~72 vagas
- `scrapers/linkedin_scraper.py` — Guest API pública, 5 termos de busca, ~44 vagas
- `scrapers/programathor_scraper.py` — HTML scraping (bloqueado no Railway por Cloudflare)
- `scrapers/indeed_scraper.py` — RSS (bloqueado por Cloudflare)
- `core/filter_engine.py` — scoring por keyword, min_score=3.0
- `core/state_manager.py` — seen_jobs.json em /data, write atômico via os.replace()
- `core/resume_analyzer.py` — Gemini API, lê /data/resume.txt, degrada graciosamente, timeout 30s
- `core/email_sender.py` — SendGrid API, timeout 15s, destinatário mascarado nos logs
- `templates/email_template.py` — HTML com cards por vaga, html.escape() em todos os campos externos

## Pipeline por ciclo
1. Scrapers Gupy + LinkedIn (~116 vagas) com isolamento de falha por termo
2. Filtro de relevância min_score=3.0
3. State manager remove vagas já notificadas
4. Se zero novas → encerra sem email
5. Gemini analisa vagas comparando com currículo do Pedro (/data/resume.txt)
6. SendGrid envia email para pedrophbezerra@gmail.com
7. Estado salvo APENAS se email enviado com sucesso

## Regras obrigatórias
- Sempre degradar graciosamente — falha em um componente não para o pipeline
- Write atômico no state manager via os.replace()
- html.escape() em todos os campos externos no template
- Nunca commitar .env ou arquivos em data/
- Rodar python main.py localmente antes de qualquer commit
- Commit em português, mensagens descritivas

## Variáveis de ambiente
GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAIL, GEMINI_API_KEY, SENDGRID_API_KEY, DATA_DIR=/data, SCHEDULE_INTERVAL_HOURS=1

## Deploy
Railway · projeto: sweet-emotion · serviço: worker · volume: worker-volume montado em /data
Redeploy automático via push no GitHub (pedroprogramador-x/job-hunter-bot)

## Candidato
Pedro Henrique · Engenharia de Software (Estácio, cursando) · Maceió, AL
Objetivo: estágio ou júnior remoto em back-end ou full-stack
