"""API views for designer agent rules."""
from __future__ import annotations

import logging

from django.db.utils import OperationalError, ProgrammingError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsDesignerRole

from .agent_rules import (
    format_rules_for_agent,
    refresh_rule_vectors,
    retrieve_relevant_rules,
    validate_rule_conflict,
)
from .models import DesignerAgentRule
from .serializers import DesignerAgentRuleSerializer

logger = logging.getLogger(__name__)

_SCHEMA_UNAVAILABLE = {
    "detail": "Agent rules storage is not ready. Run: python manage.py migrate",
    "code": "agent_rules_schema_missing",
}


def _schema_unavailable_response():
    return Response(_SCHEMA_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class DesignerAgentRuleListCreateView(APIView):
    permission_classes = [IsDesignerRole]

    def get(self, request):
        try:
            qs = DesignerAgentRule.objects.filter(designer=request.user).order_by(
                "sort_order", "created_at"
            )
        except (OperationalError, ProgrammingError):
            logger.exception("Agent rules list failed (schema missing?)")
            return _schema_unavailable_response()
        return Response(DesignerAgentRuleSerializer(qs, many=True).data)

    def post(self, request):
        body = (request.data.get("body") or "").strip()
        if not body:
            return Response({"detail": "body is required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(body) > 4000:
            return Response({"detail": "Rule too long (max 4000 chars)"}, status=status.HTTP_400_BAD_REQUEST)
        sort_order = int(request.data.get("sort_order") or 0)
        try:
            rule = DesignerAgentRule.objects.create(
                designer=request.user,
                body=body,
                sort_order=sort_order,
            )
        except (OperationalError, ProgrammingError):
            logger.exception("Agent rules create failed (schema missing?)")
            return _schema_unavailable_response()
        refresh_rule_vectors(rule)
        return Response(
            DesignerAgentRuleSerializer(rule).data,
            status=status.HTTP_201_CREATED,
        )


class DesignerAgentRuleDetailView(APIView):
    permission_classes = [IsDesignerRole]

    def patch(self, request, pk):
        rule = DesignerAgentRule.objects.filter(pk=pk, designer=request.user).first()
        if not rule:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        body = request.data.get("body")
        if body is not None:
            body = str(body).strip()
            if not body:
                return Response({"detail": "body cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)
            rule.body = body[:4000]
        if "sort_order" in request.data:
            rule.sort_order = int(request.data.get("sort_order") or 0)
        rule.save()
        refresh_rule_vectors(rule)
        return Response(DesignerAgentRuleSerializer(rule).data)

    def delete(self, request, pk):
        rule = DesignerAgentRule.objects.filter(pk=pk, designer=request.user).first()
        if not rule:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DesignerAgentRuleValidateView(APIView):
    permission_classes = [IsDesignerRole]

    def post(self, request):
        body = (request.data.get("body") or "").strip()
        if not body:
            return Response({"detail": "body is required"}, status=status.HTTP_400_BAD_REQUEST)
        exclude = request.data.get("exclude_rule_id")
        result = validate_rule_conflict(
            designer_id=request.user.id,
            new_body=body,
            exclude_rule_id=str(exclude) if exclude else None,
        )
        return Response(result)


class DesignerAgentRuleRetrievePreviewView(APIView):
    """Debug/preview hybrid retrieval for a message."""

    permission_classes = [IsDesignerRole]

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        rules = retrieve_relevant_rules(request.user.id, message or "proposal design", limit=12)
        return Response(
            {
                "count": len(rules),
                "rules": DesignerAgentRuleSerializer(rules, many=True).data,
                "formatted_block": format_rules_for_agent(rules),
            }
        )
