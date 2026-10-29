
from django.urls import path

from .views import (
    EventListCreateView,
    EventDetailView,
    EventApprovalView,
    TicketTierListCreateView,
    EventAskView,
)

urlpatterns = [
    path("", EventListCreateView.as_view(), name="event-list"),
    path("<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path(
        "<int:pk>/approval/",
        EventApprovalView.as_view(),
        name="event-approval",
    ),
    path(
        "<int:event_id>/tickets/",
        TicketTierListCreateView.as_view(),
        name="ticket-tier-list-create",
    ),
    path(
        "<int:pk>/ask/",
        EventAskView.as_view(),
        name="event-ask",
    ),
]
