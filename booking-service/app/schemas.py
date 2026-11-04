from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BookingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=255)
    flight_id: UUID
    passenger_name: str = Field(min_length=1, max_length=255)
    passenger_email: EmailStr = Field(max_length=320)
    seat_count: int = Field(gt=0, le=2147483647, strict=True)


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    flight_id: UUID
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: Decimal
    status: Literal["CONFIRMED", "CANCELLED"]
    created_at: datetime


class FlightResponse(BaseModel):
    id: UUID
    flight_number: str
    airline: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    total_seats: int
    available_seats: int
    price: Decimal
    status: Literal["SCHEDULED", "DEPARTED", "CANCELLED", "COMPLETED"]


class FlightUpdate(BaseModel):
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    status: Literal["SCHEDULED", "DEPARTED", "CANCELLED", "COMPLETED"] | None = None
