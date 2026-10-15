from datetime import datetime, timezone


def datetime_to_unix_ms(dt: datetime) -> int:
    """Конвертирует datetime в UNIX timestamp (миллисекунды).

    Naive datetime трактуется как UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def now_unix_ms() -> int:
    """Текущее время в UNIX-миллисекундах (UTC)."""
    return datetime_to_unix_ms(datetime.now(tz=timezone.utc))
