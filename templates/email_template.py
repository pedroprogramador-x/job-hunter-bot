# Template HTML para o e-mail de notificação de novas vagas

import html
from datetime import datetime

_SOURCE_COLORS = {
    "Gupy":         "#16a34a",   # verde
    "LinkedIn":     "#2563eb",   # azul
    "Programathor": "#ea580c",   # laranja
    "Indeed":       "#dc2626",   # vermelho (fallback)
}
_DEFAULT_COLOR = "#6b7280"  # cinza


def _source_color(source: str) -> str:
    return _SOURCE_COLORS.get(source, _DEFAULT_COLOR)


def _safe_url(url: str) -> str:
    """Aceita só http/https; qualquer outro valor vira '#'."""
    return url if url.startswith(("http://", "https://")) else "#"


def _job_card(job: dict, score: float) -> str:
    color    = _source_color(job.get("source", ""))
    title    = html.escape(job.get("title", "Sem título"))
    company  = html.escape(job.get("company", "") or "—")
    location = html.escape(job.get("location", "") or "—")
    source   = html.escape(job.get("source", "—"))
    url      = _safe_url(job.get("url", "#"))

    return f"""
    <div style="
        background:#ffffff;
        border-radius:8px;
        border-left:5px solid {color};
        margin:0 0 16px 0;
        padding:16px 20px;
        box-shadow:0 1px 3px rgba(0,0,0,.08);
        font-family:Arial,Helvetica,sans-serif;
    ">
        <p style="margin:0 0 4px 0;font-size:17px;font-weight:700;color:#111827;">
            {title}
        </p>
        <p style="margin:0 0 8px 0;font-size:14px;color:#374151;">
            🏢 {company}
            &nbsp;&nbsp;
            📍 {location}
        </p>
        <p style="margin:0 0 12px 0;font-size:13px;color:#6b7280;">
            <span style="
                background:{color};
                color:#fff;
                border-radius:4px;
                padding:2px 8px;
                font-size:12px;
                font-weight:600;
            ">{source}</span>
            &nbsp;
            <span style="color:#9ca3af;">Score: <strong style="color:#111827;">{score:.1f}</strong></span>
        </p>
        <a href="{url}"
           style="
               display:inline-block;
               background:{color};
               color:#ffffff;
               text-decoration:none;
               font-size:13px;
               font-weight:600;
               padding:7px 16px;
               border-radius:5px;
           ">Ver vaga →</a>
    </div>"""


def render_email(jobs: list[tuple[dict, float]], ai_analysis: str = "") -> str:
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    count   = len(jobs)

    cards_html = "\n".join(_job_card(job, score) for job, score in jobs)

    ai_section = ""
    if ai_analysis.strip():
        ai_section = f"""
        <div style="
            background:#f0f9ff;
            border:1px solid #bae6fd;
            border-radius:8px;
            padding:16px 20px;
            margin:24px 0 0 0;
            font-family:Arial,Helvetica,sans-serif;
        ">
            <div style="margin:0 0 8px 0;font-size:15px;font-weight:700;color:#0369a1;">
                🤖 Análise de IA
            </div>
            <div style="margin:0;font-size:14px;color:#374151;white-space:pre-line;">{ai_analysis}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Job Hunter Bot</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="
                background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 100%);
                border-radius:10px 10px 0 0;
                padding:28px 32px;
                text-align:center;
            ">
              <h1 style="margin:0;font-size:22px;font-weight:800;color:#ffffff;font-family:Arial,Helvetica,sans-serif;">
                🎯 Job Hunter Bot — Novas Vagas
              </h1>
              <p style="margin:8px 0 0 0;font-size:14px;color:#bfdbfe;font-family:Arial,Helvetica,sans-serif;">
                {count} nova(s) vaga(s) encontrada(s)
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background:#ffffff;padding:24px 32px;border-radius:0 0 10px 10px;">
              {cards_html}
              {ai_section}

              <!-- Footer -->
              <p style="
                  margin:24px 0 0 0;
                  font-size:12px;
                  color:#9ca3af;
                  text-align:center;
                  font-family:Arial,Helvetica,sans-serif;
                  border-top:1px solid #f3f4f6;
                  padding-top:16px;
              ">
                Gerado automaticamente por Job Hunter Bot em {now_str}
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
