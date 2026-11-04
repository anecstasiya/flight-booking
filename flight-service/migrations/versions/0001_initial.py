import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flight_number", sa.String(length=16), nullable=False),
        sa.Column("airline", sa.String(length=255), nullable=False),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_seats", sa.Integer(), nullable=False),
        sa.Column("available_seats", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="SCHEDULED", nullable=False
        ),
        sa.CheckConstraint(
            "destination ~ '^[A-Z]{3}$'", name="ck_flights_destination_iata"
        ),
        sa.CheckConstraint("origin ~ '^[A-Z]{3}$'", name="ck_flights_origin_iata"),
        sa.CheckConstraint(
            "status IN ('SCHEDULED', 'DEPARTED', 'CANCELLED', 'COMPLETED')",
            name="ck_flights_status",
        ),
        sa.CheckConstraint("arrival_time > departure_time", name="ck_flights_times"),
        sa.CheckConstraint(
            "available_seats >= 0 AND available_seats <= total_seats",
            name="ck_flights_available_seats",
        ),
        sa.CheckConstraint("origin <> destination", name="ck_flights_route"),
        sa.CheckConstraint("price > 0", name="ck_flights_price"),
        sa.CheckConstraint("total_seats > 0", name="ck_flights_total_seats"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "seat_reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flight_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="ACTIVE", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RELEASED', 'EXPIRED')", name="ck_reservations_status"
        ),
        sa.CheckConstraint("seat_count > 0", name="ck_reservations_seat_count"),
        sa.ForeignKeyConstraint(["flight_id"], ["flights.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id", name="uq_reservation_booking"),
    )
    op.create_index(
        "ix_flights_search",
        "flights",
        ["origin", "destination", "departure_time", "status"],
        unique=False,
    )
    op.create_index(
        "uq_flight_number_date",
        "flights",
        [
            "flight_number",
            sa.literal_column("((departure_time AT TIME ZONE 'UTC')::date)"),
        ],
        unique=True,
    )
    op.create_index(
        "ix_reservations_flight_id", "seat_reservations", ["flight_id"], unique=False
    )


def downgrade():
    op.drop_table("seat_reservations")
    op.drop_table("flights")
