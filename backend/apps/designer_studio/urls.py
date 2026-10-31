from django.urls import path

from .views import (
    DefaultTemplateView,
    DesignerChatStubView,
    ProposalTemplateDetailView,
    ProposalTemplateListCreateView,
)

urlpatterns = [
    path("templates/", ProposalTemplateListCreateView.as_view()),
    path("templates/<uuid:pk>/", ProposalTemplateDetailView.as_view()),
    path("chat/", DesignerChatStubView.as_view()),
    path("templates/default/", DefaultTemplateView.as_view()),
]
