
from django.conf import settings
from django.db import models
from django.db.models import Q


class Event(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    faq = models.TextField(blank=True, default="")
    city = models.CharField(max_length=100, db_index=True)
    category = models.CharField(max_length=100, db_index=True)

    start_time = models.DateTimeField(db_index=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]
        indexes = [
            models.Index(
                fields=["status", "start_time"],
                name="event_status_start_idx",
            ),
        ]

    def __str__(self):
        return self.title


class TicketTier(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="ticket_tiers",
    )

    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_seats = models.PositiveIntegerField()
    available_seats = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(available_seats__gte=0),
                name="tier_available_seats_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(total_seats__gte=1),
                name="tier_total_seats_positive",
            ),
            models.CheckConstraint(
                condition=Q(available_seats__lte=models.F("total_seats")),
                name="tier_available_lte_total",
            ),
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="tier_price_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event", "name"],
                name="tier_event_name_idx",
            ),
        ]

    def __str__(self):
        return f"{self.event.title} - {self.name}"
