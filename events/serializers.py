
from django.utils import timezone
from rest_framework import serializers

from .models import Event, TicketTier


class TicketTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketTier
        fields = [
            "id",
            "name",
            "price",
            "total_seats",
            "available_seats",
        ]
        read_only_fields = ["id", "available_seats"]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Ticket tier name cannot be empty."
            )
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Ticket price cannot be negative."
            )
        return value

    def validate_total_seats(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Total seats must be greater than zero."
            )
        return value


class EventSerializer(serializers.ModelSerializer):
    organizer = serializers.ReadOnlyField(
        source="organizer.email"
    )
    ticket_tiers = TicketTierSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Event
        fields = [
            "id",
            "organizer",
            "title",
            "description",
            "faq",
            "city",
            "category",
            "start_time",
            "status",
            "created_at",
            "ticket_tiers",
        ]
        read_only_fields = [
            "id",
            "organizer",
            "status",
            "created_at",
        ]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Event title cannot be empty."
            )
        return value

    def validate_start_time(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Event start time must be in the future."
            )
        return value
