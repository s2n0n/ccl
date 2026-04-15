"""Shared pytest fixtures."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Point LAWS_DIR at the actual laws/ directory in the repo
REPO_ROOT = Path(__file__).parent.parent
LAWS_DIR = REPO_ROOT / "laws"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def set_laws_dir(monkeypatch):
    monkeypatch.setenv("LAWS_DIR", str(LAWS_DIR))


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def clean_csv(fixtures_dir) -> str:
    return str(fixtures_dir / "sample_clean.csv")


@pytest.fixture
def violations_csv(fixtures_dir) -> str:
    return str(fixtures_dir / "sample_violations.csv")
