# Gerenciador de estado — persiste vagas já vistas para evitar notificações duplicadas

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
_STATE_FILE = _DATA_DIR / "seen_jobs.json"


def _ensure_data_dir() -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("Não foi possível criar DATA_DIR '%s': %s", _DATA_DIR, exc)


def load_seen_ids() -> set[str]:
    """Lê seen_jobs.json e retorna set de IDs já vistos. Retorna set vazio se o arquivo não existir."""
    if not _STATE_FILE.exists():
        logger.debug("Arquivo de estado não encontrado — iniciando com set vazio.")
        return set()
    try:
        with _STATE_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        ids = set(data)
        logger.debug("Carregados %d IDs do estado.", len(ids))
        return ids
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Erro ao ler '%s': %s — retornando set vazio.", _STATE_FILE, exc)
        return set()


def save_seen_ids(seen_ids: set[str]) -> bool:
    """Persiste o set de IDs como lista JSON em seen_jobs.json (escrita atômica).

    Retorna True se salvou com sucesso, False se falhou.
    """
    _ensure_data_dir()
    tmp = _STATE_FILE.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(sorted(seen_ids), fh, ensure_ascii=False, indent=2)
        os.replace(tmp, _STATE_FILE)
        logger.debug("Estado salvo: %d IDs em '%s'.", len(seen_ids), _STATE_FILE)
        return True
    except OSError as exc:
        logger.error("Erro ao salvar '%s': %s", _STATE_FILE, exc)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def filter_new_jobs(jobs: list[dict]) -> tuple[list[dict], set[str]]:
    """Filtra vagas já notificadas.

    Retorna:
        (vagas_novas, set_atualizado) — set_atualizado inclui os IDs novos e os anteriores.
    """
    seen_ids = load_seen_ids()
    new_jobs = [job for job in jobs if job["id"] not in seen_ids]
    updated_ids = seen_ids | {job["id"] for job in jobs}
    logger.info(
        "filter_new_jobs: %d recebidas, %d novas, %d no estado total.",
        len(jobs),
        len(new_jobs),
        len(updated_ids),
    )
    return new_jobs, updated_ids


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Garante estado limpo para o teste
    if _STATE_FILE.exists():
        _STATE_FILE.unlink()
    _ensure_data_dir()

    base_jobs = [
        {"id": "test_001", "title": "Vaga A"},
        {"id": "test_002", "title": "Vaga B"},
        {"id": "test_003", "title": "Vaga C"},
    ]

    sep = "-" * 52

    # ── Etapa 1: primeira execução ────────────────────────────
    print(f"\n{sep}")
    print("Etapa 1 — primeira execução (estado vazio)")
    print(sep)
    new_jobs, updated_ids = filter_new_jobs(base_jobs)
    print(f"  Vagas recebidas : {len(base_jobs)}")
    print(f"  Vagas novas     : {len(new_jobs)}  {[j['id'] for j in new_jobs]}")
    assert len(new_jobs) == 3, "FALHOU: esperava 3 vagas novas"
    print("  ✔  Todas as 3 aparecem como novas")

    # ── Etapa 2: salva estado ──────────────────────────────────
    print(f"\n{sep}")
    print("Etapa 2 — salva estado")
    print(sep)
    save_seen_ids(updated_ids)
    saved = load_seen_ids()
    print(f"  IDs salvos      : {sorted(saved)}")
    assert saved == {"test_001", "test_002", "test_003"}, "FALHOU: estado salvo incorreto"
    print("  ✔  Estado persistido corretamente")

    # ── Etapa 3: segunda execução com as mesmas vagas ──────────
    print(f"\n{sep}")
    print("Etapa 3 — segunda execução (mesmas 3 vagas)")
    print(sep)
    new_jobs2, updated_ids2 = filter_new_jobs(base_jobs)
    print(f"  Vagas recebidas : {len(base_jobs)}")
    print(f"  Vagas novas     : {len(new_jobs2)}")
    assert len(new_jobs2) == 0, "FALHOU: esperava 0 vagas novas"
    print("  ✔  Zero novas — duplicatas ignoradas corretamente")

    # ── Etapa 4: terceira execução adicionando test_004 ────────
    print(f"\n{sep}")
    print("Etapa 4 — terceira execução (+test_004)")
    print(sep)
    extended_jobs = base_jobs + [{"id": "test_004", "title": "Vaga D"}]
    new_jobs3, updated_ids3 = filter_new_jobs(extended_jobs)
    save_seen_ids(updated_ids3)
    print(f"  Vagas recebidas : {len(extended_jobs)}")
    print(f"  Vagas novas     : {len(new_jobs3)}  {[j['id'] for j in new_jobs3]}")
    assert len(new_jobs3) == 1 and new_jobs3[0]["id"] == "test_004", "FALHOU: esperava só test_004"
    print("  ✔  Apenas test_004 aparece como nova")

    print(f"\n{sep}")
    print("Todos os critérios de aceite passaram.")
    print(sep)
