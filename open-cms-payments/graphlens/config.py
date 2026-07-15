import os
from pathlib import Path

from dotenv import load_dotenv  # type: ignore[import-not-found]

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "./processed"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500_000))
PROGRAM_YEARS = [2020, 2021, 2022, 2023, 2024]
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def nodes_path() -> Path:
    return PROCESSED_DIR / "nodes.parquet"


def edges_path() -> Path:
    return PROCESSED_DIR / "edges_general.parquet"


def research_path() -> Path:
    return PROCESSED_DIR / "edges_research.parquet"


def ownership_path() -> Path:
    return PROCESSED_DIR / "edges_ownership.parquet"
