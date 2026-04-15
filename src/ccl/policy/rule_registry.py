"""Registry that maps law_id → .md file path and caches parsed rules."""
from __future__ import annotations

import os
from pathlib import Path

import frontmatter

from ccl.models import Rule
from ccl.policy.law_parser import LawParser

# Resolve LAWS_DIR: env var override for Docker or test environments
_DEFAULT_LAWS_DIR = Path(__file__).parent.parent.parent.parent / "laws"

def _laws_dir() -> Path:
    override = os.environ.get("LAWS_DIR")
    if override:
        return Path(override)
    return _DEFAULT_LAWS_DIR


# Canonical mapping from law_id (CLI argument) to relative path under LAWS_DIR
LAW_ID_TO_RELATIVE_PATH: dict[str, str] = {
    "kr-pipa":  "kr/personal-information-protection-act.md",
    "gdpr":     "eu/gdpr.md",
    "ccpa":     "us/ccpa.md",
    "hipaa":    "us/hipaa.md",
    "jp-appi":  "jp/appi.md",
    "kr-credit": "kr/credit-information-use-act.md",
    "kr-network": "kr/network-utilization-act.md",
    "eu-ai-act": "eu/ai-act.md",
    "iso27001":  "iso/iso27001.md",
}


class RuleRegistry:
    def __init__(self) -> None:
        self._parser = LawParser()
        self._cache: dict[str, tuple[dict, list[Rule]]] = {}

    def get_rules(self, law_id: str) -> list[Rule]:
        return self._get_cached(law_id.lower())[1]

    def get_law_metadata(self, law_id: str) -> dict:
        """Return frontmatter metadata from the law file."""
        return self._get_cached(law_id.lower())[0]

    def get_law_path(self, law_id: str) -> Path:
        law_id = law_id.lower()
        rel = LAW_ID_TO_RELATIVE_PATH.get(law_id)
        if rel is None:
            raise ValueError(
                f"Unknown law_id: {law_id!r}. "
                f"Available: {list(LAW_ID_TO_RELATIVE_PATH.keys())}"
            )
        path = _laws_dir() / rel
        if not path.exists():
            raise FileNotFoundError(f"Law bundle file not found: {path}")
        return path

    def _get_cached(self, law_id: str) -> tuple[dict, list[Rule]]:
        if law_id not in self._cache:
            self._cache[law_id] = self._load(law_id)
        return self._cache[law_id]

    def _load(self, law_id: str) -> tuple[dict, list[Rule]]:
        path = self.get_law_path(law_id)
        text = path.read_text(encoding="utf-8")
        post = frontmatter.loads(text)
        metadata = dict(post.metadata)
        rules = self._parser.parse_text(text, law_id=path.stem)
        if not rules:
            raise ValueError(f"No rules found in law bundle: {path}")
        return metadata, rules
