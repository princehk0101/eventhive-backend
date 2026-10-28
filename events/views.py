
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAdminUser,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Event, TicketTier
from .serializers import EventSerializer, TicketTierSerializer



# Event List and Create

class EventListCreateView(generics.ListCreateAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Event.objects.select_related(
            "organizer"
        ).prefetch_related("ticket_tiers")

        if user.is_authenticated and user.role == "admin":
            return queryset

        if user.is_authenticated and user.role == "organizer":
            return queryset.filter(organizer=user)

        return queryset.filter(status=Event.Status.APPROVED)

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer):
        user = self.request.user

        if user.role != "organizer":
            raise PermissionDenied(
                "Only organizers can create events."
            )

        serializer.save(organizer=user)



# Event Retrieve, Update and Delete

class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Event.objects.select_related(
            "organizer"
        ).prefetch_related("ticket_tiers")

        if user.is_authenticated and user.role == "admin":
            return queryset

        if user.is_authenticated and user.role == "organizer":
            return queryset.filter(organizer=user)

        return queryset.filter(status=Event.Status.APPROVED)

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_update(self, serializer):
        user = self.request.user
        event = serializer.instance

        if user.role != "organizer" or event.organizer_id != user.id:
            raise PermissionDenied(
                "You can only update your own events."
            )

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user

        if user.role != "organizer" or instance.organizer_id != user.id:
            raise PermissionDenied(
                "You can only delete your own events."
            )

        instance.delete()



# Admin Event Approval / Rejection

class EventApprovalView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        action = request.data.get("action")

        if action not in ["approve", "reject"]:
            return Response(
                {"error": "Action must be approve or reject."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event = get_object_or_404(Event, pk=pk)

        if action == "approve":
            event.status = Event.Status.APPROVED
        else:
            event.status = Event.Status.REJECTED

        event.save(update_fields=["status"])

        return Response(
            {
                "message": f"Event {action}d successfully.",
                "event_id": event.id,
                "status": event.status,
            },
            status=status.HTTP_200_OK,
        )



# Ticket Tier List and Create

class TicketTierListCreateView(generics.ListCreateAPIView):
    serializer_class = TicketTierSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TicketTier.objects.filter(
            event_id=self.kwargs["event_id"]
        ).select_related("event", "event__organizer")

    def perform_create(self, serializer):
        event = get_object_or_404(
            Event,
            pk=self.kwargs["event_id"],
        )

        if event.organizer_id != self.request.user.id:
            raise PermissionDenied(
                "You can only create tickets for your own events."
            )

        if event.status != Event.Status.APPROVED:
            raise PermissionDenied(
                "Tickets can only be created for approved events."
            )

        serializer.save(
            event=event,
            available_seats=serializer.validated_data["total_seats"],
        )
