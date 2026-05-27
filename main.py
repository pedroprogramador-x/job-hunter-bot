import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TRACKED_VARS = [
    "GMAIL_USER",
    "NOTIFY_EMAIL",
    "ANTHROPIC_API_KEY",
    "DATA_DIR",
    "SCHEDULE_INTERVAL_HOURS",
]

for var in TRACKED_VARS:
    value = os.getenv(var)
    if value:
        display = value if var in ("DATA_DIR", "SCHEDULE_INTERVAL_HOURS") else "[SET]"
        logger.info("%-28s %s", var, display)
    else:
        logger.warning("%-28s NOT SET", var)

print("Job Hunter Bot iniciado com sucesso.")
