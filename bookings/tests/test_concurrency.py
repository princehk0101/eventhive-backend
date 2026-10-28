
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone

from rest_framework.test import APIClient

from events.models import Event, TicketTier

User = get_user_model()


class BookingConcurrencyTests(TransactionTestCase):

    def setUp(self):
        self.organizer = User.objects.create_user(
            username="concurrency_organizer",
            email="concurrency_organizer@example.com",
            password="TestPass123!",
            role="organizer",
        )

        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Concurrency Test Event",
            description="Testing simultaneous bookings",
            faq="No FAQ",
            city="Lucknow",
            category="Technology",
            start_time=timezone.now() + timedelta(days=30),
            status=Event.Status.APPROVED,
        )

        self.ticket_tier = TicketTier.objects.create(
            event=self.event,
            name="Limited Seats",
            price=Decimal("100.00"),
            total_seats=10,
            available_seats=10,
        )

        self.attendee_ids = [
            User.objects.create_user(
                username=f"concurrency_attendee_{i}",
                email=f"concurrency_attendee_{i}@example.com",
                password="TestPass123!",
                role="attendee",
            ).pk
            for i in range(50)
        ]

    def book_one_ticket(self, attendee_id, ticket_tier_id):
        close_old_connections()
        try:
            attendee = User.objects.get(pk=attendee_id)
            client = APIClient()
            client.force_authenticate(user=attendee)

            response = client.post(
                "/api/bookings/",
                {
                    "ticket_tier": ticket_tier_id,
                    "quantity": 1,
                },
                format="json",
            )
            return response.status_code
        finally:
            close_old_connections()

    def test_50_requests_cannot_oversell_10_seats(self):
        with ThreadPoolExecutor(max_workers=50) as executor:
            results = list(
                executor.map(
                    lambda attendee_id: self.book_one_ticket(
                        attendee_id, self.ticket_tier.pk
                    ),
                    self.attendee_ids,
                )
            )

        successful = results.count(201)
        rejected = results.count(400)

        self.ticket_tier.refresh_from_db()

        self.assertEqual(successful, 10)
        self.assertEqual(rejected, 40)
        self.assertEqual(self.ticket_tier.available_seats, 0)
