from django.urls import path

from .agent_rules_views import (
    DesignerAgentRuleDetailView,
    DesignerAgentRuleListCreateView,
    DesignerAgentRuleRetrievePreviewView,
    DesignerAgentRuleValidateView,
)
from .views import (
    DefaultTemplateView,
    DesignerChatStreamView,
    DesignerChatLiveProgressView,
    DesignerChatCancelView,
    DesignerChatView,
    DesignerMapKnowledgeView,
    DesignerPreviewAuditView,
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
    path("map-knowledge/", DesignerMapKnowledgeView.as_view()),
    path("assets/", DesignerMediaListView.as_view()),
    path("assets/upload/", DesignerMediaUploadView.as_view()),
    path("chat/", DesignerChatView.as_view()),
    path("chat/stream/", DesignerChatStreamView.as_view()),
    path("chat/live-progress/", DesignerChatLiveProgressView.as_view()),
    path("chat/cancel/", DesignerChatCancelView.as_view()),
    path("agent-rules/", DesignerAgentRuleListCreateView.as_view()),
    path("agent-rules/validate/", DesignerAgentRuleValidateView.as_view()),
    path("agent-rules/retrieve-preview/", DesignerAgentRuleRetrievePreviewView.as_view()),
    path("agent-rules/<uuid:pk>/", DesignerAgentRuleDetailView.as_view()),
    path("preview-audit/", DesignerPreviewAuditView.as_view()),
    path("validate/", TemplateValidateView.as_view()),
    path("preview/", TemplatePreviewView.as_view()),
]
