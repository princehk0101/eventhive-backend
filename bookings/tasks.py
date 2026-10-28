
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


from celery import shared_task
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from events.models import TicketTier


@shared_task
def expire_pending_bookings():
    """Expire unpaid bookings and release their reserved seats."""
    now = timezone.now()

    expired_count = 0

    booking_ids = list(
        Booking.objects.filter(
            status=Booking.Status.PENDING,
            payment_deadline__lte=now,
        ).values_list("id", flat=True)
    )

    for booking_id in booking_ids:
        with transaction.atomic():
            try:
                booking = (
                    Booking.objects.select_for_update()
                    .get(
                        id=booking_id,
                        status=Booking.Status.PENDING,
                        payment_deadline__lte=now,
                    )
                )
            except Booking.DoesNotExist:
                continue

            tier = (
                TicketTier.objects.select_for_update()
                .get(pk=booking.ticket_tier_id)
            )

            tier.available_seats = min(
                tier.total_seats,
                tier.available_seats + booking.quantity,
            )
            tier.save(update_fields=["available_seats"])

            booking.status = Booking.Status.EXPIRED
            booking.save(update_fields=["status"])

            expired_count += 1

    return f"Expired {expired_count} pending bookings"



@shared_task
def send_event_reminders():
    """Send reminders for approved events starting in approximately 24 hours."""
    from datetime import timedelta

    from django.utils import timezone
    from events.models import Event

    now = timezone.now()
    start = now + timedelta(hours=24)
    end = start + timedelta(minutes=1)

    bookings = (
        Booking.objects.filter(
            status=Booking.Status.CONFIRMED,
            ticket_tier__event__status=Event.Status.APPROVED,
            ticket_tier__event__start_time__gte=start,
            ticket_tier__event__start_time__lt=end,
        )
        .select_related(
            "user",
            "ticket_tier",
            "ticket_tier__event",
        )
        .distinct()
    )

    sent_count = 0

    for booking in bookings:
        if not booking.user.email:
            continue

        event = booking.ticket_tier.event

        subject = f"Reminder: {event.title} is tomorrow"
        message = (
            f"Hello {booking.user.get_full_name() or booking.user.email},\n\n"
            f"This is a reminder for your upcoming event.\n"
            f"Event: {event.title}\n"
            f"Start time: {event.start_time}\n"
            f"City: {event.city}\n"
            f"Ticket: {booking.ticket_tier.name}\n"
            f"Quantity: {booking.quantity}\n"
            f"Booking ID: {booking.id}\n\n"
            "We look forward to seeing you at EventHive!"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.user.email],
            fail_silently=False,
        )
        sent_count += 1

    return f"Sent {sent_count} event reminders"

