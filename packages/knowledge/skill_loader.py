from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory containing Skill markdown files, co-located with this module.
_SKILLS_DIR = Path(__file__).parent / "skills"

# Intent-to-filename mapping declared explicitly in code.
# Keys are intent strings as returned by the intent classifier.
# Values are ordered lists of Skill filenames to load for that intent.
_INTENT_SKILL_MAP: dict[str, list[str]] = {
    "supply_chain": [
        "stockout_risk_analysis.md",
        "exception_detection.md",
        "shipment_delay_root_cause.md",
    ],
    "cross_domain_analysis": [
        "stockout_risk_analysis.md",
        "exception_detection.md",
    ],
    "domain_analysis": [
        "stockout_risk_analysis.md",
    ],
}


class SkillLoader:
    """Load Skill file contents for a given intent.

    Skills are markdown files that define standard analysis procedures.
    The ControlAgent injects the returned content into its LLM context
    before answering user queries, making analysis reproducible and auditable.
    """

    def load(self, intent: str) -> list[str]:
        """Return Skill file contents for the given intent.

        Parameters
        ----------
        intent:
            The classified intent string (e.g., ``"supply_chain"``).

        Returns
        -------
        list[str]
            Ordered list of Skill file contents as strings.
            Returns an empty list for unknown intents.
            Skill files that are mapped but do not exist on disk are silently skipped.
        """
        filenames = _INTENT_SKILL_MAP.get(intent, [])
        contents: list[str] = []
        for filename in filenames:
            skill_path = _SKILLS_DIR / filename
            if not skill_path.exists():
                logger.debug("Skill file not found, skipping: %s", skill_path)
                continue
            contents.append(skill_path.read_text(encoding="utf-8"))
        return contents
