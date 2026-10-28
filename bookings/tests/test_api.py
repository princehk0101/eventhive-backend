
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from events.models import Event, TicketTier
from bookings.models import Booking

User = get_user_model()


class BookingAPITests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.organizer = User.objects.create_user(
            username="api_organizer",
            email="api_organizer@example.com",
            password="TestPass123!",
            role="organizer",
        )

        cls.attendee = User.objects.create_user(
            username="api_attendee",
            email="api_attendee@example.com",
            password="TestPass123!",
            role="attendee",
        )

        cls.other_attendee = User.objects.create_user(
            username="other_attendee",
            email="other_attendee@example.com",
            password="TestPass123!",
            role="attendee",
        )

        cls.event = Event.objects.create(
            organizer=cls.organizer,
            title="API Test Meetup",
            description="Testing booking API",
            faq="No FAQ",
            city="Lucknow",
            category="Technology",
            start_time=timezone.now() + timedelta(days=30),
            status=Event.Status.APPROVED,
        )

        cls.ticket_tier = TicketTier.objects.create(
            event=cls.event,
            name="General",
            price=Decimal("499.00"),
            total_seats=10,
            available_seats=10,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.attendee)
        self.url = "/api/bookings/"

    def test_attendee_can_book_tickets(self):
        response = self.client.post(
            self.url,
            {
                "ticket_tier": self.ticket_tier.id,
                "quantity": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Decimal(response.data["total_price"]),
            Decimal("998.00"),
        )
        self.assertEqual(
            response.data["status"],
            Booking.Status.PENDING,
        )

        self.ticket_tier.refresh_from_db()
        self.assertEqual(self.ticket_tier.available_seats, 8)

    def test_booking_fails_when_seats_are_insufficient(self):
        response = self.client.post(
            self.url,
            {
                "ticket_tier": self.ticket_tier.id,
                "quantity": 11,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Booking.objects.exists())

        self.ticket_tier.refresh_from_db()
        self.assertEqual(self.ticket_tier.available_seats, 10)

    def test_attendee_can_cancel_own_booking(self):
        self.ticket_tier.available_seats = 8
        self.ticket_tier.save(update_fields=["available_seats"])

        booking = Booking.objects.create(
            user=self.attendee,
            ticket_tier=self.ticket_tier,
            quantity=2,
            total_price=Decimal("998.00"),
        )

        response = self.client.post(
            f"/api/bookings/{booking.id}/cancel/",
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        booking.refresh_from_db()
        self.ticket_tier.refresh_from_db()

        self.assertEqual(
            booking.status,
            Booking.Status.CANCELLED,
        )
        self.assertEqual(self.ticket_tier.available_seats, 10)

    def test_attendee_cannot_cancel_another_users_booking(self):
        booking = Booking.objects.create(
            user=self.other_attendee,
            ticket_tier=self.ticket_tier,
            quantity=1,
            total_price=Decimal("499.00"),
        )

        response = self.client.post(
            f"/api/bookings/{booking.id}/cancel/",
            format="json",
        )

        self.assertEqual(response.status_code, 404)

        booking.refresh_from_db()
        self.assertEqual(
            booking.status,
            Booking.Status.PENDING,
        )


    def test_attendee_can_confirm_payment(self):
        booking_response = self.client.post(
            self.url,
            {
                "ticket_tier": self.ticket_tier.id,
                "quantity": 2,
            },
            format="json",
        )
        self.assertEqual(booking_response.status_code, 201)

        booking_id = booking_response.data["id"]

        payment_response = self.client.post(
            f"/api/bookings/{booking_id}/confirm-payment/",
            format="json",
        )

        self.assertEqual(payment_response.status_code, 200)

        booking = Booking.objects.get(id=booking_id)
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_expired_booking_cannot_be_paid(self):
        booking_response = self.client.post(
            self.url,
            {
                "ticket_tier": self.ticket_tier.id,
                "quantity": 1,
            },
            format="json",
        )
        self.assertEqual(booking_response.status_code, 201)

        booking = Booking.objects.get(id=booking_response.data["id"])
        booking.payment_deadline = timezone.now() - timedelta(minutes=1)
        booking.save(update_fields=["payment_deadline"])

        payment_response = self.client.post(
            f"/api/bookings/{booking.id}/confirm-payment/",
            format="json",
        )

        self.assertEqual(payment_response.status_code, 400)

    def test_another_user_cannot_confirm_payment(self):
        booking = Booking.objects.create(
            user=self.other_attendee,
            ticket_tier=self.ticket_tier,
            quantity=1,
            total_price=Decimal("499.00"),
            payment_deadline=timezone.now() + timedelta(minutes=10),
        )

        payment_response = self.client.post(
            f"/api/bookings/{booking.id}/confirm-payment/",
            format="json",
        )

        self.assertEqual(payment_response.status_code, 404)

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)
