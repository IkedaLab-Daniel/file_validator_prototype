import os
import uuid

from django.conf import settings
from django.db import models


def upload_document_path(instance, filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower()
    safe_extension = extension if extension else ""
    return (
        f"uploads/user_{instance.user_id}/"
        f"{instance.document_type.lower()}/{uuid.uuid4().hex}{safe_extension}"
    )


class DocumentType(models.TextChoices):
    GOV_ID = "GOV_ID", "Government ID"
    RESIDENCY = "RESIDENCY", "Proof of Residency"
    RESUME = "RESUME", "Resume"


class ScanStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CLEAN = "clean", "Clean"
    REJECTED = "rejected", "Rejected"
    FAILED = "failed", "Failed"


class Document(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    file = models.FileField(upload_to=upload_document_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    scan_status = models.CharField(
        max_length=20,
        choices=ScanStatus.choices,
        default=ScanStatus.PENDING,
    )
    ai_reason = models.CharField(max_length=300, blank=True, default="")
    ai_model = models.CharField(max_length=100, blank=True, default="")
    ai_checked_at = models.DateTimeField(null=True, blank=True)
    ai_attempts = models.PositiveIntegerField(default=0)
    ai_last_error = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "document_type"],
                name="unique_document_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.document_type}"
