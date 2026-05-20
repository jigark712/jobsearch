from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
SECRETS_DIR = ROOT / ".secrets"
DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
DIGESTS_DIR = DATA_DIR / "digests"
RETROS_DIR = DATA_DIR / "retros"
ALERTS_DIR = DATA_DIR / "alerts"
LOGS_DIR = DATA_DIR / "logs"
PROMPTS_DIR = ROOT / "src" / "prompts"


def ensure_data_dirs() -> None:
    for d in (JOBS_DIR, DIGESTS_DIR, RETROS_DIR, ALERTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
