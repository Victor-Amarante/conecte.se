import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_text():
    def _read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _read


@pytest.fixture(scope="session")
def fixture_json():
    def _read(name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return _read
