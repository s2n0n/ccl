"""Registry that maps law_id → .md file path and caches parsed rules."""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

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
}


class RuleRegistry:
    def __init__(self) -> None:
        self._parser = LawParser()
        self._cache: dict[str, list[Rule]] = {}

    def get_rules(self, law_id: str) -> list[Rule]:
        law_id = law_id.lower()
        if law_id not in self._cache:
            self._cache[law_id] = self._load(law_id)
        return self._cache[law_id]

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

    def get_law_metadata(self, law_id: str) -> dict:
        """Return frontmatter metadata from the law file."""
        import frontmatter
        path = self.get_law_path(law_id)
        post = frontmatter.load(str(path))
        return dict(post.metadata)

    def _load(self, law_id: str) -> list[Rule]:
        path = self.get_law_path(law_id)
        rules = self._parser.parse(str(path))
        if not rules:
            raise ValueError(f"No rules found in law bundle: {path}")
        return rules
