import logging
from datetime import UTC, datetime
from datetime import date as Date
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from contracts import flight_pb2 as pb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import engine
from app.flight_client import call_flight, flight_data
from app.models import Booking
from app.schemas import BookingRequest, BookingResponse, FlightResponse, FlightUpdate

app = FastAPI(title="Booking Service")
logger = logging.getLogger(__name__)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.get("/health", tags=["health"])
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "service": "booking-service"}


@app.get("/flights", response_model=list[FlightResponse])
def search_flights(
    origin: Annotated[str, Query(pattern=r"^[A-Z]{3}$")],
    destination: Annotated[str, Query(pattern=r"^[A-Z]{3}$")],
    date: Date | None = None,
):
    request = pb.SearchFlightsRequest(origin=origin, destination=destination)
    if date is not None:
        request.date.FromDatetime(
            datetime.combine(date, datetime.min.time(), tzinfo=UTC)
        )
    response = call_flight("SearchFlights", request)
    return [flight_data(flight) for flight in response.flights]


@app.get("/flights/{flight_id}", response_model=FlightResponse)
def get_flight(flight_id: UUID):
    return flight_data(
        call_flight("GetFlight", pb.GetFlightRequest(flight_id=str(flight_id)))
    )


@app.post("/bookings", response_model=BookingResponse, status_code=201)
def create_booking(body: BookingRequest):
    flight = call_flight(
        "GetFlight", pb.GetFlightRequest(flight_id=str(body.flight_id))
    )
    booking_id = uuid4()
    call_flight(
        "ReserveSeats",
        pb.ReserveSeatsRequest(
            flight_id=str(body.flight_id),
            booking_id=str(booking_id),
            seat_count=body.seat_count,
        ),
    )
    try:
        with Session(engine) as session, session.begin():
            booking = Booking(
                id=booking_id,
                user_id=body.user_id,
                flight_id=body.flight_id,
                passenger_name=body.passenger_name,
                passenger_email=str(body.passenger_email),
                seat_count=body.seat_count,
                total_price=Decimal(flight.price) * body.seat_count,
                status="CONFIRMED",
            )
            session.add(booking)
            session.flush()
            response = BookingResponse.model_validate(booking)
        return response
    except SQLAlchemyError:
        try:
            call_flight(
                "ReleaseReservation",
                pb.ReleaseReservationRequest(booking_id=str(booking_id)),
            )
        except HTTPException:
            logger.exception("Could not release reservation %s", booking_id)
        raise


@app.patch("/flights/{flight_id}", response_model=FlightResponse)
def update_flight(flight_id: UUID, body: FlightUpdate):
    values = body.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status_code=422, detail="Provide price or status")
    request = pb.UpdateFlightRequest(flight_id=str(flight_id))
    if body.price is not None:
        request.price = str(body.price)
    if body.status is not None:
        request.status = pb.FlightStatus.Value(body.status)
    return flight_data(call_flight("UpdateFlight", request))


@app.get("/bookings", response_model=list[BookingResponse])
def list_bookings(user_id: Annotated[str, Query(min_length=1, max_length=255)]):
    with Session(engine) as session:
        bookings = session.scalars(
            select(Booking)
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc(), Booking.id)
        )
        return [BookingResponse.model_validate(booking) for booking in bookings]


@app.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: UUID):
    with Session(engine) as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        return BookingResponse.model_validate(booking)


@app.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(booking_id: UUID):
    with Session(engine) as session, session.begin():
        booking = session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=409, detail="Booking is already cancelled")
        call_flight(
            "ReleaseReservation",
            pb.ReleaseReservationRequest(booking_id=str(booking_id)),
        )
        booking.status = "CANCELLED"
        response = BookingResponse.model_validate(booking)
    return response
