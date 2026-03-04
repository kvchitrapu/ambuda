import os
from pathlib import Path

from vidyut.chandas import Chandas
from vidyut.kosha import Kosha


def get_kosha(vidyut_data_dir: str):
    """Load a kosha (no singleton, for throwaway instances in celery)."""
    return Kosha(Path(vidyut_data_dir) / "kosha")


def get_chandas() -> Chandas:
    """Load a Chandas instance from the configured data directory."""
    data_dir = os.environ.get("VIDYUT_DATA_DIR", "data/vidyut-0.4.0")
    return Chandas(str(Path(data_dir) / "chandas" / "meters.tsv"))
