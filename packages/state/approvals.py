from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

ApprovalStatus = Literal["pending", "approved", "rejected", "needs_revision", "expired"]

_LEGAL_TRANSITIONS: dict[ApprovalStatus, set[ApprovalStatus]] = {
    "pending": {"approved", "rejected", "needs_revision", "expired"},
    "approved": set(),
    "rejected": set(),
    "needs_revision": set(),
    "expired": set(),
}


@dataclass
class ApprovalRecord:
    id: UUID
    recommendation_id: UUID
    status: ApprovalStatus
    parent_approval_id: UUID | None = None


@dataclass
class ApprovalTransition:
    from_status: ApprovalStatus
    to_status: ApprovalStatus

    def __post_init__(self) -> None:
        allowed = _LEGAL_TRANSITIONS.get(self.from_status, set())
        if self.to_status not in allowed:
            raise ValueError(
                f"Illegal transition: {self.from_status} -> {self.to_status}"
            )


def create_revision(parent_id: UUID, recommendation_id: UUID) -> ApprovalRecord:
    return ApprovalRecord(
        id=uuid4(),
        recommendation_id=recommendation_id,
        status="pending",
        parent_approval_id=parent_id,
    )
