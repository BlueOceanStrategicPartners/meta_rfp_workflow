from django.urls import path

from .views import PropertyListView, SpaceListView

urlpatterns = [
    path("properties/", PropertyListView.as_view()),
    path("spaces/", SpaceListView.as_view()),
]
