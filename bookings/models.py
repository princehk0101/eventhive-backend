
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Booking(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    ticket_tier = models.ForeignKey(
        "events.TicketTier",
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    quantity = models.PositiveIntegerField()

    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    payment_deadline = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="booking_quantity_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(total_price__gte=0),
                name="booking_total_price_gte_0",
            ),
        ]

    def __str__(self):
        return (
            f"Booking #{self.id} - "
            f"{self.user} - {self.quantity} tickets"
        )

    def is_payment_expired(self):
        return (
            self.status == self.Status.PENDING
            and self.payment_deadline is not None
            and timezone.now() >= self.payment_deadline
        )
