from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from app.database import engine
from app.models import Flight

with engine.begin() as connection:
    connection.execute(
        insert(Flight)
        .values(
            id=UUID("11111111-1111-4111-8111-111111111111"),
            flight_number="SU100",
            airline="Aeroflot",
            origin="SVO",
            destination="LED",
            departure_time=datetime(2026, 12, 1, 9, tzinfo=UTC),
            arrival_time=datetime(2026, 12, 1, 10, 30, tzinfo=UTC),
            total_seats=10,
            available_seats=10,
            price=Decimal("5000.00"),
            status="SCHEDULED",
        )
        .on_conflict_do_nothing()
    )
print("Demo flight: 11111111-1111-4111-8111-111111111111")
