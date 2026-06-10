from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

IN_FLIGHT = "in_flight"
DELIVERED = "delivered"
LOST = "lost"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender: Mapped[str] = mapped_column(String(50), index=True)
    recipient: Mapped[str] = mapped_column(String(50))
    body: Mapped[str] = mapped_column(String(500))
    origin: Mapped[str] = mapped_column(String(50))
    destination: Mapped[str] = mapped_column(String(50))
    distance_km: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default=IN_FLIGHT)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_flight', 'delivered', 'lost')",
            name="ck_messages_status",
        ),
        Index("ix_messages_status_arrival_at", "status", "arrival_at"),
        Index("ix_messages_recipient_status", "recipient", "status"),
    )
