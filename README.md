# 🎯 Job Hunter Bot

![Status](https://img.shields.io/badge/status-em%20produção-brightgreen?style=flat-square)
![Railway](https://img.shields.io/badge/deploy-Railway-blueviolet?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square)

> Bot que monitora vagas de TI automaticamente, filtra por relevância, analisa o fit com seu currículo via IA e envia um e-mail formatado com as melhores oportunidades.

---

## Sobre o projeto

O Job Hunter Bot resolve um problema concreto: acompanhar manualmente múltiplos sites de vagas é repetitivo, cansativo e fácil de esquecer. O bot automatiza todo esse processo — coleta vagas em fontes diferentes, descarta o que não é relevante, compara com o seu perfil e entrega só o que importa direto no e-mail.

Útil para qualquer desenvolvedor em busca ativa de emprego, especialmente quem está começando e quer monitorar estágio e vagas júnior remotas sem perder oportunidades por desatenção.

---

## Como funciona

O bot executa um pipeline completo a cada intervalo configurado:

```
🔍 Coleta       → Busca vagas no Gupy, LinkedIn e Programathor
🎯 Filtra       → Normaliza títulos, bloqueia senioridade/local incompatível e pontua o fit
🔁 Deduplica    → Compara com vagas já notificadas, mantém só as novas
🤖 Analisa      → Envia para o Gemini: qual vaga tem melhor fit com seu currículo
📧 Envia        → Dispara e-mail HTML pela API transacional da Brevo com cards por fonte
💾 Salva estado → Marca as vagas notificadas para não repetir no próximo ciclo
```

O estado só é salvo **após** a confirmação de envio do e-mail. Se o envio falhar, as mesmas vagas aparecem novamente no próximo ciclo.

---

## Fontes de vagas

| Fonte | Método | Status |
|---|---|---|
| **Gupy** | API REST (`employability-portal.gupy.io`), remoto + Alagoas | ✅ Ativo |
| **LinkedIn** | Guest API pública (`/jobs-guest/`), remoto + Maceió | ✅ Ativo |
| **Programathor** | HTML scraping (BeautifulSoup4) | ⚠️ Bloqueado no Railway (Cloudflare) |
| **Indeed** | RSS feed | ⚠️ Bloqueado no Railway (Cloudflare) |

---

## Stack

| Tecnologia | Uso |
|---|---|
| **Python 3.11** | Linguagem principal |
| **APScheduler** | Agendamento do pipeline (BlockingScheduler) |
| **Requests** | Chamadas HTTP para APIs e scraping |
| **BeautifulSoup4** | Parsing de HTML do Programathor |
| **google-genai** | Cliente oficial da Gemini API (análise de vagas) |
| **Brevo** | Envio de e-mail pela API transacional (sem SMTP) |
| **python-dotenv** | Carregamento de variáveis de ambiente |
| **Railway** | Plataforma de deploy (worker process + volume) |

---

## Estrutura do projeto

```
job-hunter-bot/
│
├── main.py                      # Orquestrador: pipeline + APScheduler
├── requirements.txt             # Dependências do projeto
├── Procfile                     # worker: python main.py (Railway)
├── railway.json                 # Configuração de deploy
├── .env.example                 # Variáveis de ambiente necessárias
├── .gitignore
│
├── scrapers/
│   ├── gupy_scraper.py          # Coleta via API do portal Gupy
│   ├── linkedin_scraper.py      # Coleta via guest API do LinkedIn
│   ├── programathor_scraper.py  # Coleta via scraping do Programathor
│   └── indeed_scraper.py        # RSS feed (retorna vazio — Cloudflare)
│
├── core/
│   ├── filter_engine.py         # Scoring por palavras-chave e pesos
│   ├── state_manager.py         # Persistência de vagas já notificadas
│   ├── resume_analyzer.py       # Análise de fit com Gemini API
│   └── email_sender.py          # Envio de e-mail via API transacional da Brevo
│
├── templates/
│   └── email_template.py        # Template HTML do e-mail (CSS inline)
│
└── data/
    ├── .gitkeep
    ├── seen_jobs.json            # Estado persistido (ignorado pelo git)
    └── resume.txt               # Currículo do candidato (ignorado pelo git)
```

---

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

| Variável | Descrição | Obrigatória |
|---|---|---|
| `GMAIL_USER` | E-mail remetente (verificado na Brevo) | ✅ |
| `GMAIL_APP_PASSWORD` | Não utilizado atualmente (legado SMTP) | ❌ |
| `NOTIFY_EMAIL` | E-mail que recebe as notificações | ✅ |
| `BREVO_API_KEY` | Chave da API transacional da Brevo | ✅ |
| `GEMINI_API_KEY` | Chave da API do Google Gemini (AI Studio) | ✅ |
| `DATA_DIR` | Diretório de dados persistentes (padrão: `/data`) | ❌ |
| `SCHEDULE_INTERVAL_HOURS` | Intervalo entre execuções em horas (padrão: `1`) | ❌ |

---

## Como rodar localmente

**Pré-requisitos:** Python 3.11+, Git

```bash
# 1. Clone o repositório
git clone https://github.com/pedroprogramador-x/job-hunter-bot.git
cd job-hunter-bot

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas chaves

# 5. Execute o bot
python main.py
```

Na primeira execução o pipeline roda imediatamente. O scheduler aguarda o intervalo configurado para as próximas execuções. Use `Ctrl+C` para encerrar.

---

## Deploy no Railway

O projeto está configurado para rodar como **worker process** (sem porta HTTP) no Railway.

**Configuração atual:**
- `Procfile` define `worker: python main.py`
- `railway.json` configura o builder (Nixpacks) e restart automático em caso de falha
- **Volume persistente** montado em `/data` — armazena `seen_jobs.json` e `resume.txt` entre deploys
- **Redeploy automático** via integração com GitHub: push na branch `main` aciona novo deploy

**Variáveis de ambiente** configuradas pelo painel do Railway (Settings → Variables).

**Sobre o currículo:** ao iniciar, o bot cria `/data/resume.txt` quando ausente. Se encontrar exatamente a versão legada conhecida, migra atomicamente para o perfil atual. Conteúdo personalizado é preservado e gera um warning, sem sobrescrita automática.

---

## Decisões técnicas

**Estado salvo só após e-mail confirmado**
O `seen_jobs.json` é atualizado apenas quando a Brevo retorna status 201. Se o envio falhar por qualquer motivo, as mesmas vagas reaparecem no próximo ciclo e o bot tenta novamente — sem perda silenciosa de notificações.

**Write atômico no state manager**
A escrita no `seen_jobs.json` usa um arquivo temporário (`.tmp`) com `os.replace()` ao final. Isso evita corrupção do estado em caso de crash ou falha de disco no meio da escrita.

**Degradação graciosa em todas as integrações externas**
Cada scraper, a análise Gemini e o envio de e-mail são encapsulados em `try/except` independentes. Se o Gemini estiver fora do ar ou a cota acabar, o e-mail é enviado sem a análise. Se o Programathor bloquear, os outros scrapers continuam. O bot nunca trava por falha de uma dependência externa.

**Currículo versionado com migração conservadora**
O perfil atual e a versão legada conhecida ficam em `main.py`. O bot atualiza automaticamente apenas arquivos idênticos à versão legada; qualquer divergência é tratada como possível personalização e não é sobrescrita.

---

## Melhorias futuras

- [ ] **Catho como fonte** — tem API pública parcialmente documentada
- [ ] **TTL no `seen_jobs.json`** — vagas com mais de 30 dias voltam a ser elegíveis caso sejam repostadas
- [ ] **Suporte a proxy** — contornar Cloudflare do Indeed e de outros sites que bloqueiam scraping direto

---

## Autor

**Pedro Henrique Bezerra de Lima**
Desenvolvedor Backend em Formação | Python · FastAPI · PostgreSQL

[![GitHub](https://img.shields.io/badge/GitHub-pedroprogramador--x-181717?style=flat-square&logo=github)](https://github.com/pedroprogramador-x)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Pedro%20Henrique-0A66C2?style=flat-square&logo=linkedin)](https://linkedin.com/in/pedrophbezerra)
