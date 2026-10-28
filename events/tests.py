
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Event, TicketTier


User = get_user_model()


class EventAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="TestPass123!",
            role="organizer",
        )

        cls.other_organizer = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="TestPass123!",
            role="organizer",
        )

        cls.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="TestPass123!",
            role="admin",
            is_staff=True,
        )

        cls.attendee = User.objects.create_user(
            username="attendee",
            email="attendee@example.com",
            password="TestPass123!",
            role="attendee",
        )

        future_time = timezone.now() + timedelta(days=30)

        cls.approved_event = Event.objects.create(
            organizer=cls.organizer,
            title="Approved Meetup",
            description="A public developer meetup.",
            city="Lucknow",
            category="Technology",
            start_time=future_time,
            status=Event.Status.APPROVED,
        )

        cls.pending_event = Event.objects.create(
            organizer=cls.organizer,
            title="Pending Meetup",
            description="Waiting for approval.",
            city="Delhi",
            category="Technology",
            start_time=future_time + timedelta(days=1),
            status=Event.Status.PENDING,
        )

        cls.other_event = Event.objects.create(
            organizer=cls.other_organizer,
            title="Other Organizer Meetup",
            description="Another organizer's event.",
            city="Kanpur",
            category="Technology",
            start_time=future_time + timedelta(days=2),
            status=Event.Status.APPROVED,
        )

        cls.ticket_tier = TicketTier.objects.create(
            event=cls.approved_event,
            name="General",
            price=Decimal("499.00"),
            total_seats=100,
            available_seats=100,
        )

    def setUp(self):
        cache.clear()

    def test_public_list_shows_only_approved_events(self):
        response = self.client.get(reverse("event-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(
            response,
            "Approved Meetup",
            status_code=status.HTTP_200_OK,
        )
        self.assertNotContains(response, "Pending Meetup")

    def test_public_event_detail_returns_approved_event(self):
        response = self.client.get(
            reverse(
                "event-detail",
                kwargs={"pk": self.approved_event.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Approved Meetup")
        self.assertEqual(len(response.data["ticket_tiers"]), 1)

    def test_public_user_cannot_view_pending_event(self):
        response = self.client.get(
            reverse(
                "event-detail",
                kwargs={"pk": self.pending_event.pk},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_event_detail_returns_404_for_unknown_event(self):
        response = self.client.get(
            reverse("event-detail", kwargs={"pk": 999999})
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_anonymous_user_cannot_create_event(self):
        response = self.client.post(
            reverse("event-list"),
            {
                "title": "New Event",
                "description": "An event description.",
                "city": "Lucknow",
                "category": "Technology",
                "start_time": (
                    timezone.now() + timedelta(days=10)
                ).isoformat(),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_organizer_can_create_event(self):
        self.client.force_authenticate(user=self.organizer)

        response = self.client.post(
            reverse("event-list"),
            {
                "title": "New Organizer Event",
                "description": "Created through the API.",
                "city": "Lucknow",
                "category": "Technology",
                "start_time": (
                    timezone.now() + timedelta(days=10)
                ).isoformat(),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            Event.objects.filter(
                title="New Organizer Event",
                organizer=self.organizer,
                status=Event.Status.PENDING,
            ).exists()
        )

    def test_organizer_cannot_update_another_organizers_event(self):
        self.client.force_authenticate(user=self.organizer)

        response = self.client.patch(
            reverse(
                "event-detail",
                kwargs={"pk": self.other_event.pk},
            ),
            {"title": "Unauthorized Update"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.other_event.refresh_from_db()
        self.assertEqual(
            self.other_event.title,
            "Other Organizer Meetup",
        )

    def test_admin_can_approve_event(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse(
                "event-approval",
                kwargs={"pk": self.pending_event.pk},
            ),
            {"action": "approve"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.pending_event.refresh_from_db()
        self.assertEqual(
            self.pending_event.status,
            Event.Status.APPROVED,
        )

    def test_non_admin_cannot_approve_event(self):
        self.client.force_authenticate(user=self.organizer)

        response = self.client.post(
            reverse(
                "event-approval",
                kwargs={"pk": self.pending_event.pk},
            ),
            {"action": "approve"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_organizer_can_create_ticket_tier_for_own_approved_event(self):
        self.client.force_authenticate(user=self.organizer)

        response = self.client.post(
            reverse(
                "ticket-tier-list-create",
                kwargs={"event_id": self.approved_event.pk},
            ),
            {
                "name": "VIP",
                "price": "999.00",
                "total_seats": 20,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            TicketTier.objects.filter(
                event=self.approved_event,
                name="VIP",
                available_seats=20,
            ).exists()
        )

    def test_ticket_tier_rejects_zero_total_seats(self):
        self.client.force_authenticate(user=self.organizer)

        response = self.client.post(
            reverse(
                "ticket-tier-list-create",
                kwargs={"event_id": self.approved_event.pk},
            ),
            {
                "name": "Invalid Tier",
                "price": "100.00",
                "total_seats": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
