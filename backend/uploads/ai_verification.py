import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Dict, Tuple

from django.conf import settings
from django.db import close_old_connections
from django.db.models import F
from django.utils import timezone

from .models import Document, ScanStatus

logger = logging.getLogger(__name__)

_executor = None
_executor_lock = Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-verify")
    return _executor


def enqueue_verification(document_id: int, checksum: str, force: bool = False) -> None:
    executor = _get_executor()
    executor.submit(_run_verification_task, document_id, checksum, force)


def _run_verification_task(document_id: int, checksum: str, force: bool) -> None:
    close_old_connections()
    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return

    if document.checksum_sha256 != checksum:
        return

    if not force and document.scan_status in {ScanStatus.CLEAN, ScanStatus.REJECTED}:
        return

    Document.objects.filter(pk=document_id).update(
        ai_attempts=F("ai_attempts") + 1,
        ai_last_error="",
    )

    try:
        extracted_text, metadata = _extract_document_text(document)
        verdict, reason = _call_groq(document.document_type, extracted_text, metadata)
        status = _map_verdict_to_status(verdict)
        reason = _truncate_reason(reason)
        Document.objects.filter(pk=document_id).update(
            scan_status=status,
            ai_reason=reason,
            ai_model=settings.GROQ_MODEL,
            ai_checked_at=timezone.now(),
            ai_last_error="",
        )
    except Exception as exc:
        logger.warning("AI verification failed for document %s: %s", document_id, exc)
        Document.objects.filter(pk=document_id).update(
            ai_last_error=_truncate_reason(str(exc)),
        )
    finally:
        close_old_connections()


def _extract_document_text(document: Document) -> Tuple[str, Dict[str, str]]:
    if not document.file or not document.file.name:
        raise ValueError("Document file is missing.")

    path = document.file.path
    if not os.path.exists(path):
        raise ValueError("Document file is not available on disk.")

    content_type = (document.content_type or "").lower()
    is_pdf = content_type == "application/pdf" or path.lower().endswith(".pdf")

    max_pages = getattr(settings, "AI_MAX_PAGES", 3)
    min_text_chars = getattr(settings, "AI_OCR_MIN_TEXT_CHARS", 200)
    ocr_lang = getattr(settings, "AI_OCR_LANG", "eng")

    extracted_text = ""
    used_ocr = False

    if is_pdf:
        extracted_text, page_count = _extract_pdf_text(path, max_pages)
        if len(extracted_text.strip()) < min_text_chars:
            ocr_text = _ocr_pdf_text(path, max_pages, ocr_lang)
            if ocr_text.strip():
                extracted_text = f"{extracted_text}\n{ocr_text}".strip()
            used_ocr = True
        metadata = {
            "content_type": content_type or "application/pdf",
            "pages_scanned": str(min(page_count, max_pages)),
            "used_ocr": str(used_ocr),
        }
        return extracted_text, metadata

    extracted_text = _ocr_image_text(path, ocr_lang)
    metadata = {
        "content_type": content_type or "image",
        "pages_scanned": "1",
        "used_ocr": "True",
    }
    return extracted_text, metadata


def _extract_pdf_text(path: str, max_pages: int) -> Tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(path, strict=False)
    page_count = len(reader.pages)
    chunks = []
    for index in range(min(max_pages, page_count)):
        page = reader.pages[index]
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip(), page_count


def _ocr_pdf_text(path: str, max_pages: int, lang: str) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PyMuPDF is required for PDF OCR.") from exc

    from PIL import Image
    import pytesseract

    chunks = []
    with fitz.open(path) as pdf:
        for index, page in enumerate(pdf):
            if index >= max_pages:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            mode = "RGB" if pix.alpha == 0 else "RGBA"
            image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            if mode == "RGBA":
                image = image.convert("RGB")
            chunks.append(pytesseract.image_to_string(image, lang=lang))
    return "\n".join(chunks).strip()


def _ocr_image_text(path: str, lang: str) -> str:
    from PIL import Image
    import pytesseract

    with Image.open(path) as image:
        image = image.convert("RGB")
        return pytesseract.image_to_string(image, lang=lang).strip()


def _call_groq(document_type: str, text: str, metadata: Dict[str, str]) -> Tuple[str, str]:
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured.")

    from groq import Groq

    max_chars = getattr(settings, "AI_MAX_CHARS", 4000)
    truncated_text = _truncate_text(text, max_chars)
    metadata = dict(metadata)
    metadata["text_chars"] = str(len(truncated_text))
    metadata["text_truncated"] = str(len(text) > max_chars)
    metadata_lines = "\n".join(
        f"- {key}: {value}" for key, value in sorted(metadata.items())
    )

    system_prompt = (
        "You verify if an uploaded document matches the expected type. "
        "Be lenient and only reject if the content is clearly unrelated, random, or junk. "
        "If the text is unclear or too short, return verdict 'clean' and explain that manual review is advised. "
        "Respond ONLY with a JSON object: {\"verdict\": \"clean\"|\"reject\", \"reason\": \"short reason\"}."
    )

    user_prompt = (
        f"Document type: {document_type}\n"
        f"Metadata:\n{metadata_lines}\n\n"
        "Extracted text:\n"
        f"{truncated_text}\n"
    )

    client = Groq(
        api_key=settings.GROQ_API_KEY,
        timeout=getattr(settings, "GROQ_TIMEOUT_SECONDS", 20),
    )
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=300,
    )

    content = (response.choices[0].message.content or "").strip()
    data = _parse_json_response(content)
    verdict = str(data.get("verdict", "")).strip().lower()
    reason = str(data.get("reason", "")).strip()

    if not verdict or not reason:
        raise ValueError("Groq response missing verdict or reason.")

    return verdict, reason


def _parse_json_response(content: str) -> Dict[str, str]:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Groq response was not valid JSON.")
    return json.loads(content[start : end + 1])


def _map_verdict_to_status(verdict: str) -> str:
    reject_values = {
        "reject",
        "rejected",
        "junk",
        "spam",
        "invalid",
        "fail",
        "failed",
    }
    if verdict in reject_values:
        return ScanStatus.REJECTED
    return ScanStatus.CLEAN


def _truncate_reason(reason: str) -> str:
    return reason.strip()[:240]


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
