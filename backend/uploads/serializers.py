from typing import Optional

from django.db import transaction
from rest_framework import serializers

from .ai_verification import enqueue_verification
from .models import Document, DocumentType, ScanStatus
from .validators import compute_sha256, validate_document_upload


class DocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "document_type",
            "file_url",
            "original_name",
            "content_type",
            "size_bytes",
            "checksum_sha256",
            "scan_status",
            "ai_reason",
            "ai_model",
            "ai_checked_at",
            "ai_last_error",
            "created_at",
            "updated_at",
        ]

    def get_file_url(self, obj) -> Optional[str]:
        if not obj.file:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url


class DocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=DocumentType.choices)
    file = serializers.FileField()

    def validate(self, attrs):
        document_type = attrs.get("document_type")
        uploaded_file = attrs.get("file")
        sniffed_extension, sniffed_mime = validate_document_upload(
            document_type, uploaded_file
        )
        attrs["sniffed_extension"] = sniffed_extension
        attrs["sniffed_mime"] = sniffed_mime
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        document_type = validated_data["document_type"]
        uploaded_file = validated_data["file"]
        sniffed_mime = validated_data["sniffed_mime"]
        checksum = compute_sha256(uploaded_file)
        size_bytes = uploaded_file.size
        original_name = uploaded_file.name

        document = Document.objects.filter(
            user=user, document_type=document_type
        ).first()

        if document:
            old_file = document.file
            document.file = uploaded_file
            document.original_name = original_name
            document.content_type = sniffed_mime
            document.size_bytes = size_bytes
            document.checksum_sha256 = checksum
            document.scan_status = ScanStatus.PENDING
            document.ai_reason = ""
            document.ai_model = ""
            document.ai_checked_at = None
            document.ai_attempts = 0
            document.ai_last_error = ""
            document.save()

            if old_file and old_file.name and old_file.name != document.file.name:
                old_file.delete(save=False)

            transaction.on_commit(
                lambda: enqueue_verification(document.id, document.checksum_sha256)
            )
            return document

        document = Document.objects.create(
            user=user,
            document_type=document_type,
            file=uploaded_file,
            original_name=original_name,
            content_type=sniffed_mime,
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            scan_status=ScanStatus.PENDING,
            ai_reason="",
            ai_model="",
            ai_checked_at=None,
            ai_attempts=0,
            ai_last_error="",
        )

        transaction.on_commit(
            lambda: enqueue_verification(document.id, document.checksum_sha256)
        )
        return document
