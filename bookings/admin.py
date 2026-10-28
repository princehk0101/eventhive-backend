from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "ticket_tier",
        "quantity",
        "total_price",
        "status",
        "payment_deadline",
    )
    list_filter = ("status",)
    search_fields = ("user__email", "ticket_tier__event__title")