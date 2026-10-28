from django.urls import path
from .views import BookingListCreateView, BookingCancelView


from .views import (
    BookingListCreateView,
    BookingCancelView,
    BookingPaymentConfirmView,
)

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("<int:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path(
        "<int:pk>/confirm-payment/",
        BookingPaymentConfirmView.as_view(),
        name="booking-confirm-payment",
    ),
]