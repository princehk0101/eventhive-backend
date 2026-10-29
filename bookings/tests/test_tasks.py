
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from bookings.models import Booking
from bookings.tasks import (
    expire_pending_bookings,
    send_booking_confirmation_email,
    send_event_reminders,
)
from events.models import Event, TicketTier


User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
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
            description="Testing booking tasks",
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

    def test_confirmation_email_is_sent(self):
        self.booking.status = Booking.Status.CONFIRMED
        self.booking.save(update_fields=["status"])

        result = send_booking_confirmation_email(self.booking.id)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.attendee.email])
        self.assertIn("Task Test Event", mail.outbox[0].subject)
        self.assertIn(str(self.booking.id), mail.outbox[0].body)
        self.assertIn("processed", result)

    def test_confirmation_email_for_missing_booking(self):
        result = send_booking_confirmation_email(99999)

        self.assertEqual(result, "Booking 99999 not found")
        self.assertEqual(len(mail.outbox), 0)

    def test_confirmation_email_skipped_without_email(self):
        self.attendee.email = ""
        self.attendee.save(update_fields=["email"])

        result = send_booking_confirmation_email(self.booking.id)

        self.assertIn("No email address", result)
        self.assertEqual(len(mail.outbox), 0)

    def test_reminder_sent_for_eligible_confirmed_booking(self):
        self.booking.status = Booking.Status.CONFIRMED
        self.booking.save(update_fields=["status"])

        self.event.start_time = timezone.now() + timedelta(
            hours=24, seconds=30
        )
        self.event.save(update_fields=["start_time"])

        result = send_event_reminders()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.attendee.email])
        self.assertIn("Reminder", mail.outbox[0].subject)
        self.assertIn("Task Test Event", mail.outbox[0].body)
        self.assertEqual(result, "Sent 1 event reminders")

    def test_reminder_not_sent_for_event_outside_window(self):
        self.booking.status = Booking.Status.CONFIRMED
        self.booking.save(update_fields=["status"])

        self.event.start_time = timezone.now() + timedelta(hours=26)
        self.event.save(update_fields=["start_time"])

        result = send_event_reminders()

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(result, "Sent 0 event reminders")

    def test_reminder_skipped_without_attendee_email(self):
        self.attendee.email = ""
        self.attendee.save(update_fields=["email"])

        self.booking.status = Booking.Status.CONFIRMED
        self.booking.save(update_fields=["status"])

        self.event.start_time = timezone.now() + timedelta(
            hours=24, seconds=30
        )
        self.event.save(update_fields=["start_time"])

        result = send_event_reminders()

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(result, "Sent 0 event reminders")

    @patch(
        "bookings.tasks.send_mail",
        side_effect=RuntimeError("Email failed"),
    )
    def test_confirmation_email_error_propagates(self, mock_send_mail):
        with self.assertRaises(RuntimeError):
            send_booking_confirmation_email(self.booking.id)

        mock_send_mail.assert_called_once()
