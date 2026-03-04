from datetime import timedelta

from app.services.task_service import compute_deadline_flags, utcnow


def test_compute_deadline_flags_overdue() -> None:
    due_date = utcnow() - timedelta(days=1)
    state, urgency, is_overdue = compute_deadline_flags(
        due_date,
        yellow_days=3,
        normal_days=5,
    )

    assert state.value == "red"
    assert urgency.value == "overdue"
    assert is_overdue is True


def test_compute_deadline_flags_critical() -> None:
    due_date = utcnow() + timedelta(days=2)
    state, urgency, is_overdue = compute_deadline_flags(
        due_date,
        yellow_days=3,
        normal_days=5,
    )

    assert state.value == "yellow"
    assert urgency.value == "critical"
    assert is_overdue is False


def test_compute_deadline_flags_reserve() -> None:
    due_date = utcnow() + timedelta(days=6)
    state, urgency, is_overdue = compute_deadline_flags(
        due_date,
        yellow_days=3,
        normal_days=5,
    )

    assert state.value == "green"
    assert urgency.value == "reserve"
    assert is_overdue is False
