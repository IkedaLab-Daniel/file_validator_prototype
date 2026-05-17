from django.urls import path

from .views import DocumentListCreateView

urlpatterns = [
    path("", DocumentListCreateView.as_view(), name="document-list-create"),
]
