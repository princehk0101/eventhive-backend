
from rest_framework import serializers
from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    ticket_name = serializers.CharField(
        source="ticket_tier.name",
        read_only=True,
    )

    event_title = serializers.CharField(
        source="ticket_tier.event.title",
        read_only=True,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "ticket_tier",
            "ticket_name",
            "event_title",
            "quantity",
            "total_price",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "ticket_name",
            "event_title",
            "total_price",
            "status",
            "created_at",
        ]

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "You must book at least one ticket."
            )
        return value
