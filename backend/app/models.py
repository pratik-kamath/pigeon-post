from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, Index, String, text,
)
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


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))

    __table_args__ = (
        # Case-insensitive uniqueness; usernames are ASCII-only so SQLite's
        # ASCII-only lower() is sufficient.
        Index("ux_users_username_lower", text("lower(username)"), unique=True),
        Index("ux_users_email_lower", text("lower(email)"), unique=True),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
