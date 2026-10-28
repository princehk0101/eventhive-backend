
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from bookings.models import Booking


@shared_task
def send_booking_confirmation_email(booking_id):
    try:
        booking = Booking.objects.select_related(
            "user",
            "ticket_tier",
            "ticket_tier__event",
        ).get(id=booking_id)
    except Booking.DoesNotExist:
        return f"Booking {booking_id} not found"

    if not booking.user.email:
        return f"No email address for booking {booking_id}"

    event = booking.ticket_tier.event

    subject = f"Booking Confirmation - {event.title}"

    message = f"""
Hello {booking.user.get_full_name() or booking.user.email},

Your booking has been confirmed!

Event: {event.title}
Ticket: {booking.ticket_tier.name}
Quantity: {booking.quantity}
Total Price: Rs. {booking.total_price}
Booking ID: {booking.id}
Booking Status: {booking.status}

Thank you for booking with EventHive!
"""

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[booking.user.email],
        fail_silently=False,
    )

    return f"Confirmation email processed for booking {booking_id}"
