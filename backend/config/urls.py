from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts_rbac.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/rfp/", include("apps.rfp_debate.urls")),
    path("api/cards/", include("apps.ui_card_validator.urls")),
    path("api/maps/", include("apps.venue_map_studio.urls")),
    path("api/designer/", include("apps.designer_studio.urls")),
    path("api/pricing/", include("apps.dynamic_pricing.urls")),
    path("api/negotiation/", include("apps.negotiation_agent.urls")),
    path("api/voice/", include("apps.voice_synthesis.urls")),
    path("api/admin-center/", include("apps.admin_command_center.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
