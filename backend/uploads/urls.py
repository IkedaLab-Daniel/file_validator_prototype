from django.urls import path

from .views import DocumentListCreateView, DocumentVerifyView

urlpatterns = [
    path("", DocumentListCreateView.as_view(), name="document-list-create"),
    path("<int:pk>/verify/", DocumentVerifyView.as_view(), name="document-verify"),
]
