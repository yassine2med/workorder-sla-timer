from datetime import date, datetime

import pytest

from slatimer import Policy, add_business_hours, assess, business_hours_between
from slatimer.cli import main

P = Policy()


def dt(text):
    return datetime.fromisoformat(text)


def test_add_within_one_day():
    assert add_business_hours(dt("2026-03-02T09:00"), 3, P) == dt("2026-03-02T12:00")


def test_add_rolls_over_night():
    assert add_business_hours(dt("2026-03-02T15:00"), 4, P) == dt("2026-03-03T10:00")


def test_add_skips_weekend():
    # Friday 16:00 + 2h = 1h Friday, 1h Monday morning
    assert add_business_hours(dt("2026-02-27T16:00"), 2, P) == dt("2026-03-02T09:00")


def test_start_outside_hours_moves_to_opening():
    assert add_business_hours(dt("2026-03-01T12:00"), 1, P) == dt("2026-03-02T09:00")
    assert add_business_hours(dt("2026-03-02T06:00"), 1, P) == dt("2026-03-02T09:00")


def test_holiday_is_skipped():
    holiday = Policy(holidays=frozenset({date(2026, 3, 3)}))
    assert add_business_hours(dt("2026-03-02T16:00"), 2, holiday) == dt("2026-03-04T09:00")


def test_ending_exactly_at_close():
    assert add_business_hours(dt("2026-03-02T13:00"), 4, P) == dt("2026-03-02T17:00")


def test_negative_hours_rejected():
    with pytest.raises(ValueError):
        add_business_hours(dt("2026-03-02T09:00"), -1, P)


def test_hours_between_spans_weekend():
    assert business_hours_between(dt("2026-02-27T15:00"), dt("2026-03-02T10:00"), P) == 4.0
    assert business_hours_between(dt("2026-03-02T10:00"), dt("2026-03-02T10:00"), P) == 0.0


def test_states_for_open_tickets():
    opened = dt("2026-03-02T09:00")  # high: 8h, deadline Mon 17:00
    assert assess("a", "High", opened, None, dt("2026-03-02T10:00"), P).state == "ok"
    assert assess("a", "High", opened, None, dt("2026-03-02T15:30"), P).state == "at-risk"
    assert assess("a", "High", opened, None, dt("2026-03-03T08:30"), P).state == "breached"


def test_states_for_closed_tickets():
    opened = dt("2026-03-02T09:00")
    assert assess("a", "high", opened, dt("2026-03-02T16:00"), dt("2026-03-09T09:00"), P).state == "met"
    assert assess("a", "high", opened, dt("2026-03-03T09:00"), dt("2026-03-09T09:00"), P).state == "late"


def test_unknown_priority_raises():
    with pytest.raises(ValueError):
        assess("a", "urgent", dt("2026-03-02T09:00"), None, dt("2026-03-02T10:00"), P)


def test_cli_exit_codes_and_bad_rows(tmp_path, capsys):
    good = tmp_path / "t.csv"
    good.write_text("ticket_id,priority,opened,closed\nT1,High,2026-03-02T09:00,\nT2,Bogus,2026-03-02T09:00,\n")
    assert main([str(good), "--now", "2026-03-05T09:00"]) == 1
    captured = capsys.readouterr()
    assert "breached" in captured.out and "skipped line 3" in captured.err
    assert main([str(good), "--now", "2026-03-02T10:00"]) == 0
    assert main([str(tmp_path / "missing.csv")]) == 2
