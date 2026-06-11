import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _chdir_repo_root(monkeypatch):
    """Run every test from the repo root so config/ paths resolve."""
    monkeypatch.chdir(REPO_ROOT)


@pytest.fixture
def modules_config():
    with open(REPO_ROOT / "config" / "clinical_modules.json") as f:
        return json.load(f)


@pytest.fixture
def sme_config():
    with open(REPO_ROOT / "config" / "sme_registry.json") as f:
        return json.load(f)


def load_fixture(name: str):
    with open(FIXTURES / name) as f:
        return json.load(f)


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"status {self.status_code}")
