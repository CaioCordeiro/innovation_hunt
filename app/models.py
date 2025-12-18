from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    phone_number: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    category: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # LEAD/TALENT/PARTNER
    raw_profile_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connector_phone: Mapped[str] = mapped_column(String(32), ForeignKey("users.phone_number"), index=True)
    connectee_phone: Mapped[str] = mapped_column(String(32), ForeignKey("users.phone_number"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("connector_phone", "connectee_phone", name="uq_connection_once"),
        CheckConstraint("connector_phone <> connectee_phone", name="ck_no_self_connect"),
    )


class Event(Base):
    __tablename__ = "events"

    event_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    point_value: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
