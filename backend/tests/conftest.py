import sys
from pathlib import Path

import pytest

# Permite `from src...` al ejecutar pytest desde la raíz o desde backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _runtime_dir(tmp_path, monkeypatch):
    """Caché del boletín, fotos y máscaras en un directorio temporal por test."""
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("CENTINELA_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("LATENCY_TUNING", "on")  # independiente del .env local
    from src.clients import meta

    meta.reset_tuning_state()
    return runtime
