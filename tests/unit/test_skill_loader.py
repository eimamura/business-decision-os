from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from packages.knowledge.skill_loader import SkillLoader


# ---------------------------------------------------------------------------
# T-287 — SkillLoader unit tests
# ---------------------------------------------------------------------------


def test_skill_loader_supply_chain_returns_nonempty_list() -> None:
    result = SkillLoader().load("supply_chain")
    assert len(result) >= 1


def test_skill_loader_supply_chain_returns_all_three_skills() -> None:
    result = SkillLoader().load("supply_chain")
    assert len(result) == 3


def test_skill_loader_unknown_intent_returns_empty_list() -> None:
    result = SkillLoader().load("unknown_intent_xyz")
    assert result == []


def test_skill_loader_chat_intent_returns_empty_list() -> None:
    result = SkillLoader().load("chat")
    assert result == []


def test_skill_loader_missing_file_silently_skipped() -> None:
    # Patch Path.exists so that the first skill file appears to be missing.
    original_exists = Path.exists

    call_count = 0

    def _fake_exists(self: Path) -> bool:
        nonlocal call_count
        if self.name == "stockout_risk_analysis.md":
            call_count += 1
            if call_count == 1:
                return False
        return original_exists(self)

    with patch.object(Path, "exists", _fake_exists):
        result = SkillLoader().load("supply_chain")

    # One file was skipped, so fewer than 3 items are returned and no error raised.
    assert len(result) < 3
    assert isinstance(result, list)
