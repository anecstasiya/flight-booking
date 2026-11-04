import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Flight(Base):
    __tablename__ = "flights"
    __table_args__ = (
        Index(
            "uq_flight_number_date",
            "flight_number",
            text("((departure_time AT TIME ZONE 'UTC')::date)"),
            unique=True,
        ),
        CheckConstraint("total_seats > 0", name="ck_flights_total_seats"),
        CheckConstraint(
            "available_seats >= 0 AND available_seats <= total_seats",
            name="ck_flights_available_seats",
        ),
        CheckConstraint("price > 0", name="ck_flights_price"),
        CheckConstraint("arrival_time > departure_time", name="ck_flights_times"),
        CheckConstraint("origin <> destination", name="ck_flights_route"),
        CheckConstraint("origin ~ '^[A-Z]{3}$'", name="ck_flights_origin_iata"),
        CheckConstraint(
            "destination ~ '^[A-Z]{3}$'", name="ck_flights_destination_iata"
        ),
        CheckConstraint(
            "status IN ('SCHEDULED', 'DEPARTED', 'CANCELLED', 'COMPLETED')",
            name="ck_flights_status",
        ),
        Index("ix_flights_search", "origin", "destination", "departure_time", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    flight_number: Mapped[str] = mapped_column(String(16))
    airline: Mapped[str] = mapped_column(String(255))
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total_seats: Mapped[int] = mapped_column(Integer)
    available_seats: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(16), server_default="SCHEDULED")


class SeatReservation(Base):
    __tablename__ = "seat_reservations"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_reservation_booking"),
        CheckConstraint("seat_count > 0", name="ck_reservations_seat_count"),
        CheckConstraint(
            "status IN ('ACTIVE', 'RELEASED', 'EXPIRED')", name="ck_reservations_status"
        ),
        Index("ix_reservations_flight_id", "flight_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    flight_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("flights.id", ondelete="RESTRICT")
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    seat_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
