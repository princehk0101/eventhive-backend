
from django.contrib import admin
from .models import Event, TicketTier


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "organizer", "status", "start_time")
    list_filter = ("status", "category")
    search_fields = ("title", "city", "description")


@admin.register(TicketTier)
class TicketTierAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event",
        "name",
        "price",
        "total_seats",
        "available_seats",
    )
    search_fields = ("name", "event__title")
