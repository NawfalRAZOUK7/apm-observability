# notifications/incident_views.py
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .incidents import (
    acknowledge_incident,
    assign_incident,
    generate_ai_postmortem,
    generate_postmortem,
    incident_metrics,
    resolve_incident,
)
from .models import Incident
from .serializers import IncidentDetailSerializer, IncidentSerializer

User = get_user_model()


def _actor(request):
    return request.user if request.user and request.user.is_authenticated else None


class IncidentListView(ListAPIView):
    serializer_class = IncidentSerializer
    permission_classes = [AllowAny]
    queryset = Incident.objects.all()
    filterset_fields = ["status", "severity"]
    ordering_fields = ["opened_at", "severity"]
    ordering = ["-opened_at"]


class IncidentDetailView(RetrieveAPIView):
    serializer_class = IncidentDetailSerializer
    permission_classes = [AllowAny]
    queryset = Incident.objects.prefetch_related("events")


class IncidentAckView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        incident = get_object_or_404(Incident, pk=pk)
        acknowledge_incident(incident, user=_actor(request), message=request.data.get("message", ""))
        return Response(IncidentDetailSerializer(incident).data)


class IncidentAssignView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        incident = get_object_or_404(Incident, pk=pk)
        owner = get_object_or_404(User, username=request.data.get("username"))
        assign_incident(incident, owner=owner, actor=_actor(request))
        return Response(IncidentDetailSerializer(incident).data)


class IncidentResolveView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        incident = get_object_or_404(Incident, pk=pk)
        resolve_incident(incident, user=_actor(request), message=request.data.get("message", ""))
        return Response(IncidentDetailSerializer(incident).data)


class IncidentMetricsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: None}, description="MTTA/MTTR and open/resolved counts.")
    def get(self, request):
        return Response(incident_metrics())


class IncidentPostmortemView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: None},
        description="Blameless postmortem (markdown). Add ?ai=1 for an LLM-drafted "
        "version (falls back to the template when no LLM is configured).",
    )
    def get(self, request, pk):
        incident = get_object_or_404(Incident.objects.prefetch_related("events"), pk=pk)
        use_ai = request.query_params.get("ai") in ("1", "true", "yes")
        markdown = generate_ai_postmortem(incident) if use_ai else generate_postmortem(incident)
        if request.query_params.get("format") == "json":
            return Response({"markdown": markdown})
        return HttpResponse(markdown, content_type="text/markdown; charset=utf-8")
