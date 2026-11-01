from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsClientRole

from .models import RFPSubmission, RFPStatus
from .serializers import RFPSubmissionSerializer
from .tasks import enqueue_debate_pipeline, run_debate_pipeline
from .voice_intro import build_voice_intro_for_rfp
from .card_normalize import normalize_cards_for_ui


def _request_run_debate(request) -> bool:
    flag = request.data.get("run_debate", False)
    return flag is True or str(flag).lower() in {"1", "true", "yes"}


class RFPListCreateView(generics.ListCreateAPIView):
    serializer_class = RFPSubmissionSerializer
    permission_classes = []

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return RFPSubmission.objects.filter(client=self.request.user)
        return RFPSubmission.objects.none()

    def perform_create(self, serializer):
        from apps.accounts_rbac.models import CustomUser, UserRole

        user = self.request.user
        if not user.is_authenticated:
            user, _ = CustomUser.objects.get_or_create(
                email="demo-client@local",
                defaults={"username": "demo_client", "role": UserRole.CLIENT},
            )
        text = (serializer.validated_data.get("source_document_text") or "").strip()
        rfp = serializer.save(client=user, status=RFPStatus.EXTRACTING, source_document_text=text)
        if _request_run_debate(self.request):
            enqueue_debate_pipeline(str(rfp.id))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        rfp = serializer.instance
        rfp.refresh_from_db()
        normalize_cards_for_ui(rfp)
        data = RFPSubmissionSerializer(rfp).data
        data["voice_intro"] = ""
        if _request_run_debate(request):
            partial = bool(rfp.amber_conflict_fields_json)
            intro = build_voice_intro_for_rfp(rfp, partial=partial)
            if not intro.strip():
                intro = (
                    "I'm analyzing your dates and room block now — "
                    "your summary will appear on the right in a moment."
                )
            data["voice_intro"] = intro
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)


class RFPDetailView(generics.RetrieveAPIView):
    serializer_class = RFPSubmissionSerializer
    permission_classes = [IsClientRole]

    def get_queryset(self):
        return RFPSubmission.objects.filter(client=self.request.user)


class RFPStartDebateView(APIView):
    permission_classes = [IsClientRole]

    def post(self, request, pk):
        rfp = RFPSubmission.objects.get(pk=pk, client=request.user)
        run_debate_pipeline.delay(str(rfp.id))
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class RFPCardsSnapshotView(APIView):
    """Public read of normalized UI cards (demo client has no login)."""

    permission_classes = []

    def get(self, request, pk):
        rfp = RFPSubmission.objects.filter(pk=pk).first()
        if not rfp:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        normalize_cards_for_ui(rfp)
        return Response({"cards": rfp.active_ui_cards_json})
