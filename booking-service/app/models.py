import uuid

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        sa.CheckConstraint("seat_count > 0", name="ck_bookings_seat_count"),
        sa.CheckConstraint("total_price > 0", name="ck_bookings_total_price"),
        sa.CheckConstraint(
            "status IN ('CONFIRMED', 'CANCELLED')", name="ck_bookings_status"
        ),
    )

    id = sa.Column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id = sa.Column(sa.String(255), nullable=False, index=True)
    flight_id = sa.Column(sa.Uuid, nullable=False)
    passenger_name = sa.Column(sa.String(255), nullable=False)
    passenger_email = sa.Column(sa.String(320), nullable=False)
    seat_count = sa.Column(sa.Integer, nullable=False)
    total_price = sa.Column(sa.Numeric(14, 2), nullable=False)
    status = sa.Column(sa.String(16), nullable=False, server_default="CONFIRMED")
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
