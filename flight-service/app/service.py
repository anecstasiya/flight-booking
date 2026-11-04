import re
import uuid
from datetime import UTC
from decimal import Decimal, InvalidOperation

import grpc
from contracts import flight_pb2 as pb
from contracts import flight_pb2_grpc as rpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import Date, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Flight, SeatReservation


def parse_id(value, context):
    try:
        return uuid.UUID(value)
    except ValueError:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID")


def timestamp(value):
    result = Timestamp()
    result.FromDatetime(value)
    return result


def flight_message(flight):
    return pb.Flight(
        id=str(flight.id),
        flight_number=flight.flight_number,
        airline=flight.airline,
        origin=flight.origin,
        destination=flight.destination,
        departure_time=timestamp(flight.departure_time),
        arrival_time=timestamp(flight.arrival_time),
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        price=str(flight.price),
        status=pb.FlightStatus.Value(flight.status),
    )


def reservation_message(reservation):
    return pb.SeatReservation(
        id=str(reservation.id),
        flight_id=str(reservation.flight_id),
        booking_id=str(reservation.booking_id),
        seat_count=reservation.seat_count,
        status=pb.ReservationStatus.Value(reservation.status),
        created_at=timestamp(reservation.created_at),
    )


class FlightService(rpc.FlightServiceServicer):
    def SearchFlights(self, request, context):
        if not all(
            re.fullmatch(r"[A-Z]{3}", code)
            for code in (request.origin, request.destination)
        ):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid IATA code")
        query = select(Flight).where(
            Flight.origin == request.origin,
            Flight.destination == request.destination,
            Flight.status == "SCHEDULED",
        )
        if request.HasField("date"):
            try:
                date = request.date.ToDatetime(tzinfo=UTC).date()
            except (ValueError, OverflowError):
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid date")
            query = query.where(
                cast(func.timezone("UTC", Flight.departure_time), Date) == date
            )
        with Session(engine) as session:
            flights = session.scalars(query.order_by(Flight.departure_time, Flight.id))
            return pb.SearchFlightsResponse(
                flights=[flight_message(flight) for flight in flights]
            )

    def GetFlight(self, request, context):
        flight_id = parse_id(request.flight_id, context)
        with Session(engine) as session:
            flight = session.get(Flight, flight_id)
            if flight is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
            return flight_message(flight)

    def UpdateFlight(self, request, context):
        flight_id = parse_id(request.flight_id, context)
        values = {}
        try:
            if request.HasField("price"):
                price = Decimal(request.price)
                if (
                    not price.is_finite()
                    or not 0 < price < 10**10
                    or price != price.quantize(Decimal("0.01"))
                ):
                    raise ValueError()
                values["price"] = price
            if request.HasField("status"):
                status = pb.FlightStatus.Name(request.status)
                if status == "FLIGHT_STATUS_UNSPECIFIED":
                    raise ValueError()
                values["status"] = status
            if not values:
                raise ValueError()
        except (ValueError, InvalidOperation):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid flight update")
        with Session(engine) as session, session.begin():
            flight = session.scalar(
                select(Flight).where(Flight.id == flight_id).with_for_update()
            )
            if flight is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
            for field, value in values.items():
                setattr(flight, field, value)
            response = flight_message(flight)
        return response

    def ReserveSeats(self, request, context):
        flight_id = parse_id(request.flight_id, context)
        booking_id = parse_id(request.booking_id, context)
        if request.seat_count <= 0:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "seat_count must be positive"
            )
        try:
            with Session(engine) as session, session.begin():
                flight = session.scalar(
                    select(Flight).where(Flight.id == flight_id).with_for_update()
                )
                if flight is None:
                    context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
                reservation = session.scalar(
                    select(SeatReservation).where(
                        SeatReservation.booking_id == booking_id
                    )
                )
                if reservation is not None:
                    if (
                        reservation.flight_id != flight_id
                        or reservation.seat_count != request.seat_count
                    ):
                        context.abort(
                            grpc.StatusCode.ALREADY_EXISTS,
                            "booking_id already used for another reservation",
                        )
                    if reservation.status != "ACTIVE":
                        context.abort(
                            grpc.StatusCode.FAILED_PRECONDITION,
                            "Reservation is no longer active",
                        )
                    return reservation_message(reservation)
                if flight.status != "SCHEDULED":
                    context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION, "Flight is not scheduled"
                    )
                if flight.available_seats < request.seat_count:
                    context.abort(
                        grpc.StatusCode.RESOURCE_EXHAUSTED, "Not enough seats"
                    )
                flight.available_seats -= request.seat_count
                reservation = SeatReservation(
                    flight_id=flight_id,
                    booking_id=booking_id,
                    seat_count=request.seat_count,
                    status="ACTIVE",
                )
                session.add(reservation)
                session.flush()
                response = reservation_message(reservation)
            return response
        except IntegrityError:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "booking_id already used")

    def ReleaseReservation(self, request, context):
        booking_id = parse_id(request.booking_id, context)
        with Session(engine) as session, session.begin():
            reservation = session.scalar(
                select(SeatReservation)
                .where(SeatReservation.booking_id == booking_id)
                .with_for_update()
            )
            if reservation is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Reservation not found")
            if reservation.status == "RELEASED":
                return reservation_message(reservation)
            if reservation.status != "ACTIVE":
                context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION, "Reservation is not active"
                )
            flight = session.scalar(
                select(Flight)
                .where(Flight.id == reservation.flight_id)
                .with_for_update()
            )
            flight.available_seats += reservation.seat_count
            reservation.status = "RELEASED"
            session.flush()
            response = reservation_message(reservation)
        return response
