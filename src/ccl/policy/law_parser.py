"""Parse .md law bundle files into Rule objects."""
from __future__ import annotations

import re
from pathlib import Path

import frontmatter

from ccl.models import Rule, RuleAction, Severity


# Matches a rule block like:
# - rule_id: KR-PIPA-ART23-001
# - severity: HIGH
# - article: ...
# - description: ...
# - condition: any_column(category='sensitive', masked=False)
# - action: FAIL
_RULE_BLOCK_RE = re.compile(
    r"-\s*rule_id:\s*(?P<rule_id>\S+).*?"
    r"(?:-\s*severity:\s*(?P<severity>\S+).*?)?"
    r"(?:-\s*article:\s*(?P<article>[^\n]+).*?)?"
    r"(?:-\s*description:\s*(?P<description>[^\n]+).*?)?"
    r"-\s*condition:\s*(?P<condition>[^\n]+).*?"
    r"-\s*action:\s*(?P<action>\S+)",
    re.DOTALL,
)


class LawParser:
    def parse(self, path: str) -> list[Rule]:
        """Parse a .md law file and return a list of Rule objects."""
        text = Path(path).read_text(encoding="utf-8")
        return self.parse_text(text, law_id=Path(path).stem)

    def parse_text(self, text: str, law_id: str) -> list[Rule]:
        """Parse law bundle text and return a list of Rule objects."""
        post = frontmatter.loads(text)
        actual_law_id = post.metadata.get("law_id", law_id)

        rules = []
        for m in _RULE_BLOCK_RE.finditer(post.content):
            try:
                severity = Severity(m.group("severity") or "HIGH")
            except ValueError:
                severity = Severity.HIGH
            try:
                action = RuleAction(m.group("action") or "FAIL")
            except ValueError:
                action = RuleAction.FAIL

            rules.append(Rule(
                rule_id=m.group("rule_id").strip(),
                law_id=actual_law_id,
                severity=severity,
                article=(m.group("article") or "").strip(),
                description=(m.group("description") or "").strip(),
                condition=m.group("condition").strip(),
                action=action,
            ))
        return rules
