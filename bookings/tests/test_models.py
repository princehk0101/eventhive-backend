
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from events.models import Event, TicketTier
from bookings.models import Booking


User = get_user_model()


class BookingModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizer = User.objects.create_user(
            username="organizer_test",
            email="organizer_test@example.com",
            password="TestPass123!",
            role="organizer",
        )

        cls.attendee = User.objects.create_user(
            username="attendee_test",
            email="attendee_test@example.com",
            password="TestPass123!",
            role="attendee",
        )

        cls.event = Event.objects.create(
            organizer=cls.organizer,
            title="Python Meetup Test",
            description="Test event",
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

    def test_booking_creation(self):
        booking = Booking.objects.create(
            user=self.attendee,
            ticket_tier=self.ticket_tier,
            quantity=2,
            total_price=Decimal("998.00"),
        )

        self.assertEqual(booking.quantity, 2)
        self.assertEqual(booking.total_price, Decimal("998.00"))
        self.assertEqual(booking.status, Booking.Status.PENDING)

    def test_booking_belongs_to_attendee(self):
        booking = Booking.objects.create(
            user=self.attendee,
            ticket_tier=self.ticket_tier,
            quantity=1,
            total_price=Decimal("499.00"),
        )

        self.assertEqual(booking.user, self.attendee)
        self.assertEqual(booking.ticket_tier, self.ticket_tier)
