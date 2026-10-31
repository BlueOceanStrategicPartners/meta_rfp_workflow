from django.urls import path
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.accounts_rbac.permissions import IsClientRole

from .services import validate_card_mutation


class CardMutationView(APIView):
    permission_classes = [IsClientRole]

    def post(self, request):
        session_id = request.data.get("session_id")
        payload = request.data.get("payload", {})
        try:
            result = validate_card_mutation(session_id, payload)
            return Response(result)
        except Exception as exc:
            from apps.core.exceptions import CardMutationValidationError

            if isinstance(exc, CardMutationValidationError):
                return Response(
                    {
                        "ok": False,
                        "error": str(exc),
                        "alternatives": getattr(exc, "alternatives", []),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise
