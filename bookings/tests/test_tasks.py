
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from events.models import Event, TicketTier
from bookings.models import Booking
from bookings.tasks import expire_pending_bookings


User = get_user_model()


class BookingTaskTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="task_organizer",
            email="organizer@example.com",
            password="TestPass123!",
            role="organizer",
        )

        self.attendee = User.objects.create_user(
            username="task_attendee",
            email="attendee@example.com",
            password="TestPass123!",
            role="attendee",
        )

        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Task Test Event",
            description="Testing booking expiry",
            faq="No FAQ",
            city="Lucknow",
            category="Technology",
            start_time=timezone.now() + timedelta(days=30),
            status=Event.Status.APPROVED,
        )

        self.ticket_tier = TicketTier.objects.create(
            event=self.event,
            name="General",
            price=Decimal("499.00"),
            total_seats=10,
            available_seats=8,
        )

        self.booking = Booking.objects.create(
            user=self.attendee,
            ticket_tier=self.ticket_tier,
            quantity=2,
            total_price=Decimal("998.00"),
            status=Booking.Status.PENDING,
            payment_deadline=timezone.now() - timedelta(minutes=1),
        )

    def test_expired_pending_booking_releases_seats(self):
        result = expire_pending_bookings()

        self.booking.refresh_from_db()
        self.ticket_tier.refresh_from_db()

        self.assertEqual(self.booking.status, Booking.Status.EXPIRED)
        self.assertEqual(self.ticket_tier.available_seats, 10)
        self.assertIn("Expired 1", result)

    def test_task_does_not_expire_unexpired_booking(self):
        self.booking.payment_deadline = timezone.now() + timedelta(minutes=10)
        self.booking.save(update_fields=["payment_deadline"])

        result = expire_pending_bookings()

        self.booking.refresh_from_db()
        self.ticket_tier.refresh_from_db()

        self.assertEqual(self.booking.status, Booking.Status.PENDING)
        self.assertEqual(self.ticket_tier.available_seats, 8)
        self.assertIn("Expired 0", result)
