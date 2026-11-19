"""Business-hours arithmetic and SLA state for work orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

AT_RISK_FRACTION = 0.75


@dataclass(frozen=True)
class Policy:
    """Working calendar and SLA targets, in business hours per priority."""

    day_start: time = time(8, 0)
    day_end: time = time(17, 0)
    holidays: frozenset[date] = field(default_factory=frozenset)
    sla_hours: dict[str, float] = field(default_factory=lambda: {
        "emergency": 4.0, "high": 8.0, "medium": 24.0, "low": 72.0})

    def is_workday(self, day: date) -> bool:
        """Monday to Friday and not a listed holiday."""
        return day.weekday() < 5 and day not in self.holidays


@dataclass(frozen=True)
class Assessment:
    """SLA position of one ticket at a given moment."""

    ticket_id: str
    priority: str
    deadline: datetime
    elapsed_hours: float
    target_hours: float
    state: str  # met, late, ok, at-risk, breached

    @property
    def percent_used(self) -> int:
        return round(100 * self.elapsed_hours / self.target_hours)


def next_open(moment: datetime, policy: Policy) -> datetime:
    """Return moment if inside working hours, else the next opening time."""
    current = moment
    while True:
        day = current.date()
        if policy.is_workday(day):
            opening = datetime.combine(day, policy.day_start)
            closing = datetime.combine(day, policy.day_end)
            if current < opening:
                return opening
            if current < closing:
                return current
        current = datetime.combine(day + timedelta(days=1), policy.day_start)


def add_business_hours(start: datetime, hours: float, policy: Policy) -> datetime:
    """Move forward by a number of business hours, skipping nights, weekends and holidays."""
    if hours < 0:
        raise ValueError("hours must not be negative")
    current = next_open(start, policy)
    remaining = hours * 3600
    while True:
        closing = datetime.combine(current.date(), policy.day_end)
        available = (closing - current).total_seconds()
        if remaining <= available:
            return current + timedelta(seconds=remaining)
        remaining -= available
        current = next_open(closing, policy)


def business_hours_between(start: datetime, end: datetime, policy: Policy) -> float:
    """Business hours elapsed from start to end; 0.0 when end is not after start."""
    if end <= start:
        return 0.0
    total = 0.0
    day = start.date()
    while day <= end.date():
        if policy.is_workday(day):
            opening = max(start, datetime.combine(day, policy.day_start))
            closing = min(end, datetime.combine(day, policy.day_end))
            if closing > opening:
                total += (closing - opening).total_seconds()
        day += timedelta(days=1)
    return total / 3600


def assess(ticket_id: str, priority: str, opened: datetime, closed: datetime | None,
           now: datetime, policy: Policy) -> Assessment:
    """Classify a ticket. Closed tickets are met or late; open ones ok, at-risk or breached."""
    key = priority.strip().lower()
    if key not in policy.sla_hours:
        raise ValueError(f"unknown priority '{priority}'")
    target = policy.sla_hours[key]
    deadline = add_business_hours(opened, target, policy)
    stop = closed if closed is not None else now
    elapsed = business_hours_between(opened, stop, policy)
    if closed is not None:
        state = "met" if closed <= deadline else "late"
    elif now > deadline:
        state = "breached"
    elif elapsed >= AT_RISK_FRACTION * target:
        state = "at-risk"
    else:
        state = "ok"
    return Assessment(ticket_id, key, deadline, round(elapsed, 2), target, state)
