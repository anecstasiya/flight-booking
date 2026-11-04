import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("flight_id", sa.Uuid(), nullable=False),
        sa.Column("passenger_name", sa.String(length=255), nullable=False),
        sa.Column("passenger_email", sa.String(length=320), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="CONFIRMED", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('CONFIRMED', 'CANCELLED')", name="ck_bookings_status"
        ),
        sa.CheckConstraint("seat_count > 0", name="ck_bookings_seat_count"),
        sa.CheckConstraint("total_price > 0", name="ck_bookings_total_price"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_user_id"), "bookings", ["user_id"], unique=False)


def downgrade():
    op.drop_table("bookings")
