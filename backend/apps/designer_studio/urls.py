from django.urls import path

from .views import (
    DefaultTemplateView,
    DesignerChatView,
    DesignerDefaultVenueMapView,
    DesignerInjectDefaultMapView,
    DesignerMediaListView,
    DesignerMediaUploadView,
    ProposalTemplateDetailView,
    ProposalTemplateListCreateView,
    TemplateDuplicateView,
    TemplateExportView,
    TemplatePreviewView,
    TemplateRestoreRevisionView,
    TemplateValidateView,
)

urlpatterns = [
    path("templates/", ProposalTemplateListCreateView.as_view()),
    path("templates/<uuid:pk>/", ProposalTemplateDetailView.as_view()),
    path("templates/<uuid:pk>/duplicate/", TemplateDuplicateView.as_view()),
    path("templates/<uuid:pk>/restore-revision/", TemplateRestoreRevisionView.as_view()),
    path("templates/<uuid:pk>/export/", TemplateExportView.as_view()),
    path("templates/default/", DefaultTemplateView.as_view()),
    path("default-venue-map/", DesignerDefaultVenueMapView.as_view()),
    path("inject-default-venue-map/", DesignerInjectDefaultMapView.as_view()),
    path("assets/", DesignerMediaListView.as_view()),
    path("assets/upload/", DesignerMediaUploadView.as_view()),
    path("chat/", DesignerChatView.as_view()),
    path("validate/", TemplateValidateView.as_view()),
    path("preview/", TemplatePreviewView.as_view()),
]
