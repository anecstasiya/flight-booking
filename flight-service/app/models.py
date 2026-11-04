import uuid

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Flight(Base):
    __tablename__ = "flights"
    __table_args__ = (
        sa.Index(
            "uq_flight_number_date",
            "flight_number",
            sa.text("((departure_time AT TIME ZONE 'UTC')::date)"),
            unique=True,
        ),
        sa.CheckConstraint("total_seats > 0", name="ck_flights_total_seats"),
        sa.CheckConstraint(
            "available_seats >= 0 AND available_seats <= total_seats",
            name="ck_flights_available_seats",
        ),
        sa.CheckConstraint("price > 0", name="ck_flights_price"),
        sa.CheckConstraint("arrival_time > departure_time", name="ck_flights_times"),
        sa.CheckConstraint("origin <> destination", name="ck_flights_route"),
        sa.CheckConstraint("origin ~ '^[A-Z]{3}$'", name="ck_flights_origin_iata"),
        sa.CheckConstraint(
            "destination ~ '^[A-Z]{3}$'", name="ck_flights_destination_iata"
        ),
        sa.CheckConstraint(
            "status IN ('SCHEDULED', 'DEPARTED', 'CANCELLED', 'COMPLETED')",
            name="ck_flights_status",
        ),
        sa.Index(
            "ix_flights_search", "origin", "destination", "departure_time", "status"
        ),
    )

    id = sa.Column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    flight_number = sa.Column(sa.String(16), nullable=False)
    airline = sa.Column(sa.String(255), nullable=False)
    origin = sa.Column(sa.String(3), nullable=False)
    destination = sa.Column(sa.String(3), nullable=False)
    departure_time = sa.Column(sa.DateTime(timezone=True), nullable=False)
    arrival_time = sa.Column(sa.DateTime(timezone=True), nullable=False)
    total_seats = sa.Column(sa.Integer, nullable=False)
    available_seats = sa.Column(sa.Integer, nullable=False)
    price = sa.Column(sa.Numeric(12, 2), nullable=False)
    status = sa.Column(sa.String(16), nullable=False, server_default="SCHEDULED")


class SeatReservation(Base):
    __tablename__ = "seat_reservations"
    __table_args__ = (
        sa.UniqueConstraint("booking_id", name="uq_reservation_booking"),
        sa.CheckConstraint("seat_count > 0", name="ck_reservations_seat_count"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RELEASED', 'EXPIRED')", name="ck_reservations_status"
        ),
        sa.Index("ix_reservations_flight_id", "flight_id"),
    )

    id = sa.Column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    flight_id = sa.Column(
        sa.Uuid, sa.ForeignKey("flights.id", ondelete="RESTRICT"), nullable=False
    )
    booking_id = sa.Column(sa.Uuid, nullable=False)
    seat_count = sa.Column(sa.Integer, nullable=False)
    status = sa.Column(sa.String(16), nullable=False, server_default="ACTIVE")
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
