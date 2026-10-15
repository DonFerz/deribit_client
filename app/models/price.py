from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Price(Base):
    """ORM-модель сохранённой index-цены тикера.

    Уникальность `(ticker, timestamp)` защищает от дубликатов при
    повторной доставке Celery-задачи (task_acks_late=True).
    Timestamp хранится в миллисекундах UTC, как его отдаёт Deribit.
    """

    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("ticker", "timestamp", name="uq_prices_ticker_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)

    def __repr__(self) -> str:
        return (
            f"Price(id={self.id!r}, ticker={self.ticker!r}, "
            f"price={self.price!r}, timestamp={self.timestamp!r})"
        )
