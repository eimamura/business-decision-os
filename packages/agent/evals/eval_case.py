from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

_log = logging.getLogger(__name__)


class FailureMode(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["retrieval", "selection", "pollution", "routing", "reasoning", "output"]
    description: str


class ResponseAssertions(BaseModel):
    model_config = ConfigDict(frozen=True)

    must_contain: list[str]
    must_not_contain: list[str]


class EvalCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    spec_question: str
    intent: str
    required_tools: list[str]
    must_not_use_tools: list[str]
    response_assertions: ResponseAssertions
    expected_behavior: list[str]
    failure_modes: list[FailureMode]


def load_eval_cases(path: Path) -> list[EvalCase]:
    """Load and validate evaluation cases from a YAML file.

    Args:
        path: Absolute path to a YAML file containing a list of eval case dicts.

    Returns:
        A list of validated EvalCase objects, one per entry in the YAML file.

    Raises:
        FileNotFoundError: If the YAML file does not exist at the given path.
        pydantic.ValidationError: If any entry fails EvalCase schema validation.
        yaml.YAMLError: If the file is not valid YAML.
    """
    with path.open() as f:
        raw = yaml.safe_load(f)
    return [EvalCase.model_validate(case) for case in raw]
