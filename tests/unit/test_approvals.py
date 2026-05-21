from __future__ import annotations

from uuid import uuid4

import pytest

from packages.persistence.approvals import ApprovalTransition, create_revision


def test_legal_transition_pending_to_approved():
    t = ApprovalTransition(from_status="pending", to_status="approved")
    assert t.to_status == "approved"


def test_legal_transition_pending_to_rejected():
    t = ApprovalTransition(from_status="pending", to_status="rejected")
    assert t.to_status == "rejected"


def test_legal_transition_pending_to_needs_revision():
    t = ApprovalTransition(from_status="pending", to_status="needs_revision")
    assert t.to_status == "needs_revision"


def test_legal_transition_pending_to_expired():
    t = ApprovalTransition(from_status="pending", to_status="expired")
    assert t.to_status == "expired"


def test_illegal_transition_approved_to_pending():
    with pytest.raises(ValueError, match="Illegal transition"):
        ApprovalTransition(from_status="approved", to_status="pending")


def test_illegal_transition_rejected_to_approved():
    with pytest.raises(ValueError, match="Illegal transition"):
        ApprovalTransition(from_status="rejected", to_status="approved")


def test_create_revision_links_parent():
    parent_id = uuid4()
    rec_id = uuid4()
    new_record = create_revision(parent_id, rec_id)
    assert new_record.status == "pending"
    assert new_record.parent_approval_id == parent_id
    assert new_record.recommendation_id == rec_id
    assert new_record.id != parent_id


def test_create_revision_generates_new_id():
    parent_id = uuid4()
    rec_id = uuid4()
    r1 = create_revision(parent_id, rec_id)
    r2 = create_revision(parent_id, rec_id)
    assert r1.id != r2.id
