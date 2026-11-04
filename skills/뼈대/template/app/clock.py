"""시각 — 고치지 않는 곳.

서버 시각은 UTC 일 수 있다(컨테이너). '오늘'·'지금'은 언제나 APP_UTC_OFFSET 기준으로 본다.
자정을 넘는 구간(22:00~06:00)은 시작한 날의 날짜에 속한다. 새벽 03:00 에 보는 사람의 '오늘 일정'은 어제 날짜다.
"""
import os
from datetime import date, datetime, timedelta, timezone


def _tz():
    s = os.environ.get("APP_UTC_OFFSET", "+09:00")
    sign = -1 if s.startswith("-") else 1
    h, m = s.lstrip("+-").split(":")
    return timezone(sign * timedelta(hours=int(h), minutes=int(m)))


def now():
    """APP_NOW=2026-01-05T03:10 으로 고정해 확인할 수 있다."""
    fixed = os.environ.get("APP_NOW")
    if fixed:
        return datetime.fromisoformat(fixed).replace(tzinfo=_tz())
    return datetime.now(_tz())


def span(day, start, end):
    """(날짜, 'HH:MM', 'HH:MM') → (시작 datetime, 끝 datetime). 끝 <= 시작 이면 다음 날 끝."""
    d = date.fromisoformat(day) if isinstance(day, str) else day
    s = datetime.combine(d, datetime.strptime(start, "%H:%M").time(), _tz())
    e = datetime.combine(d, datetime.strptime(end, "%H:%M").time(), _tz())
    if e <= s:
        e += timedelta(days=1)
    return s, e


def item_span(it):
    return span(it.get("day") or it["date"], it["start"], it["end"])


def work_date(items, at=None):
    """items: [{date,start,end[,day]}]. 지금 걸쳐 있는 구간의 date(묶는 날짜), 없으면 오늘(현지).
    day 가 있으면 그 항목의 시작 시각은 day 날짜다(묶는 날짜 다음 날 새벽에 시작하는 항목)."""
    at = at or now()
    for it in items:
        s, e = item_span(it)
        if s <= at < e:
            return it["date"]
    return at.date().isoformat()


def days(date_from, date_to):
    d, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)
