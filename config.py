from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

UNDERSTAT_LEAGUE = "EPL"
SOFASCORE_TOURNAMENT_ID = 17

SEASONS = [str(year) for year in range(2016, 2026)]

REQUEST_DELAY = 1.0

MIN_MINUTES = 450
