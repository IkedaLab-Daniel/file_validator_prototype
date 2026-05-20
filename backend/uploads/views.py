from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .ai_verification import enqueue_verification
from .models import Document, ScanStatus
from .serializers import DocumentSerializer, DocumentUploadSerializer


class DocumentListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user).order_by(
            "document_type"
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DocumentUploadSerializer
        return DocumentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        output = DocumentSerializer(document, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class DocumentVerifyView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk, user=request.user)

        needs_reset = document.scan_status != ScanStatus.PENDING
        had_error = bool(document.ai_last_error)
        if needs_reset:
            document.scan_status = ScanStatus.PENDING
            document.ai_reason = ""
            document.ai_model = ""
            document.ai_checked_at = None
        document.ai_last_error = ""

        if needs_reset or had_error:
            document.save(
                update_fields=[
                    "scan_status",
                    "ai_reason",
                    "ai_model",
                    "ai_checked_at",
                    "ai_last_error",
                    "updated_at",
                ]
            )

        enqueue_verification(document.id, document.checksum_sha256, force=True)
        output = DocumentSerializer(document, context={"request": request})
        return Response(output.data, status=status.HTTP_202_ACCEPTED)
