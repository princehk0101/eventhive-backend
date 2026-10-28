
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import TicketTier
from .models import Booking
from .serializers import BookingSerializer
from .tasks import send_booking_confirmation_email


class BookingListCreateView(generics.ListCreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects
            .filter(user=self.request.user)
            .select_related("ticket_tier", "ticket_tier__event")
        )

    def create(self, request, *args, **kwargs):
        ticket_tier_id = request.data.get("ticket_tier")
        quantity = request.data.get("quantity")

        try:
            quantity = int(quantity)
            if quantity < 1:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"quantity": "Enter a valid positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not ticket_tier_id:
            return Response(
                {"ticket_tier": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            ticket_tier = get_object_or_404(
                TicketTier.objects.select_for_update().select_related("event"),
                pk=ticket_tier_id,
            )

            if ticket_tier.event.status != "approved":
                return Response(
                    {"error": "Tickets are available only for approved events."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if ticket_tier.event.organizer_id == request.user.id:
                return Response(
                    {"error": "Organizers cannot book tickets for their own event."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if ticket_tier.available_seats < quantity:
                return Response(
                    {"error": "Not enough seats available."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            booking = Booking.objects.create(
                user=request.user,
                ticket_tier=ticket_tier,
                quantity=quantity,
                total_price=ticket_tier.price * quantity,
                status=Booking.Status.PENDING,
                payment_deadline=timezone.now() + timedelta(minutes=10),
            )

            ticket_tier.available_seats -= quantity
            ticket_tier.save(update_fields=["available_seats"])

        serializer = self.get_serializer(booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BookingPaymentConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            booking = get_object_or_404(
                Booking.objects.select_for_update(),
                pk=pk,
                user=request.user,
            )

            if booking.status == Booking.Status.CONFIRMED:
                return Response(
                    {"message": "Payment is already confirmed.", "booking_id": booking.id},
                    status=status.HTTP_200_OK,
                )

            if booking.status != Booking.Status.PENDING:
                return Response(
                    {"error": "This booking cannot be paid."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if (
                booking.payment_deadline is None
                or timezone.now() >= booking.payment_deadline
            ):
                return Response(
                    {"error": "Payment deadline has passed. Booking will expire."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            booking.status = Booking.Status.CONFIRMED
            booking.save(update_fields=["status"])

            transaction.on_commit(
                lambda booking_id=booking.id:
                    send_booking_confirmation_email.delay(booking_id)
            )

        return Response(
            {
                "message": "Mock payment successful.",
                "booking_id": booking.id,
                "status": booking.status,
            },
            status=status.HTTP_200_OK,
        )


class BookingCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            booking = get_object_or_404(
                Booking.objects.select_for_update(),
                pk=pk,
                user=request.user,
            )

            if booking.status == Booking.Status.CANCELLED:
                return Response(
                    {"error": "Booking is already cancelled."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if booking.status in (
                Booking.Status.EXPIRED,
                Booking.Status.PENDING,
            ):
                # Pending bookings have already reserved seats.
                # Release them here only when the booking is still pending.
                if booking.status == Booking.Status.PENDING:
                    tier = TicketTier.objects.select_for_update().get(
                        pk=booking.ticket_tier_id
                    )
                    tier.available_seats = min(
                        tier.total_seats,
                        tier.available_seats + booking.quantity,
                    )
                    tier.save(update_fields=["available_seats"])

                booking.status = Booking.Status.CANCELLED
                booking.save(update_fields=["status"])

                return Response(
                    {
                        "message": "Booking cancelled successfully.",
                        "booking_id": booking.id,
                        "status": booking.status,
                    },
                    status=status.HTTP_200_OK,
                )

            tier = TicketTier.objects.select_for_update().get(
                pk=booking.ticket_tier_id
            )
            tier.available_seats = min(
                tier.total_seats,
                tier.available_seats + booking.quantity,
            )
            tier.save(update_fields=["available_seats"])

            booking.status = Booking.Status.CANCELLED
            booking.save(update_fields=["status"])

        return Response(
            {
                "message": "Booking cancelled successfully.",
                "booking_id": booking.id,
                "status": booking.status,
                "available_seats": tier.available_seats,
            },
            status=status.HTTP_200_OK,
        )
