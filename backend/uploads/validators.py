import hashlib
import os
from typing import Dict, Set, Tuple

import filetype
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import DocumentType

ALLOWED_TYPES: Dict[str, Dict[str, Set[str]]] = {
    DocumentType.GOV_ID: {
        "extensions": {"pdf", "jpg", "png"},
        "mimes": {"application/pdf", "image/jpeg", "image/png"},
    },
    DocumentType.RESIDENCY: {
        "extensions": {"pdf", "jpg", "png"},
        "mimes": {"application/pdf", "image/jpeg", "image/png"},
    },
    DocumentType.RESUME: {
        "extensions": {"pdf"},
        "mimes": {"application/pdf"},
    },
}

ARCHIVE_EXTENSIONS = {"zip", "rar", "7z", "tar", "gz", "bz2", "xz"}


def _normalize_extension(extension: str) -> str:
    normalized = extension.lower().lstrip(".")
    if normalized == "jpeg":
        return "jpg"
    return normalized


def _sniff_file_type(uploaded_file) -> Tuple[str, str]:
    position = uploaded_file.tell()
    kind = filetype.guess(uploaded_file)
    uploaded_file.seek(position)

    if not kind:
        raise ValidationError("Unsupported or unrecognized file type.")

    extension = _normalize_extension(kind.extension or "")
    mime = (kind.mime or "").lower()
    return extension, mime


def _validate_file_size(uploaded_file) -> None:
    max_size = getattr(settings, "MAX_UPLOAD_SIZE", 10 * 1024 * 1024)
    if uploaded_file.size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValidationError(f"File exceeds max size of {max_mb} MB.")


def compute_sha256(uploaded_file) -> str:
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def validate_document_upload(document_type: str, uploaded_file) -> Tuple[str, str]:
    if document_type not in ALLOWED_TYPES:
        raise ValidationError("Invalid document type.")

    if not uploaded_file:
        raise ValidationError("File is required.")

    _validate_file_size(uploaded_file)

    original_extension = _normalize_extension(os.path.splitext(uploaded_file.name)[1])
    if not original_extension:
        raise ValidationError("File must include an extension.")

    sniffed_extension, sniffed_mime = _sniff_file_type(uploaded_file)

    if (
        original_extension in ARCHIVE_EXTENSIONS
        or sniffed_extension in ARCHIVE_EXTENSIONS
    ):
        raise ValidationError("Archive files are not allowed.")

    allowed = ALLOWED_TYPES[document_type]

    if original_extension not in allowed["extensions"]:
        raise ValidationError("File extension not allowed for this document type.")

    if sniffed_extension not in allowed["extensions"] or sniffed_mime not in allowed["mimes"]:
        raise ValidationError("File content type does not match allowed types.")

    if original_extension != sniffed_extension:
        raise ValidationError("File extension does not match file content.")

    return sniffed_extension, sniffed_mime
