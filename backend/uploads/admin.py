from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "document_type",
        "scan_status",
        "created_at",
        "updated_at",
    )
    list_filter = ("document_type", "scan_status")
    search_fields = ("user__username", "original_name")
